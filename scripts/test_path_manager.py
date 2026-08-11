#!/usr/bin/env python3
from __future__ import annotations

import csv
import importlib.util
import io
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "path_manager.py"
TEMPLATE = ROOT / "assets" / "project-templates" / "Directory_Index.tsv"
SPEC = importlib.util.spec_from_file_location("path_manager", SCRIPT)
assert SPEC and SPEC.loader
manager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(manager)


def passed(label: str) -> None:
    print(f"PASS | {label}")


def expect_error(fragment: str, function, *args, **kwargs) -> None:
    try:
        function(*args, **kwargs)
    except manager.PathManagerError as exc:
        assert fragment in str(exc), (fragment, str(exc))
    else:
        raise AssertionError(f"expected PathManagerError containing {fragment!r}")


def run_cli(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


def make_project(root: Path) -> Path:
    project = root / "project"
    for name in ("config", "data", "scripts", "logs", "tmp", "results", "reports"):
        (project / name).mkdir(parents=True, exist_ok=True)
    (project / "config" / "Directory_Index.tsv").write_bytes(TEMPLATE.read_bytes())
    return project


parser = manager.build_parser()
subcommands = next(
    action.choices for action in parser._actions if isinstance(action, manager.argparse._SubParsersAction)
)
assert set(subcommands) == {"suggest", "audit", "create", "register"}

# Deterministic names preserve caller-selected scientific casing and IDs.
name, stage = manager.build_name("stage", 30, ["RNA", "DE"], None)
assert name == "30_RNA_DE" and stage == "30"
assert manager.build_name("stage", 5, ["align"], None)[0] == "05_align"
assert manager.build_name("result", None, ["BUSCO", "LM134"], "V2")[0] == "BUSCO_LM134_V2"
completed = run_cli(["suggest", "--kind", "stage", "--step", "30", "--token", "RNA", "--token", "DE"])
assert completed.returncode == 0, completed.stderr
suggest_lines = completed.stdout.splitlines()
assert suggest_lines[0].split("\t") == list(manager.SUGGEST_COLUMNS)
assert suggest_lines[1].split("\t")[:4] == ["30_RNA_DE", "9", "2", "PASS"]
passed("deterministic concise names and TSV suggest output")

for arguments, fragment in (
    (("stage", 100, ["RNA"], None), "between 0 and 99"),
    (("stage", 30, ["RNA-seq"], None), "ASCII letters/digits"),
    (("stage", 30, ["RNA", "DE", "QC", "extra"], None), "1-3"),
    (("stage", 30, ["RNA", "Final"], None), "forbidden"),
    (("stage", 30, ["abcdefghijklmnopqrstuvwx"], None), "exceeds 24"),
    (("result", 30, ["BUSCO"], None), "only for kind=stage"),
):
    expect_error(fragment, manager.build_name, *arguments)
for version in ("version2", "2026-08-10", "v1.1.2", "V"):
    expect_error("--version", manager.build_name, "result", None, ["BUSCO"], version)
expect_error("invalid Directory_ID", manager.render_index, [{"Directory_ID": "BAD"}])
passed("invalid step/token/version/name budgets and index IDs refused")

with tempfile.TemporaryDirectory(prefix="bioflow-path-audit.") as tmp_name:
    tmp = Path(tmp_name)
    project = make_project(tmp)
    (project / "results" / "30_RNA_DE").mkdir()
    (project / "results" / "BUSCO_Final").mkdir()
    (project / "results" / "this_is_a_very_long_directory_name_for_results").mkdir()
    (project / "results" / "NativeToolOutputDirectoryWithLongName").mkdir()
    (project / "results" / "Old-Folder").mkdir()
    (project / "results" / "BUSCO").mkdir()
    (project / "results" / "busco").mkdir()
    outside = tmp / "outside"
    (outside / "Should_Not_Be_Visited_Final_Results").mkdir(parents=True)
    (project / "results" / "outside_link").symlink_to(outside, target_is_directory=True)
    index_rows = [
        {
            "Directory_ID": "D001",
            "Relative_Path": "results/NativeToolOutputDirectoryWithLongName",
            "Directory_Kind": "tool_managed",
            "Stage": "",
            "Name_Tokens": "NativeTool",
            "Purpose": "Native tool outputs",
            "Owner": "test",
            "Status": "Active",
            "Notes": "",
        },
        {
            "Directory_ID": "D002",
            "Relative_Path": "results/Old-Folder",
            "Directory_Kind": "legacy",
            "Stage": "",
            "Name_Tokens": "Old,Folder",
            "Purpose": "Legacy project directory",
            "Owner": "test",
            "Status": "External",
            "Notes": "Do not rename",
        },
        {
            "Directory_ID": "D003",
            "Relative_Path": "results/Missing_Indexed",
            "Directory_Kind": "result",
            "Stage": "",
            "Name_Tokens": "Missing,Indexed",
            "Purpose": "Stale fixture",
            "Owner": "test",
            "Status": "Active",
            "Notes": "",
        },
    ]
    manager.atomic_write_index(project / "config" / "Directory_Index.tsv", index_rows)

    audit = run_cli(["audit", "--project", str(project), "--max-depth", "3"])
    assert audit.returncode == 0, audit.stderr
    audit_again = run_cli(["audit", "--project", str(project), "--max-depth", "3"])
    assert audit_again.stdout == audit.stdout
    rows = list(csv.DictReader(audit.stdout.splitlines(), delimiter="\t"))
    assert list(rows[0]) == list(manager.AUDIT_COLUMNS)
    assert any(row["Relative_Path"] == "config" and row["Rule_ID"] == "PATH010" for row in rows)
    assert any(row["Relative_Path"].endswith("NativeToolOutputDirectoryWithLongName") and row["Rule_ID"] == "PATH009" for row in rows)
    assert any(row["Relative_Path"].endswith("Old-Folder") and row["Rule_ID"] == "PATH006" for row in rows)
    assert any(row["Relative_Path"].endswith("BUSCO_Final") and row["Rule_ID"] == "PATH003" for row in rows)
    assert any(row["Rule_ID"] == "PATH001" for row in rows)
    assert any(row["Rule_ID"] == "PATH005" for row in rows)
    assert any(row["Relative_Path"].endswith("outside_link") and row["Rule_ID"] == "PATH008" for row in rows)
    assert any(row["Relative_Path"] == "results/Missing_Indexed" and row["Rule_ID"] == "PATH007" for row in rows)
    assert "Should_Not_Be_Visited" not in audit.stdout
    strict = run_cli(["audit", "--project", str(project), "--max-depth", "3", "--strict"])
    assert strict.returncode == 1
    too_deep = run_cli(["audit", "--project", str(project), "--max-depth", "6"])
    assert too_deep.returncode == 2 and "between 1 and 5" in too_deep.stderr
    passed("bounded deterministic audit, exemptions, warnings, collision, and no symlink traversal")

with tempfile.TemporaryDirectory(prefix="bioflow-path-write.") as tmp_name:
    tmp = Path(tmp_name)
    project = make_project(tmp)
    create_args = [
        "create",
        "--project",
        str(project),
        "--parent",
        "results",
        "--kind",
        "stage",
        "--step",
        "30",
        "--token",
        "RNA",
        "--token",
        "DE",
        "--purpose",
        "RNA-seq differential expression",
        "--owner",
        "qgzeng",
    ]
    before_index = (project / "config" / "Directory_Index.tsv").read_bytes()
    dry = run_cli(create_args)
    assert dry.returncode == 0, dry.stderr
    assert dry.stdout.splitlines()[1].split("\t")[0] == "DRY_RUN"
    assert not (project / "results" / "30_RNA_DE").exists()
    assert (project / "config" / "Directory_Index.tsv").read_bytes() == before_index

    created = run_cli([*create_args, "--yes"])
    assert created.returncode == 0, created.stderr
    assert (project / "results" / "30_RNA_DE").is_dir()
    _, indexed = manager.load_index(project)
    assert indexed[0]["Directory_ID"] == "D001"
    assert indexed[0]["Relative_Path"] == "results/30_RNA_DE"
    assert indexed[0]["Name_Tokens"] == "RNA,DE"

    existing = project / "results" / "NativeBUSCO"
    existing.mkdir()
    register_args = [
        "register",
        "--project",
        str(project),
        "--relative",
        "results/NativeBUSCO",
        "--kind",
        "tool_managed",
        "--purpose",
        "BUSCO native outputs",
        "--owner",
        "qgzeng",
    ]
    register_dry = run_cli(register_args)
    assert register_dry.returncode == 0 and "DRY_RUN" in register_dry.stdout
    assert len(manager.load_index(project)[1]) == 1
    registered = run_cli([*register_args, "--yes"])
    assert registered.returncode == 0, registered.stderr
    _, indexed = manager.load_index(project)
    assert [row["Directory_ID"] for row in indexed] == ["D001", "D002"]
    assert indexed[1]["Directory_Kind"] == "tool_managed"
    duplicate_path = run_cli([*register_args, "--yes"])
    assert duplicate_path.returncode == 2 and "already indexed" in duplicate_path.stderr
    duplicate_id_args = [value for value in register_args]
    duplicate_id_args.extend(["--directory-id", "D001", "--yes"])
    # Use a different existing directory so Directory_ID is the first duplicate gate.
    another = project / "results" / "AnotherTool"
    another.mkdir()
    duplicate_id_args[duplicate_id_args.index("results/NativeBUSCO")] = "results/AnotherTool"
    duplicate_id = run_cli(duplicate_id_args)
    assert duplicate_id.returncode == 2 and "Directory_ID already exists" in duplicate_id.stderr
    passed("create/register dry-run, confirmed write, stable IDs, and duplicate gates")

    existing_target = run_cli([*create_args, "--yes"])
    assert existing_target.returncode == 2 and "already exists" in existing_target.stderr
    (project / "results" / "BUSCO").mkdir()
    collision = run_cli([
        "create", "--project", str(project), "--parent", "results", "--kind", "result",
        "--token", "busco", "--purpose", "collision", "--yes",
    ])
    assert collision.returncode == 2 and "case-insensitive" in collision.stderr
    missing_parent = run_cli([
        "create", "--project", str(project), "--parent", "results/missing", "--kind", "result",
        "--token", "QC", "--purpose", "missing parent",
    ])
    assert missing_parent.returncode == 2 and "parent must be an existing" in missing_parent.stderr
    outside_dir = tmp / "external-existing"
    outside_dir.mkdir()
    escape = run_cli([
        "register", "--project", str(project), "--relative", "../external-existing",
        "--kind", "legacy", "--purpose", "escape",
    ])
    assert escape.returncode == 2 and "must not contain '..'" in escape.stderr
    symlink = project / "results" / "ExternalLink"
    symlink.symlink_to(outside_dir, target_is_directory=True)
    symlink_escape = run_cli([
        "register", "--project", str(project), "--relative", "results/ExternalLink",
        "--kind", "legacy", "--purpose", "symlink",
    ])
    assert symlink_escape.returncode == 2 and "symbolic-link" in symlink_escape.stderr
    broad = run_cli(["audit", "--project", str(Path.home() / "projects"), "--max-depth", "1"])
    assert broad.returncode == 2 and "broad project root" in broad.stderr
    protected = run_cli(["audit", "--project", str(Path.home() / "data"), "--max-depth", "1"])
    assert protected.returncode == 2 and "protected project root" in protected.stderr
    passed("existing target, missing parent, broad/protected/escape/collision gates")

with tempfile.TemporaryDirectory(prefix="bioflow-path-rollback.") as tmp_name:
    tmp = Path(tmp_name)
    project = make_project(tmp)
    args = manager.build_parser().parse_args([
        "create", "--project", str(project), "--parent", "results", "--kind", "result",
        "--token", "BUSCO", "--purpose", "rollback fixture", "--owner", "test", "--yes",
    ])
    original_index = (project / "config" / "Directory_Index.tsv").read_bytes()
    with mock.patch.object(manager, "atomic_write_index", side_effect=OSError("simulated index failure")):
        try:
            with redirect_stdout(io.StringIO()):
                manager.run_create(args)
        except OSError:
            pass
        else:
            raise AssertionError("simulated index failure did not propagate")
    assert not (project / "results" / "BUSCO").exists()
    assert (project / "config" / "Directory_Index.tsv").read_bytes() == original_index
    assert not list((project / "config").glob(".*.tmp"))

    # A failure after replacement must restore the old index bytes as well.
    real_fsync = manager.os.fsync

    def fail_directory_fsync(descriptor: int) -> None:
        nonlocal_calls[0] += 1
        if nonlocal_calls[0] == 2:
            raise OSError("simulated directory fsync failure")
        real_fsync(descriptor)

    nonlocal_calls = [0]
    replacement_rows = [{
        "Directory_ID": "D001",
        "Relative_Path": "results/BUSCO",
        "Directory_Kind": "result",
        "Stage": "",
        "Name_Tokens": "BUSCO",
        "Purpose": "replacement fixture",
        "Owner": "test",
        "Status": "Active",
        "Notes": "",
    }]
    with mock.patch.object(manager.os, "fsync", side_effect=fail_directory_fsync):
        try:
            manager.atomic_write_index(project / "config" / "Directory_Index.tsv", replacement_rows)
        except OSError:
            pass
        else:
            raise AssertionError("simulated post-replacement failure did not propagate")
    assert (project / "config" / "Directory_Index.tsv").read_bytes() == original_index
    assert not list((project / "config").glob(".*.tmp"))
    assert not list((project / "config").glob(".*.backup"))
    passed("index failure rolls back directory and restores previous index")

with tempfile.TemporaryDirectory(prefix="bioflow-path-config-link.") as tmp_name:
    tmp = Path(tmp_name)
    project = tmp / "project"
    project.mkdir()
    for name in ("data", "scripts", "logs", "tmp", "results", "reports"):
        (project / name).mkdir()
    outside = tmp / "outside-config"
    outside.mkdir()
    (project / "config").symlink_to(outside, target_is_directory=True)
    expect_error("symbolic-link", manager.load_index, project)
    expect_error(
        "non-symlink directory",
        manager.atomic_write_index,
        project / "config" / "Directory_Index.tsv",
        [],
    )
    assert not (outside / "Directory_Index.tsv").exists()
    passed("directory index refuses a symlinked config root")

print("PASS | bounded project path manager regression fixtures")
