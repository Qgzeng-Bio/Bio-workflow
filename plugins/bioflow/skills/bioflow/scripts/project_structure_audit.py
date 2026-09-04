#!/usr/bin/env python3
"""Read-only audit for Bioflow layout-v2 result, tmp, and figure contracts."""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

import project_layout as layout_contract

MAX_DEPTH = 5
MAX_ENTRIES = 5000
MODULE_RE = re.compile(r"^(?P<stage>[0-9]{2})-(?P<key>[a-z][a-z0-9-]*)$")
VERSION_RE = re.compile(r"^V[0-9]{2,}$")
FIGURE_RE = re.compile(r"^F[0-9]{3}_[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*$")
MANUSCRIPT_RE = re.compile(r"^P[0-9]{2}-[a-z][a-z0-9-]*$")
FORBIDDEN_MODULE_PARTS = {"final", "new", "latest", "best", "revised", "rerun"}
VERSION_COLUMNS = (
    "Version_ID", "Parent_Version", "Status", "Selected", "Input_Manifest",
    "Parameter_File", "Script_Commit", "Result_Path", "Acceptance_Path", "Notes",
)
FIGURE_COLUMNS = (
    "Figure_ID", "Figure_Title", "Figure_Directory", "Source_Result",
    "Plot_Script", "Status", "Manuscript_Target", "Notes",
)
FORMAL_STATUS = {"Validated", "Manuscript_ready", "Frozen"}
FIGURE_STATUSES = {"Draft", "Candidate", "Validated", "Manuscript_ready", "Frozen", "Rejected"}
VERSION_STATUSES = {"Candidate", "Validated", "Superseded", "Rejected", "Frozen"}
SEVERITY = {"PASS": 0, "WARN": 1, "BLOCK": 2}


class StructureError(ValueError):
    pass


@dataclass(frozen=True)
class Finding:
    Status: str
    Rule_ID: str
    Relative_Path: str
    Detail: str


def safe_project(value: str) -> Path:
    raw = Path(value).expanduser()
    if not raw.is_dir():
        raise StructureError(f"project must be an existing directory: {raw}")
    root = raw.resolve(strict=True)
    home = Path.home().resolve(strict=False)
    if root in {Path("/"), Path("/data9"), Path("/data9/home"), home, home / "projects"}:
        raise StructureError(f"refusing broad project root: {root}")
    return root


def add(findings: list[Finding], status: str, rule: str, path: str, detail: str) -> None:
    findings.append(Finding(status, rule, path, detail))


def read_tsv(path: Path, columns: tuple[str, ...], findings: list[Finding], rule: str) -> list[dict[str, str]]:
    relative = path.as_posix()
    if path.is_symlink() or not path.is_file():
        add(findings, "BLOCK", rule, relative, "required TSV is missing or not a regular file")
        return []
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            if tuple(reader.fieldnames or ()) != columns:
                add(findings, "BLOCK", rule, relative, "TSV header does not match the layout-v2 contract")
                return []
            rows = []
            for line, raw in enumerate(reader, 2):
                if None in raw:
                    add(findings, "BLOCK", rule, relative, f"line {line} has extra TSV fields")
                    continue
                rows.append({key: (raw.get(key) or "").strip() for key in columns})
            return rows
    except (OSError, csv.Error, UnicodeError) as exc:
        add(findings, "BLOCK", rule, relative, f"cannot read TSV: {exc}")
        return []


def bounded_entries(root: Path, max_depth: int) -> list[Path]:
    entries: list[Path] = []

    def visit(parent: Path, depth: int) -> None:
        if depth >= max_depth:
            return
        try:
            children = sorted(parent.iterdir(), key=lambda item: (item.name.casefold(), item.name))
        except OSError as exc:
            raise StructureError(f"cannot list {parent}: {exc}") from exc
        for child in children:
            entries.append(child)
            if len(entries) > MAX_ENTRIES:
                raise StructureError(f"bounded inventory exceeds {MAX_ENTRIES} entries")
            if child.is_symlink() or not child.is_dir():
                continue
            visit(child, depth + 1)

    if root.is_dir() and not root.is_symlink():
        visit(root, 0)
    return entries


