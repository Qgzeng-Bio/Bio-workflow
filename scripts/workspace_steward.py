#!/usr/bin/env python3
"""Plan, route, audit, and safely apply Bioflow project workspaces.

The steward manages an explicit module DAG and a small set of directory/key-
artifact routes. It never infers biological dependencies from names, never
follows symlinks, and exposes no rename/move/delete/archive mutation.
"""
from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import io
import json
import os
import re
import stat
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
import path_manager as pm  # noqa: E402
import project_layout as layout_contract  # noqa: E402

SCHEMA_VERSION = "workspace.v1"
V2_SCHEMA_VERSION = "workspace.v2"
SUPPORTED_SCHEMA_VERSIONS = {SCHEMA_VERSION, V2_SCHEMA_VERSION}
MAX_AUDIT_DEPTH = 5
DEFAULT_AUDIT_DEPTH = 3
MAX_INVENTORY_ENTRIES = 5000

POLICY_COLUMNS = (
    "Schema_Version",
    "Enforcement_Mode",
    "Plan_Status",
    "Plan_SHA256",
    "Max_Audit_Depth",
    "Updated_Time",
)
MODULE_COLUMNS = (
    "Module_ID",
    "Parent_Module",
    "Stage",
    "Short_Name",
    "Module_Kind",
    "Depends_On",
    "Purpose",
    "Owner",
    "Compatibility",
    "Notes",
)
MODULE_COLUMNS_V2 = (
    "Module_ID",
    "Analysis_Key",
    "Parent_Module",
    "Stage",
    "Short_Name",
    "Module_Kind",
    "Depends_On",
    "Purpose",
    "Owner",
    "Compatibility",
    "Notes",
)
ROUTE_COLUMNS = (
    "Route_ID",
    "Module_ID",
    "Path_Type",
    "Path_Role",
    "Relative_Path",
    "Producer_Tasks",
    "Consumer_Tasks",
    "Retention",
    "Required",
    "Compatibility",
    "Purpose",
    "Notes",
)
INVENTORY_COLUMNS = (
    "Relative_Path",
    "Entry_Type",
    "Depth",
    "Observed_Role",
    "Index_Status",
    "Status",
    "Rule_ID",
    "Detail",
)
PLAN_COLUMNS = (
    "Plan_SHA256",
    "Module_ID",
    "Analysis_Key",
    "Parent_Module",
    "Stage",
    "Module_Path",
    "Module_Kind",
    "Depends_On",
    "Route_ID",
    "Path_Type",
    "Path_Role",
    "Relative_Path",
    "Required",
    "Compatibility",
)
ROUTE_OUTPUT_COLUMNS = (
    "Route_ID",
    "Module_ID",
    "Path_Type",
    "Path_Role",
    "Relative_Path",
    "Compatibility",
    "Required",
    "Retention",
    "Purpose",
)
AUDIT_COLUMNS = (
    "Status",
    "Rule_ID",
    "Relative_Path",
    "Module_ID",
    "Route_ID",
    "Detail",
)
APPLY_COLUMNS = (
    "Mode",
    "Action",
    "Route_ID",
    "Relative_Path",
    "Directory_ID",
    "Detail",
)
PREFLIGHT_COLUMNS = (
    "Status",
    "Rule_ID",
    "Path_Type",
    "Path",
    "Route_ID",
    "Detail",
)
MIGRATION_COLUMNS = (
    "Current_Path",
    "Observed_Type",
    "Suggested_Role",
    "Suggested_Path",
    "Confidence",
    "Reason",
    "Action",
)

