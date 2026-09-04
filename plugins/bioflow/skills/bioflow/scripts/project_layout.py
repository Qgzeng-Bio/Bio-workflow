#!/usr/bin/env python3
"""Resolve Bioflow project-layout profiles without mutating a project."""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

LAYOUT_COLUMNS = (
    "Schema_Version",
    "Rawdata_Root",
    "Documentation_Root",
    "Manuscript_Root",
    "Module_Separator",
)
V2_SCHEMA = "bioflow.layout.v2"


class LayoutError(ValueError):
    """Invalid or ambiguous project layout."""


@dataclass(frozen=True)
class ProjectLayout:
    schema_version: str
    canonical_dirs: tuple[str, ...]
    rawdata_root: str
    documentation_root: str
    manuscript_root: str | None
    module_separator: str

    @property
    def is_v2(self) -> bool:
        return self.schema_version == V2_SCHEMA


LEGACY_LAYOUT = ProjectLayout(
    schema_version="bioflow.layout.v1-legacy",
    canonical_dirs=("config", "data", "scripts", "logs", "tmp", "results", "reports"),
    rawdata_root="data",
    documentation_root="reports",
    manuscript_root=None,
    module_separator="_",
)
V2_LAYOUT = ProjectLayout(
    schema_version=V2_SCHEMA,
    canonical_dirs=("config", "rawdata", "scripts", "logs", "tmp", "results", "docs", "manuscripts"),
    rawdata_root="rawdata",
    documentation_root="docs",
    manuscript_root="manuscripts",
    module_separator="-",
)


def detect_layout(project: str | Path) -> ProjectLayout:
    root = Path(project).expanduser().resolve(strict=False)
    marker = root / "config" / "Project_Layout.tsv"
    if marker.is_symlink():
        raise LayoutError(f"layout marker must not be a symbolic link: {marker}")
    if not marker.exists():
        return LEGACY_LAYOUT
    if not marker.is_file():
        raise LayoutError(f"layout marker must be a regular non-symlink file: {marker}")
    with marker.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if tuple(reader.fieldnames or ()) != LAYOUT_COLUMNS:
            raise LayoutError(f"Project_Layout.tsv header must be exactly: {' | '.join(LAYOUT_COLUMNS)}")
        rows = list(reader)
    if len(rows) != 1 or None in rows[0]:
        raise LayoutError("Project_Layout.tsv must contain exactly one complete data row")
    row = {key: (value or "").strip() for key, value in rows[0].items()}
    expected = {
        "Schema_Version": V2_SCHEMA,
        "Rawdata_Root": "rawdata",
        "Documentation_Root": "docs",
        "Manuscript_Root": "manuscripts",
        "Module_Separator": "-",
    }
    if row != expected:
        raise LayoutError(f"unsupported or modified Project_Layout.tsv contract: {row}")
    return V2_LAYOUT


def find_project_root(start: str | Path) -> Path | None:
    """Find the nearest explicit Bioflow project root from a file or directory."""
    raw = Path(start).expanduser().absolute()
    current = raw if raw.is_dir() else raw.parent
    for _ in range(16):
        config = current / "config"
        if (
            (config / "Project_Layout.tsv").exists()
            or (config / "Workspace_Policy.tsv").exists()
            or (
                config.is_dir()
                and (current / "results").is_dir()
                and ((current / "data").is_dir() or (current / "rawdata").is_dir())
            )
        ):
            # detect_layout performs strict marker validation.
            detect_layout(current)
            return current
        if current.parent == current:
            break
        current = current.parent
    return None


def control_relative(layout: ProjectLayout, key: str) -> str:
    legacy = {
        "analysis_plan": "reports/Analysis_Plan.md",
        "task_status": "reports/Task_Status.tsv",
        "workflow_status": "reports/workflow_status.tsv",
        "run_record": "reports/run_record.tsv",
        "claim_audit": "reports/claim_audit.tsv",
        "acceptance": "reports/Acceptance_Report.md",
        "methods": "reports/Methods_Summary.md",
        "delivery": "reports/Delivery_Index.md",
        "onboarding": "reports/program-onboarding",
        "submitted_scripts": "reports/submitted_scripts",
    }
    modern = {
        "analysis_plan": "docs/Analysis_Plan.md",
        "task_status": "docs/status/Task_Status.tsv",
        "workflow_status": "docs/status/workflow_status.tsv",
        "run_record": "docs/status/run_record.tsv",
        "claim_audit": "docs/validation/Claim_Audit.tsv",
        "acceptance": "docs/validation/Acceptance_Report.md",
        "methods": "docs/methods/Methods_Summary.md",
        "delivery": "docs/delivery/Delivery_Index.md",
        "onboarding": "docs/program-onboarding",
        "submitted_scripts": "docs/status/submitted-scripts",
    }
    mapping = modern if layout.is_v2 else legacy
    try:
        return mapping[key]
    except KeyError as exc:
        raise LayoutError(f"unknown control path key: {key}") from exc


def control_paths(layout: ProjectLayout) -> set[str]:
    keys = (
        "analysis_plan", "task_status", "workflow_status", "run_record",
        "claim_audit", "acceptance", "methods", "delivery",
    )
    return {control_relative(layout, key) for key in keys}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read a Bioflow project layout profile")
    parser.add_argument("--project")
    parser.add_argument("--find-root")
    parser.add_argument("--field", choices=("schema", "rawdata", "docs", "manuscripts", "separator"))
    parser.add_argument("--path", choices=(
        "analysis_plan", "task_status", "workflow_status", "run_record", "claim_audit",
        "acceptance", "methods", "delivery", "onboarding", "submitted_scripts",
    ))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.find_root:
            root = find_project_root(args.find_root)
            if root is None:
                raise LayoutError(f"no Bioflow project root found from: {args.find_root}")
            print(root)
            return 0
        if not args.project:
            raise LayoutError("--project is required unless --find-root is used")
        layout = detect_layout(args.project)
        if args.path:
            print(control_relative(layout, args.path))
        elif args.field == "rawdata":
            print(layout.rawdata_root)
        elif args.field == "docs":
            print(layout.documentation_root)
        elif args.field == "manuscripts":
            print(layout.manuscript_root or "NA")
        elif args.field == "separator":
            print(layout.module_separator)
        else:
            print(layout.schema_version)
    except (LayoutError, OSError, csv.Error) as exc:
        print(f"[ERROR] {exc}", file=__import__("sys").stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
