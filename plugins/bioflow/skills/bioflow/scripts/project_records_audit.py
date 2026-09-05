#!/usr/bin/env python3
"""Read-only audit for Bioflow layout-v2 project records.

This contract checks the human status page, dated research logs, log index,
decision index, and changelog. It does not duplicate scheduler logs, task TSV
state, claim checking, or workspace routing, and never writes project files.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
import project_layout as layout_contract  # noqa: E402

MAX_RECORDS = 2000
MAX_MARKDOWN_BYTES = 2 * 1024 * 1024
AUDIT_COLUMNS = ("Status", "Rule_ID", "Relative_Path", "Detail")
SEVERITY = {"PASS": 0, "INFO": 0, "WARN": 1, "BLOCK": 2}

LIFECYCLE_STAGES = {
    "Project_intake", "Input_ready", "Plan_ready", "Script_ready",
    "Queued_or_running", "Failed", "Complete_unvalidated", "Analysis_ready",
    "Delivered",
}
MATURITY = {"Exploratory", "Provisional", "Verified", "Frozen"}
MANUSCRIPT_STAGES = {
    "Not_started", "Outline", "Drafting", "Evidence_review", "Coauthor_review",
    "Pre_submission", "Submitted", "Revision", "Published",
}
RECORD_STATUS = {"Draft", "Complete", "Superseded"}
DECISION_STATUS = {"Proposed", "Accepted", "Superseded", "Reversed"}

LOG_COLUMNS = (
    "Research_Log_ID", "Date", "Filename", "Analysis_Key", "Module_ID",
    "Task_ID", "Result_Maturity", "Record_Status", "Title", "Notes",
)
DECISION_COLUMNS = (
    "Decision_ID", "Date", "Decision", "Evidence_Path", "Affected_Modules",
    "Affected_Claims", "Status", "Decided_By", "Notes",
)
LOG_ID_RE = re.compile(r"^R[0-9]{3,}$")
DECISION_ID_RE = re.compile(r"^D[0-9]{3,}$")
MODULE_ID_RE = re.compile(r"^M[0-9]{3,}$")
TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
FILENAME_RE = re.compile(r"^[0-9]{8}_[A-Za-z][A-Za-z0-9_]*\.md$")
ANALYSIS_KEY_RE = re.compile(r"^[a-z][a-z0-9-]*$")
REQUIRED_LOG_HEADINGS = (
    "## Scientific question",
    "## Inputs and versions",
    "## Exact commands and parameters",
    "## Outputs",
    "## Checks",
    "## Observations",
    "## Interpretation",
    "## Limitations",
    "## Impact",
    "## Next action",
)
REQUIRED_STATUS_HEADINGS = (
    "## Current objective",
    "## Priorities",
    "## Blockers",
    "## Machine-readable status",
)


class RecordsAuditError(ValueError):
    pass


@dataclass(frozen=True)
class Finding:
    Status: str
    Rule_ID: str
    Relative_Path: str
    Detail: str


def add(findings: list[Finding], status: str, rule: str, relative: str, detail: str) -> None:
    findings.append(Finding(status, rule, relative, detail))


def safe_project(value: str) -> Path:
    raw = Path(value).expanduser()
    if not raw.is_dir():
        raise RecordsAuditError(f"project must be an existing directory: {raw}")
    project = raw.resolve(strict=True)
    home = Path.home().resolve(strict=False)
    if project in {Path("/"), Path("/data9"), Path("/data9/home"), home, home / "projects"}:
        raise RecordsAuditError(f"refusing broad project root: {project}")
    return project


def read_text_bounded(path: Path, label: str) -> str:
    if path.is_symlink() or not path.is_file() or not os.access(path, os.R_OK):
        raise RecordsAuditError(f"{label} must be a readable regular non-symlink file: {path}")
    size = path.stat().st_size
    if size > MAX_MARKDOWN_BYTES:
        raise RecordsAuditError(f"{label} exceeds {MAX_MARKDOWN_BYTES} bytes: {path}")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RecordsAuditError(f"cannot read {label} {path}: {exc}") from exc


def read_tsv(path: Path, columns: tuple[str, ...]) -> tuple[list[dict[str, str]], str | None]:
    if path.is_symlink() or not path.is_file() or not os.access(path, os.R_OK):
        return [], "missing-or-unreadable"
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            if tuple(reader.fieldnames or ()) != columns:
                return [], "header"
            rows: list[dict[str, str]] = []
            for line, raw in enumerate(reader, 2):
                if None in raw:
                    return [], f"line-{line}-extra-fields"
                row = {key: (raw.get(key) or "").strip() for key in columns}
                if any("\t" in value or "\n" in value or "\r" in value for value in row.values()):
                    return [], f"line-{line}-control-characters"
                rows.append(row)
                if len(rows) > MAX_RECORDS:
                    return [], "too-many-rows"
            return rows, None
    except (OSError, UnicodeError, csv.Error) as exc:
        return [], f"read-error:{exc}"


def metadata_value(text: str, key: str) -> str | None:
    # Metadata lives before the first Markdown heading. A body line such as
    # `Date: ...` inside a narrative section must not override record metadata.
    header = re.split(r"(?m)^##\s", text, maxsplit=1)[0]
    match = re.search(rf"(?m)^(?:-\s)?{re.escape(key)}:\s*(.*?)\s*$", header)
    return match.group(1).strip() if match else None


def section(text: str, heading: str) -> str | None:
    pattern = rf"(?ms)^{re.escape(heading)}\s*\n(.*?)(?=^##\s|\Z)"
    match = re.search(pattern, text)
    return match.group(1).strip() if match else None


def valid_date(value: str) -> bool:
    if not DATE_RE.fullmatch(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def date_from_filename(filename: str) -> str:
    stamp = filename[:8]
    return f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}"


def mentions_tmp(text: str) -> bool:
    return bool(re.search(r"(?<![A-Za-z0-9_.-])tmp/", text))


def existing_non_tmp(
    project: Path, value: str, *, allow_na: bool = True, allow_directory: bool = False
) -> str | None:
    value = value.strip()
    if not value or (allow_na and value == "NA"):
        return None
    raw = Path(value).expanduser()
    lexical = raw if raw.is_absolute() else project / raw
    try:
        lexical = lexical.resolve(strict=False)
        lexical.relative_to(project)
    except ValueError:
        return "outside-project"
    if project / "tmp" in lexical.parents or lexical == project / "tmp":
        return "tmp"
    try:
        relative = lexical.relative_to(project)
    except ValueError:
        return "outside-project"
    if "tmp" in relative.parts:
        return "tmp"
    if lexical.is_symlink():
        return "symlink"
    if allow_directory and lexical.is_dir():
        return None if os.access(lexical, os.R_OK) else "unreadable"
    if not lexical.is_file() or not os.access(lexical, os.R_OK):
        return "missing-or-unreadable"
    return None


def audit_status(project: Path, findings: list[Finding]) -> None:
    relative = "PROJECT_STATUS.md"
    path = project / relative
    if path.is_symlink():
        add(findings, "BLOCK", "REC_STATUS_UNSAFE", relative, "PROJECT_STATUS.md must not be a symlink")
        return
    if not path.is_file():
        add(findings, "WARN", "REC_STATUS_MISSING", relative, "layout-v2 project has no PROJECT_STATUS.md")
        return
    try:
        text = read_text_bounded(path, relative)
    except RecordsAuditError as exc:
        add(findings, "BLOCK", "REC_STATUS_UNSAFE", relative, str(exc))
        return
    missing = [heading for heading in REQUIRED_STATUS_HEADINGS if re.search(rf"(?m)^{re.escape(heading)}\s*$", text) is None]
    if missing:
        add(findings, "BLOCK", "REC_STATUS_SCHEMA", relative, "missing headings: " + ", ".join(missing))
    objective = section(text, "## Current objective") or ""
    stage = metadata_value(objective, "Current analysis stage")
    maturity = metadata_value(objective, "Current result maturity")
    manuscript = metadata_value(objective, "Current manuscript stage")
    reviewed = metadata_value(text, "Last_Reviewed")
    baseline = metadata_value(objective, "Baseline commit/tag")
    if stage not in LIFECYCLE_STAGES:
        add(findings, "BLOCK", "REC_STATUS_VALUE", relative, f"invalid Current analysis stage: {stage!r}")
    if maturity not in MATURITY:
        add(findings, "BLOCK", "REC_STATUS_VALUE", relative, f"invalid Current result maturity: {maturity!r}")
    if manuscript not in MANUSCRIPT_STAGES:
        add(findings, "BLOCK", "REC_STATUS_VALUE", relative, f"invalid Current manuscript stage: {manuscript!r}")
    if reviewed != "UNKNOWN" and not valid_date(reviewed):
        add(findings, "BLOCK", "REC_STATUS_VALUE", relative, f"invalid Last_Reviewed date: {reviewed!r}")
    if maturity in {"Verified", "Frozen"} and baseline == "UNKNOWN":
        add(findings, "WARN", "REC_STATUS_BASELINE", relative, "verified/frozen maturity still has UNKNOWN baseline")
    if "`docs/status/workflow_status.tsv`" not in text or "`docs/status/Task_Status.tsv`" not in text:
        add(findings, "WARN", "REC_STATUS_LINKS", relative, "machine-authority TSV links are missing")


def known_analysis_keys(project: Path) -> set[str]:
    keys: set[str] = set()
    modules = project / "config" / "Workspace_Modules.tsv"
    if modules.is_file() and not modules.is_symlink():
        rows, _ = read_tsv(modules, (
            "Module_ID", "Analysis_Key", "Parent_Module", "Stage", "Short_Name",
            "Module_Kind", "Depends_On", "Purpose", "Owner", "Compatibility", "Notes",
        ))
        keys.update(row.get("Analysis_Key", "") for row in rows if row.get("Analysis_Key"))
    results = project / "results"
    if results.is_dir() and not results.is_symlink():
        for child in results.iterdir():
            match = re.fullmatch(r"[0-9]{2}-([a-z][a-z0-9-]*)", child.name)
            if match and child.is_dir() and not child.is_symlink():
                keys.add(match.group(1))
    return keys


def known_task_ids(project: Path, layout: layout_contract.ProjectLayout) -> set[str]:
    path = project / layout_contract.control_relative(layout, "task_status")
    rows, _ = read_tsv(path, (
        "Task_ID", "Stage", "Sample_ID", "Status", "Job_ID", "Dependency",
        "Script_Path", "Log_Path", "Output_Path", "Acceptance_Path", "Retry_Count",
        "Updated_Time",
    ))
    return {row["Task_ID"] for row in rows if row.get("Task_ID")}


def audit_one_log(
    project: Path,
    path: Path,
    analysis_keys: set[str],
    task_ids: set[str],
    findings: list[Finding],
) -> dict[str, str] | None:
    relative = path.relative_to(project).as_posix()
    if not FILENAME_RE.fullmatch(path.name):
        add(findings, "BLOCK", "REC_LOG_NAME", relative, "research-log filename must be YYYYMMDD_Short_Name.md")
        return None
    if path.is_symlink() or not path.is_file():
        add(findings, "BLOCK", "REC_LOG_UNSAFE", relative, "research log must be a regular non-symlink file")
        return None
    try:
        text = read_text_bounded(path, relative)
    except RecordsAuditError as exc:
        add(findings, "BLOCK", "REC_LOG_UNSAFE", relative, str(exc))
        return None
    values = {
        "Research_Log_ID": metadata_value(text, "Research_Log_ID"),
        "Date": metadata_value(text, "Date"),
        "Analysis_Key": metadata_value(text, "Analysis_Key"),
        "Module_ID": metadata_value(text, "Module_ID"),
        "Task_ID": metadata_value(text, "Task_ID"),
        "Result_Maturity": metadata_value(text, "Result_Maturity"),
    }
    missing = [key for key, value in values.items() if value is None]
    if missing:
        add(findings, "BLOCK", "REC_LOG_META", relative, "missing metadata: " + ", ".join(missing))
        return None
    if not LOG_ID_RE.fullmatch(values["Research_Log_ID"]):  # type: ignore[index]
        add(findings, "BLOCK", "REC_LOG_META", relative, f"invalid Research_Log_ID: {values['Research_Log_ID']!r}")
    if not valid_date(values["Date"]):  # type: ignore[index]
        add(findings, "BLOCK", "REC_LOG_META", relative, f"invalid Date: {values['Date']!r}")
    elif values["Date"] != date_from_filename(path.name):  # type: ignore[index]
        add(findings, "BLOCK", "REC_LOG_DATE", relative, "Date does not match filename")
    if values["Analysis_Key"] != "NA":  # type: ignore[index]
        if not ANALYSIS_KEY_RE.fullmatch(values["Analysis_Key"]):  # type: ignore[index]
            add(findings, "BLOCK", "REC_LOG_META", relative, f"invalid Analysis_Key: {values['Analysis_Key']!r}")
        elif analysis_keys and values["Analysis_Key"] not in analysis_keys:  # type: ignore[index]
            add(findings, "WARN", "REC_LOG_MODULE", relative, f"Analysis_Key is not known in workspace/results: {values['Analysis_Key']}")
    if values["Module_ID"] != "NA" and not MODULE_ID_RE.fullmatch(values["Module_ID"]):  # type: ignore[index]
        add(findings, "BLOCK", "REC_LOG_META", relative, f"invalid Module_ID: {values['Module_ID']!r}")
    if values["Task_ID"] != "NA":  # type: ignore[index]
        if not TASK_ID_RE.fullmatch(values["Task_ID"]):  # type: ignore[index]
            add(findings, "BLOCK", "REC_LOG_META", relative, f"invalid Task_ID: {values['Task_ID']!r}")
        elif task_ids and values["Task_ID"] not in task_ids:  # type: ignore[index]
            add(findings, "WARN", "REC_LOG_TASK", relative, f"Task_ID is not registered: {values['Task_ID']}")
    if values["Result_Maturity"] not in MATURITY:  # type: ignore[index]
        add(findings, "BLOCK", "REC_LOG_MATURITY", relative, f"invalid Result_Maturity: {values['Result_Maturity']!r}")
    missing_headings = [heading for heading in REQUIRED_LOG_HEADINGS if section(text, heading) is None]
    if missing_headings:
        add(findings, "BLOCK", "REC_LOG_SECTION", relative, "missing sections: " + ", ".join(missing_headings))
    outputs = section(text, "## Outputs") or ""
    if outputs and mentions_tmp(outputs):
        add(findings, "BLOCK", "REC_LOG_TMP", relative, "Outputs section cites disposable tmp/")
    if values["Result_Maturity"] in {"Verified", "Frozen"}:  # type: ignore[index]
        if "UNKNOWN" in text:
            add(findings, "BLOCK", "REC_LOG_FORMAL", relative, "Verified/Frozen log still contains UNKNOWN placeholders")
        output_lines = [line for line in outputs.splitlines() if line.startswith("- Path:")]
        output_values = [line.split(":", 1)[1].strip() if ":" in line else "" for line in output_lines]
        if not output_values or all(value == "NA" for value in output_values):
            add(findings, "BLOCK", "REC_LOG_FORMAL", relative, "Verified/Frozen log has no formal output path")
        for value in output_values:
            if value == "NA":
                continue
            issue = existing_non_tmp(project, value, allow_na=False)
            if issue:
                add(findings, "BLOCK", "REC_LOG_FORMAL", relative, f"formal output is {issue}: {value}")
        impact = section(text, "## Impact") or ""
        if "Affected claims: NA" in impact and "Affected figures/tables: NA" in impact:
            add(findings, "WARN", "REC_LOG_IMPACT", relative, "formal record records no claim or figure/table impact")
    return {key: str(value) for key, value in values.items()}


def audit_research_logs(project: Path, layout: layout_contract.ProjectLayout, findings: list[Finding]) -> None:
    root = project / "docs" / "research-log"
    index_path = root / "Log_Index.tsv"
    if root.is_symlink() or not root.is_dir():
        add(findings, "WARN", "REC_LOG_DIR", "docs/research-log", "research-log directory is missing or unsafe")
        return
    children = sorted(root.iterdir(), key=lambda path: path.name.casefold())
    subdirectories = [path for path in children if path.is_dir()]
    if subdirectories:
        names = ", ".join(path.name for path in subdirectories)
        add(findings, "BLOCK", "REC_LOG_DIR", "docs/research-log", f"research-log subdirectories are forbidden (logs must be direct children): {names}")
        return
    entries = [
        path for path in children
        if path.is_file() and path.suffix.lower() == ".md"
        and path.name not in {"README.md", "TEMPLATE.md"}
    ]
    entries.sort(key=lambda path: path.name.casefold())
    if len(entries) > MAX_RECORDS:
        raise RecordsAuditError(f"research-log exceeds bounded cap {MAX_RECORDS}")
    analysis_keys = known_analysis_keys(project)
    task_ids = known_task_ids(project, layout)
    parsed: dict[str, dict[str, str]] = {}
    parsed_filenames: dict[str, str] = {}
    for path in entries:
        metadata = audit_one_log(project, path, analysis_keys, task_ids, findings)
        if metadata and metadata["Research_Log_ID"] in parsed:
            add(findings, "BLOCK", "REC_LOG_ID", path.relative_to(project).as_posix(), f"duplicate Research_Log_ID: {metadata['Research_Log_ID']}")
        elif metadata:
            parsed[metadata["Research_Log_ID"]] = metadata  # type: ignore[index]
            parsed_filenames[metadata["Research_Log_ID"]] = path.name
    rows, error = read_tsv(index_path, LOG_COLUMNS)
    if error == "missing-or-unreadable":
        status = "BLOCK" if entries else "WARN"
        add(findings, status, "REC_LOG_INDEX", index_path.relative_to(project).as_posix(), "Log_Index.tsv is missing or unreadable")
        return
    if error:
        add(findings, "BLOCK", "REC_LOG_INDEX", index_path.relative_to(project).as_posix(), f"Log_Index.tsv invalid: {error}")
        return
    indexed: dict[str, dict[str, str]] = {}
    filenames: set[str] = set()
    for row in rows:
        row_id = row["Research_Log_ID"]
        if not LOG_ID_RE.fullmatch(row_id):
            add(findings, "BLOCK", "REC_LOG_INDEX", index_path.relative_to(project).as_posix(), f"invalid Research_Log_ID: {row_id!r}")
            continue
        if row_id in indexed:
            add(findings, "BLOCK", "REC_LOG_INDEX", index_path.relative_to(project).as_posix(), f"duplicate Research_Log_ID: {row_id}")
            continue
        indexed[row_id] = row
        filename = row["Filename"]
        if filename in filenames:
            add(findings, "BLOCK", "REC_LOG_INDEX", index_path.relative_to(project).as_posix(), f"duplicate Filename: {filename}")
        filenames.add(filename)
        if not FILENAME_RE.fullmatch(filename):
            add(findings, "BLOCK", "REC_LOG_INDEX", index_path.relative_to(project).as_posix(), f"invalid Filename: {filename!r}")
        if not valid_date(row["Date"]):
            add(findings, "BLOCK", "REC_LOG_INDEX", index_path.relative_to(project).as_posix(), f"invalid Date: {row['Date']!r}")
        if row["Result_Maturity"] not in MATURITY:
            add(findings, "BLOCK", "REC_LOG_INDEX", index_path.relative_to(project).as_posix(), f"invalid Result_Maturity: {row['Result_Maturity']!r}")
        if row["Record_Status"] not in RECORD_STATUS:
            add(findings, "BLOCK", "REC_LOG_INDEX", index_path.relative_to(project).as_posix(), f"invalid Record_Status: {row['Record_Status']!r}")
        if row["Analysis_Key"] != "NA" and not ANALYSIS_KEY_RE.fullmatch(row["Analysis_Key"]):
            add(findings, "BLOCK", "REC_LOG_INDEX", index_path.relative_to(project).as_posix(), f"invalid Analysis_Key: {row['Analysis_Key']!r}")
    actual_ids = set(parsed)
    indexed_ids = set(indexed)
    for log_id in sorted(actual_ids - indexed_ids):
        add(findings, "BLOCK", "REC_LOG_INDEX", index_path.relative_to(project).as_posix(), f"research log is not indexed: {log_id}")
    for log_id in sorted(indexed_ids - actual_ids):
        add(findings, "BLOCK", "REC_LOG_INDEX", index_path.relative_to(project).as_posix(), f"indexed research log is missing: {log_id}")
    for log_id in sorted(actual_ids & indexed_ids):
        metadata = parsed[log_id]
        row = indexed[log_id]
        expected_filename = parsed_filenames[log_id]
        mismatches = []
        for field in ("Date", "Analysis_Key", "Module_ID", "Task_ID", "Result_Maturity"):
            if row[field] != metadata[field]:
                mismatches.append(f"{field}: index={row[field]!r} log={metadata[field]!r}")
        if row["Filename"] != expected_filename:
            mismatches.append(f"Filename: index={row['Filename']!r} actual={expected_filename!r}")
        if mismatches:
            add(findings, "BLOCK", "REC_LOG_INDEX", index_path.relative_to(project).as_posix(), f"index/log mismatch for {log_id}: " + "; ".join(mismatches))


def audit_decisions(project: Path, findings: list[Finding]) -> None:
    path = project / "docs" / "decisions" / "Decision_Index.tsv"
    relative = path.relative_to(project).as_posix()
    rows, error = read_tsv(path, DECISION_COLUMNS)
    if error == "missing-or-unreadable":
        add(findings, "WARN", "REC_DECISION_INDEX", relative, "Decision_Index.tsv is missing or unreadable")
        return
    if error:
        add(findings, "BLOCK", "REC_DECISION_INDEX", relative, f"Decision_Index.tsv invalid: {error}")
        return
    seen: set[str] = set()
    for row in rows:
        decision_id = row["Decision_ID"]
        if not DECISION_ID_RE.fullmatch(decision_id):
            add(findings, "BLOCK", "REC_DECISION_ROW", relative, f"invalid Decision_ID: {decision_id!r}")
            continue
        if decision_id in seen:
            add(findings, "BLOCK", "REC_DECISION_ROW", relative, f"duplicate Decision_ID: {decision_id}")
            continue
        seen.add(decision_id)
        if not valid_date(row["Date"]):
            add(findings, "BLOCK", "REC_DECISION_ROW", relative, f"{decision_id}: invalid Date {row['Date']!r}")
        if not row["Decision"]:
            add(findings, "BLOCK", "REC_DECISION_ROW", relative, f"{decision_id}: Decision is empty")
        if row["Status"] not in DECISION_STATUS:
            add(findings, "BLOCK", "REC_DECISION_ROW", relative, f"{decision_id}: invalid Status {row['Status']!r}")
        if row["Status"] == "Accepted":
            if not row["Evidence_Path"] or row["Evidence_Path"] == "NA":
                add(findings, "BLOCK", "REC_DECISION_EVIDENCE", relative, f"{decision_id}: accepted decision must name readable non-tmp evidence")
            else:
                evidence_issue = existing_non_tmp(
                    project, row["Evidence_Path"], allow_na=False, allow_directory=True
                )
                if evidence_issue:
                    add(findings, "BLOCK", "REC_DECISION_EVIDENCE", relative, f"{decision_id}: accepted evidence is {evidence_issue}: {row['Evidence_Path']}")
        elif row["Status"] in {"Superseded", "Reversed"} and (not row["Evidence_Path"] or row["Evidence_Path"] == "NA"):
            add(findings, "BLOCK", "REC_DECISION_EVIDENCE", relative, f"{decision_id}: {row['Status'].lower()} decision must cite the evidence that changed it")
        for field in ("Affected_Modules", "Affected_Claims"):
            if row[field] and row[field] != "NA":
                for value in row[field].split(","):
                    value = value.strip()
                    if value and not TASK_ID_RE.fullmatch(value):
                        add(findings, "BLOCK", "REC_DECISION_ROW", relative, f"{decision_id}: invalid token in {field}: {value!r}")
        if not row["Decided_By"]:
            add(findings, "WARN", "REC_DECISION_OWNER", relative, f"{decision_id}: Decided_By is empty")


def audit_changelog(project: Path, findings: list[Finding]) -> None:
    relative = "CHANGELOG.md"
    path = project / relative
    if path.is_symlink() or not path.is_file():
        add(findings, "WARN", "REC_CHANGELOG", relative, "CHANGELOG.md is missing or unsafe")
        return
    try:
        read_text_bounded(path, relative)
    except RecordsAuditError as exc:
        add(findings, "BLOCK", "REC_CHANGELOG", relative, str(exc))
        return
    add(findings, "PASS", "REC_CHANGELOG_OK", relative, "changelog is readable")


def audit(project: Path) -> list[Finding]:
    layout = layout_contract.detect_layout(project)
    if not layout.is_v2:
        return [Finding("PASS", "REC_LEGACY", ".", "legacy project; v2 record contracts are not enforced")]
    findings: list[Finding] = []
    audit_status(project, findings)
    audit_research_logs(project, layout, findings)
    audit_decisions(project, findings)
    audit_changelog(project, findings)
    if not findings:
        add(findings, "PASS", "REC_OK", ".", "project records satisfy the v2 contract")
    return sorted(findings, key=lambda item: (-SEVERITY[item.Status], item.Relative_Path.casefold(), item.Rule_ID, item.Detail))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Bioflow project-records audit")
    parser.add_argument("--project", required=True)
    parser.add_argument("--format", choices=("text", "tsv", "json"), default="text")
    args = parser.parse_args(argv)
    try:
        project = safe_project(args.project)
        findings = audit(project)
    except (RecordsAuditError, layout_contract.LayoutError, OSError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps({"Project": str(project), "Findings": [asdict(item) for item in findings]}, indent=2, ensure_ascii=False))
    elif args.format == "tsv":
        writer = csv.DictWriter(sys.stdout, fieldnames=AUDIT_COLUMNS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for item in findings:
            writer.writerow(asdict(item))
    else:
        for item in findings:
            print(f"{item.Status} | {item.Rule_ID} | {item.Relative_Path} | {item.Detail}")
    worst = max(SEVERITY[item.Status] for item in findings)
    return 2 if worst == 2 else 1 if worst == 1 else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        try:
            sys.stdout.close()
        except OSError:
            pass
        raise SystemExit(0)