MODULE_ID_RE = re.compile(r"^M([0-9]{3,})$")
ROUTE_ID_RE = re.compile(r"^R([0-9]{3,})$")
TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
ANALYSIS_KEY_RE = re.compile(r"^[a-z][a-z0-9-]*$")
FIGURE_PACKAGE_RE = re.compile(r"^F[0-9]{3}_[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*$")
MANUSCRIPT_DIR_RE = re.compile(r"^P[0-9]{2}-[a-z][a-z0-9-]*$")
VERSION_DIR_RE = re.compile(r"^V[0-9]{2,}$")
STAGE_RE = re.compile(r"^[0-9]{2}$")
MODULE_KINDS = {"group", "analysis", "publication", "management", "legacy"}
MODULE_COMPATIBILITY = {"Managed", "Legacy"}
PATH_TYPES = {"Directory", "Artifact"}
PATH_ROLES = {
    "Config",
    "Manifest",
    "Input_Link",
    "Script",
    "Log",
    "Temporary",
    "Result",
    "QC",
    "Plot_Data",
    "Source_Table",
    "Figure",
    "Report",
    "Manuscript",
    "Acceptance",
    "Delivery",
}
ROLE_ROOT_V1 = {
    "Config": "config",
    "Manifest": "config",
    "Input_Link": "data",
    "Script": "scripts",
    "Log": "logs",
    "Temporary": "tmp",
    "Result": "results",
    "QC": "results",
    "Plot_Data": "results",
    "Source_Table": "results",
    "Figure": "reports",
    "Report": "reports",
    "Manuscript": "reports",
    "Acceptance": "reports",
    "Delivery": "reports",
}
ROLE_ROOT_V2 = {
    "Config": "config",
    "Manifest": "config",
    "Input_Link": "rawdata",
    "Script": "scripts",
    "Log": "logs",
    "Temporary": "tmp",
    "Result": "results",
    "QC": "results",
    "Plot_Data": "results",
    "Source_Table": "results",
    "Figure": "results",
    "Report": "docs",
    "Manuscript": "manuscripts",
    "Acceptance": "docs",
    "Delivery": "docs",
}
# Compatibility alias for callers/tests that inspect the v1 contract directly.
ROLE_ROOT = ROLE_ROOT_V1
ROUTE_COMPATIBILITY = {"Managed", "Tool_managed", "Legacy"}
RETENTION_VALUES = {"Disposable", "Working", "Retained", "Delivery"}
REQUIRED_VALUES = {"Yes", "No"}
PRUNE_NAMES = {"__pycache__", ".cache", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
PRUNE_ROOTS = {"data", "logs", "tmp"}
CANONICAL_CONTROL_PATHS = {
    "config/Input_Manifest.tsv",
    "config/result_manifest.yaml",
    "config/Directory_Index.tsv",
    "config/Workspace_Policy.tsv",
    "config/Workspace_Modules.tsv",
    "config/Workspace_Routes.tsv",
    "reports/Analysis_Plan.md",
    "reports/workflow_status.tsv",
    "reports/Task_Status.tsv",
    "reports/run_record.tsv",
    "reports/Acceptance_Report.md",
    "reports/Methods_Summary.md",
    "reports/Delivery_Index.md",
}
V2_CONTROL_PATHS = {
    "config/Project_Layout.tsv",
    "config/Input_Manifest.tsv",
    "config/Sample_Metadata.tsv",
    "config/Reference_Manifest.tsv",
    "config/Tool_Versions.tsv",
    "config/result_manifest.yaml",
    "config/Directory_Index.tsv",
    "config/Workspace_Policy.tsv",
    "config/Workspace_Modules.tsv",
    "config/Workspace_Routes.tsv",
    "rawdata/README.md",
    "docs/Analysis_Plan.md",
    "docs/status/workflow_status.tsv",
    "docs/status/Task_Status.tsv",
    "docs/status/run_record.tsv",
    "docs/validation/Claim_Audit.tsv",
    "docs/validation/Acceptance_Report.md",
    "docs/methods/Methods_Summary.md",
    "docs/delivery/Delivery_Index.md",
    "docs/decisions/Decision_Log.md",
    "docs/research-log/README.md",
    "manuscripts/README.md",
}
ROOT_CONTROL_NAMES = {
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    "LICENSE",
    "LICENSE.md",
    ".gitignore",
    ".gitattributes",
    ".github",
    "PROJECT_STATUS.md",
    "CHANGELOG.md",
}
COMPLETED_TASK_STATUSES = {"Complete_unvalidated", "Validated"}
DELIVERED_WORKFLOW_STAGES = {"Delivered"}
SEVERITY = {"PASS": 0, "INFO": 0, "EXEMPT": 0, "WARN": 1, "BLOCK": 2}


class WorkspaceError(ValueError):
    """Expected workspace schema, safety, or routing failure."""


def clean(value: str, label: str, *, allow_empty: bool = False) -> str:
    try:
        return pm.require_clean_text(value, label, allow_empty=allow_empty)
    except pm.PathManagerError as exc:
        raise WorkspaceError(str(exc)) from exc


def split_ids(value: str, label: str) -> list[str]:
    value = clean(value, label, allow_empty=True)
    if not value:
        return []
    result: list[str] = []
    for item in value.split(","):
        item = clean(item, label)
        if not TASK_ID_RE.fullmatch(item):
            raise WorkspaceError(f"{label} contains invalid ID: {item!r}")
        if item in result:
            raise WorkspaceError(f"{label} contains duplicate ID: {item}")
        result.append(item)
    return result


def workspace_paths(project: Path) -> dict[str, Path]:
    config = project / "config"
    return {
        "policy": config / "Workspace_Policy.tsv",
        "modules": config / "Workspace_Modules.tsv",
        "routes": config / "Workspace_Routes.tsv",
        "lock": config / ".Workspace_Steward.lock",
    }


def safe_inside(project: Path, relative: str | Path, label: str) -> Path:
    try:
        return pm.resolve_inside(project, Path(relative), label)
    except pm.PathManagerError as exc:
        raise WorkspaceError(str(exc)) from exc


def open_project_lock(project: Path):
    path = safe_inside(project, "config/.Workspace_Steward.lock", "workspace lock")
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        raise WorkspaceError(f"cannot safely open workspace lock {path}: {exc}") from exc
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise WorkspaceError(f"workspace lock must be a regular file: {path}")
        return os.fdopen(descriptor, "a+")
    except Exception:
        os.close(descriptor)
        raise


def read_exact_tsv(path: Path, columns: tuple[str, ...], label: str) -> list[dict[str, str]]:
    if not path.exists() or path.is_symlink() or not path.is_file() or not os.access(path, os.R_OK):
        raise WorkspaceError(f"{label} must be a readable regular file: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if tuple(reader.fieldnames or ()) != columns:
            raise WorkspaceError(f"{label} header must be exactly: {' | '.join(columns)}")
        rows: list[dict[str, str]] = []
        for line_number, raw in enumerate(reader, 2):
            if None in raw:
                raise WorkspaceError(f"{path}:{line_number}: too many TSV fields")
            row = {column: (raw.get(column) or "").strip() for column in columns}
            if any(pm.contains_control(value) for value in row.values()):
                raise WorkspaceError(f"{path}:{line_number}: tabs/newlines are forbidden in fields")
            rows.append(row)
    return rows


def render_tsv(columns: Iterable[str], rows: Iterable[dict[str, Any]]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(columns), delimiter="\t", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in writer.fieldnames})
    return stream.getvalue()


def write_tsv(columns: Iterable[str], rows: Iterable[dict[str, Any]]) -> None:
    sys.stdout.write(render_tsv(columns, rows))


def read_policy(project: Path) -> dict[str, str]:
    rows = read_exact_tsv(workspace_paths(project)["policy"], POLICY_COLUMNS, "Workspace_Policy.tsv")
    if len(rows) != 1:
        raise WorkspaceError("Workspace_Policy.tsv must contain exactly one data row")
    row = rows[0]
    try:
        layout = layout_contract.detect_layout(project)
    except layout_contract.LayoutError as exc:
        raise WorkspaceError(str(exc)) from exc
    expected_schema = V2_SCHEMA_VERSION if layout.is_v2 else SCHEMA_VERSION
    if row["Schema_Version"] != expected_schema:
        raise WorkspaceError(
            f"workspace schema {row['Schema_Version']!r} does not match project layout "
            f"{layout.schema_version!r}; expected {expected_schema!r}"
        )
    if row["Enforcement_Mode"] != "Hybrid":
        raise WorkspaceError(f"Enforcement_Mode must be Hybrid in {expected_schema}")
    if row["Plan_Status"] not in {"Draft", "Reviewed"}:
        raise WorkspaceError("Plan_Status must be Draft or Reviewed")
    if row["Plan_Status"] == "Reviewed" and not re.fullmatch(r"[0-9a-f]{64}", row["Plan_SHA256"]):
        raise WorkspaceError("Reviewed policy requires a lowercase SHA256 Plan_SHA256")
    if row["Plan_Status"] == "Draft" and row["Plan_SHA256"] and not re.fullmatch(r"[0-9a-f]{64}", row["Plan_SHA256"]):
        raise WorkspaceError("Draft Plan_SHA256 must be empty or a lowercase SHA256")
    try:
        depth = int(row["Max_Audit_Depth"])
    except ValueError as exc:
        raise WorkspaceError("Max_Audit_Depth must be an integer") from exc
    if not 1 <= depth <= MAX_AUDIT_DEPTH:
        raise WorkspaceError(f"Max_Audit_Depth must be between 1 and {MAX_AUDIT_DEPTH}")
    clean(row["Updated_Time"], "Updated_Time")
    return row


def validate_short_name(
    stage: str, short_name: str, layout: layout_contract.ProjectLayout
) -> None:
    tokens = short_name.split(layout.module_separator) if short_name else []
    if layout.is_v2 and any(
        token.casefold() in pm.FORBIDDEN_TOKENS or pm.VERSION_RE.fullmatch(token)
        for token in tokens
    ):
        raise WorkspaceError(
            "analysis-module names cannot contain version/status tokens; use <module>/versions/VNN"
        )
    try:
        pm.build_name(
            "stage", int(stage), tokens, None, separator=layout.module_separator
        )
    except (pm.PathManagerError, ValueError) as exc:
        expected = f"{stage}{layout.module_separator}{short_name}"
        raise WorkspaceError(f"invalid managed module name {expected}: {exc}") from exc


def validate_modules(
    rows: list[dict[str, str]], layout: layout_contract.ProjectLayout = layout_contract.LEGACY_LAYOUT
) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    if not rows:
        raise WorkspaceError("Workspace_Modules.tsv must contain at least one module")
    modules: dict[str, dict[str, str]] = {}
    analysis_keys: dict[str, str] = {}
    for line_number, row in enumerate(rows, 2):
        module_id = row["Module_ID"]
        if not MODULE_ID_RE.fullmatch(module_id):
            raise WorkspaceError(f"Workspace_Modules.tsv:{line_number}: invalid Module_ID {module_id!r}")
        if module_id in modules:
            raise WorkspaceError(f"duplicate Module_ID: {module_id}")
        if layout.is_v2:
            analysis_key = clean(row.get("Analysis_Key", ""), "Analysis_Key")
            if not ANALYSIS_KEY_RE.fullmatch(analysis_key):
                raise WorkspaceError(
                    f"{module_id}: Analysis_Key must use lowercase letters/digits/hyphens"
                )
            folded_key = analysis_key.casefold()
            if folded_key in analysis_keys:
                raise WorkspaceError(
                    f"duplicate Analysis_Key {analysis_key!r}: "
                    f"{analysis_keys[folded_key]} and {module_id}; one analysis may have only one module entry"
                )
            analysis_keys[folded_key] = module_id
            row["Analysis_Key"] = analysis_key
            if row.get("Short_Name", "") and row["Short_Name"] != analysis_key:
                raise WorkspaceError(
                    f"{module_id}: Short_Name must equal stable Analysis_Key in layout v2"
                )
        else:
            row["Analysis_Key"] = ""
        row["Parent_Module"] = clean(row["Parent_Module"], "Parent_Module")
        row["Stage"] = clean(row["Stage"], "Stage", allow_empty=True)
        row["Short_Name"] = clean(row["Short_Name"], "Short_Name")
        row["Purpose"] = clean(row["Purpose"], "Purpose")
        row["Owner"] = clean(row["Owner"], "Owner")
        row["Notes"] = clean(row["Notes"], "Notes", allow_empty=True)
        if row["Module_Kind"] not in MODULE_KINDS:
            raise WorkspaceError(f"{module_id}: invalid Module_Kind {row['Module_Kind']!r}")
        if row["Compatibility"] not in MODULE_COMPATIBILITY:
            raise WorkspaceError(f"{module_id}: invalid Compatibility {row['Compatibility']!r}")
        if row["Compatibility"] == "Managed":
            if not STAGE_RE.fullmatch(row["Stage"]) or row["Stage"] == "00":
                raise WorkspaceError(f"{module_id}: managed Stage must be 01-99")
            if row["Module_Kind"] == "legacy":
                raise WorkspaceError(f"{module_id}: Managed module cannot have Module_Kind=legacy")
            validate_short_name(row["Stage"], row["Short_Name"], layout)
        else:
            if row["Module_Kind"] != "legacy":
                raise WorkspaceError(f"{module_id}: Legacy compatibility requires Module_Kind=legacy")
        row["_Depends"] = split_ids(row["Depends_On"], f"{module_id}.Depends_On")  # type: ignore[assignment]
        modules[module_id] = row

    for module_id, row in modules.items():
        parent = row["Parent_Module"]
        if parent != "ROOT" and parent not in modules:
            raise WorkspaceError(f"{module_id}: missing Parent_Module {parent}")
        if parent == module_id:
            raise WorkspaceError(f"{module_id}: module cannot parent itself")
        for dependency in row["_Depends"]:  # type: ignore[index]
            if dependency not in modules:
                raise WorkspaceError(f"{module_id}: missing dependency {dependency}")
            if dependency == module_id:
                raise WorkspaceError(f"{module_id}: module cannot depend on itself")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit_parent(module_id: str) -> None:
        if module_id in visiting:
            raise WorkspaceError(f"parent-module cycle includes {module_id}")
        if module_id in visited:
            return
        visiting.add(module_id)
        parent = modules[module_id]["Parent_Module"]
        if parent != "ROOT":
            visit_parent(parent)
        visiting.remove(module_id)
        visited.add(module_id)

    for module_id in modules:
        visit_parent(module_id)

    visiting.clear()
    visited.clear()

    def visit_dependency(module_id: str) -> None:
        if module_id in visiting:
            raise WorkspaceError(f"dependency DAG cycle includes {module_id}")
        if module_id in visited:
            return
        visiting.add(module_id)
        for dependency in modules[module_id]["_Depends"]:  # type: ignore[index]
            visit_dependency(dependency)
        visiting.remove(module_id)
        visited.add(module_id)

    for module_id in modules:
        visit_dependency(module_id)

    siblings: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in modules.values():
        if row["Compatibility"] == "Managed":
            siblings[row["Parent_Module"]].append(row)
    for parent, group in siblings.items():
        observed = sorted(int(row["Stage"]) for row in group)
        expected = list(range(1, len(group) + 1))
        if observed != expected:
            raise WorkspaceError(
                f"managed sibling stages under {parent} must be consecutive 01..{len(group):02d}; "
                f"observed={','.join(f'{value:02d}' for value in observed)}"
            )
        for row in group:
            for dependency in row["_Depends"]:  # type: ignore[index]
                dep = modules[dependency]
                if dep["Parent_Module"] == parent and dep["Compatibility"] == "Managed":
                    if int(dep["Stage"]) >= int(row["Stage"]):
                        raise WorkspaceError(
                            f"{row['Module_ID']}: sibling dependency {dependency} must have an earlier Stage"
                        )

    module_paths: dict[str, str] = {}

    def module_path(module_id: str) -> str:
        if module_id in module_paths:
            return module_paths[module_id]
        row = modules[module_id]
        segment = (
            f"{row['Stage']}{layout.module_separator}{row['Short_Name']}"
            if row["Compatibility"] == "Managed"
            else row["Short_Name"]
        )
        parent = row["Parent_Module"]
        value = segment if parent == "ROOT" else f"{module_path(parent)}/{segment}"
        module_paths[module_id] = value
        return value

    seen_module_paths: dict[str, str] = {}
    for module_id in modules:
        value = module_path(module_id)
        folded = value.casefold()
        if folded in seen_module_paths:
            raise WorkspaceError(
                f"module paths collide: {seen_module_paths[folded]} and {module_id} -> {value}"
            )
        seen_module_paths[folded] = module_id

    # Validate the combined structural-parent and scientific-dependency graph.
    topological_modules(modules)
    return modules, module_paths


def validate_routes(
    rows: list[dict[str, str]],
    modules: dict[str, dict[str, str]],
    module_paths: dict[str, str],
    layout: layout_contract.ProjectLayout = layout_contract.LEGACY_LAYOUT,
) -> dict[str, dict[str, str]]:
    if not rows:
        raise WorkspaceError("Workspace_Routes.tsv must contain at least one route")
    routes: dict[str, dict[str, str]] = {}
    seen_paths: dict[str, str] = {}
    for line_number, row in enumerate(rows, 2):
        route_id = row["Route_ID"]
        if not ROUTE_ID_RE.fullmatch(route_id):
            raise WorkspaceError(f"Workspace_Routes.tsv:{line_number}: invalid Route_ID {route_id!r}")
        if route_id in routes:
            raise WorkspaceError(f"duplicate Route_ID: {route_id}")
        if row["Module_ID"] not in modules:
            raise WorkspaceError(f"{route_id}: unknown Module_ID {row['Module_ID']}")
        if row["Path_Type"] not in PATH_TYPES:
            raise WorkspaceError(f"{route_id}: invalid Path_Type {row['Path_Type']!r}")
        if row["Path_Role"] not in PATH_ROLES:
            raise WorkspaceError(f"{route_id}: invalid Path_Role {row['Path_Role']!r}")
        if row["Retention"] not in RETENTION_VALUES:
            raise WorkspaceError(f"{route_id}: invalid Retention {row['Retention']!r}")
        if row["Required"] not in REQUIRED_VALUES:
            raise WorkspaceError(f"{route_id}: Required must be Yes or No")
        if row["Compatibility"] not in ROUTE_COMPATIBILITY:
            raise WorkspaceError(f"{route_id}: invalid Compatibility {row['Compatibility']!r}")
        if any(character in row["Relative_Path"] for character in "*?[]{}"):
            raise WorkspaceError(f"{route_id}: glob syntax is forbidden in Relative_Path")
        try:
            relative = pm.clean_relative(row["Relative_Path"], f"{route_id}.Relative_Path")
        except pm.PathManagerError as exc:
            raise WorkspaceError(str(exc)) from exc
        relative_text = relative.as_posix()
        row["Relative_Path"] = relative_text
        root = relative.parts[0]
        canonical_roots = set(layout.canonical_dirs)
        if root not in canonical_roots:
            raise WorkspaceError(f"{route_id}: route must stay under a canonical project root")
        role_roots = ROLE_ROOT_V2 if layout.is_v2 else ROLE_ROOT_V1
        expected_root = role_roots[row["Path_Role"]]
        if row["Compatibility"] == "Managed" and root != expected_root:
            raise WorkspaceError(
                f"{route_id}: role {row['Path_Role']} must be under {expected_root}/, not {root}/"
            )
        if row["Path_Type"] == "Artifact" and relative.name in {"", "."}:
            raise WorkspaceError(f"{route_id}: Artifact must identify an exact file path")
        if layout.is_v2 and root == "tmp" and row["Path_Role"] != "Temporary":
            raise WorkspaceError(f"{route_id}: tmp/ may only use the Temporary role")
        folded = relative_text.casefold()
        if folded in seen_paths:
            raise WorkspaceError(
                f"duplicate/case-colliding route paths: {seen_paths[folded]} and {route_id}"
            )
        seen_paths[folded] = route_id
        row["_Producer"] = split_ids(row["Producer_Tasks"], f"{route_id}.Producer_Tasks")  # type: ignore[assignment]
        row["_Consumer"] = split_ids(row["Consumer_Tasks"], f"{route_id}.Consumer_Tasks")  # type: ignore[assignment]
        row["Purpose"] = clean(row["Purpose"], f"{route_id}.Purpose")
        row["Notes"] = clean(row["Notes"], f"{route_id}.Notes", allow_empty=True)

        module = modules[row["Module_ID"]]
        if module["Compatibility"] == "Legacy" and row["Compatibility"] == "Managed":
            raise WorkspaceError(f"{route_id}: a Legacy module cannot own a Managed route")
        if row["Compatibility"] == "Managed":
            after_root_path = Path(*relative.parts[1:])
            owned_path = after_root_path if row["Path_Type"] == "Directory" else after_root_path.parent
            owned_text = owned_path.as_posix()
            module_prefix = module_paths[row["Module_ID"]]
            manuscript_exception = layout.is_v2 and row["Path_Role"] == "Manuscript"
            if manuscript_exception:
                if (
                    modules[row["Module_ID"]]["Module_Kind"] != "publication"
                    or row["Path_Type"] != "Directory"
                    or len(relative.parts) != 2
                    or not MANUSCRIPT_DIR_RE.fullmatch(relative.parts[1])
                ):
                    raise WorkspaceError(
                        f"{route_id}: Manuscript directory must be manuscripts/PNN-short-name "
                        "owned by a publication module"
                    )
            elif owned_text != module_prefix and not owned_text.startswith(module_prefix + "/"):
                raise WorkspaceError(
                    f"{route_id}: managed {row['Path_Type'].lower()} must follow module path "
                    f"{root}/{module_prefix}"
                )
            if layout.is_v2 and root == "results":
                tail = Path(owned_text).relative_to(Path(module_prefix)).parts
                version_positions = [index for index, part in enumerate(tail) if re.match(r"^[Vv][0-9]", part)]
                for position in version_positions:
                    version = tail[position]
                    if position == 0 or tail[position - 1] != "versions" or not VERSION_DIR_RE.fullmatch(version):
                        raise WorkspaceError(
                            f"{route_id}: retained versions must use {root}/{module_prefix}/versions/VNN"
                        )
            if layout.is_v2 and row["Path_Role"] == "Figure":
                if row["Path_Type"] != "Directory":
                    raise WorkspaceError(f"{route_id}: a managed Figure route must identify one figure-package directory")
                tail = Path(relative_text).relative_to(Path(root) / module_prefix).parts
                if len(tail) != 2 or tail[0] != "figures" or not FIGURE_PACKAGE_RE.fullmatch(tail[1]):
                    raise WorkspaceError(
                        f"{route_id}: Figure directory must be {root}/{module_prefix}/figures/FNNN_Name"
                    )
        routes[route_id] = row

    for route_id, row in routes.items():
        if row["Compatibility"] != "Managed":
            continue
        relative = Path(row["Relative_Path"])
        if row["Path_Type"] == "Directory":
            parent = relative.parent.as_posix()
            if parent not in set(layout.canonical_dirs):
                parent_routes = [
                    candidate
                    for candidate in routes.values()
                    if candidate["Path_Type"] == "Directory"
                    and candidate["Relative_Path"] == parent
                ]
                if not parent_routes:
                    raise WorkspaceError(f"{route_id}: parent directory is neither canonical nor planned: {parent}")
                if parent_routes[0]["Compatibility"] != "Managed":
                    raise WorkspaceError(f"{route_id}: managed directory requires a managed parent route: {parent}")
            continue
        covered = False
        for directory in routes.values():
            if (
                directory["Path_Type"] == "Directory"
                and directory["Compatibility"] == "Managed"
                and directory["Module_ID"] == row["Module_ID"]
            ):
                try:
                    relative.relative_to(Path(directory["Relative_Path"]))
                except ValueError:
                    continue
                covered = True
                break
        if not covered:
            raise WorkspaceError(
                f"{route_id}: managed artifact must be below a managed Directory route owned by "
                f"module {row['Module_ID']}"
            )

    role_sets: dict[str, set[str]] = defaultdict(set)
    directory_count: Counter[str] = Counter()
    for row in routes.values():
        if row["Path_Type"] == "Directory" and row["Compatibility"] == "Managed":
            role_sets[row["Module_ID"]].add(row["Path_Role"])
            directory_count[row["Module_ID"]] += 1
    required_by_kind = {
        "analysis": {"Script", "Log", "Temporary", "Result"},
        "publication": (
            {"Script", "Plot_Data", "Figure", "Manuscript"}
            if layout.is_v2 else {"Script", "Plot_Data", "Figure", "Report"}
        ),
        "management": {"Config", "Report"},
    }
    for module_id, module in modules.items():
        if module["Compatibility"] != "Managed":
            continue
        kind = module["Module_Kind"]
        if kind == "group" and directory_count[module_id] == 0:
            raise WorkspaceError(f"{module_id}: group module requires at least one managed Directory route")
        missing = required_by_kind.get(kind, set()) - role_sets[module_id]
        if missing:
            raise WorkspaceError(f"{module_id}: {kind} module missing Directory roles: {','.join(sorted(missing))}")
        if layout.is_v2 and kind == "publication":
            manuscript_routes = [
                row for row in routes.values()
                if row["Module_ID"] == module_id
                and row["Path_Type"] == "Directory"
                and row["Path_Role"] == "Manuscript"
                and row["Compatibility"] == "Managed"
            ]
            if len(manuscript_routes) != 1:
                raise WorkspaceError(
                    f"{module_id}: publication module requires exactly one Manuscript directory route"
                )

    if layout.is_v2:
        for module_id, module in modules.items():
            if module["Compatibility"] != "Managed" or module["Module_Kind"] not in {"analysis", "publication"}:
                continue
            expected = f"results/{module_paths[module_id]}"
            roots = [
                row for row in routes.values()
                if row["Module_ID"] == module_id
                and row["Path_Type"] == "Directory"
                and row["Compatibility"] == "Managed"
                and row["Relative_Path"] == expected
                and row["Path_Role"] in {"Result", "Plot_Data"}
            ]
            if len(roots) != 1:
                raise WorkspaceError(
                    f"{module_id}: Analysis_Key={module['Analysis_Key']} requires exactly one retained "
                    f"results entry at {expected}"
                )
    return routes


def canonical_rows(columns: tuple[str, ...], rows: Iterable[dict[str, str]], id_column: str) -> str:
    public_rows = [{column: row.get(column, "") for column in columns} for row in rows]
    public_rows.sort(key=lambda row: row[id_column])
    return render_tsv(columns, public_rows)


def plan_sha256(
    modules: dict[str, dict[str, str]],
    routes: dict[str, dict[str, str]],
    layout: layout_contract.ProjectLayout = layout_contract.LEGACY_LAYOUT,
) -> str:
    columns = MODULE_COLUMNS_V2 if layout.is_v2 else MODULE_COLUMNS
    content = (
        canonical_rows(columns, modules.values(), "Module_ID")
        + "\0"
        + canonical_rows(ROUTE_COLUMNS, routes.values(), "Route_ID")
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def load_workspace(project: Path) -> tuple[dict[str, str], dict[str, dict[str, str]], dict[str, str], dict[str, dict[str, str]], str]:
    paths = workspace_paths(project)
    try:
        layout = layout_contract.detect_layout(project)
        config = safe_inside(project, "config", "workspace config directory")
        if not config.is_dir():
            raise WorkspaceError(f"workspace config directory must exist: {config}")
        policy = read_policy(project)
        module_columns = MODULE_COLUMNS_V2 if layout.is_v2 else MODULE_COLUMNS
        module_rows = read_exact_tsv(paths["modules"], module_columns, "Workspace_Modules.tsv")
        route_rows = read_exact_tsv(paths["routes"], ROUTE_COLUMNS, "Workspace_Routes.tsv")
    except (WorkspaceError, layout_contract.LayoutError) as exc:
        raise WorkspaceError(f"[WS001] schema/contract error: {exc}") from exc
    try:
        modules, module_paths = validate_modules(module_rows, layout)
    except WorkspaceError as exc:
        raise WorkspaceError(f"[WS002] module tree/DAG/stage error: {exc}") from exc
    try:
        routes = validate_routes(route_rows, modules, module_paths, layout)
    except WorkspaceError as exc:
        raise WorkspaceError(f"[WS003] route/root/path error: {exc}") from exc
    fingerprint = plan_sha256(modules, routes, layout)
    return policy, modules, module_paths, routes, fingerprint


def topological_modules(modules: dict[str, dict[str, str]]) -> list[str]:
    children: dict[str, list[str]] = defaultdict(list)
    indegree = {module_id: 0 for module_id in modules}
    for module_id, row in modules.items():
        prerequisites = set(row["_Depends"])  # type: ignore[arg-type,index]
        if row["Parent_Module"] != "ROOT":
            prerequisites.add(row["Parent_Module"])
        for dependency in sorted(prerequisites):
            children[dependency].append(module_id)
            indegree[module_id] += 1
    ready = sorted(
        (module_id for module_id, degree in indegree.items() if degree == 0),
        key=lambda item: (modules[item]["Parent_Module"], modules[item]["Stage"], item),
    )
    ordered: list[str] = []
    while ready:
        module_id = ready.pop(0)
        ordered.append(module_id)
        for child in sorted(children[module_id]):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
                ready.sort(key=lambda item: (modules[item]["Parent_Module"], modules[item]["Stage"], item))
    if len(ordered) != len(modules):
        raise WorkspaceError("combined parent/dependency graph cannot be topologically sorted")
    return ordered


def output_payload(format_name: str, *, columns: tuple[str, ...], rows: list[dict[str, Any]], text: str, json_payload: Any) -> None:
    if format_name == "tsv":
        write_tsv(columns, rows)
    elif format_name == "json":
        print(json.dumps(json_payload, indent=2, sort_keys=True))
    else:
        print(text)


def run_bootstrap(args: argparse.Namespace) -> int:
    project = pm.resolve_project(args.project)
    config = project / "config"
    if not config.exists() or not config.is_dir() or config.is_symlink():
        raise WorkspaceError(f"project config directory must be an existing non-symlink directory: {config}")
    template_dir = SCRIPT_DIR.parent / "assets" / "project-templates"
    paths = workspace_paths(project)
    try:
        layout = layout_contract.detect_layout(project)
    except layout_contract.LayoutError as exc:
        raise WorkspaceError(str(exc)) from exc
    sources = {
        "policy": template_dir / ("Workspace_Policy_v2.tsv" if layout.is_v2 else "Workspace_Policy.tsv"),
        "modules": template_dir / ("Workspace_Modules_v2.tsv" if layout.is_v2 else "Workspace_Modules.tsv"),
        "routes": template_dir / "Workspace_Routes.tsv",
    }
    actions: list[dict[str, str]] = []
    for key in ("policy", "modules", "routes"):
        source, target = sources[key], paths[key]
        if not source.is_file():
            raise WorkspaceError(f"workspace template missing: {source}")
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise WorkspaceError(f"workspace contract target must be a regular non-symlink file: {target}")
        actions.append({"Mode": "WRITE" if args.yes else "DRY_RUN", "Action": "EXISTS" if target.exists() else "CREATE_FILE", "Path": str(target)})
    write_tsv(("Mode", "Action", "Path"), actions)
    if not args.yes:
        return 0
    lock_handle = open_project_lock(project)
    created: list[Path] = []
    try:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise WorkspaceError(f"workspace writer lock is already held: {paths['lock']}") from exc
        try:
            for key in ("policy", "modules", "routes"):
                target = paths[key]
                if target.exists():
                    continue
                data = sources[key].read_bytes()
                descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                created.append(target)
        except Exception:
            for target in reversed(created):
                target.unlink(missing_ok=True)
            raise
    finally:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        finally:
            lock_handle.close()
    return 0


def observed_role(path: Path, entry_type: str) -> str:
    name = path.name.lower()
    if entry_type == "File":
        if name.endswith((".out", ".err", ".log")):
            return "Log"
        if name.endswith((".slurm", ".sbatch")):
            return "Script"
        if name.endswith((".md", ".pdf")):
            return "Report"
        if name.endswith((".png", ".jpg", ".jpeg", ".svg")):
            return "Figure"
        if name.endswith((".tsv", ".csv")):
            return "Table"
        return "Unknown"
    if name in {"tmp", "temp", "intermediate", "intermediates"}:
        return "Temporary"
    if name in {"docs", "doc", "reports", "report"}:
        return "Report"
    if name in {"figures", "figure", "plots"}:
        return "Figure"
    if name in {"qc", "quality_control"}:
        return "QC"
    return "Unknown"


def inventory(project: Path, max_depth: int) -> list[dict[str, str]]:
    if not 1 <= max_depth <= MAX_AUDIT_DEPTH:
        raise WorkspaceError(f"--max-depth must be between 1 and {MAX_AUDIT_DEPTH}")
    safe_inside(project, "config/Directory_Index.tsv", "Directory_Index.tsv")
    try:
        _, index_rows = pm.load_index(project)
    except pm.PathManagerError as exc:
        raise WorkspaceError(str(exc)) from exc
    indexed = {row["Relative_Path"]: row for row in index_rows}
    try:
        layout = layout_contract.detect_layout(project)
    except layout_contract.LayoutError as exc:
        raise WorkspaceError(str(exc)) from exc
    pruned_roots = {layout.rawdata_root, "logs", "tmp"}
    rows: list[dict[str, str]] = []

    def visit(parent: Path, depth: int) -> None:
        if depth >= max_depth:
            return
        try:
            children = sorted(parent.iterdir(), key=lambda item: (item.name.casefold(), item.name))
        except OSError as exc:
            raise WorkspaceError(f"cannot list directory {parent}: {exc}") from exc
        for child in children:
            if child.name.startswith(".") or child.name in PRUNE_NAMES:
                continue
            relative = child.relative_to(project).as_posix()
            if child.is_symlink():
                entry_type = "Symlink"
            elif child.is_dir():
                entry_type = "Directory"
            elif child.is_file():
                entry_type = "File"
            else:
                entry_type = "Other"
            index = indexed.get(relative)
            rows.append({
                "Relative_Path": relative,
                "Entry_Type": entry_type,
                "Depth": str(depth + 1),
                "Observed_Role": observed_role(child, entry_type),
                "Index_Status": index["Directory_Kind"] if index else "Unregistered",
                "Status": "EXEMPT" if entry_type == "Symlink" else "INFO",
                "Rule_ID": "WS013" if entry_type == "Symlink" else "OK",
                "Detail": "symbolic link not followed" if entry_type == "Symlink" else "bounded inventory evidence only",
            })
            if len(rows) > MAX_INVENTORY_ENTRIES:
                raise WorkspaceError(f"inventory exceeds hard cap of {MAX_INVENTORY_ENTRIES} entries")
            if entry_type != "Directory":
                continue
            if depth == 0 and child.name in pruned_roots:
                continue
            visit(child, depth + 1)

    visit(project, 0)
    return rows


def run_inspect(args: argparse.Namespace) -> int:
    project = pm.resolve_project(args.project)
    rows = inventory(project, args.max_depth)
    counts = dict(Counter(row["Entry_Type"] for row in rows))
    text = "\n".join([
        f"[INFO] Project: {project}",
        f"[INFO] Bounded_depth: {args.max_depth}",
        f"[INFO] Entries: {len(rows)} | " + " | ".join(f"{key}={counts[key]}" for key in sorted(counts)),
        "[INFO] No biological role or dependency was inferred.",
    ])
    output_payload(args.format, columns=INVENTORY_COLUMNS, rows=rows, text=text, json_payload={"Project": str(project), "Max_depth": args.max_depth, "Counts": counts, "Entries": rows})
    return 0


def plan_rows(fingerprint: str, modules: dict[str, dict[str, str]], module_paths: dict[str, str], routes: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    by_module: dict[str, list[dict[str, str]]] = defaultdict(list)
    for route in routes.values():
        by_module[route["Module_ID"]].append(route)
    rows: list[dict[str, str]] = []
    for module_id in topological_modules(modules):
        module = modules[module_id]
        module_routes = sorted(by_module[module_id], key=lambda row: row["Route_ID"])
        if not module_routes:
            module_routes = [{column: "" for column in ROUTE_COLUMNS}]
        for route in module_routes:
            rows.append({
                "Plan_SHA256": fingerprint,
                "Module_ID": module_id,
                "Analysis_Key": module.get("Analysis_Key", "NA") or "NA",
                "Parent_Module": module["Parent_Module"],
                "Stage": module["Stage"],
                "Module_Path": module_paths[module_id],
                "Module_Kind": module["Module_Kind"],
                "Depends_On": module["Depends_On"],
                "Route_ID": route.get("Route_ID", ""),
                "Path_Type": route.get("Path_Type", ""),
                "Path_Role": route.get("Path_Role", ""),
                "Relative_Path": route.get("Relative_Path", ""),
                "Required": route.get("Required", ""),
                "Compatibility": route.get("Compatibility", module["Compatibility"]),
            })
    return rows


def plan_text(project: Path, policy: dict[str, str], modules: dict[str, dict[str, str]], module_paths: dict[str, str], routes: dict[str, dict[str, str]], fingerprint: str) -> str:
    children: dict[str, list[str]] = defaultdict(list)
    for module_id, row in modules.items():
        children[row["Parent_Module"]].append(module_id)
    lines = [
        f"[INFO] Project: {project}",
        f"[INFO] Policy: {policy['Plan_Status']} | Stored_SHA256={policy['Plan_SHA256'] or 'NA'}",
        f"[INFO] Plan_SHA256: {fingerprint}",
        f"[INFO] Modules: {len(modules)} | Routes: {len(routes)}",
        "[TREE]",
    ]

    def render(parent: str, depth: int) -> None:
        for module_id in sorted(children[parent], key=lambda item: (modules[item]["Stage"], item)):
            row = modules[module_id]
            route_count = sum(1 for route in routes.values() if route["Module_ID"] == module_id)
            lines.append(f"{'  ' * depth}- {module_id} | {module_paths[module_id]} | {row['Module_Kind']} | routes={route_count} | depends={row['Depends_On'] or 'NA'}")
            render(module_id, depth + 1)

    render("ROOT", 0)
    return "\n".join(lines)


def run_plan(args: argparse.Namespace) -> int:
    project = pm.resolve_project(args.project)
    policy, modules, module_paths, routes, fingerprint = load_workspace(project)
    rows = plan_rows(fingerprint, modules, module_paths, routes)
    output_payload(
        args.format,
        columns=PLAN_COLUMNS,
        rows=rows,
        text=plan_text(project, policy, modules, module_paths, routes, fingerprint),
        json_payload={"Project": str(project), "Policy": policy, "Plan_SHA256": fingerprint, "Modules": rows},
    )
    return 0


def run_route(args: argparse.Namespace) -> int:
    project = pm.resolve_project(args.project)
    _, modules, _, routes, _ = load_workspace(project)
    if args.module not in modules:
        raise WorkspaceError(f"unknown module: {args.module}")
    matches = [
        {column: row[column] for column in ROUTE_OUTPUT_COLUMNS}
        for row in routes.values()
        if row["Module_ID"] == args.module
        and row["Path_Role"] == args.role
        and (args.path_type is None or row["Path_Type"] == args.path_type)
    ]
    matches.sort(key=lambda row: row["Route_ID"])
    if not matches:
        raise WorkspaceError(f"no route matches module={args.module} role={args.role} path_type={args.path_type or 'ANY'}")
    if len(matches) > 1:
        raise WorkspaceError(f"ambiguous route ({len(matches)} matches); select a unique role/path type in the plan")
    if args.format == "json":
        print(json.dumps(matches[0], indent=2, sort_keys=True))
    else:
        write_tsv(ROUTE_OUTPUT_COLUMNS, matches)
    return 0


def latest_task_rows(project: Path) -> tuple[dict[str, dict[str, str]], list[str]]:
    try:
        layout = layout_contract.detect_layout(project)
        relative = layout_contract.control_relative(layout, "task_status")
    except layout_contract.LayoutError as exc:
        raise WorkspaceError(str(exc)) from exc
    path = safe_inside(project, relative, "Task_Status.tsv")
    if not path.exists():
        return {}, []
    required = (
        "Task_ID", "Stage", "Sample_ID", "Status", "Job_ID", "Dependency",
        "Script_Path", "Log_Path", "Output_Path", "Acceptance_Path", "Retry_Count", "Updated_Time",
    )
    rows = read_exact_tsv(path, required, "Task_Status.tsv")
    latest: dict[str, dict[str, str]] = {}
    order: list[str] = []
    for row in rows:
        task_id = clean(row["Task_ID"], "Task_ID")
        if not TASK_ID_RE.fullmatch(task_id):
            raise WorkspaceError(f"Task_Status.tsv contains invalid Task_ID: {task_id!r}")
        if task_id not in latest:
            order.append(task_id)
        latest[task_id] = row
    return latest, order


def workflow_stage(project: Path) -> str:
    try:
        layout = layout_contract.detect_layout(project)
        relative = layout_contract.control_relative(layout, "workflow_status")
    except layout_contract.LayoutError as exc:
        raise WorkspaceError(str(exc)) from exc
    path = safe_inside(project, relative, "workflow_status.tsv")
    if not path.exists():
        return "NA"
    columns = ("Stage", "Status", "Evidence_Path", "Job_ID", "Exit_Code", "Input_Path", "Output_Path", "Next_Action", "Updated_Time")
    rows = read_exact_tsv(path, columns, "workflow_status.tsv")
    return rows[-1]["Stage"] if rows else "NA"


def relative_from_explicit(project: Path, value: str, label: str) -> str:
    value = clean(value, label)
    path = Path(value).expanduser()
    if path.is_absolute():
        normalized = path.resolve(strict=False)
        if not pm.is_within(normalized, project):
            raise WorkspaceError(f"{label} is outside project: {value}")
        relative = normalized.relative_to(project)
    else:
        try:
            relative = pm.clean_relative(value, label)
        except pm.PathManagerError as exc:
            raise WorkspaceError(str(exc)) from exc
    try:
        pm.resolve_inside(project, relative, label)
    except pm.PathManagerError as exc:
        raise WorkspaceError(str(exc)) from exc
    return relative.as_posix()


def route_covers(route: dict[str, str], relative: str) -> bool:
    route_path = Path(route["Relative_Path"])
    candidate = Path(relative)
    if route["Path_Type"] == "Artifact":
        return candidate.as_posix().casefold() == route_path.as_posix().casefold()
    try:
        candidate.relative_to(route_path)
    except ValueError:
        return False
    return True


def matching_routes(routes: dict[str, dict[str, str]], relative: str, *, module_id: str | None = None, roles: set[str] | None = None) -> list[dict[str, str]]:
    result = []
    for route in routes.values():
        if module_id is not None and route["Module_ID"] != module_id:
            continue
        if roles is not None and route["Path_Role"] not in roles:
            continue
        if route_covers(route, relative):
            result.append(route)
    return sorted(result, key=lambda row: (len(Path(row["Relative_Path"]).parts), row["Route_ID"]), reverse=True)


def finding(status: str, rule_id: str, detail: str, *, relative: str = "NA", module_id: str = "NA", route_id: str = "NA") -> dict[str, str]:
    return {"Status": status, "Rule_ID": rule_id, "Relative_Path": relative, "Module_ID": module_id, "Route_ID": route_id, "Detail": detail}


def audit_workspace(project: Path, max_depth: int | None = None) -> tuple[list[dict[str, str]], dict[str, Any]]:
    try:
        layout = layout_contract.detect_layout(project)
    except layout_contract.LayoutError as exc:
        raise WorkspaceError(str(exc)) from exc
    policy, modules, _, routes, fingerprint = load_workspace(project)
    depth = max_depth if max_depth is not None else int(policy["Max_Audit_Depth"])
    entries = inventory(project, depth)
    findings: list[dict[str, str]] = []
    if policy["Plan_Status"] != "Reviewed":
        findings.append(finding("BLOCK", "WS004", "workspace plan is Draft; managed execution is not approved"))
    elif policy["Plan_SHA256"] != fingerprint:
        findings.append(finding("BLOCK", "WS004", "workspace plan fingerprint drifted after review"))

    canonical_roots = set(layout.canonical_dirs)
    for root in sorted(canonical_roots):
        root_path = project / root
        if root_path.is_symlink():
            findings.append(finding("BLOCK", "WS013", "canonical project root is a symbolic link", relative=root))
        elif not root_path.is_dir():
            findings.append(finding("BLOCK", "WS005", "canonical project root is missing or not a directory", relative=root))

    try:
        _, index_rows = pm.load_index(project)
    except pm.PathManagerError as exc:
        raise WorkspaceError(str(exc)) from exc
    index = {row["Relative_Path"]: row for row in index_rows}
    route_by_path = {row["Relative_Path"]: row for row in routes.values()}

    for route in sorted(routes.values(), key=lambda row: row["Route_ID"]):
        relative = route["Relative_Path"]
        try:
            target = safe_inside(project, relative, f"route {route['Route_ID']}")
        except WorkspaceError as exc:
            findings.append(finding("BLOCK", "WS013", str(exc), relative=relative, module_id=route["Module_ID"], route_id=route["Route_ID"]))
            continue
        if route["Path_Type"] == "Directory":
            if route["Compatibility"] == "Managed" and route["Required"] == "Yes" and not target.is_dir():
                findings.append(finding("BLOCK", "WS005", "required managed directory is missing", relative=relative, module_id=route["Module_ID"], route_id=route["Route_ID"]))
            if target.is_dir() and relative not in index:
                status = "BLOCK" if route["Compatibility"] == "Managed" else "WARN"
                rule = "WS011" if route["Compatibility"] == "Managed" else ("WS007" if route["Compatibility"] == "Legacy" else "WS008")
                findings.append(finding(status, rule, "planned directory is not registered in Directory_Index.tsv", relative=relative, module_id=route["Module_ID"], route_id=route["Route_ID"]))
            if route["Compatibility"] == "Legacy":
                findings.append(finding("WARN", "WS007", "legacy route is advisory and is not auto-migrated", relative=relative, module_id=route["Module_ID"], route_id=route["Route_ID"]))
            elif route["Compatibility"] == "Tool_managed":
                findings.append(finding("EXEMPT", "WS008", "tool-managed route is layout-exempt but remains boundary-checked", relative=relative, module_id=route["Module_ID"], route_id=route["Route_ID"]))

    latest_tasks, _ = latest_task_rows(project)
    for route in routes.values():
        status = "WARN" if route["Compatibility"] == "Legacy" else "BLOCK"
        for task_id in route["_Producer"]:  # type: ignore[index]
            task = latest_tasks.get(task_id)
            if task is None:
                findings.append(finding(status, "WS012", f"Producer_Tasks references unknown Task_ID {task_id}", relative=route["Relative_Path"], module_id=route["Module_ID"], route_id=route["Route_ID"]))
            elif task["Stage"] != route["Module_ID"]:
                findings.append(finding(status, "WS012", f"producer task {task_id} belongs to {task['Stage']}, not route module {route['Module_ID']}", relative=route["Relative_Path"], module_id=route["Module_ID"], route_id=route["Route_ID"]))
        for task_id in route["_Consumer"]:  # type: ignore[index]
            if task_id not in latest_tasks:
                findings.append(finding(status, "WS012", f"Consumer_Tasks references unknown Task_ID {task_id}", relative=route["Relative_Path"], module_id=route["Module_ID"], route_id=route["Route_ID"]))

    delivered = workflow_stage(project) in DELIVERED_WORKFLOW_STAGES
    for route in routes.values():
        if route["Path_Type"] != "Artifact" or route["Required"] != "Yes":
            continue
        try:
            target = safe_inside(project, route["Relative_Path"], f"route {route['Route_ID']}")
        except WorkspaceError:
            # The route-level WS013 finding above is the authoritative blocker.
            continue
        producers = route["_Producer"]  # type: ignore[index]
        producer_done = any(
            task_id in latest_tasks and latest_tasks[task_id]["Status"] in COMPLETED_TASK_STATUSES
            for task_id in producers
        )
        if not target.is_file() and (producer_done or delivered):
            findings.append(finding("BLOCK", "WS010", "required key artifact is missing after producer completion/delivery", relative=route["Relative_Path"], module_id=route["Module_ID"], route_id=route["Route_ID"]))

    if layout.is_v2:
        for route in routes.values():
            if route["Path_Type"] != "Directory" or route["Path_Role"] != "Figure":
                continue
            package = safe_inside(project, route["Relative_Path"], f"figure package {route['Route_ID']}")
            producers = route["_Producer"]  # type: ignore[index]
            producer_done = any(
                task_id in latest_tasks and latest_tasks[task_id]["Status"] in COMPLETED_TASK_STATUSES
                for task_id in producers
            )
            if not (producer_done or delivered):
                continue
            requirements = {
                "README.md": (package / "README.md").is_file(),
                "PDF": package.is_dir() and any(path.is_file() for path in package.glob("*.pdf")),
                "PNG": package.is_dir() and any(path.is_file() for path in package.glob("*.png")),
                "source-data TSV": (package / "source-data").is_dir() and any(
                    path.is_file() for path in (package / "source-data").glob("*.tsv")
                ),
                "checks Markdown": (package / "checks").is_dir() and any(
                    path.is_file() for path in (package / "checks").glob("*.md")
                ),
                "checks JSON": (package / "checks").is_dir() and any(
                    path.is_file() for path in (package / "checks").glob("*.json")
                ),
                "Figure_Index.tsv": (package.parent / "Figure_Index.tsv").is_file(),
            }
            missing = [name for name, present in requirements.items() if not present]
            if missing:
                findings.append(finding(
                    "BLOCK", "WS015",
                    "completed figure package is incomplete: " + ", ".join(missing),
                    relative=route["Relative_Path"], module_id=route["Module_ID"], route_id=route["Route_ID"],
                ))

    allowed_control = V2_CONTROL_PATHS if layout.is_v2 else CANONICAL_CONTROL_PATHS
    allowed_control = set(allowed_control)
    for relative in list(allowed_control):
        parent = Path(relative).parent
        while parent != Path("."):
            allowed_control.add(parent.as_posix())
            parent = parent.parent
    if layout.is_v2:
        allowed_control.update({"config/parameters", "config/environments", "docs/status", "docs/research-log", "docs/decisions", "docs/methods", "docs/validation", "docs/delivery"})
    for entry in entries:
        relative = entry["Relative_Path"]
        path = Path(relative)
        if entry["Entry_Type"] == "Directory":
            matches = [route for route in routes.values() if route["Relative_Path"].casefold() == relative.casefold()]
        else:
            matches = matching_routes(routes, relative)
        indexed_row = index.get(relative)
        if entry["Entry_Type"] == "Symlink":
            managed_control = relative in canonical_roots or relative in allowed_control
            status = "BLOCK" if managed_control or (matches and matches[0]["Compatibility"] == "Managed") else "WARN"
            findings.append(finding(status, "WS013", "symbolic link not followed", relative=relative, module_id=matches[0]["Module_ID"] if matches else "NA", route_id=matches[0]["Route_ID"] if matches else "NA"))
            continue
        if relative in canonical_roots or relative in allowed_control:
            continue
        if path.parent == Path(".") and path.name in ROOT_CONTROL_NAMES:
            continue
        strong_role = entry["Observed_Role"]
        if strong_role == "Log" and path.parts[0] != "logs":
            status = "WARN" if matches and matches[0]["Compatibility"] in {"Legacy", "Tool_managed"} else "BLOCK"
            findings.append(finding(status, "WS009", "log-like file is outside logs/", relative=relative))
        if strong_role == "Script" and path.parts[0] != "scripts":
            status = "WARN" if matches and matches[0]["Compatibility"] in {"Legacy", "Tool_managed"} else "BLOCK"
            findings.append(finding(status, "WS009", "SLURM script is outside scripts/", relative=relative))
        if matches:
            continue
        if indexed_row and indexed_row["Directory_Kind"] == "legacy":
            findings.append(finding("WARN", "WS007", "unplanned directory is explicitly registered as legacy", relative=relative))
            continue
        if indexed_row and indexed_row["Directory_Kind"] == "tool_managed":
            findings.append(finding("EXEMPT", "WS008", "unplanned directory is explicitly tool-managed", relative=relative))
            continue
        if path.parent == Path("."):
            findings.append(finding("BLOCK", "WS014", "unplanned project-root entry", relative=relative))
        else:
            findings.append(finding("BLOCK", "WS006", "path is outside every planned route", relative=relative))

    for relative, row in index.items():
        if relative in route_by_path:
            route = route_by_path[relative]
            expected_kind = "tool_managed" if route["Compatibility"] == "Tool_managed" else "legacy" if route["Compatibility"] == "Legacy" else None
            if expected_kind and row["Directory_Kind"] != expected_kind:
                findings.append(finding("BLOCK", "WS011", f"Directory_Index kind must be {expected_kind}", relative=relative, module_id=route["Module_ID"], route_id=route["Route_ID"]))
        elif row["Directory_Kind"] not in {"legacy", "tool_managed"}:
            findings.append(finding("BLOCK", "WS011", "managed Directory_Index row has no Workspace route", relative=relative))

    task_roles = {
        "Script_Path": {"Script"},
        "Log_Path": {"Log"},
        "Output_Path": {"Result", "QC", "Plot_Data", "Source_Table", "Figure", "Report", "Manuscript", "Acceptance", "Delivery"},
        "Acceptance_Path": {"Acceptance", "Delivery", "Report"},
    }
    for task_id, task in latest_tasks.items():
        module_id = task["Stage"]
        if module_id not in modules:
            findings.append(finding("BLOCK", "WS012", f"Task {task_id} references unknown module in Stage: {module_id}", module_id=module_id))
            continue
        for field, roles in task_roles.items():
            value = task[field].strip()
            if not value or value == "NA":
                continue
            try:
                relative = relative_from_explicit(project, value, f"Task_Status.{field}")
            except WorkspaceError as exc:
                findings.append(finding("BLOCK", "WS012", str(exc), relative=value, module_id=module_id))
                continue
            matches = matching_routes(routes, relative, module_id=module_id, roles=roles)
            if not matches:
                status = "WARN" if modules[module_id]["Compatibility"] == "Legacy" else "BLOCK"
                findings.append(finding(status, "WS012", f"Task {task_id} {field} is outside module routes", relative=relative, module_id=module_id))

    findings.sort(key=lambda row: (-SEVERITY[row["Status"]], row["Relative_Path"].casefold(), row["Rule_ID"], row["Detail"]))
    counts = Counter(row["Status"] for row in findings)
    overall = "BLOCK" if counts["BLOCK"] else "WARN" if counts["WARN"] else "PASS"
    summary = {
        "Status": overall,
        "Modules": len(modules),
        "Routes": len(routes),
        "Findings": len(findings),
        "Missing": sum(1 for row in findings if row["Rule_ID"] in {"WS005", "WS010"}),
        "Unplanned": sum(1 for row in findings if row["Rule_ID"] in {"WS006", "WS014"}),
        "Counts": {key: counts[key] for key in ("BLOCK", "WARN", "EXEMPT", "INFO")},
        "Plan_SHA256": fingerprint,
        "Plan_Status": policy["Plan_Status"],
    }
    return findings, summary


def workspace_summary(project: Path, max_depth: int | None = None) -> dict[str, Any]:
    """Read-only dashboard integration API."""
    findings, summary = audit_workspace(project, max_depth)
    return {**summary, "Findings_detail": findings}


def run_audit(args: argparse.Namespace) -> int:
    project = pm.resolve_project(args.project)
    findings, summary = audit_workspace(project, args.max_depth)
    text = "\n".join([
        f"[INFO] Project: {project}",
        f"[INFO] Workspace: {summary['Status']}",
        f"[INFO] Modules={summary['Modules']} Routes={summary['Routes']} Findings={summary['Findings']} BLOCK={summary['Counts']['BLOCK']} WARN={summary['Counts']['WARN']}",
    ] + [f"{row['Status']} | {row['Rule_ID']} | {row['Relative_Path']} | {row['Detail']}" for row in findings])
    output_payload(args.format, columns=AUDIT_COLUMNS, rows=findings, text=text, json_payload={"Project": str(project), "Summary": summary, "Findings": findings})
    return 2 if summary["Status"] == "BLOCK" else 1 if summary["Status"] == "WARN" else 0


def infer_index_spec(route: dict[str, str], modules: dict[str, dict[str, str]]) -> tuple[str, str, list[str]]:
    if route["Compatibility"] == "Tool_managed":
        return "tool_managed", "NA", []
    if route["Compatibility"] == "Legacy":
        return "legacy", "NA", []
    name = Path(route["Relative_Path"]).name
    match = re.match(r"^([0-9]{2})([_-])", name)
    if match:
        separator = match.group(2)
        parts = name.split(separator)
        return "stage", parts[0], parts[1:]
    return "result", "NA", re.split(r"[_-]", name)


def render_policy(row: dict[str, str]) -> str:
    return render_tsv(POLICY_COLUMNS, [row])


def atomic_write_text(path: Path, text: str) -> None:
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise WorkspaceError(f"atomic-write parent must be an existing non-symlink directory: {path.parent}")
    if path.is_symlink():
        raise WorkspaceError(f"atomic-write target must not be a symbolic link: {path}")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            os.fchmod(handle.fileno(), 0o644)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def restored_write(path: Path, data: bytes | None, mode: int | None = None) -> None:
    if data is None:
        path.unlink(missing_ok=True)
    else:
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".restore", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                if mode is not None:
                    os.fchmod(handle.fileno(), mode)
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def apply_actions(project: Path, modules: dict[str, dict[str, str]], routes: dict[str, dict[str, str]], index_rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[Path], list[dict[str, str]]]:
    actions: list[dict[str, str]] = []
    create_targets: list[Path] = []
    new_rows: list[dict[str, str]] = []
    working_rows = list(index_rows)
    indexed = {row["Relative_Path"]: row for row in index_rows}
    directory_routes = sorted(
        (row for row in routes.values() if row["Path_Type"] == "Directory"),
        key=lambda row: (len(Path(row["Relative_Path"]).parts), row["Relative_Path"].casefold(), row["Route_ID"]),
    )
    for route in directory_routes:
        relative = route["Relative_Path"]
        target = safe_inside(project, relative, f"planned directory {relative}")
        existing_index = indexed.get(relative)
        if target.exists() and not target.is_dir():
            raise WorkspaceError(f"planned directory collides with a non-directory: {relative}")
        if target.is_dir() and existing_index is None:
            if route["Compatibility"] == "Managed":
                raise WorkspaceError(f"existing managed path is unregistered; mark/adopt it explicitly first: {relative}")
        if not target.exists():
            if route["Compatibility"] != "Managed":
                actions.append({"Mode": "DRY_RUN", "Action": "SKIP_MISSING_EXCEPTION", "Route_ID": route["Route_ID"], "Relative_Path": relative, "Directory_ID": "NA", "Detail": f"{route['Compatibility']} paths are never created"})
                continue
            create_targets.append(target)
            action = "CREATE_DIR"
        else:
            action = "EXISTS"
        directory_id = existing_index["Directory_ID"] if existing_index else pm.next_directory_id(working_rows)
        if existing_index is None:
            kind, stage, tokens = infer_index_spec(route, modules)
            try:
                row = pm.make_index_row(
                    working_rows,
                    directory_id=directory_id,
                    relative=relative,
                    kind=kind,
                    stage=stage,
                    tokens=tokens,
                    purpose=route["Purpose"],
                    owner=modules[route["Module_ID"]]["Owner"],
                    status="Active",
                    notes=f"Workspace_Route={route['Route_ID']};Role={route['Path_Role']}",
                )
            except pm.PathManagerError as exc:
                raise WorkspaceError(str(exc)) from exc
            working_rows.append(row)
            new_rows.append(row)
            indexed[relative] = row
            if action == "EXISTS":
                action = "REGISTER_EXCEPTION" if route["Compatibility"] != "Managed" else "REGISTER_DIR"
        actions.append({"Mode": "DRY_RUN", "Action": action, "Route_ID": route["Route_ID"], "Relative_Path": relative, "Directory_ID": directory_id, "Detail": route["Purpose"]})
    return actions, create_targets, new_rows


def run_apply(args: argparse.Namespace) -> int:
    project = pm.resolve_project(args.project)
    policy, modules, _, routes, fingerprint = load_workspace(project)
    try:
        index_path, index_rows = pm.load_index(project)
    except pm.PathManagerError as exc:
        raise WorkspaceError(str(exc)) from exc
    if not index_path.parent.is_dir() or index_path.parent.is_symlink():
        raise WorkspaceError("config directory must be an existing non-symlink directory")
    actions, create_targets, new_rows = apply_actions(project, modules, routes, index_rows)
    actions.append({"Mode": "WRITE" if args.yes else "DRY_RUN", "Action": "REVIEW_POLICY", "Route_ID": "NA", "Relative_Path": "config/Workspace_Policy.tsv", "Directory_ID": "NA", "Detail": fingerprint})
    for action in actions:
        action["Mode"] = "WRITE" if args.yes else "DRY_RUN"
    write_tsv(APPLY_COLUMNS, actions)
    if not args.yes:
        return 0

    paths = workspace_paths(project)
    lock_handle = open_project_lock(project)
    try:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise WorkspaceError(f"workspace writer lock is already held: {paths['lock']}") from exc
        # Re-read under lock to close the validation/write race.
        policy, modules, _, routes, fingerprint = load_workspace(project)
        index_path, index_rows = pm.load_index(project)
        actions, create_targets, new_rows = apply_actions(project, modules, routes, index_rows)
        old_index = index_path.read_bytes() if index_path.exists() else None
        old_index_mode = stat.S_IMODE(index_path.stat().st_mode) if index_path.exists() else None
        old_policy = paths["policy"].read_bytes()
        old_policy_mode = stat.S_IMODE(paths["policy"].stat().st_mode)
        created: list[Path] = []
        try:
            for target in create_targets:
                parent = target.parent
                if not parent.is_dir() or parent.is_symlink():
                    raise WorkspaceError(f"planned parent does not exist safely: {parent}")
                target.mkdir()
                created.append(target)
            pm.atomic_write_index(index_path, index_rows + new_rows)
            reviewed = dict(policy)
            reviewed["Plan_Status"] = "Reviewed"
            reviewed["Plan_SHA256"] = fingerprint
            reviewed["Updated_Time"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
            atomic_write_text(paths["policy"], render_policy(reviewed))
        except Exception:
            restored_write(index_path, old_index, old_index_mode)
            restored_write(paths["policy"], old_policy, old_policy_mode)
            for target in reversed(created):
                try:
                    target.rmdir()
                except OSError as rollback_error:
                    sys.stderr.write(f"[WARN] failed to roll back newly created empty directory {target}: {rollback_error}\n")
            raise
    finally:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        finally:
            lock_handle.close()
    return 0


def preflight_check(
    project: Path,
    module_id: str,
    task_id: str,
    paths_by_type: list[tuple[str, str, set[str]]],
) -> tuple[list[dict[str, str]], int]:
    _, modules, _, routes, _ = load_workspace(project)
    rows: list[dict[str, str]] = []
    audit_findings, _ = audit_workspace(project)
    for item in audit_findings:
        if item["Status"] != "BLOCK":
            continue
        rows.append({
            "Status": "BLOCK",
            "Rule_ID": item["Rule_ID"],
            "Path_Type": "Workspace_Audit",
            "Path": item["Relative_Path"],
            "Route_ID": item["Route_ID"],
            "Detail": item["Detail"],
        })
    if module_id not in modules:
        rows.append({"Status": "BLOCK", "Rule_ID": "WS002", "Path_Type": "Module", "Path": module_id, "Route_ID": "NA", "Detail": "unknown Module_ID"})
        return rows, 2
    latest, _ = latest_task_rows(project)
    task = latest.get(task_id)
    declared_script: str | None = None
    if task is None:
        rows.append({"Status": "BLOCK", "Rule_ID": "WS012", "Path_Type": "Task", "Path": task_id, "Route_ID": "NA", "Detail": "Task_ID is not registered in Task_Status.tsv"})
    else:
        if task["Stage"] != module_id:
            rows.append({"Status": "BLOCK", "Rule_ID": "WS012", "Path_Type": "Task", "Path": task_id, "Route_ID": "NA", "Detail": f"Task_Status.Stage={task['Stage']} does not match {module_id}"})
        script_value = task["Script_Path"].strip()
        if not script_value or script_value.upper() in {"NA", "N/A", "NONE", "NULL"}:
            rows.append({"Status": "BLOCK", "Rule_ID": "WS012", "Path_Type": "Task", "Path": task_id, "Route_ID": "NA", "Detail": "registered task must declare Script_Path"})
        else:
            try:
                declared_script = relative_from_explicit(project, script_value, "Task_Status.Script_Path")
            except WorkspaceError as exc:
                rows.append({"Status": "BLOCK", "Rule_ID": "WS012", "Path_Type": "Task", "Path": script_value, "Route_ID": "NA", "Detail": str(exc)})

    for path_type, value, roles in paths_by_type:
        try:
            relative = relative_from_explicit(project, value, path_type)
        except WorkspaceError as exc:
            rows.append({"Status": "BLOCK", "Rule_ID": "WS003", "Path_Type": path_type, "Path": value, "Route_ID": "NA", "Detail": str(exc)})
            continue
        if path_type == "Script" and declared_script is not None and relative != declared_script:
            rows.append({"Status": "BLOCK", "Rule_ID": "WS012", "Path_Type": path_type, "Path": relative, "Route_ID": "NA", "Detail": f"script path does not match Task_Status.Script_Path={declared_script}"})
            continue
        matches = matching_routes(routes, relative, module_id=module_id, roles=roles)
        if not matches:
            rows.append({"Status": "BLOCK", "Rule_ID": "WS012", "Path_Type": path_type, "Path": relative, "Route_ID": "NA", "Detail": "path is outside allowed module routes"})
            continue
        route = matches[0]
        producers = route["_Producer"]  # type: ignore[index]
        if producers and task_id not in producers:
            rows.append({"Status": "BLOCK", "Rule_ID": "WS012", "Path_Type": path_type, "Path": relative, "Route_ID": route["Route_ID"], "Detail": f"Task_ID is not an allowed producer ({route['Producer_Tasks']})"})
            continue
        if route["Compatibility"] == "Legacy":
            status, rule, detail = "WARN", "WS007", "legacy route allowed with warning"
        elif route["Compatibility"] == "Tool_managed":
            status, rule, detail = "EXEMPT", "WS008", "tool-managed route allowed"
        else:
            status, rule, detail = "PASS", "OK", "path matches managed route"
        rows.append({"Status": status, "Rule_ID": rule, "Path_Type": path_type, "Path": relative, "Route_ID": route["Route_ID"], "Detail": detail})
    worst = max((SEVERITY[row["Status"]] for row in rows), default=0)
    return rows, worst


def run_preflight(args: argparse.Namespace) -> int:
    project = pm.resolve_project(args.project)
    paths: list[tuple[str, str, set[str]]] = [("Script", args.script_path, {"Script"})]
    paths.extend(("Log", value, {"Log"}) for value in args.log_path)
    paths.extend(("Output", value, {"Result", "QC", "Plot_Data", "Source_Table", "Figure", "Report", "Manuscript", "Acceptance", "Delivery"}) for value in args.output_path)
    paths.extend(("Temporary", value, {"Temporary"}) for value in args.tmp_path)
    rows, worst = preflight_check(project, args.module, args.task_id, paths)
    write_tsv(PREFLIGHT_COLUMNS, rows)
    return worst


def run_migration_plan(args: argparse.Namespace) -> int:
    project = pm.resolve_project(args.project)
    try:
        layout = layout_contract.detect_layout(project)
    except layout_contract.LayoutError as exc:
        raise WorkspaceError(str(exc)) from exc
    entries = inventory(project, args.max_depth)
    rows: list[dict[str, str]] = []
    for entry in entries:
        relative = entry["Relative_Path"]
        allowed_controls = V2_CONTROL_PATHS if layout.is_v2 else CANONICAL_CONTROL_PATHS
        if relative in set(layout.canonical_dirs) or relative in allowed_controls:
            continue
        path = Path(relative)
        role = entry["Observed_Role"]
        suggested_role = role if role != "Unknown" else "REVIEW_REQUIRED"
        suggested_path = "REVIEW_REQUIRED"
        confidence = "Low"
        reason = "semantic role and dependency require Agent review"
        if entry["Entry_Type"] == "File" and role == "Log" and path.parts[0] != "logs":
            suggested_path = f"logs/unassigned/{path.name}"
            confidence = "High"
            reason = "strong .out/.err/.log evidence outside logs/"
        elif entry["Entry_Type"] == "File" and role == "Script" and path.parts[0] != "scripts":
            suggested_path = f"scripts/unassigned/{path.name}"
            confidence = "High"
            reason = "strong .slurm/.sbatch evidence outside scripts/"
        elif entry["Entry_Type"] == "Directory" and role == "Temporary" and path.parts[0] == "results":
            suggested_path = "tmp/REVIEW_REQUIRED"
            confidence = "Medium"
            reason = "temporary-like directory is under results/; content semantics need review"
        elif entry["Entry_Type"] == "Directory" and role == "Report" and path.parts[0] == "results":
            root = layout.documentation_root
            suggested_path = f"{root}/REVIEW_REQUIRED"
            confidence = "Medium"
            reason = "report-like directory is under results/; module association needs review"
        rows.append({
            "Current_Path": relative,
            "Observed_Type": entry["Entry_Type"],
            "Suggested_Role": suggested_role,
            "Suggested_Path": suggested_path,
            "Confidence": confidence,
            "Reason": reason,
            "Action": "PLAN_ONLY",
        })
    rows.sort(key=lambda row: (row["Current_Path"].casefold(), row["Current_Path"]))
    if args.format == "json":
        print(json.dumps({"Project": str(project), "Migration_plan": rows, "Mutations": []}, indent=2, sort_keys=True))
    else:
        write_tsv(MIGRATION_COLUMNS, rows)
    return 0


def add_format(parser: argparse.ArgumentParser, *, text: bool = True) -> None:
    choices = ("text", "tsv", "json") if text else ("tsv", "json")
    parser.add_argument("--format", choices=choices, default=choices[0])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage an explicit Bioflow project workspace without rename/move/delete operations.")
    sub = parser.add_subparsers(dest="command", required=True)

    bootstrap = sub.add_parser("bootstrap", help="dry-run or install workspace contract templates")
    bootstrap.add_argument("--project", required=True)
    bootstrap.add_argument("--yes", action="store_true")
    bootstrap.set_defaults(handler=run_bootstrap)

    inspect = sub.add_parser("inspect", help="bounded read-only workspace inventory")
    inspect.add_argument("--project", required=True)
    inspect.add_argument("--max-depth", type=int, default=DEFAULT_AUDIT_DEPTH)
    add_format(inspect)
    inspect.set_defaults(handler=run_inspect)

    plan = sub.add_parser("plan", help="validate and compile module DAG and routes")
    plan.add_argument("--project", required=True)
    add_format(plan)
    plan.set_defaults(handler=run_plan)

    route = sub.add_parser("route", help="resolve one explicit module/role route")
    route.add_argument("--project", required=True)
    route.add_argument("--module", required=True)
    route.add_argument("--role", choices=sorted(PATH_ROLES), required=True)
    route.add_argument("--path-type", choices=sorted(PATH_TYPES))
    add_format(route, text=False)
    route.set_defaults(handler=run_route)

    audit = sub.add_parser("audit", help="cross-audit plan, index, filesystem, and project status")
    audit.add_argument("--project", required=True)
    audit.add_argument("--max-depth", type=int)
    add_format(audit)
    audit.set_defaults(handler=run_audit)

    apply = sub.add_parser("apply", help="dry-run or transactionally create/register the reviewed workspace tree")
    apply.add_argument("--project", required=True)
    apply.add_argument("--yes", action="store_true")
    apply.set_defaults(handler=run_apply)

    preflight = sub.add_parser("preflight", help="validate explicit task paths against reviewed routes")
    preflight.add_argument("--project", required=True)
    preflight.add_argument("--module", required=True)
    preflight.add_argument("--task-id", required=True)
    preflight.add_argument("--script-path", required=True)
    preflight.add_argument("--log-path", action="append", default=[], required=True)
    preflight.add_argument("--output-path", action="append", default=[], required=True)
    preflight.add_argument("--tmp-path", action="append", default=[])
    preflight.set_defaults(handler=run_preflight)

    migration = sub.add_parser("migration-plan", help="read-only placement suggestions; never changes paths")
    migration.add_argument("--project", required=True)
    migration.add_argument("--max-depth", type=int, default=DEFAULT_AUDIT_DEPTH)
    add_format(migration, text=False)
    migration.set_defaults(handler=run_migration_plan)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except (WorkspaceError, pm.PathManagerError, OSError, ValueError, csv.Error) as exc:
        sys.stderr.write(f"[ERROR] {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
