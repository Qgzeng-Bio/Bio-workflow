#!/usr/bin/env python3
"""Suggest, audit, create, and register concise Bioflow project directories.

The tool is intentionally narrow. ``suggest`` and ``audit`` are read-only.
``create`` and ``register`` are dry-run by default and write only with ``--yes``.
There is no rename, move, delete, cleanup, or archive operation.
"""
from __future__ import annotations

import argparse
import csv
import getpass
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable

import project_layout as layout_contract

MAX_NAME_LENGTH = 24
MAX_SEMANTIC_TOKENS = 3
MAX_AUDIT_DEPTH = 5
DEFAULT_AUDIT_DEPTH = 3
# Kept as the legacy compatibility surface. New code must call
# canonical_dirs()/prune_roots() for a concrete project.
CANONICAL_DIRS = set(layout_contract.LEGACY_LAYOUT.canonical_dirs)
PRUNE_ROOTS = {layout_contract.LEGACY_LAYOUT.rawdata_root, "logs", "tmp"}
PRUNE_NAMES = {"__pycache__", ".cache", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
FORBIDDEN_TOKENS = {
    "final",
    "new",
    "latest",
    "result",
    "results",
    "report",
    "reports",
    "output",
    "outputs",
    "run",
    "best",
    "revised",
    "rerun",
}
INDEX_COLUMNS = (
    "Directory_ID",
    "Relative_Path",
    "Directory_Kind",
    "Stage",
    "Name_Tokens",
    "Purpose",
    "Owner",
    "Status",
    "Notes",
)
AUDIT_COLUMNS = (
    "Relative_Path",
    "Directory_Kind",
    "Name_Length",
    "Token_Count",
    "Status",
    "Rule_ID",
    "Detail",
    "Suggested_Name",
)
SUGGEST_COLUMNS = (
    "Recommended_Name",
    "Name_Length",
    "Token_Count",
    "Status",
    "Rule_ID",
    "Detail",
)
DIRECTORY_KINDS = {"stage", "result", "tool_managed", "legacy"}
INDEX_STATUSES = {"Active", "Archived", "External"}
PROTECTED_RE = re.compile(r"^/data9/home/[^/]+/(?:data|tools)(?:/|$)")
TOKEN_RE = re.compile(r"^[A-Za-z0-9]+$")
VERSION_RE = re.compile(r"^(?:V[0-9]+|v[0-9]+(?:\.[0-9]+)?|[0-9]{8})$")
LEGACY_MANAGED_NAME_RE = re.compile(r"^[A-Za-z0-9_]+(?:\.[0-9]+)?$")
V2_MANAGED_NAME_RE = re.compile(r"^[A-Za-z0-9-]+(?:\.[0-9]+)?$")
DIRECTORY_ID_RE = re.compile(r"^D([0-9]{3,})$")


class PathManagerError(ValueError):
    """Expected naming, path-safety, or index-contract failure."""


def project_layout(project: Path) -> layout_contract.ProjectLayout:
    try:
        return layout_contract.detect_layout(project)
    except layout_contract.LayoutError as exc:
        raise PathManagerError(str(exc)) from exc


def canonical_dirs(project: Path) -> set[str]:
    return set(project_layout(project).canonical_dirs)


def prune_roots(project: Path) -> set[str]:
    layout = project_layout(project)
    return {layout.rawdata_root, "logs", "tmp"}


def name_pattern(separator: str) -> re.Pattern[str]:
    if separator == "_":
        return LEGACY_MANAGED_NAME_RE
    if separator == "-":
        return V2_MANAGED_NAME_RE
    raise PathManagerError(f"unsupported module separator: {separator!r}")


def contains_control(value: str) -> bool:
    return any(character in value for character in "\t\r\n")


def require_clean_text(value: str, label: str, *, allow_empty: bool = False) -> str:
    value = value.strip()
    if not value and not allow_empty:
        raise PathManagerError(f"{label} must be non-empty")
    if contains_control(value):
        raise PathManagerError(f"{label} must not contain tabs or newlines")
    return value


def is_protected(path: Path) -> bool:
    return bool(PROTECTED_RE.match(str(path)))


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def resolve_project(value: str | Path) -> Path:
    raw = Path(value).expanduser()
    if not raw.exists() or not raw.is_dir():
        raise PathManagerError(f"project must be an existing directory: {raw}")
    project = raw.resolve(strict=True)
    home = Path.home().resolve(strict=False)
    broad = {
        Path("/"),
        Path("/data9"),
        Path("/data9/home"),
        home,
        (home / "projects").resolve(strict=False),
    }
    if project in broad:
        raise PathManagerError(f"refusing broad project root: {project}")
    if is_protected(project):
        raise PathManagerError(f"refusing protected project root: {project}")
    return project


def clean_relative(value: str, label: str, *, allow_dot: bool = False) -> Path:
    value = require_clean_text(value, label)
    path = Path(value)
    if path.is_absolute():
        raise PathManagerError(f"{label} must be project-relative: {value}")
    if any(part == ".." for part in path.parts):
        raise PathManagerError(f"{label} must not contain '..': {value}")
    normalized = Path(os.path.normpath(value))
    if normalized == Path(".") and not allow_dot:
        raise PathManagerError(f"{label} must identify a directory below the project root")
    return normalized


def ensure_no_symlink_components(project: Path, relative: Path) -> None:
    current = project
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise PathManagerError(f"symbolic-link path component is not allowed: {current}")


def resolve_inside(project: Path, relative: Path, label: str) -> Path:
    ensure_no_symlink_components(project, relative)
    target = (project / relative).resolve(strict=False)
    if not is_within(target, project):
        raise PathManagerError(f"{label} resolves outside project: {relative}")
    if is_protected(target):
        raise PathManagerError(f"{label} resolves to protected path: {target}")
    return target


def normalize_step(value: int | None, kind: str) -> str:
    if kind == "stage":
        if value is None:
            raise PathManagerError("--step is required for kind=stage")
        if not 0 <= value <= 99:
            raise PathManagerError("--step must be between 0 and 99")
        return f"{value:02d}"
    if value is not None:
        raise PathManagerError("--step is valid only for kind=stage")
    return "NA"


def validate_tokens(tokens: list[str]) -> list[str]:
    if not 1 <= len(tokens) <= MAX_SEMANTIC_TOKENS:
        raise PathManagerError(
            f"supply 1-{MAX_SEMANTIC_TOKENS} short semantic --token values"
        )
    cleaned: list[str] = []
    for token in tokens:
        token = require_clean_text(token, "--token")
        if not TOKEN_RE.fullmatch(token):
            raise PathManagerError(
                f"token must contain ASCII letters/digits only; use separate tokens instead: {token!r}"
            )
        if token.casefold() in FORBIDDEN_TOKENS:
            raise PathManagerError(f"redundant token is forbidden: {token}")
        cleaned.append(token)
    return cleaned


def validate_version(version: str | None) -> str | None:
    if version is None:
        return None
    version = require_clean_text(version, "--version")
    if not VERSION_RE.fullmatch(version):
        raise PathManagerError("--version must be YYYYMMDD, V2-style, or v1.1-style")
    return version


def build_name(
    kind: str,
    step: int | None,
    tokens: list[str],
    version: str | None,
    *,
    separator: str = "_",
) -> tuple[str, str]:
    if kind not in {"stage", "result"}:
        raise PathManagerError("suggest/create kind must be stage or result")
    stage = normalize_step(step, kind)
    tokens = validate_tokens(tokens)
    version = validate_version(version)
    if kind == "stage" and version is not None:
        raise PathManagerError("analysis-module names cannot carry versions; use <module>/versions/VNN")
    pieces = tokens + ([version] if version else [])
    if kind == "stage":
        pieces.insert(0, stage)
    name = separator.join(pieces)
    if len(name) > MAX_NAME_LENGTH:
        raise PathManagerError(
            f"recommended name exceeds {MAX_NAME_LENGTH} characters ({len(name)}): {name}"
        )
    if not name_pattern(separator).fullmatch(name):
        raise PathManagerError(f"generated name violates managed-name syntax: {name}")
    return name, stage


def casefold_collision(parent: Path, name: str) -> str | None:
    if not parent.exists() or not parent.is_dir():
        raise PathManagerError(f"parent must be an existing directory: {parent}")
    matches = sorted(
        child.name for child in parent.iterdir() if child.name.casefold() == name.casefold()
    )
    return matches[0] if matches else None


def write_tsv_stdout(columns: Iterable[str], rows: Iterable[dict[str, Any]]) -> None:
    writer = csv.DictWriter(sys.stdout, fieldnames=list(columns), delimiter="\t", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in writer.fieldnames})