def path_has_symlink(project: Path, path: Path) -> bool:
    """Check lexical path components inside project without following them."""
    try:
        relative = path.absolute().relative_to(project)
    except ValueError:
        return True
    current = project
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def regular_file(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


def regular_dir(path: Path) -> bool:
    return path.is_dir() and not path.is_symlink()


def text_mentions_tmp(project: Path, path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False
    patterns = (
        r"(?<![A-Za-z0-9_.-])tmp/",
        re.escape(str(project / "tmp")) + r"(?:/|$)",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def audit_figure_root(project: Path, figure_root: Path, findings: list[Finding]) -> None:
    relative_root = figure_root.relative_to(project).as_posix()
    index_path = figure_root / "Figure_Index.tsv"
    if index_path.exists():
        rows = read_tsv(index_path, FIGURE_COLUMNS, findings, "STRUCT_FIGURE_INDEX")
    else:
        add(findings, "WARN", "STRUCT_FIGURE_INDEX", relative_root, "draft figures/ has no Figure_Index.tsv yet")
        rows = []
    by_directory: dict[str, dict[str, str]] = {}
    for row in rows:
        directory = row["Figure_Directory"]
        if not FIGURE_RE.fullmatch(directory):
            add(findings, "BLOCK", "STRUCT_FIGURE_NAME", relative_root, f"invalid Figure_Directory: {directory!r}")
        if directory in by_directory:
            add(findings, "BLOCK", "STRUCT_FIGURE_INDEX", relative_root, f"duplicate Figure_Directory: {directory}")
        by_directory[directory] = row
        if not re.fullmatch(r"F[0-9]{3}", row["Figure_ID"]):
            add(findings, "BLOCK", "STRUCT_FIGURE_INDEX", relative_root, f"invalid Figure_ID: {row['Figure_ID']!r}")
        elif not directory.startswith(row["Figure_ID"] + "_"):
            add(findings, "BLOCK", "STRUCT_FIGURE_INDEX", relative_root, f"Figure_ID does not match directory: {row['Figure_ID']} vs {directory}")
        if row["Status"] not in FIGURE_STATUSES:
            add(findings, "BLOCK", "STRUCT_FIGURE_INDEX", relative_root, f"invalid figure Status: {row['Status']!r}")
        for label in ("Source_Result", "Plot_Script"):
            value = row[label]
            if value and value != "NA" and (value == "tmp" or value.startswith("tmp/") or "/tmp/" in value):
                add(findings, "BLOCK", "STRUCT_TMP_REFERENCE", index_path.relative_to(project).as_posix(), f"{label} points to tmp/: {value}")

    for child in sorted(figure_root.iterdir(), key=lambda item: item.name.casefold()):
        if child.name == "Figure_Index.tsv":
            continue
        if child.is_symlink() or not child.is_dir() or not FIGURE_RE.fullmatch(child.name):
            add(findings, "BLOCK", "STRUCT_FIGURE_ROOT", child.relative_to(project).as_posix(), "figures/ may contain only Figure_Index.tsv and FNNN_Name package directories")
            continue
        row = by_directory.get(child.name)
        if row is None:
            add(findings, "WARN", "STRUCT_FIGURE_INDEX", child.relative_to(project).as_posix(), "figure package is not registered in Figure_Index.tsv")
        formal = row is not None and row["Status"] in FORMAL_STATUS
        if formal and row is not None:
            for label in ("Source_Result", "Plot_Script"):
                value = row[label]
                raw = Path(value).expanduser()
                lexical_target = raw if raw.is_absolute() else project / raw
                if path_has_symlink(project, lexical_target):
                    add(findings, "BLOCK", "STRUCT_FIGURE_SOURCE", child.relative_to(project).as_posix(), f"formal {label} must not use a symlink or external path: {value}")
                target = lexical_target.resolve(strict=False)
                if target == project / "tmp" or project / "tmp" in target.parents:
                    add(findings, "BLOCK", "STRUCT_TMP_REFERENCE", index_path.relative_to(project).as_posix(), f"{label} points to tmp/: {value}")
                expected_root = project / ("results" if label == "Source_Result" else "scripts")
                if target != expected_root and expected_root not in target.parents:
                    add(findings, "BLOCK", "STRUCT_FIGURE_SOURCE", child.relative_to(project).as_posix(), f"formal {label} must be under {expected_root.relative_to(project)}: {value}")
                if not target.is_file() or not os.access(target, os.R_OK):
                    add(findings, "BLOCK", "STRUCT_FIGURE_SOURCE", child.relative_to(project).as_posix(), f"formal {label} is missing or unreadable: {value}")
        source_dir = child / "source-data"
        checks_dir = child / "checks"
        required = {
            "README.md": regular_file(child / "README.md"),
            "PDF": any(regular_file(path) for path in child.glob("*.pdf")),
            "PNG": any(regular_file(path) for path in child.glob("*.png")),
            "source-data TSV": regular_dir(source_dir) and any(regular_file(path) for path in source_dir.glob("*.tsv")),
            "checks Markdown": regular_dir(checks_dir) and any(regular_file(path) for path in checks_dir.glob("*.md")),
            "checks JSON": regular_dir(checks_dir) and any(regular_file(path) for path in checks_dir.glob("*.json")),
        }
        missing = [label for label, present in required.items() if not present]
        if missing:
            add(findings, "BLOCK" if formal else "WARN", "STRUCT_FIGURE_PACKAGE", child.relative_to(project).as_posix(), "incomplete figure package: " + ", ".join(missing))
    for directory in sorted(set(by_directory) - {path.name for path in figure_root.iterdir() if path.is_dir()}):
        add(findings, "BLOCK", "STRUCT_FIGURE_INDEX", relative_root, f"indexed figure package is missing: {directory}")


def audit(project: Path, max_depth: int) -> list[Finding]:
    if not 1 <= max_depth <= MAX_DEPTH:
        raise StructureError(f"--max-depth must be between 1 and {MAX_DEPTH}")
    layout = layout_contract.detect_layout(project)
    if not layout.is_v2:
        return [Finding("PASS", "STRUCT_LEGACY", ".", "legacy project left unchanged; layout-v2 rules were not applied")]
    findings: list[Finding] = []
    for root in layout.canonical_dirs:
        path = project / root
        if path.is_symlink() or not path.is_dir():
            add(findings, "BLOCK", "STRUCT_ROOT", root, "required layout-v2 root is missing or unsafe")
    for legacy_root in ("data", "reports"):
        if (project / legacy_root).exists() or (project / legacy_root).is_symlink():
            add(findings, "BLOCK", "STRUCT_MIXED_LAYOUT", legacy_root, "layout v2 must not contain legacy data/reports roots")

    results = project / "results"
    modules: dict[str, str] = {}
    if results.is_dir():
        for module in sorted(results.iterdir(), key=lambda item: item.name.casefold()):
            relative = module.relative_to(project).as_posix()
            if module.is_symlink() or not module.is_dir():
                add(findings, "BLOCK", "STRUCT_RESULT_ENTRY", relative, "results/ may contain only analysis-module directories")
                continue
            match = MODULE_RE.fullmatch(module.name)
            if not match:
                add(findings, "BLOCK", "STRUCT_MODULE_NAME", relative, "result module must use NN-analysis-key")
                continue
            key = match.group("key")
            if any(part in FORBIDDEN_MODULE_PARTS or re.fullmatch(r"v[0-9]+", part) for part in key.split("-")):
                add(findings, "BLOCK", "STRUCT_MODULE_VERSION", relative, "module name must not contain version/status words; use versions/VNN")
            if key in modules:
                add(findings, "BLOCK", "STRUCT_ANALYSIS_UNIQUE", relative, f"analysis key {key!r} already uses {modules[key]}")
            modules[key] = relative

            versions = module / "versions"
            index_path = module / "Version_Index.tsv"
            if versions.exists() or index_path.exists():
                rows = read_tsv(index_path, VERSION_COLUMNS, findings, "STRUCT_VERSION_INDEX")
                indexed_list = [row["Version_ID"] for row in rows]
                indexed = set(indexed_list)
                if len(indexed) != len(indexed_list):
                    add(findings, "BLOCK", "STRUCT_VERSION_INDEX", index_path.relative_to(project).as_posix(), "Version_ID values must be unique")
                selected = [row for row in rows if row["Selected"] == "Yes"]
                if len(selected) > 1:
                    add(findings, "BLOCK", "STRUCT_VERSION_INDEX", index_path.relative_to(project).as_posix(), "at most one version may be Selected=Yes")
                for row in rows:
                    version_id = row["Version_ID"]
                    expected_result = f"{relative}/versions/{version_id}"
                    if not VERSION_RE.fullmatch(version_id):
                        add(findings, "BLOCK", "STRUCT_VERSION_INDEX", index_path.relative_to(project).as_posix(), f"invalid Version_ID: {version_id!r}")
                    if row["Status"] not in VERSION_STATUSES:
                        add(findings, "BLOCK", "STRUCT_VERSION_INDEX", index_path.relative_to(project).as_posix(), f"invalid version Status: {row['Status']!r}")
                    if row["Selected"] not in {"Yes", "No"}:
                        add(findings, "BLOCK", "STRUCT_VERSION_INDEX", index_path.relative_to(project).as_posix(), f"Selected must be Yes or No: {version_id}")
                    if row["Result_Path"] != expected_result:
                        add(findings, "BLOCK", "STRUCT_VERSION_INDEX", index_path.relative_to(project).as_posix(), f"Result_Path must be {expected_result}")
                    parent = row["Parent_Version"]
                    if parent not in {"", "NA"} and (parent == version_id or parent not in indexed):
                        add(findings, "BLOCK", "STRUCT_VERSION_INDEX", index_path.relative_to(project).as_posix(), f"invalid Parent_Version for {version_id}: {parent}")
                actual: set[str] = set()
                if versions.is_symlink() or not versions.is_dir():
                    add(findings, "BLOCK", "STRUCT_VERSION_PATH", versions.relative_to(project).as_posix(), "versions must be a regular directory")
                else:
                    for version in versions.iterdir():
                        if version.is_symlink() or not version.is_dir() or not VERSION_RE.fullmatch(version.name):
                            add(findings, "BLOCK", "STRUCT_VERSION_PATH", version.relative_to(project).as_posix(), "retained versions must use versions/VNN")
                        else:
                            actual.add(version.name)
                for version in sorted(actual - indexed):
                    add(findings, "BLOCK", "STRUCT_VERSION_INDEX", versions.relative_to(project).as_posix(), f"unregistered retained version: {version}")
                for version in sorted(indexed - actual):
                    add(findings, "BLOCK", "STRUCT_VERSION_INDEX", index_path.relative_to(project).as_posix(), f"indexed version directory is missing: {version}")
            for candidate in bounded_entries(module, max_depth):
                if candidate.is_symlink():
                    continue
                if candidate.is_dir() and re.fullmatch(r"[Vv][0-9].*", candidate.name):
                    rel = candidate.relative_to(module)
                    if len(rel.parts) != 2 or rel.parts[0] != "versions" or not VERSION_RE.fullmatch(rel.parts[1]):
                        add(findings, "BLOCK", "STRUCT_VERSION_PATH", candidate.relative_to(project).as_posix(), "version-like directory must be <module>/versions/VNN")
            figure_root = module / "figures"
            if figure_root.exists():
                if figure_root.is_symlink() or not figure_root.is_dir():
                    add(findings, "BLOCK", "STRUCT_FIGURE_ROOT", figure_root.relative_to(project).as_posix(), "figures must be a regular directory")
                else:
                    audit_figure_root(project, figure_root, findings)

    observed_stages = sorted(
        int(match.group("stage"))
        for path in results.iterdir() if path.is_dir() and not path.is_symlink()
        if (match := MODULE_RE.fullmatch(path.name))
    ) if results.is_dir() else []
    expected_stages = list(range(1, len(observed_stages) + 1))
    if observed_stages != expected_stages:
        add(findings, "BLOCK", "STRUCT_MODULE_STAGE", "results", f"top-level result stages must be consecutive 01..{len(observed_stages):02d}; observed={observed_stages}")

    manuscript_root = project / "manuscripts"
    if manuscript_root.is_dir():
        for child in sorted(manuscript_root.iterdir(), key=lambda item: item.name.casefold()):
            if child.name == "README.md":
                continue
            relative = child.relative_to(project).as_posix()
            if child.is_symlink() or not child.is_dir() or not MANUSCRIPT_RE.fullmatch(child.name):
                add(findings, "BLOCK", "STRUCT_MANUSCRIPT_NAME", relative, "manuscripts/ may contain only README.md and stable PNN-short-name paper directories")

    formal_files = [project / "config" / "result_manifest.yaml"]
    for relative in (
        layout_contract.control_relative(layout, "acceptance"),
        layout_contract.control_relative(layout, "delivery"),
    ):
        formal_files.append(project / relative)
    formal_files.extend(
        path for path in bounded_entries(project / "manuscripts", max_depth)
        if path.name == "Claim_Evidence_Map.tsv"
    )
    formal_files.extend(
        path for path in bounded_entries(project / "results", max_depth)
        if path.name in {"Version_Index.tsv", "Figure_Index.tsv"}
    )
    for path in formal_files:
        if path.is_symlink():
            add(findings, "BLOCK", "STRUCT_FORMAL_SYMLINK", path.relative_to(project).as_posix(), "formal result, claim, figure, acceptance, or delivery record must not be a symlink")
            continue
        if path.is_file() and text_mentions_tmp(project, path):
            add(findings, "BLOCK", "STRUCT_TMP_REFERENCE", path.relative_to(project).as_posix(), "formal result, claim, figure, acceptance, or delivery record references tmp/")

    if not findings:
        findings.append(Finding("PASS", "STRUCT_OK", ".", "layout-v2 structural contracts pass"))
    return sorted(findings, key=lambda row: (-SEVERITY[row.Status], row.Relative_Path.casefold(), row.Rule_ID, row.Detail))


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Bioflow layout-v2 structure audit")
    parser.add_argument("--project", required=True)
    parser.add_argument("--max-depth", type=int, default=3)
    parser.add_argument("--format", choices=("text", "tsv", "json"), default="text")
    args = parser.parse_args()
    try:
        project = safe_project(args.project)
        findings = audit(project, args.max_depth)
    except (StructureError, layout_contract.LayoutError, OSError, csv.Error) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    worst = max(SEVERITY[row.Status] for row in findings)
    if args.format == "json":
        print(json.dumps({"Project": str(project), "Findings": [asdict(row) for row in findings]}, indent=2, ensure_ascii=False))
    elif args.format == "tsv":
        writer = csv.DictWriter(sys.stdout, fieldnames=Finding.__dataclass_fields__, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in findings:
            writer.writerow(asdict(row))
    else:
        for row in findings:
            print(f"{row.Status} | {row.Rule_ID} | {row.Relative_Path} | {row.Detail}")
    return 2 if worst == 2 else 1 if worst == 1 else 0


if __name__ == "__main__":
    raise SystemExit(main())
