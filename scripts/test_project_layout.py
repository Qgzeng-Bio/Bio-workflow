#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "project_layout.py"
INIT = ROOT / "scripts" / "init_project.sh"
SPEC = importlib.util.spec_from_file_location("project_layout", SCRIPT)
assert SPEC and SPEC.loader
layout = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = layout
SPEC.loader.exec_module(layout)

with tempfile.TemporaryDirectory(prefix="bioflow-layout-test.") as tmp_name:
    tmp = Path(tmp_name)
    project = tmp / "v2"
    result = subprocess.run([str(INIT), "--project", str(project), "--yes"], check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    detected = layout.detect_layout(project)
    assert detected.is_v2
    assert detected.canonical_dirs == ("config", "rawdata", "scripts", "logs", "tmp", "results", "docs", "manuscripts")
    assert layout.control_relative(detected, "task_status") == "docs/status/Task_Status.tsv"
    assert layout.control_relative(detected, "acceptance") == "docs/validation/Acceptance_Report.md"
    for relative in (
        "README.md", "PROJECT_STATUS.md", "CHANGELOG.md", ".gitignore",
        ".github/PULL_REQUEST_TEMPLATE.md", ".github/ISSUE_TEMPLATE/analysis.md",
        "rawdata/README.md", "docs/Analysis_Plan.md", "docs/status/Task_Status.tsv",
        "docs/decisions/Decision_Log.md", "manuscripts/README.md",
        "docs/research-log/TEMPLATE.md", "docs/research-log/Log_Index.tsv",
        "docs/decisions/Decision_Index.tsv",
    ):
        assert (project / relative).is_file(), relative
    assert not (project / "data").exists() and not (project / "reports").exists()

    existing_git_root = tmp / "existing_git"
    existing_git_root.mkdir()
    (existing_git_root / "README.md").write_text("existing\n", encoding="utf-8")
    result = subprocess.run(
        [str(INIT), "--project", str(existing_git_root), "--layout-v2", "--yes"],
        check=False, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert layout.detect_layout(existing_git_root).is_v2
    assert (existing_git_root / "README.md").read_text(encoding="utf-8") == "existing\n"

    mixed = tmp / "mixed"
    (mixed / "data").mkdir(parents=True)
    denied = subprocess.run(
        [str(INIT), "--project", str(mixed), "--layout-v2", "--yes"],
        check=False, capture_output=True, text=True,
    )
    assert denied.returncode == 2 and "existing legacy root" in denied.stderr
    assert not (mixed / "config" / "Project_Layout.tsv").exists()

    legacy = tmp / "legacy"
    result = subprocess.run([str(INIT), "--project", str(legacy), "--legacy-layout", "--yes"], check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    detected_legacy = layout.detect_layout(legacy)
    assert not detected_legacy.is_v2
    assert layout.control_relative(detected_legacy, "task_status") == "reports/Task_Status.tsv"

    conflict = subprocess.run(
        [str(INIT), "--project", str(tmp / "conflict"), "--layout-v2", "--legacy-layout"],
        check=False, capture_output=True, text=True,
    )
    assert conflict.returncode == 2 and "mutually exclusive" in conflict.stderr

    marker = project / "config" / "Project_Layout.tsv"
    marker.write_text("bad\theader\n", encoding="utf-8")
    try:
        layout.detect_layout(project)
    except layout.LayoutError:
        pass
    else:
        raise AssertionError("malformed layout marker was accepted")

print("PASS | project layout v2 detection and legacy fallback")