def index_path(project: Path) -> Path:
    return project / "config" / "Directory_Index.tsv"


def normalize_index_relative(value: str) -> str:
    relative = clean_relative(value, "Directory_Index.Relative_Path")
    return relative.as_posix()


def load_index(project: Path) -> tuple[Path, list[dict[str, str]]]:
    path = resolve_inside(project, Path("config/Directory_Index.tsv"), "directory index")
    if not path.exists():
        return path, []
    if path.is_symlink() or not path.is_file() or not os.access(path, os.R_OK):
        raise PathManagerError(f"directory index is not a readable regular file: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if tuple(reader.fieldnames or ()) != INDEX_COLUMNS:
            raise PathManagerError(
                f"directory index header must be exactly: {' | '.join(INDEX_COLUMNS)}"
            )
        rows: list[dict[str, str]] = []
        seen_ids: set[str] = set()
        seen_paths: set[str] = set()
        for line_number, raw in enumerate(reader, 2):
            if None in raw:
                raise PathManagerError(f"{path}:{line_number}: too many TSV fields")
            row = {column: (raw.get(column) or "").strip() for column in INDEX_COLUMNS}
            directory_id = row["Directory_ID"]
            if not DIRECTORY_ID_RE.fullmatch(directory_id):
                raise PathManagerError(f"{path}:{line_number}: invalid Directory_ID {directory_id!r}")
            relative = normalize_index_relative(row["Relative_Path"])
            row["Relative_Path"] = relative
            if row["Directory_Kind"] not in DIRECTORY_KINDS:
                raise PathManagerError(f"{path}:{line_number}: invalid Directory_Kind")
            if row["Status"] not in INDEX_STATUSES:
                raise PathManagerError(f"{path}:{line_number}: invalid Status")
            if directory_id in seen_ids:
                raise PathManagerError(f"{path}:{line_number}: duplicate Directory_ID {directory_id}")
            folded = relative.casefold()
            if folded in seen_paths:
                raise PathManagerError(f"{path}:{line_number}: duplicate/case-colliding Relative_Path {relative}")
            if any(contains_control(value) for value in row.values()):
                raise PathManagerError(f"{path}:{line_number}: tabs/newlines are forbidden in fields")
            seen_ids.add(directory_id)
            seen_paths.add(folded)
            rows.append(row)
    return path, rows


def next_directory_id(rows: list[dict[str, str]]) -> str:
    highest = 0
    for row in rows:
        match = DIRECTORY_ID_RE.fullmatch(row["Directory_ID"])
        if match:
            highest = max(highest, int(match.group(1)))
    return f"D{highest + 1:03d}"


def validate_new_row(
    rows: list[dict[str, str]], row: dict[str, str]
) -> None:
    if not DIRECTORY_ID_RE.fullmatch(row["Directory_ID"]):
        raise PathManagerError("--directory-id must match D001-style stable IDs")
    if row["Directory_Kind"] not in DIRECTORY_KINDS:
        raise PathManagerError(f"invalid Directory_Kind: {row['Directory_Kind']}")
    if row["Status"] not in INDEX_STATUSES:
        raise PathManagerError(f"invalid Status: {row['Status']}")
    for field, value in row.items():
        require_clean_text(value, field, allow_empty=field in {"Stage", "Name_Tokens", "Notes"})
    path_folded = row["Relative_Path"].casefold()
    for existing in rows:
        if existing["Directory_ID"] == row["Directory_ID"]:
            raise PathManagerError(f"Directory_ID already exists: {row['Directory_ID']}")
        if existing["Relative_Path"].casefold() == path_folded:
            raise PathManagerError(f"Relative_Path already indexed: {row['Relative_Path']}")


def render_index(rows: list[dict[str, str]]) -> str:
    import io

    def directory_number(row: dict[str, str]) -> int:
        match = DIRECTORY_ID_RE.fullmatch(row.get("Directory_ID", ""))
        if match is None:
            raise PathManagerError(f"invalid Directory_ID while rendering index: {row.get('Directory_ID', '')!r}")
        return int(match.group(1))

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=INDEX_COLUMNS, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    for row in sorted(rows, key=directory_number):
        writer.writerow(row)
    return stream.getvalue()


def atomic_write_index(path: Path, rows: list[dict[str, str]]) -> None:
    if path.parent.is_symlink() or not path.parent.exists() or not path.parent.is_dir():
        raise PathManagerError(f"config directory must be an existing non-symlink directory: {path.parent}")
    if path.is_symlink():
        raise PathManagerError(f"directory index must not be a symbolic link: {path}")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    backup: Path | None = None
    replaced = False
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            os.fchmod(handle.fileno(), 0o644)
            handle.write(render_index(rows))
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            backup_descriptor, backup_name = tempfile.mkstemp(
                prefix=f".{path.name}.", suffix=".backup", dir=path.parent
            )
            os.close(backup_descriptor)
            backup = Path(backup_name)
            backup.unlink()
            os.replace(path, backup)
        try:
            os.replace(temporary, path)
            replaced = True
            directory_descriptor = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
        except Exception:
            if replaced:
                path.unlink(missing_ok=True)
            if backup is not None and backup.exists():
                os.replace(backup, path)
            raise
        if backup is not None:
            try:
                backup.unlink(missing_ok=True)
            except OSError as exc:
                sys.stderr.write(f"[WARN] committed index but could not remove backup {backup}: {exc}\n")
    finally:
        temporary.unlink(missing_ok=True)
        if backup is not None and backup.exists():
            if not path.exists():
                os.replace(backup, path)
            else:
                try:
                    backup.unlink(missing_ok=True)
                except OSError as exc:
                    sys.stderr.write(f"[WARN] stale index backup remains at {backup}: {exc}\n")


def make_index_row(
    rows: list[dict[str, str]],
    *,
    directory_id: str | None,
    relative: str,
    kind: str,
    stage: str,
    tokens: list[str],
    purpose: str,
    owner: str,
    status: str,
    notes: str,
) -> dict[str, str]:
    row = {
        "Directory_ID": directory_id or next_directory_id(rows),
        "Relative_Path": normalize_index_relative(relative),
        "Directory_Kind": kind,
        "Stage": "" if stage == "NA" else stage,
        "Name_Tokens": ",".join(tokens),
        "Purpose": require_clean_text(purpose, "--purpose"),
        "Owner": require_clean_text(owner, "--owner"),
        "Status": status,
        "Notes": require_clean_text(notes, "--notes", allow_empty=True),
    }
    validate_new_row(rows, row)
    return row


def preview_write(mode: str, target: Path, path: Path, row: dict[str, str]) -> None:
    columns = ("Mode", "Target_Path", "Index_Path") + INDEX_COLUMNS
    payload = {"Mode": mode, "Target_Path": str(target), "Index_Path": str(path), **row}
    write_tsv_stdout(columns, [payload])


def normalized_suggestion(name: str, kind: str, separator: str = "_") -> str:
    candidate = re.sub(r"[\s_-]+", separator, name.strip())
    candidate = re.sub(re.escape(separator) + "+", separator, candidate).strip(separator)
    parts = candidate.split(separator) if candidate else []
    kept: list[str] = []
    for position, part in enumerate(parts):
        if kind == "stage" and position == 0 and re.fullmatch(r"[0-9]{1,2}", part):
            kept.append(f"{int(part):02d}")
        elif part.casefold() not in FORBIDDEN_TOKENS:
            kept.append(part)
    candidate = separator.join(kept)
    if not candidate or len(candidate) > MAX_NAME_LENGTH:
        return "REVIEW_REQUIRED"
    if not name_pattern(separator).fullmatch(candidate):
        return "REVIEW_REQUIRED"
    semantic = kept[1:] if kind == "stage" and kept and re.fullmatch(r"[0-9]{2}", kept[0]) else kept
    if semantic and VERSION_RE.fullmatch(semantic[-1]):
        semantic = semantic[:-1]
    if not 1 <= len(semantic) <= MAX_SEMANTIC_TOKENS:
        return "REVIEW_REQUIRED"
    return candidate


def evaluate_name(name: str, kind: str, separator: str = "_") -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    suggestion = normalized_suggestion(name, kind, separator)
    if len(name) > MAX_NAME_LENGTH:
        findings.append({"Rule_ID": "PATH001", "Detail": f"name exceeds {MAX_NAME_LENGTH} characters", "Suggested_Name": "REVIEW_REQUIRED"})
    if (
        not name_pattern(separator).fullmatch(name)
        or name.startswith(separator)
        or name.endswith(separator)
        or separator * 2 in name
    ):
        findings.append({"Rule_ID": "PATH004", "Detail": f"name must use ASCII letters/digits/{separator!r}; one dot is allowed only in a trailing version", "Suggested_Name": suggestion})
    parts = name.split(separator)
    semantic = parts[:]
    if kind == "stage":
        if not parts or not re.fullmatch(r"[0-9]{2}", parts[0]):
            findings.append({"Rule_ID": "PATH004", "Detail": "stage name must begin with a two-digit NN_ prefix", "Suggested_Name": suggestion})
        elif parts:
            semantic = parts[1:]
    if semantic and VERSION_RE.fullmatch(semantic[-1]):
        semantic = semantic[:-1]
    if len(semantic) > MAX_SEMANTIC_TOKENS:
        findings.append({"Rule_ID": "PATH002", "Detail": f"name has more than {MAX_SEMANTIC_TOKENS} semantic tokens", "Suggested_Name": "REVIEW_REQUIRED"})
    forbidden = sorted({token for token in semantic if token.casefold() in FORBIDDEN_TOKENS})
    if forbidden:
        findings.append({"Rule_ID": "PATH003", "Detail": f"redundant tokens: {','.join(forbidden)}", "Suggested_Name": suggestion})
    return findings


def audit_row(
    relative: str,
    kind: str,
    name: str,
    status: str,
    rule_id: str,
    detail: str,
    suggested: str = "NA",
    separator: str = "_",
) -> dict[str, str]:
    parts = name.split(separator) if name else []
    semantic = parts[1:] if kind == "stage" and parts and re.fullmatch(r"[0-9]{2}", parts[0]) else parts
    if semantic and VERSION_RE.fullmatch(semantic[-1]):
        semantic = semantic[:-1]
    return {
        "Relative_Path": relative,
        "Directory_Kind": kind,
        "Name_Length": str(len(name)),
        "Token_Count": str(len(semantic)),
        "Status": status,
        "Rule_ID": rule_id,
        "Detail": detail,
        "Suggested_Name": suggested,
    }


def scan_directories(
    project: Path, max_depth: int, pruned_roots: set[str] | None = None
) -> list[tuple[str, Path, bool]]:
    found: list[tuple[str, Path, bool]] = []
    pruned_roots = PRUNE_ROOTS if pruned_roots is None else pruned_roots

    def visit(parent: Path, depth: int) -> None:
        if depth >= max_depth:
            return
        try:
            children = sorted(parent.iterdir(), key=lambda item: (item.name.casefold(), item.name))
        except OSError as exc:
            raise PathManagerError(f"cannot list directory {parent}: {exc}") from exc
        for child in children:
            if child.name.startswith(".") or child.name in PRUNE_NAMES:
                continue
            relative = child.relative_to(project).as_posix()
            if child.is_symlink():
                found.append((relative, child, True))
                continue
            if not child.is_dir():
                continue
            found.append((relative, child, False))
            if depth == 0 and child.name in pruned_roots:
                continue
            visit(child, depth + 1)

    visit(project, 0)
    return found


def run_suggest(args: argparse.Namespace) -> int:
    separator = "-"
    if args.project:
        separator = project_layout(resolve_project(args.project)).module_separator
    name, _ = build_name(args.kind, args.step, args.token, args.version, separator=separator)
    status, rule_id, detail = "PASS", "OK", "name satisfies managed-directory rules"
    if (args.project is None) != (args.parent is None):
        raise PathManagerError("--project and --parent must be supplied together for collision checking")
    if args.project:
        project = resolve_project(args.project)
        parent_relative = clean_relative(args.parent, "--parent", allow_dot=True)
        parent = resolve_inside(project, parent_relative, "parent")
        collision = casefold_collision(parent, name)
        if collision:
            status, rule_id, detail = "WARN", "PATH005", f"case-insensitive sibling collision: {collision}"
    write_tsv_stdout(
        SUGGEST_COLUMNS,
        [{
            "Recommended_Name": name,
            "Name_Length": len(name),
            "Token_Count": len(args.token),
            "Status": status,
            "Rule_ID": rule_id,
            "Detail": detail,
        }],
    )
    return 1 if status == "WARN" else 0


def run_audit(args: argparse.Namespace) -> int:
    if not 1 <= args.max_depth <= MAX_AUDIT_DEPTH:
        raise PathManagerError(f"--max-depth must be between 1 and {MAX_AUDIT_DEPTH}")
    project = resolve_project(args.project)
    layout = project_layout(project)
    fixed_roots = set(layout.canonical_dirs)
    separator = layout.module_separator
    _, index_rows = load_index(project)
    indexed = {row["Relative_Path"]: row for row in index_rows}
    scanned = scan_directories(project, args.max_depth, prune_roots(project))
    rows: list[dict[str, str]] = []
    sibling_groups: dict[tuple[str, str], list[str]] = {}
    scanned_paths = {relative for relative, _, _ in scanned}

    for relative, path, is_symlink in scanned:
        parent = str(Path(relative).parent.as_posix())
        sibling_groups.setdefault((parent, path.name.casefold()), []).append(relative)
        entry = indexed.get(relative)
        if is_symlink:
            rows.append(audit_row(relative, entry["Directory_Kind"] if entry else "unmanaged", path.name, "EXEMPT", "PATH008", "symbolic link not followed", separator=separator))
            continue
        if Path(relative).parent == Path(".") and path.name in fixed_roots:
            rows.append(audit_row(relative, "canonical", path.name, "EXEMPT", "PATH010", "fixed Bioflow project directory", separator=separator))
            continue
        if entry and entry["Directory_Kind"] == "tool_managed":
            rows.append(audit_row(relative, "tool_managed", path.name, "EXEMPT", "PATH009", "tool-controlled name registered in Directory_Index.tsv", separator=separator))
            continue
        if entry and entry["Directory_Kind"] == "legacy":
            rows.append(audit_row(relative, "legacy", path.name, "WARN", "PATH006", "legacy directory is advisory-only; no automatic rename", separator=separator))
            continue
        kind = entry["Directory_Kind"] if entry else ("stage" if re.match(r"^[0-9]{2}[_-]", path.name) else "result")
        findings = evaluate_name(path.name, kind, separator)
        if findings:
            for finding in findings:
                rows.append(audit_row(relative, kind, path.name, "WARN", finding["Rule_ID"], finding["Detail"], finding["Suggested_Name"], separator))
        else:
            rows.append(audit_row(relative, kind, path.name, "PASS", "OK", "name satisfies managed-directory rules", separator=separator))

    for (_, _), relatives in sibling_groups.items():
        if len(relatives) > 1:
            detail = f"case-insensitive sibling collision: {','.join(sorted(relatives))}"
            for relative in sorted(relatives):
                path = project / relative
                entry = indexed.get(relative)
                kind = entry["Directory_Kind"] if entry else "result"
                rows.append(audit_row(relative, kind, path.name, "WARN", "PATH005", detail, separator=separator))

    for row in index_rows:
        relative = row["Relative_Path"]
        if relative not in scanned_paths and not (project / relative).exists():
            rows.append(audit_row(relative, row["Directory_Kind"], Path(relative).name, "WARN", "PATH007", "indexed directory is missing", separator=separator))

    rows.sort(key=lambda row: (row["Relative_Path"].casefold(), row["Relative_Path"], row["Rule_ID"]))
    write_tsv_stdout(AUDIT_COLUMNS, rows)
    has_warn = any(row["Status"] == "WARN" for row in rows)
    return 1 if args.strict and has_warn else 0


def common_write_context(args: argparse.Namespace) -> tuple[Path, Path, list[dict[str, str]]]:
    project = resolve_project(args.project)
    path, rows = load_index(project)
    if not path.parent.exists() or not path.parent.is_dir():
        raise PathManagerError(f"project config directory must already exist: {path.parent}")
    if not os.access(path.parent, os.W_OK):
        raise PathManagerError(f"project config directory is not writable: {path.parent}")
    return project, path, rows


def run_create(args: argparse.Namespace) -> int:
    project, path, rows = common_write_context(args)
    parent_relative = clean_relative(args.parent, "--parent", allow_dot=True)
    parent = resolve_inside(project, parent_relative, "parent")
    if parent.is_symlink() or not parent.exists() or not parent.is_dir():
        raise PathManagerError(f"parent must be an existing non-symlink directory: {parent}")
    if not os.access(parent, os.W_OK):
        raise PathManagerError(f"parent is not writable: {parent}")
    layout = project_layout(project)
    name, stage = build_name(
        args.kind, args.step, args.token, args.version, separator=layout.module_separator
    )
    collision = casefold_collision(parent, name)
    if collision:
        raise PathManagerError(f"target/case-insensitive sibling already exists: {collision}")
    target = parent / name
    relative = target.relative_to(project).as_posix()
    resolve_inside(project, Path(relative), "target")
    row = make_index_row(
        rows,
        directory_id=args.directory_id,
        relative=relative,
        kind=args.kind,
        stage=stage,
        tokens=args.token,
        purpose=args.purpose,
        owner=args.owner,
        status=args.status,
        notes=args.notes,
    )
    preview_write("WRITE" if args.yes else "DRY_RUN", target, path, row)
    if not args.yes:
        return 0
    created = False
    try:
        target.mkdir()
        created = True
        atomic_write_index(path, rows + [row])
    except Exception:
        if created:
            try:
                target.rmdir()
            except OSError as rollback_error:
                sys.stderr.write(f"[WARN] failed to roll back newly created empty directory {target}: {rollback_error}\n")
        raise
    return 0


def run_register(args: argparse.Namespace) -> int:
    project, path, rows = common_write_context(args)
    relative_path = clean_relative(args.relative, "--relative")
    target = resolve_inside(project, relative_path, "registered directory")
    if target.is_symlink() or not target.exists() or not target.is_dir():
        raise PathManagerError(f"registered path must be an existing non-symlink directory: {target}")
    if args.kind in {"tool_managed", "legacy"} and args.step is not None:
        raise PathManagerError("--step is valid only for kind=stage")
    stage = normalize_step(args.step, args.kind) if args.kind in {"stage", "result"} else "NA"
    tokens = validate_tokens(args.token) if args.token else []
    if args.kind in {"stage", "result"} and not tokens:
        separator = project_layout(project).module_separator
        inferred = target.name.split(separator)
        if args.kind == "stage":
            inferred = inferred[1:]
        if inferred and VERSION_RE.fullmatch(inferred[-1]):
            inferred = inferred[:-1]
        tokens = validate_tokens(inferred)
    if args.kind == "result" and args.step is not None:
        raise PathManagerError("--step is valid only for kind=stage")
    if args.kind in {"stage", "result"}:
        findings = evaluate_name(target.name, args.kind, project_layout(project).module_separator)
        if findings:
            rules = ",".join(sorted({finding["Rule_ID"] for finding in findings}))
            raise PathManagerError(
                f"registered {args.kind} name fails {rules}; use kind=legacy for advisory-only existing paths"
            )
    row = make_index_row(
        rows,
        directory_id=args.directory_id,
        relative=relative_path.as_posix(),
        kind=args.kind,
        stage=stage,
        tokens=tokens,
        purpose=args.purpose,
        owner=args.owner,
        status=args.status,
        notes=args.notes,
    )
    preview_write("WRITE" if args.yes else "DRY_RUN", target, path, row)
    if args.yes:
        atomic_write_index(path, rows + [row])
    return 0


def add_name_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--kind", choices=("stage", "result"), required=True)
    parser.add_argument("--step", type=int)
    parser.add_argument("--token", action="append", default=[], help="repeat 1-3 times; casing is preserved")
    parser.add_argument("--version", help="optional for result directories only; analysis modules use versions/VNN internally")


def add_index_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--purpose", required=True)
    parser.add_argument("--owner", default=getpass.getuser())
    parser.add_argument("--status", choices=sorted(INDEX_STATUSES), default="Active")
    parser.add_argument("--notes", default="")
    parser.add_argument("--directory-id")
    parser.add_argument("--yes", action="store_true", help="write; default is dry-run")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage concise Bioflow project directories without rename/delete operations."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    suggest = subparsers.add_parser("suggest", help="validate and emit one deterministic short name")
    add_name_arguments(suggest)
    suggest.add_argument("--project", help="optional explicit project for sibling collision check")
    suggest.add_argument("--parent", help="project-relative existing parent; requires --project")
    suggest.set_defaults(handler=run_suggest)

    audit = subparsers.add_parser("audit", help="bounded read-only directory naming audit")
    audit.add_argument("--project", required=True)
    audit.add_argument("--max-depth", type=int, default=DEFAULT_AUDIT_DEPTH)
    audit.add_argument("--strict", action="store_true", help="return 1 when WARN findings exist")
    audit.set_defaults(handler=run_audit)

    create = subparsers.add_parser("create", help="dry-run or create one short directory and index row")
    create.add_argument("--project", required=True)
    create.add_argument("--parent", required=True)
    add_name_arguments(create)
    add_index_arguments(create)
    create.set_defaults(handler=run_create)

    register = subparsers.add_parser("register", help="dry-run or index one existing directory")
    register.add_argument("--project", required=True)
    register.add_argument("--relative", required=True)
    register.add_argument("--kind", choices=sorted(DIRECTORY_KINDS), required=True)
    register.add_argument("--step", type=int)
    register.add_argument("--token", action="append", default=[])
    add_index_arguments(register)
    register.set_defaults(handler=run_register)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except (PathManagerError, OSError, ValueError) as exc:
        sys.stderr.write(f"[ERROR] {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
