#!/usr/bin/env python3
"""Read-only Draft/Reviewed/Frozen publication trace audit for Bioflow layout v2."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.stderr.write("PyYAML is required; use an existing Python environment with yaml support.\n")
    raise SystemExit(2)

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
import check_result_contract as result_contract  # noqa: E402
import project_layout as layout_contract  # noqa: E402
import project_records_audit as records_audit  # noqa: E402
import project_structure_audit as structure_audit  # noqa: E402

MAP_COLUMNS = (
    "Schema_Version", "Paper_ID", "Claim_ID", "Manuscript_Path",
    "Figure_Refs", "Source_Table_Paths", "Version_Refs",
    "Mapping_Status", "Notes",
)
VERSION_COLUMNS = (
    "Version_ID", "Parent_Version", "Status", "Selected", "Input_Manifest",
    "Parameter_File", "Script_Commit", "Result_Path", "Acceptance_Path", "Notes",
)
FIGURE_COLUMNS = (
    "Figure_ID", "Figure_Title", "Figure_Directory", "Source_Result",
    "Plot_Script", "Status", "Manuscript_Target", "Notes",
)
AUDIT_COLUMNS = ("Status", "Rule_ID", "Paper_ID", "Claim_ID", "Relative_Path", "Detail")
SEVERITY = {"PASS": 0, "INFO": 0, "WARN": 1, "BLOCK": 2}
MAPPING_STATUS = {"Draft", "Reviewed", "Frozen"}
PAPER_RE = re.compile(r"^(P[0-9]{2})-[a-z][a-z0-9-]*$")
CLAIM_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
FIGURE_REF_RE = re.compile(r"^([a-z][a-z0-9-]*):(F[0-9]{3})$")
VERSION_REF_RE = re.compile(r"^([a-z][a-z0-9-]*):(V[0-9]{2,})$")
ANCHOR_RE = re.compile(r"<!--\s*bioflow-claim:\s*([A-Za-z0-9][A-Za-z0-9_.-]*)\s*-->")
MAX_PAPERS = 50
MAX_MAP_ROWS = 1000
MAX_MARKDOWN_FILES = 250
MAX_MARKDOWN_BYTES = 2 * 1024 * 1024
MAX_METADATA_BYTES = 2 * 1024 * 1024
MAX_SOURCE_TABLE_BYTES = 10 * 1024 * 1024
MAX_RELEASE_ARTIFACT_BYTES = 100 * 1024 * 1024
MAX_RELEASE_ARTIFACTS = 500
MAX_TSV_ROWS = 100_000
RELEASE_RE = re.compile(r"^R[0-9]{2,}$")
RELEASE_ID_RE = re.compile(r"^P[0-9]{2}-R[0-9]{2,}$")
ARTIFACT_ID_RE = re.compile(r"^A[0-9]{3,}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
TAG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
ARTIFACT_ROLES = {"Manuscript", "Figure", "Source_Table", "Supplement"}
CHECKLIST_KEYS = {
    "result_contract_required", "structure_audit_required", "records_audit_required",
    "trace_audit_required", "limitations_reviewed", "sensitive_data_reviewed",
    "licenses_reviewed", "coauthor_approval_recorded",
}


class TraceAuditError(ValueError):
    pass


@dataclass(frozen=True)
class Finding:
    Status: str
    Rule_ID: str
    Paper_ID: str
    Claim_ID: str
    Relative_Path: str
    Detail: str


@dataclass
class PaperTrace:
    paper_id: str
    mapping_statuses: set[str]
    claims: set[str]
    versions: set[str]
    figures: set[str]
    manuscripts: set[Path]
    source_tables: set[Path]
    figure_pdfs: set[Path]
    supplements: set[Path]


def add(
    findings: list[Finding], status: str, rule: str, relative: str, detail: str,
    *, paper_id: str = "NA", claim_id: str = "NA",
) -> None:
    findings.append(Finding(status, rule, paper_id, claim_id, relative, detail))


def strictness(mapping_status: str) -> str:
    return "WARN" if mapping_status == "Draft" else "BLOCK"


def safe_project(value: str) -> Path:
    raw = Path(value).expanduser()
    if not raw.is_dir():
        raise TraceAuditError(f"project must be an existing directory: {raw}")
    project = raw.resolve(strict=True)
    home = Path.home().resolve(strict=False)
    if project in {Path("/"), Path("/data9"), Path("/data9/home"), home, home / "projects"}:
        raise TraceAuditError(f"refusing broad project root: {project}")
    return project


def safe_relative_path(
    project: Path, value: str, label: str, *, required_root: str | None = None,
) -> tuple[Path, str]:
    value = value.strip()
    raw = Path(value)
    if not value or value == "NA" or raw.is_absolute() or ".." in raw.parts:
        raise TraceAuditError(f"{label} must be a non-NA project-relative path: {value!r}")
    if "tmp" in raw.parts:
        raise TraceAuditError(f"{label} must not contain a tmp path segment: {value}")
    if required_root is not None and (not raw.parts or raw.parts[0] != required_root):
        raise TraceAuditError(f"{label} must be under {required_root}/: {value}")
    current = project
    for part in raw.parts:
        current = current / part
        if current.is_symlink():
            raise TraceAuditError(f"{label} must not use a symbolic-link component: {value}")
    target = (project / raw).resolve(strict=False)
    try:
        target.relative_to(project)
    except ValueError as exc:
        raise TraceAuditError(f"{label} resolves outside project: {value}") from exc
    return target, raw.as_posix()


def safe_layout(project: Path):
    """Check marker ancestry before content reads; an absent marker stays legacy."""
    marker = project / "config" / "Project_Layout.tsv"
    if marker.exists() or marker.is_symlink():
        safe_relative_path(project, "config/Project_Layout.tsv", "layout marker", required_root="config")
    return layout_contract.detect_layout(project)


def read_exact_tsv(
    path: Path, columns: tuple[str, ...], label: str, *, max_rows: int = MAX_MAP_ROWS,
) -> list[dict[str, str]]:
    if path.is_symlink() or not path.is_file() or not os.access(path, os.R_OK):
        raise TraceAuditError(f"{label} must be a readable regular non-symlink file: {path}")
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            if tuple(reader.fieldnames or ()) != columns:
                raise TraceAuditError(f"{label} header must be exactly: {' | '.join(columns)}")
            rows: list[dict[str, str]] = []
            for line_number, raw in enumerate(reader, 2):
                if None in raw:
                    raise TraceAuditError(f"{label}:{line_number}: too many TSV fields")
                row = {column: (raw.get(column) or "").strip() for column in columns}
                if any("\t" in value or "\r" in value or "\n" in value for value in row.values()):
                    raise TraceAuditError(f"{label}:{line_number}: control characters are forbidden in fields")
                rows.append(row)
                if len(rows) > max_rows:
                    raise TraceAuditError(f"{label} exceeds bounded row cap {max_rows}")
            return rows
    except (OSError, UnicodeError, csv.Error) as exc:
        raise TraceAuditError(f"cannot read {label}: {exc}") from exc


def parse_semicolon(value: str, label: str, pattern: re.Pattern[str] | None = None) -> list[str]:
    value = value.strip()
    if value == "NA":
        return []
    if not value:
        raise TraceAuditError(f"{label} must be NA or a non-empty semicolon list")
    if "," in value:
        raise TraceAuditError(f"{label} uses semicolons, not commas")
    items = [item.strip() for item in value.split(";")]
    if any(not item for item in items):
        raise TraceAuditError(f"{label} contains an empty list item")
    if len(set(items)) != len(items):
        raise TraceAuditError(f"{label} contains duplicate values")
    if pattern is not None:
        invalid = [item for item in items if not pattern.fullmatch(item)]
        if invalid:
            raise TraceAuditError(f"{label} contains invalid refs: {invalid}")
    return items


def paper_directories(project: Path, selected: str | None, findings: list[Finding]) -> list[Path]:
    root = project / "manuscripts"
    if root.is_symlink() or not root.is_dir():
        add(findings, "BLOCK", "TRACE_UNSAFE_PATH", "manuscripts", "manuscripts root is missing or unsafe")
        return []
    papers: list[Path] = []
    for child in sorted(root.iterdir(), key=lambda item: (item.name.casefold(), item.name)):
        if child.name == "README.md":
            continue
        relative = child.relative_to(project).as_posix()
        if child.is_symlink() or not child.is_dir() or not PAPER_RE.fullmatch(child.name):
            add(findings, "BLOCK", "TRACE_PAPER_NAME", relative, "paper entry must be a regular PNN-short-name directory")
            continue
        papers.append(child)
    if len(papers) > MAX_PAPERS:
        raise TraceAuditError(f"paper count exceeds bounded cap {MAX_PAPERS}")
    if selected:
        if "/" in selected or selected in {".", ".."}:
            raise TraceAuditError("--paper must be one PNN-short-name basename")
        matches = [paper for paper in papers if paper.name == selected]
        if not matches:
            raise TraceAuditError(f"selected paper does not exist: {selected}")
        return matches
    return papers


def module_index(project: Path, findings: list[Finding]) -> dict[str, Path]:
    root = project / "results"
    modules: dict[str, Path] = {}
    if root.is_symlink() or not root.is_dir():
        add(findings, "BLOCK", "TRACE_LAYOUT_RESULTS", "results", "results root is missing or unsafe")
        return modules
    for child in sorted(root.iterdir(), key=lambda item: (item.name.casefold(), item.name)):
        match = re.fullmatch(r"[0-9]{2}-([a-z][a-z0-9-]*)", child.name)
        if not match or child.is_symlink() or not child.is_dir():
            continue  # project_structure_audit is the authority for unrelated malformed entries.
        key = match.group(1)
        if key in modules:
            add(findings, "BLOCK", "TRACE_LAYOUT_MODULE", "results", f"duplicate Analysis_Key: {key}")
        modules[key] = child
    return modules


def load_result_manifest(project: Path) -> tuple[dict[str, Any], Path, dict[str, dict[str, Any]], list[dict[str, str]]]:
    path, _ = safe_relative_path(project, "config/result_manifest.yaml", "result manifest", required_root="config")
    if path.is_symlink() or not path.is_file() or not os.access(path, os.R_OK):
        raise TraceAuditError(f"result manifest must be a readable regular non-symlink file: {path}")
    manifest = yaml_mapping(path, "result manifest")
    claims: dict[str, dict[str, Any]] = {}
    for claim in result_contract.list_of(manifest, "claims"):
        claim_id = str(claim.get("claim_id") or "")
        if claim_id in claims:
            raise TraceAuditError(f"result manifest contains duplicate claim_id: {claim_id}")
        if claim_id:
            claims[claim_id] = claim
    rules = result_contract.load_rules(result_contract.DEFAULT_RULES)
    return manifest, path, claims, rules


def claim_contract_status(
    manifest: dict[str, Any], claim: dict[str, Any], rules: list[dict[str, str]], manifest_dir: Path,
) -> tuple[str, list[result_contract.Finding]]:
    subset = dict(manifest)
    subset["claims"] = [claim]
    return result_contract.run(subset, rules, {}, manifest_dir)


def load_version_rows(project: Path, module: Path) -> dict[str, dict[str, str]]:
    path, _ = safe_relative_path(project, (module / "Version_Index.tsv").relative_to(project).as_posix(), "version index", required_root="results")
    rows = read_exact_tsv(path, VERSION_COLUMNS, f"{module.name}/Version_Index.tsv")
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        key = row["Version_ID"]
        if key in result:
            raise TraceAuditError(f"{module.name}/Version_Index.tsv has duplicate Version_ID: {key}")
        result[key] = row
    return result


def load_figure_rows(project: Path, module: Path) -> dict[str, dict[str, str]]:
    path, _ = safe_relative_path(project, (module / "figures/Figure_Index.tsv").relative_to(project).as_posix(), "figure index", required_root="results")
    rows = read_exact_tsv(path, FIGURE_COLUMNS, f"{module.name}/figures/Figure_Index.tsv")
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        key = row["Figure_ID"]
        if key in result:
            raise TraceAuditError(f"{module.name}/Figure_Index.tsv has duplicate Figure_ID: {key}")
        result[key] = row
    return result


def bounded_markdown_files(paper: Path) -> list[Path]:
    found: list[Path] = []

    def visit(parent: Path, depth: int) -> None:
        if depth >= 5:
            if next(parent.iterdir(), None) is not None:
                raise TraceAuditError(f"Markdown inventory exceeds depth bound 5: {parent}")
            return
        for child in sorted(parent.iterdir(), key=lambda item: (item.name.casefold(), item.name)):
            if child.name.startswith(".") or (depth == 0 and child.name == "releases"):
                continue
            if child.is_symlink():
                continue
            if child.is_dir():
                visit(child, depth + 1)
            elif child.is_file() and child.suffix.lower() == ".md":
                found.append(child)
                if len(found) > MAX_MARKDOWN_FILES:
                    raise TraceAuditError(f"Markdown count exceeds bounded cap {MAX_MARKDOWN_FILES}")

    visit(paper, 0)
    return found


def read_bounded_bytes(path: Path, label: str, max_bytes: int) -> bytes:
    if path.is_symlink() or not path.is_file() or not os.access(path, os.R_OK):
        raise TraceAuditError(f"{label} must be a readable regular non-symlink file: {path}")
    if path.stat().st_size > max_bytes:
        raise TraceAuditError(f"{label} exceeds {max_bytes} bytes: {path}")
    with path.open("rb") as handle:
        data = handle.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise TraceAuditError(f"{label} grew beyond {max_bytes} bytes: {path}")
    return data


def read_markdown(path: Path) -> str:
    return read_bounded_bytes(path, "manuscript", MAX_MARKDOWN_BYTES).decode("utf-8")


def validate_source_table(path: Path) -> str | None:
    if path.is_symlink() or not path.is_file() or not os.access(path, os.R_OK):
        return "source table is missing, unreadable, or a symlink"
    if path.suffix.lower() != ".tsv":
        return "source table must use .tsv"
    if path.stat().st_size > MAX_SOURCE_TABLE_BYTES:
        return f"source table exceeds bounded size cap {MAX_SOURCE_TABLE_BYTES}"
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle, delimiter="\t")
            header = next(reader, None)
            if header is None or len(header) < 2 or any(not value.strip() for value in header):
                return "source table requires at least two non-empty tab-separated header columns"
            count = 0
            for count, row in enumerate(reader, 1):
                if count > MAX_TSV_ROWS:
                    return f"source table exceeds bounded row cap {MAX_TSV_ROWS}"
                if len(row) != len(header):
                    return f"source table data row {count} does not match header width"
            if not count:
                return "source table has a header but no data row"
    except (OSError, UnicodeError, csv.Error) as exc:
        return f"cannot parse source table: {exc}"
    return None


def sha256_file(path: Path) -> str:
    if path.stat().st_size > MAX_RELEASE_ARTIFACT_BYTES:
        raise TraceAuditError(f"artifact exceeds {MAX_RELEASE_ARTIFACT_BYTES} bytes: {path}")
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as handle:
        while chunk := handle.read(min(1024 * 1024, MAX_RELEASE_ARTIFACT_BYTES - total + 1)):
            total += len(chunk)
            if total > MAX_RELEASE_ARTIFACT_BYTES:
                raise TraceAuditError(f"artifact grew beyond size bound: {path}")
            digest.update(chunk)
    return digest.hexdigest()


def bounded_files(root: Path, *, depth_limit: int = 5, count_limit: int = MAX_RELEASE_ARTIFACTS) -> set[Path]:
    found: set[Path] = set()
    visited = 0

    def visit(parent: Path, depth: int) -> None:
        nonlocal visited
        if depth >= depth_limit:
            if next(parent.iterdir(), None) is not None:
                raise TraceAuditError(f"release inventory exceeds depth bound {depth_limit}: {parent}")
            return
        for child in parent.iterdir():
            visited += 1
            if visited > count_limit:
                raise TraceAuditError(f"release inventory exceeds entry cap {count_limit}: {root}")
            if child.is_symlink():
                raise TraceAuditError(f"symlink is forbidden in release inventory: {child}")
            if child.is_dir():
                visit(child, depth + 1)
            elif child.is_file():
                found.add(child)
            else:
                raise TraceAuditError(f"release inventory entry is not a regular file/directory: {child}")

    if root.is_symlink():
        raise TraceAuditError(f"symlink is forbidden at release inventory root: {root}")
    if root.exists() and not root.is_dir():
        raise TraceAuditError(f"release inventory root must be a directory: {root}")
    if root.is_dir():
        visit(root, 0)
    return found


def yaml_mapping(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or not os.access(path, os.R_OK):
        raise TraceAuditError(f"{label} must be a readable regular non-symlink file: {path}")
    try:
        value = yaml.safe_load(read_bounded_bytes(path, label, MAX_METADATA_BYTES).decode("utf-8")) or {}
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise TraceAuditError(f"cannot parse {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise TraceAuditError(f"{label} root must be a mapping")
    return value


def exact_string_set(value: Any, label: str, pattern: re.Pattern[str] | None = None) -> set[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise TraceAuditError(f"{label} must be a list of non-empty strings")
    items = [item.strip() for item in value]
    if len(set(items)) != len(items):
        raise TraceAuditError(f"{label} contains duplicate values")
    if pattern is not None:
        invalid = [item for item in items if not pattern.fullmatch(item)]
        if invalid:
            raise TraceAuditError(f"{label} contains invalid values: {invalid}")
    return set(items)


def run_local_git(project: Path, *arguments: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(project), *arguments], check=False, capture_output=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).decode("utf-8", errors="replace").strip()
        raise TraceAuditError(f"local git {' '.join(arguments)} failed: {detail or result.returncode}")
    return result.stdout


def read_git_blob(project: Path, commit: str, relative_path: str, *, max_bytes: int) -> bytes:
    """Read an immutable blob only after validating its identity, type and size."""
    if not COMMIT_RE.fullmatch(commit):
        raise TraceAuditError("Git blob lookup requires a resolved full commit SHA")
    raw = Path(relative_path)
    if raw.is_absolute() or ".." in raw.parts or not relative_path:
        raise TraceAuditError("Git blob path must be project-relative")
    oid = run_local_git(project, "rev-parse", "--verify", f"{commit}:{relative_path}").decode().strip()
    if not COMMIT_RE.fullmatch(oid):
        raise TraceAuditError("Git blob lookup did not return a full object SHA")
    object_type = run_local_git(project, "cat-file", "-t", oid).decode().strip()
    if object_type != "blob":
        raise TraceAuditError(f"Git object is not a blob: {relative_path}")
    try:
        size = int(run_local_git(project, "cat-file", "-s", oid).decode().strip())
    except (ValueError, UnicodeError) as exc:
        raise TraceAuditError(f"invalid Git blob size: {relative_path}") from exc
    if size < 0 or size > max_bytes:
        raise TraceAuditError(f"Git blob exceeds {max_bytes} bytes: {relative_path}")
    with subprocess.Popen(
        ["git", "-C", str(project), "cat-file", "blob", oid],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    ) as process:
        assert process.stdout is not None
        data = process.stdout.read(max_bytes + 1)
        if len(data) > max_bytes:
            process.kill()
            process.wait()
            raise TraceAuditError(f"Git blob stream exceeds {max_bytes} bytes: {relative_path}")
        status = process.wait()
    if status != 0 or len(data) != size:
        raise TraceAuditError(f"Git blob read failed or size changed: {relative_path}")
    return data


def audit_release(
    project: Path,
    paper: Path,
    release_dir: Path,
    trace: PaperTrace,
    map_path: Path,
    findings: list[Finding],
    *,
    check_git: bool,
) -> str | None:
    paper_id = trace.paper_id
    release_name = release_dir.name
    manifest_path = release_dir / "Release_Manifest.yaml"
    relative_manifest = manifest_path.relative_to(project).as_posix()
    try:
        release = yaml_mapping(manifest_path, relative_manifest)
    except TraceAuditError as exc:
        add(findings, "BLOCK", "TRACE_RELEASE_SCHEMA", relative_manifest, str(exc), paper_id=paper_id)
        return
    if release.get("schema_version") != "bioflow.release.v1":
        add(findings, "BLOCK", "TRACE_RELEASE_SCHEMA", relative_manifest, f"unsupported schema_version: {release.get('schema_version')!r}", paper_id=paper_id)
        return
    status = release.get("status")
    if status not in {"Draft", "Frozen"}:
        add(findings, "BLOCK", "TRACE_RELEASE_SCHEMA", relative_manifest, f"invalid release status: {status!r}", paper_id=paper_id)
        return
    if status == "Draft":
        add(findings, "WARN", "TRACE_RELEASE_DRAFT", relative_manifest, "Draft release is not frozen or publication-ready", paper_id=paper_id)
        return "Draft"

    if trace.mapping_statuses != {"Frozen"}:
        add(findings, "BLOCK", "TRACE_RELEASE_CLOSURE", relative_manifest, f"Frozen release requires every map row to be Frozen; found={sorted(trace.mapping_statuses)}", paper_id=paper_id)
    if release.get("paper_id") != paper_id:
        add(findings, "BLOCK", "TRACE_RELEASE_SCHEMA", relative_manifest, f"paper_id must be {paper_id}", paper_id=paper_id)
    expected_release_id = f"{paper_id}-{release_name}"
    if release.get("release_id") != expected_release_id or not RELEASE_ID_RE.fullmatch(str(release.get("release_id") or "")):
        add(findings, "BLOCK", "TRACE_RELEASE_SCHEMA", relative_manifest, f"release_id must be {expected_release_id}", paper_id=paper_id)
    try:
        date.fromisoformat(str(release.get("release_date") or ""))
    except ValueError:
        add(findings, "BLOCK", "TRACE_RELEASE_SCHEMA", relative_manifest, f"invalid release_date: {release.get('release_date')!r}", paper_id=paper_id)

    selected = release.get("selected")
    if not isinstance(selected, dict):
        add(findings, "BLOCK", "TRACE_RELEASE_SCHEMA", relative_manifest, "selected must be a mapping", paper_id=paper_id)
        selected = {}
    try:
        selected_claims = exact_string_set(selected.get("claims"), "selected.claims", CLAIM_RE)
        selected_versions = exact_string_set(selected.get("versions"), "selected.versions", VERSION_REF_RE)
        selected_figures = exact_string_set(selected.get("figures"), "selected.figures", FIGURE_REF_RE)
    except TraceAuditError as exc:
        add(findings, "BLOCK", "TRACE_RELEASE_SCHEMA", relative_manifest, str(exc), paper_id=paper_id)
        selected_claims, selected_versions, selected_figures = set(), set(), set()
    for label, selected_set, expected in (
        ("claims", selected_claims, trace.claims),
        ("versions", selected_versions, trace.versions),
        ("figures", selected_figures, trace.figures),
    ):
        if selected_set != expected:
            add(findings, "BLOCK", "TRACE_RELEASE_CLOSURE", relative_manifest, f"selected.{label} must equal trace closure; missing={sorted(expected-selected_set)} extra={sorted(selected_set-expected)}", paper_id=paper_id)

    authorities = release.get("authorities")
    if not isinstance(authorities, dict):
        add(findings, "BLOCK", "TRACE_RELEASE_SCHEMA", relative_manifest, "authorities must be a mapping", paper_id=paper_id)
        authorities = {}
    authority_specs = {
        "result_manifest": (project / "config" / "result_manifest.yaml", "config"),
        "claim_evidence_map": (map_path, "manuscripts"),
    }
    for key, (expected, root_name) in authority_specs.items():
        try:
            resolved, _ = safe_relative_path(project, str(authorities.get(key) or ""), f"authorities.{key}", required_root=root_name)
        except TraceAuditError as exc:
            add(findings, "BLOCK", "TRACE_RELEASE_AUTHORITY", relative_manifest, str(exc), paper_id=paper_id)
            continue
        if resolved != expected or not resolved.is_file():
            add(findings, "BLOCK", "TRACE_RELEASE_AUTHORITY", relative_manifest, f"authorities.{key} does not resolve to expected file", paper_id=paper_id)
    unsafe_acceptance_read = False
    for key, root_name in (("manuscript_source", "manuscripts"), ("acceptance_path", "docs"), ("rerun_entrypoint", "scripts")):
        try:
            resolved, _ = safe_relative_path(project, str(authorities.get(key) or ""), f"authorities.{key}", required_root=root_name)
        except TraceAuditError as exc:
            add(findings, "BLOCK", "TRACE_RELEASE_AUTHORITY", relative_manifest, str(exc), paper_id=paper_id)
            continue
        if not resolved.is_file():
            add(findings, "BLOCK", "TRACE_RELEASE_AUTHORITY", relative_manifest, f"authorities.{key} is missing or not a file", paper_id=paper_id)
        if key == "acceptance_path" and resolved.is_file():
            try:
                acceptance_text = read_bounded_bytes(resolved, "acceptance metadata", MAX_METADATA_BYTES).decode("utf-8")
            except (TraceAuditError, OSError, UnicodeError) as exc:
                acceptance_text = ""
                unsafe_acceptance_read = True
                add(findings, "BLOCK", "TRACE_RELEASE_AUTHORITY", relative_manifest, str(exc), paper_id=paper_id)
            if re.search(r"(?m)^Acceptance_Status:\s*(Accepted|Validated|Passed)\s*$", acceptance_text) is None:
                add(findings, "BLOCK", "TRACE_RELEASE_AUTHORITY", relative_manifest, "acceptance_path lacks an Accepted/Validated/Passed marker", paper_id=paper_id)
        if key == "manuscript_source" and resolved not in trace.manuscripts:
            add(findings, "BLOCK", "TRACE_RELEASE_AUTHORITY", relative_manifest, "manuscript_source is not referenced by the Claim Evidence Map", paper_id=paper_id)

    checklist = release.get("checklist")
    if not isinstance(checklist, dict) or set(checklist) != CHECKLIST_KEYS:
        add(findings, "BLOCK", "TRACE_RELEASE_CHECKLIST", relative_manifest, f"checklist keys must be exactly {sorted(CHECKLIST_KEYS)}", paper_id=paper_id)
    elif any(value is not True for value in checklist.values()):
        false_keys = sorted(key for key, value in checklist.items() if value is not True)
        add(findings, "BLOCK", "TRACE_RELEASE_CHECKLIST", relative_manifest, f"Frozen checklist values must all be true: {false_keys}", paper_id=paper_id)
    # The structure prerequisite also reads the layout's canonical acceptance
    # record, which may differ from authorities.acceptance_path. Check that
    # dependency before invoking either prerequisite; a BLOCK is not permission
    # to continue with an already-known unsafe content read.
    try:
        layout = safe_layout(project)
        acceptance_relative = layout_contract.control_relative(layout, "acceptance")
        canonical_acceptance, _ = safe_relative_path(project, acceptance_relative, "prerequisite acceptance")
        if canonical_acceptance.exists():
            if not canonical_acceptance.is_file() or not os.access(canonical_acceptance, os.R_OK):
                raise TraceAuditError("prerequisite acceptance must be a readable regular file")
            if canonical_acceptance.stat().st_size > MAX_METADATA_BYTES:
                raise TraceAuditError(f"prerequisite acceptance exceeds {MAX_METADATA_BYTES} bytes")
    except (TraceAuditError, OSError, layout_contract.LayoutError) as exc:
        unsafe_acceptance_read = True
        add(findings, "BLOCK", "TRACE_RELEASE_PREREQUISITE", relative_manifest, str(exc), paper_id=paper_id)
    if unsafe_acceptance_read:
        add(findings, "BLOCK", "TRACE_RELEASE_PREREQUISITE", relative_manifest, "prerequisite content checks not run because acceptance metadata is unsafe", paper_id=paper_id)
        return "Frozen"

    for audit_name, audit_call in (
        ("structure", lambda: structure_audit.audit(project, 3)),
        ("records", lambda: records_audit.audit(project)),
    ):
        try:
            prerequisite_findings = audit_call()
        except Exception as exc:
            add(findings, "BLOCK", "TRACE_RELEASE_PREREQUISITE", relative_manifest, f"{audit_name} audit failed: {exc}", paper_id=paper_id)
            continue
        problems = [item for item in prerequisite_findings if item.Status in {"WARN", "BLOCK"}]
        if problems:
            rules = sorted({item.Rule_ID for item in problems})
            add(findings, "BLOCK", "TRACE_RELEASE_PREREQUISITE", relative_manifest, f"Frozen release requires {audit_name} audit without WARN/BLOCK; rules={rules}", paper_id=paper_id)

    limitations = release.get("known_limitations")
    if not isinstance(limitations, list) or any(not isinstance(item, str) or not item.strip() for item in limitations):
        add(findings, "BLOCK", "TRACE_RELEASE_LIMITATIONS", relative_manifest, "known_limitations must be a list of non-empty strings or an empty list", paper_id=paper_id)
    elif any(re.search(r"(?i)UNKNOWN|replace_me|TBD", item) for item in limitations):
        add(findings, "BLOCK", "TRACE_RELEASE_LIMITATIONS", relative_manifest, "known_limitations contains a placeholder", paper_id=paper_id)

    artifacts = release.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) > MAX_RELEASE_ARTIFACTS:
        add(findings, "BLOCK", "TRACE_RELEASE_SCHEMA", relative_manifest, f"artifacts must be a list with <= {MAX_RELEASE_ARTIFACTS} rows", paper_id=paper_id)
        artifacts = []
    expected_roles: dict[Path, str] = {}
    expected_roles.update({path: "Manuscript" for path in trace.manuscripts})
    expected_roles.update({path: "Figure" for path in trace.figure_pdfs})
    expected_roles.update({path: "Source_Table" for path in trace.source_tables})
    expected_roles.update({path: "Supplement" for path in trace.supplements})
    seen_ids: set[str] = set()
    seen_canonical: set[Path] = set()
    seen_release: set[Path] = set()
    git_eligible_release: set[Path] = set()
    files_root = release_dir / "files"
    for index, artifact in enumerate(artifacts, 1):
        if not isinstance(artifact, dict):
            add(findings, "BLOCK", "TRACE_RELEASE_SCHEMA", relative_manifest, f"artifact {index} must be a mapping", paper_id=paper_id)
            continue
        artifact_id = str(artifact.get("artifact_id") or "")
        role = str(artifact.get("role") or "")
        if not ARTIFACT_ID_RE.fullmatch(artifact_id) or artifact_id in seen_ids:
            add(findings, "BLOCK", "TRACE_RELEASE_SCHEMA", relative_manifest, f"invalid/duplicate artifact_id: {artifact_id!r}", paper_id=paper_id)
        seen_ids.add(artifact_id)
        if role not in ARTIFACT_ROLES:
            add(findings, "BLOCK", "TRACE_RELEASE_SCHEMA", relative_manifest, f"{artifact_id}: invalid role {role!r}", paper_id=paper_id)
        try:
            canonical, canonical_relative = safe_relative_path(project, str(artifact.get("canonical_path") or ""), f"{artifact_id}.canonical_path")
            release_path, release_relative = safe_relative_path(project, str(artifact.get("release_path") or ""), f"{artifact_id}.release_path", required_root="manuscripts")
        except TraceAuditError as exc:
            add(findings, "BLOCK", "TRACE_UNSAFE_PATH", relative_manifest, str(exc), paper_id=paper_id)
            continue
        if release_path.parent != files_root and files_root not in release_path.parents:
            add(findings, "BLOCK", "TRACE_RELEASE_PATH", release_relative, f"{artifact_id}: release_path must stay under {files_root.relative_to(project)}", paper_id=paper_id)
        if canonical in seen_canonical or release_path in seen_release:
            add(findings, "BLOCK", "TRACE_RELEASE_SCHEMA", relative_manifest, f"{artifact_id}: duplicate canonical_path or release_path", paper_id=paper_id)
        seen_canonical.add(canonical); seen_release.add(release_path)
        expected_role = expected_roles.get(canonical)
        canonical_hashable = False
        if expected_role is None:
            add(findings, "BLOCK", "TRACE_RELEASE_CLOSURE", canonical_relative, f"{artifact_id}: canonical_path is outside required trace closure", paper_id=paper_id)
        elif not canonical.is_file() or not os.access(canonical, os.R_OK):
            add(findings, "BLOCK", "TRACE_RELEASE_PATH", canonical_relative, f"{artifact_id}: canonical source is missing or unreadable", paper_id=paper_id)
        elif canonical.stat().st_size > MAX_RELEASE_ARTIFACT_BYTES:
            add(findings, "BLOCK", "TRACE_LIMIT", canonical_relative, f"{artifact_id}: canonical source exceeds {MAX_RELEASE_ARTIFACT_BYTES} bytes", paper_id=paper_id)
        elif role != expected_role:
            add(findings, "BLOCK", "TRACE_RELEASE_CLOSURE", canonical_relative, f"{artifact_id}: role must be {expected_role}, not {role}", paper_id=paper_id)
        else:
            canonical_hashable = True
        if release_path.is_symlink() or not release_path.is_file() or not os.access(release_path, os.R_OK):
            add(findings, "BLOCK", "TRACE_RELEASE_PATH", release_relative, f"{artifact_id}: frozen release file is missing/unreadable/symlink", paper_id=paper_id)
            continue
        if release_path.stat().st_size > MAX_RELEASE_ARTIFACT_BYTES:
            add(findings, "BLOCK", "TRACE_LIMIT", release_relative, f"{artifact_id}: artifact exceeds {MAX_RELEASE_ARTIFACT_BYTES} bytes", paper_id=paper_id)
            continue
        git_eligible_release.add(release_path)
        expected_hash = str(artifact.get("sha256") or "")
        if not SHA256_RE.fullmatch(expected_hash) or sha256_file(release_path) != expected_hash:
            add(findings, "BLOCK", "TRACE_RELEASE_HASH", release_relative, f"{artifact_id}: SHA256 is invalid or does not match release file", paper_id=paper_id)
        if canonical_hashable and sha256_file(canonical) != expected_hash:
            add(findings, "WARN", "TRACE_RELEASE_SOURCE_CHANGED", canonical_relative, f"{artifact_id}: canonical source differs from frozen release copy", paper_id=paper_id)
    missing_artifacts = set(expected_roles) - seen_canonical
    extra_artifacts = seen_canonical - set(expected_roles)
    if missing_artifacts or extra_artifacts:
        render = lambda values: sorted(path.relative_to(project).as_posix() for path in values)
        add(findings, "BLOCK", "TRACE_RELEASE_CLOSURE", relative_manifest, f"artifact closure mismatch; missing={render(missing_artifacts)} extra={render(extra_artifacts)}", paper_id=paper_id)

    try:
        actual_release_files = bounded_files(files_root)
    except TraceAuditError as exc:
        add(findings, "BLOCK", "TRACE_UNSAFE_PATH", relative_manifest, str(exc), paper_id=paper_id)
    else:
        if actual_release_files != seen_release:
            missing = sorted(path.relative_to(project).as_posix() for path in seen_release - actual_release_files)
            extra = sorted(path.relative_to(project).as_posix() for path in actual_release_files - seen_release)
            add(findings, "BLOCK", "TRACE_RELEASE_CLOSURE", relative_manifest, f"frozen files inventory mismatch; missing={missing} extra={extra}", paper_id=paper_id)

    git_block = release.get("git")
    if not isinstance(git_block, dict):
        add(findings, "BLOCK", "TRACE_RELEASE_GIT", relative_manifest, "git must be a mapping", paper_id=paper_id)
        return "Frozen"
    source_commit = str(git_block.get("source_commit_sha") or "")
    release_tag = str(git_block.get("release_tag") or "")
    invalid_tag = (
        not TAG_RE.fullmatch(release_tag) or ".." in release_tag
        or "//" in release_tag or release_tag.endswith((".", "/"))
        or any(part.startswith(".") or part.endswith(".lock") for part in release_tag.split("/"))
    )
    if not COMMIT_RE.fullmatch(source_commit) or invalid_tag:
        add(findings, "BLOCK", "TRACE_RELEASE_GIT", relative_manifest, "Frozen git block requires a 40-char lowercase source_commit_sha and a safe release_tag", paper_id=paper_id)
    elif check_git:
        try:
            run_local_git(project, "cat-file", "-e", f"{source_commit}^{{commit}}")
            tag_ref = f"refs/tags/{release_tag}"
            run_local_git(project, "check-ref-format", tag_ref)
            tagged_commit = run_local_git(project, "rev-parse", "--verify", f"{tag_ref}^{{commit}}").decode().strip()
            tagged_manifest = read_git_blob(project, tagged_commit, relative_manifest, max_bytes=MAX_METADATA_BYTES)
            current_manifest = read_bounded_bytes(manifest_path, "release manifest", MAX_METADATA_BYTES)
        except TraceAuditError as exc:
            add(findings, "BLOCK", "TRACE_RELEASE_GIT", relative_manifest, str(exc), paper_id=paper_id)
        else:
            if not COMMIT_RE.fullmatch(tagged_commit):
                add(findings, "BLOCK", "TRACE_RELEASE_GIT", relative_manifest, f"release tag did not resolve to a full commit: {tagged_commit}", paper_id=paper_id)
            if tagged_manifest != current_manifest:
                add(findings, "BLOCK", "TRACE_RELEASE_GIT", relative_manifest, "release tag does not contain this exact Release Manifest content", paper_id=paper_id)
            for release_path in sorted(git_eligible_release):
                release_relative = release_path.relative_to(project).as_posix()
                try:
                    tagged_artifact = read_git_blob(project, tagged_commit, release_relative, max_bytes=MAX_RELEASE_ARTIFACT_BYTES)
                    current_artifact = read_bounded_bytes(release_path, "frozen artifact", MAX_RELEASE_ARTIFACT_BYTES)
                except TraceAuditError as exc:
                    add(findings, "BLOCK", "TRACE_RELEASE_GIT", release_relative, str(exc), paper_id=paper_id)
                    continue
                if tagged_artifact != current_artifact:
                    add(findings, "BLOCK", "TRACE_RELEASE_GIT", release_relative, "release tag artifact differs from current frozen release file", paper_id=paper_id)
    else:
        add(findings, "INFO", "TRACE_RELEASE_GIT_UNCHECKED", relative_manifest, "local source-commit/tag verification was not requested", paper_id=paper_id)
    return "Frozen"


def audit_releases(
    project: Path,
    paper: Path,
    trace: PaperTrace,
    map_path: Path,
    findings: list[Finding],
    *,
    selected_release: str | None,
    check_git: bool,
) -> None:
    root = paper / "releases"
    if not root.exists():
        if "Frozen" in trace.mapping_statuses or selected_release:
            add(findings, "BLOCK", "TRACE_RELEASE_MISSING", root.relative_to(project).as_posix(), "Frozen mapping or selected release has no releases directory", paper_id=trace.paper_id)
        return
    if root.is_symlink() or not root.is_dir():
        add(findings, "BLOCK", "TRACE_UNSAFE_PATH", root.relative_to(project).as_posix(), "releases must be a regular directory", paper_id=trace.paper_id)
        return
    releases: list[Path] = []
    for child in sorted(root.iterdir(), key=lambda item: (item.name.casefold(), item.name)):
        if child.is_symlink() or not child.is_dir() or not RELEASE_RE.fullmatch(child.name):
            add(findings, "BLOCK", "TRACE_RELEASE_PATH", child.relative_to(project).as_posix(), "release entry must be a regular RNN directory", paper_id=trace.paper_id)
            continue
        releases.append(child)
    if selected_release:
        matches = [release for release in releases if release.name == selected_release]
        if not matches:
            raise TraceAuditError(f"selected release does not exist in {paper.name}: {selected_release}")
        releases = matches
    release_statuses: list[str] = []
    for release in releases:
        observed = audit_release(project, paper, release, trace, map_path, findings, check_git=check_git)
        if observed:
            release_statuses.append(observed)
    if "Frozen" in trace.mapping_statuses and "Frozen" not in release_statuses:
        add(findings, "BLOCK", "TRACE_RELEASE_MISSING", root.relative_to(project).as_posix(), "Frozen mapping has no valid Frozen release manifest", paper_id=trace.paper_id)


def requires_complete_map(paper: Path, selected_release: str | None) -> bool:
    """Apply the same release requirement to absent and header-only maps."""
    if selected_release:
        return True
    releases_root = paper / "releases"
    if releases_root.is_symlink() or (releases_root.exists() and not releases_root.is_dir()):
        raise TraceAuditError(f"releases root is unsafe: {releases_root}")
    if not releases_root.exists():
        return False
    for count, directory in enumerate(releases_root.iterdir(), 1):
        if count > MAX_RELEASE_ARTIFACTS:
            raise TraceAuditError("release directory inventory exceeds bounded cap")
        if directory.is_symlink() or not directory.is_dir() or not RELEASE_RE.fullmatch(directory.name):
            raise TraceAuditError(f"release entry must be a regular RNN directory: {directory}")
        candidate = directory / "Release_Manifest.yaml"
        try:
            if yaml_mapping(candidate, candidate.name).get("status") == "Frozen":
                return True
        except TraceAuditError:
            return True
    return False


def audit_paper(
    project: Path,
    paper: Path,
    modules: dict[str, Path],
    manifest: dict[str, Any],
    manifest_path: Path,
    claims: dict[str, dict[str, Any]],
    rules: list[dict[str, str]],
    findings: list[Finding],
    *,
    selected_release: str | None,
    check_git: bool,
) -> None:
    match = PAPER_RE.fullmatch(paper.name)
    assert match is not None
    paper_id = match.group(1)
    map_path = paper / "Claim_Evidence_Map.tsv"
    relative_map = map_path.relative_to(project).as_posix()
    if map_path.is_symlink() or not map_path.exists():
        status = "BLOCK" if requires_complete_map(paper, selected_release) else "WARN"
        add(findings, status, "TRACE_MAP_MISSING", relative_map, "paper has no Claim_Evidence_Map.tsv", paper_id=paper_id)
        return
    try:
        rows = read_exact_tsv(map_path, MAP_COLUMNS, relative_map)
    except TraceAuditError as exc:
        add(findings, "BLOCK", "TRACE_MAP_SCHEMA", relative_map, str(exc), paper_id=paper_id)
        return
    if not rows:
        status = "BLOCK" if requires_complete_map(paper, selected_release) else "WARN"
        add(findings, status, "TRACE_MAP_EMPTY", relative_map, "Claim Evidence Map has no rows", paper_id=paper_id)
        return

    trace = PaperTrace(
        paper_id=paper_id, mapping_statuses=set(), claims=set(), versions=set(),
        figures=set(), manuscripts=set(), source_tables=set(), figure_pdfs=set(),
        supplements=bounded_files(paper / "supplement"),
    )
    seen_claims: set[str] = set()
    mapped_claims: set[str] = set()
    manuscript_expected: dict[Path, set[str]] = defaultdict(set)
    manuscript_status: dict[tuple[Path, str], str] = {}
    # Per-paper only: reuse parsed data/error text, never claim-specific findings.
    version_indexes: dict[Path, dict[str, dict[str, str]] | str] = {}
    figure_indexes: dict[Path, dict[str, dict[str, str]] | str] = {}
    source_table_results: dict[Path, str | None] = {}

    for row_number, row in enumerate(rows, 2):
        claim_id = row["Claim_ID"]
        mapping_status = row["Mapping_Status"]
        row_label = f"{relative_map}:{row_number}"
        if row["Schema_Version"] != "claim_evidence.v1":
            add(findings, "BLOCK", "TRACE_MAP_SCHEMA", row_label, f"unsupported Schema_Version: {row['Schema_Version']!r}", paper_id=paper_id, claim_id=claim_id or "NA")
        if row["Paper_ID"] != paper_id:
            add(findings, "BLOCK", "TRACE_MAP_SCHEMA", row_label, f"Paper_ID must match directory {paper_id}", paper_id=paper_id, claim_id=claim_id or "NA")
        if not CLAIM_RE.fullmatch(claim_id):
            add(findings, "BLOCK", "TRACE_MAP_SCHEMA", row_label, f"invalid Claim_ID: {claim_id!r}", paper_id=paper_id)
            continue
        if claim_id in seen_claims:
            add(findings, "BLOCK", "TRACE_MAP_SCHEMA", row_label, f"duplicate Claim_ID: {claim_id}", paper_id=paper_id, claim_id=claim_id)
            continue
        seen_claims.add(claim_id)
        mapped_claims.add(claim_id)
        if mapping_status not in MAPPING_STATUS:
            add(findings, "BLOCK", "TRACE_MAP_SCHEMA", row_label, f"invalid Mapping_Status: {mapping_status!r}", paper_id=paper_id, claim_id=claim_id)
            continue
        trace.mapping_statuses.add(mapping_status)
        trace.claims.add(claim_id)
        if mapping_status == "Draft":
            add(findings, "WARN", "TRACE_MAP_DRAFT", row_label, "Draft mapping is not ready for formal review", paper_id=paper_id, claim_id=claim_id)

        try:
            manuscript_path, manuscript_relative = safe_relative_path(project, row["Manuscript_Path"], "Manuscript_Path", required_root="manuscripts")
        except TraceAuditError as exc:
            add(findings, "BLOCK", "TRACE_UNSAFE_PATH", row_label, str(exc), paper_id=paper_id, claim_id=claim_id)
            manuscript_path = None
        else:
            try:
                manuscript_path.relative_to(paper)
            except ValueError:
                add(findings, "BLOCK", "TRACE_UNSAFE_PATH", manuscript_relative, "Manuscript_Path must stay inside current paper directory", paper_id=paper_id, claim_id=claim_id)
            else:
                manuscript_expected[manuscript_path].add(claim_id)
                manuscript_status[(manuscript_path, claim_id)] = mapping_status
                trace.manuscripts.add(manuscript_path)
                if not manuscript_path.is_file():
                    add(findings, strictness(mapping_status), "TRACE_MARKDOWN_MISSING", manuscript_relative, "mapped manuscript file is missing", paper_id=paper_id, claim_id=claim_id)

        claim = claims.get(claim_id)
        claim_evidence: set[Path] = set()
        if claim is None:
            add(findings, "BLOCK", "TRACE_CLAIM_MISSING", row_label, "Claim_ID is absent from config/result_manifest.yaml", paper_id=paper_id, claim_id=claim_id)
        else:
            status, claim_findings = claim_contract_status(manifest, claim, rules, manifest_path.parent)
            for value in claim.get("evidence_paths", []) if isinstance(claim.get("evidence_paths"), list) else []:
                if isinstance(value, str) and value.strip():
                    raw = Path(value).expanduser()
                    claim_evidence.add((raw if raw.is_absolute() else manifest_path.parent / raw).resolve(strict=False))
            if mapping_status == "Draft" and status != "PASS":
                add(findings, "WARN", "TRACE_CLAIM_STATUS", row_label, f"Draft claim contract status is {status}", paper_id=paper_id, claim_id=claim_id)
            elif mapping_status in {"Reviewed", "Frozen"} and status != "PASS":
                rules_text = ",".join(sorted({rule for severity, rule, _ in claim_findings if severity in {"BLOCK", "UNCERTAIN", "WARN"}})) or "NA"
                add(findings, "BLOCK", "TRACE_CLAIM_STATUS", row_label, f"formal mapping requires claim-contract PASS; status={status} rules={rules_text}", paper_id=paper_id, claim_id=claim_id)

        try:
            figure_refs = parse_semicolon(row["Figure_Refs"], "Figure_Refs", FIGURE_REF_RE)
            source_values = parse_semicolon(row["Source_Table_Paths"], "Source_Table_Paths")
            version_refs = parse_semicolon(row["Version_Refs"], "Version_Refs", VERSION_REF_RE)
            trace.figures.update(figure_refs)
            trace.versions.update(version_refs)
        except TraceAuditError as exc:
            add(findings, "BLOCK", "TRACE_MAP_SCHEMA", row_label, str(exc), paper_id=paper_id, claim_id=claim_id)
            continue

        resolved_versions: list[tuple[str, dict[str, str], Path]] = []
        if not version_refs:
            add(findings, strictness(mapping_status), "TRACE_VERSION_MISSING", row_label, "mapping has no Version_Refs", paper_id=paper_id, claim_id=claim_id)
        for ref in version_refs:
            ref_match = VERSION_REF_RE.fullmatch(ref)
            assert ref_match is not None
            analysis_key, version_id = ref_match.groups()
            module = modules.get(analysis_key)
            if module is None:
                add(findings, strictness(mapping_status), "TRACE_VERSION_MISSING", row_label, f"unknown Analysis_Key in version ref: {ref}", paper_id=paper_id, claim_id=claim_id)
                continue
            try:
                # Path safety is rechecked even when parsed content is reused.
                safe_relative_path(project, (module / "Version_Index.tsv").relative_to(project).as_posix(), "version index", required_root="results")
                if module not in version_indexes:
                    try:
                        version_indexes[module] = load_version_rows(project, module)
                    except TraceAuditError as error:
                        version_indexes[module] = str(error)
                cached_versions = version_indexes[module]
                if isinstance(cached_versions, str):
                    raise TraceAuditError(cached_versions)
                version_rows = cached_versions
            except TraceAuditError as exc:
                add(findings, strictness(mapping_status), "TRACE_VERSION_INDEX", module.relative_to(project).as_posix(), str(exc), paper_id=paper_id, claim_id=claim_id)
                continue
            version = version_rows.get(version_id)
            if version is None:
                add(findings, strictness(mapping_status), "TRACE_VERSION_MISSING", module.relative_to(project).as_posix(), f"Version_ID not found: {ref}", paper_id=paper_id, claim_id=claim_id)
                continue
            try:
                result_path, result_relative = safe_relative_path(project, version["Result_Path"], f"{ref}.Result_Path", required_root="results")
            except TraceAuditError as exc:
                add(findings, "BLOCK", "TRACE_UNSAFE_PATH", row_label, str(exc), paper_id=paper_id, claim_id=claim_id)
                continue
            expected_version_path = module / "versions" / version_id
            if result_path != expected_version_path:
                add(findings, strictness(mapping_status), "TRACE_VERSION_RESULT", result_relative, f"{ref}: Result_Path must equal {expected_version_path.relative_to(project)}", paper_id=paper_id, claim_id=claim_id)
                continue
            if not result_path.is_dir():
                add(findings, strictness(mapping_status), "TRACE_VERSION_RESULT", result_relative, f"version result directory is missing: {ref}", paper_id=paper_id, claim_id=claim_id)
            if mapping_status in {"Reviewed", "Frozen"} and version["Status"] not in {"Validated", "Frozen"}:
                add(findings, "BLOCK", "TRACE_VERSION_STATUS", row_label, f"formal mapping uses non-validated version {ref}: {version['Status']}", paper_id=paper_id, claim_id=claim_id)
            if mapping_status == "Frozen" and version["Selected"] != "Yes":
                add(findings, "BLOCK", "TRACE_VERSION_STATUS", row_label, f"Frozen mapping uses unselected version {ref}", paper_id=paper_id, claim_id=claim_id)
            if mapping_status == "Frozen" and version["Status"] != "Frozen":
                add(findings, "WARN", "TRACE_VERSION_STATUS", row_label, f"Frozen mapping version is only {version['Status']}: {ref}", paper_id=paper_id, claim_id=claim_id)
            resolved_versions.append((analysis_key, version, result_path))

        figure_packages: list[Path] = []
        resolved_figures: list[tuple[str, dict[str, str], Path]] = []
        for ref in figure_refs:
            ref_match = FIGURE_REF_RE.fullmatch(ref)
            assert ref_match is not None
            analysis_key, figure_id = ref_match.groups()
            module = modules.get(analysis_key)
            if module is None:
                add(findings, strictness(mapping_status), "TRACE_FIGURE_MISSING", row_label, f"unknown Analysis_Key in figure ref: {ref}", paper_id=paper_id, claim_id=claim_id)
                continue
            try:
                safe_relative_path(project, (module / "figures/Figure_Index.tsv").relative_to(project).as_posix(), "figure index", required_root="results")
                if module not in figure_indexes:
                    try:
                        figure_indexes[module] = load_figure_rows(project, module)
                    except TraceAuditError as error:
                        figure_indexes[module] = str(error)
                cached_figures = figure_indexes[module]
                if isinstance(cached_figures, str):
                    raise TraceAuditError(cached_figures)
                figure_rows = cached_figures
            except TraceAuditError as exc:
                add(findings, strictness(mapping_status), "TRACE_FIGURE_INDEX", module.relative_to(project).as_posix(), str(exc), paper_id=paper_id, claim_id=claim_id)
                continue
            figure = figure_rows.get(figure_id)
            if figure is None:
                add(findings, strictness(mapping_status), "TRACE_FIGURE_MISSING", module.relative_to(project).as_posix(), f"Figure_ID not found: {ref}", paper_id=paper_id, claim_id=claim_id)
                continue
            directory = figure["Figure_Directory"]
            if not structure_audit.FIGURE_RE.fullmatch(directory) or not directory.startswith(figure_id + "_"):
                add(findings, "BLOCK", "TRACE_FIGURE_PACKAGE", row_label, f"{ref}: Figure_Directory must be a matching F-ID basename", paper_id=paper_id, claim_id=claim_id)
                continue
            try:
                package, _ = safe_relative_path(project, (module / "figures" / directory).relative_to(project).as_posix(), f"{ref}.Figure_Directory", required_root="results")
            except TraceAuditError as exc:
                add(findings, "BLOCK", "TRACE_FIGURE_PACKAGE", row_label, str(exc), paper_id=paper_id, claim_id=claim_id)
                continue
            if package.is_symlink() or not package.is_dir():
                add(findings, strictness(mapping_status), "TRACE_FIGURE_PACKAGE", package.relative_to(project).as_posix(), f"figure package is missing or unsafe: {ref}", paper_id=paper_id, claim_id=claim_id)
                continue
            if mapping_status in {"Reviewed", "Frozen"} and figure["Status"] not in {"Manuscript_ready", "Frozen"}:
                add(findings, "BLOCK", "TRACE_FIGURE_STATUS", row_label, f"formal mapping uses non-ready figure {ref}: {figure['Status']}", paper_id=paper_id, claim_id=claim_id)
            if mapping_status == "Frozen" and figure["Status"] != "Frozen":
                add(findings, "BLOCK", "TRACE_FIGURE_STATUS", row_label, f"Frozen mapping requires Frozen figure status: {ref}", paper_id=paper_id, claim_id=claim_id)
            if mapping_status in {"Reviewed", "Frozen"} and figure["Manuscript_Target"] in {"", "NA"}:
                add(findings, "BLOCK", "TRACE_FIGURE_TARGET", row_label, f"formal mapping figure has no Manuscript_Target: {ref}", paper_id=paper_id, claim_id=claim_id)
            try:
                source_result, source_relative = safe_relative_path(project, figure["Source_Result"], f"{ref}.Source_Result", required_root="results")
                plot_script, plot_relative = safe_relative_path(project, figure["Plot_Script"], f"{ref}.Plot_Script", required_root="scripts")
            except TraceAuditError as exc:
                add(findings, "BLOCK", "TRACE_UNSAFE_PATH", row_label, str(exc), paper_id=paper_id, claim_id=claim_id)
                continue
            if not source_result.is_file():
                add(findings, strictness(mapping_status), "TRACE_FIGURE_SOURCE", source_relative, f"figure Source_Result is missing: {ref}", paper_id=paper_id, claim_id=claim_id)
            if not plot_script.is_file():
                add(findings, strictness(mapping_status), "TRACE_FIGURE_SCRIPT", plot_relative, f"figure Plot_Script is missing: {ref}", paper_id=paper_id, claim_id=claim_id)
            linked_to_version = any(source_result == result_path or result_path in source_result.parents for _, _, result_path in resolved_versions)
            if source_result not in claim_evidence and not linked_to_version:
                add(findings, strictness(mapping_status), "TRACE_FIGURE_CLAIM_LINK", source_relative, f"Figure Source_Result is neither claim evidence nor below a mapped version: {ref}", paper_id=paper_id, claim_id=claim_id)
            figure_packages.append(package)
            resolved_figures.append((analysis_key, figure, package))
            trace.figure_pdfs.add(package / f"{figure['Figure_Directory']}.pdf")

        if figure_refs and not source_values:
            add(findings, strictness(mapping_status), "TRACE_SOURCE_TABLE_MISSING", row_label, "mapped figure has no Source_Table_Paths", paper_id=paper_id, claim_id=claim_id)
        if source_values and not figure_refs:
            add(findings, strictness(mapping_status), "TRACE_SOURCE_TABLE_ORPHAN", row_label, "Source_Table_Paths require at least one Figure_Ref", paper_id=paper_id, claim_id=claim_id)
        covered_packages: set[Path] = set()
        for value in source_values:
            try:
                source_path, source_relative = safe_relative_path(project, value, "Source_Table_Paths", required_root="results")
            except TraceAuditError as exc:
                add(findings, "BLOCK", "TRACE_UNSAFE_PATH", row_label, str(exc), paper_id=paper_id, claim_id=claim_id)
                continue
            owners = {package for package in figure_packages if package / "source-data" == source_path.parent}
            if not owners:
                add(findings, strictness(mapping_status), "TRACE_SOURCE_TABLE_PACKAGE", source_relative, "source table is not inside a referenced figure package/source-data", paper_id=paper_id, claim_id=claim_id)
                continue
            if source_path not in source_table_results:
                source_table_results[source_path] = validate_source_table(source_path)
            issue = source_table_results[source_path]
            if issue:
                add(findings, strictness(mapping_status), "TRACE_SOURCE_TABLE_FORMAT", source_relative, issue, paper_id=paper_id, claim_id=claim_id)
                continue
            trace.source_tables.add(source_path)
            covered_packages.update(owners)
        for package in set(figure_packages) - covered_packages:
            add(findings, strictness(mapping_status), "TRACE_SOURCE_TABLE_MISSING", package.relative_to(project).as_posix(), "each mapped figure requires an explicit valid source table", paper_id=paper_id, claim_id=claim_id)

    # Check every manuscript anchor in the paper, not only files referenced by map rows.
    anchor_locations: dict[str, list[Path]] = defaultdict(list)
    markdown_files = bounded_markdown_files(paper)
    for path in markdown_files:
        try:
            text = read_markdown(path)
        except (TraceAuditError, UnicodeError) as exc:
            add(findings, "BLOCK", "TRACE_MARKDOWN_UNSAFE", path.relative_to(project).as_posix(), str(exc), paper_id=paper_id)
            continue
        for anchor in ANCHOR_RE.findall(text):
            anchor_locations[anchor].append(path)
    for claim_id, locations in sorted(anchor_locations.items()):
        if claim_id not in mapped_claims:
            rendered = ", ".join(path.relative_to(project).as_posix() for path in locations)
            add(findings, "BLOCK", "TRACE_MARKDOWN_ORPHAN", rendered, "manuscript anchor has no map row", paper_id=paper_id, claim_id=claim_id)
        if len(locations) > 1:
            rendered = ", ".join(path.relative_to(project).as_posix() for path in locations)
            add(findings, "BLOCK", "TRACE_MARKDOWN_DUPLICATE", rendered, "Claim_ID has multiple primary anchors", paper_id=paper_id, claim_id=claim_id)
    for manuscript_path, expected in manuscript_expected.items():
        for claim_id in sorted(expected):
            count = sum(1 for path in anchor_locations.get(claim_id, []) if path == manuscript_path)
            mapping_status = manuscript_status[(manuscript_path, claim_id)]
            if count == 0:
                add(findings, strictness(mapping_status), "TRACE_MARKDOWN_MISSING", manuscript_path.relative_to(project).as_posix(), "mapped claim anchor is missing from declared manuscript", paper_id=paper_id, claim_id=claim_id)
            elif count > 1:
                add(findings, "BLOCK", "TRACE_MARKDOWN_DUPLICATE", manuscript_path.relative_to(project).as_posix(), "mapped claim anchor appears more than once in declared manuscript", paper_id=paper_id, claim_id=claim_id)

    for claim_id, claim in sorted(claims.items()):
        if claim_id not in mapped_claims and claim.get("status") == "supported":
            add(findings, "INFO", "TRACE_CLAIM_UNUSED", relative_map, "supported result claim is not used by this paper", paper_id=paper_id, claim_id=claim_id)
    audit_releases(
        project, paper, trace, map_path, findings,
        selected_release=selected_release, check_git=check_git,
    )


def audit(
    project: Path, selected_paper: str | None,
    selected_release: str | None = None, check_git: bool = False,
) -> list[Finding]:
    layout = safe_layout(project)
    if not layout.is_v2:
        return [Finding("PASS", "TRACE_LEGACY", "NA", "NA", ".", "legacy project; publication traceability is not enforced")]
    findings: list[Finding] = []
    papers = paper_directories(project, selected_paper, findings)
    if not papers:
        if findings:
            return sorted(findings, key=finding_sort_key)
        return [Finding("PASS", "TRACE_NOT_APPLICABLE", "NA", "NA", "manuscripts", "no paper package exists")]
    modules = module_index(project, findings)
    try:
        manifest, manifest_path, claims, rules = load_result_manifest(project)
    except (TraceAuditError, OSError, ValueError, yaml.YAMLError) as exc:
        add(findings, "BLOCK", "TRACE_CLAIM_MANIFEST", "config/result_manifest.yaml", str(exc))
        return sorted(findings, key=finding_sort_key)
    for paper in papers:
        audit_paper(
            project, paper, modules, manifest, manifest_path, claims, rules, findings,
            selected_release=selected_release, check_git=check_git,
        )
    if not any(item.Status in {"WARN", "BLOCK"} for item in findings):
        add(findings, "PASS", "TRACE_OK", ".", "publication claim trace is internally consistent")
    return sorted(findings, key=finding_sort_key)


def finding_sort_key(item: Finding) -> tuple[int, str, str, str, str]:
    return (-SEVERITY[item.Status], item.Paper_ID, item.Claim_ID, item.Relative_Path.casefold(), item.Rule_ID)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Bioflow Draft/Reviewed/Frozen publication trace audit")
    parser.add_argument("--project", required=True)
    parser.add_argument("--paper")
    parser.add_argument("--release")
    parser.add_argument("--check-git", action="store_true")
    parser.add_argument("--format", choices=("text", "tsv", "json"), default="text")
    args = parser.parse_args(argv)
    try:
        if args.release and not args.paper:
            raise TraceAuditError("--release requires --paper")
        project = safe_project(args.project)
        findings = audit(project, args.paper, args.release, args.check_git)
    except (TraceAuditError, layout_contract.LayoutError, OSError, ValueError, csv.Error, yaml.YAMLError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps({"Project": str(project), "Paper": args.paper, "Release": args.release, "Check_Git": args.check_git, "Findings": [asdict(item) for item in findings]}, indent=2, ensure_ascii=False))
    elif args.format == "tsv":
        writer = csv.DictWriter(sys.stdout, fieldnames=AUDIT_COLUMNS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for item in findings:
            writer.writerow(asdict(item))
    else:
        for item in findings:
            print(f"{item.Status} | {item.Rule_ID} | {item.Paper_ID} | {item.Claim_ID} | {item.Relative_Path} | {item.Detail}")
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
