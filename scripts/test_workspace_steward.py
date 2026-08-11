#!/usr/bin/env python3
from __future__ import annotations

import csv
import fcntl
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "workspace_steward.py"
TEMPLATES = ROOT / "assets" / "project-templates"
SPEC = importlib.util.spec_from_file_location("workspace_steward", SCRIPT)
assert SPEC and SPEC.loader
workspace = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(workspace)


def passed(label: str) -> None:
    print(f"PASS | {label}")


def cli(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *arguments], check=False, capture_output=True, text=True)


def write_tsv(path: Path, columns: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_tsv_text(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text), delimiter="\t"))


def make_project(base: Path, *, plan: bool = True) -> Path:
    project = base / "project"
    for name in ("config", "data", "scripts", "logs", "tmp", "results", "reports"):
        (project / name).mkdir(parents=True, exist_ok=True)
    for name in ("Directory_Index.tsv", "Workspace_Policy.tsv", "Workspace_Modules.tsv", "Workspace_Routes.tsv"):
        source = TEMPLATES / name
        if source.exists() and (plan or not name.startswith("Workspace_")):
            (project / "config" / name).write_bytes(source.read_bytes())
    (project / "reports" / "Task_Status.tsv").write_text(
        "Task_ID\tStage\tSample_ID\tStatus\tJob_ID\tDependency\tScript_Path\tLog_Path\tOutput_Path\tAcceptance_Path\tRetry_Count\tUpdated_Time\n",
        encoding="utf-8",
    )
    (project / "reports" / "workflow_status.tsv").write_text(
        "Stage\tStatus\tEvidence_Path\tJob_ID\tExit_Code\tInput_Path\tOutput_Path\tNext_Action\tUpdated_Time\n",
        encoding="utf-8",
    )
    return project


def base_modules() -> list[dict[str, str]]:
    return [
        {
            "Module_ID": "M001", "Parent_Module": "ROOT", "Stage": "01", "Short_Name": "core",
            "Module_Kind": "analysis", "Depends_On": "", "Purpose": "Core analysis", "Owner": "tester",
            "Compatibility": "Managed", "Notes": "",
        },
        {
            "Module_ID": "M002", "Parent_Module": "ROOT", "Stage": "02", "Short_Name": "publication",
            "Module_Kind": "publication", "Depends_On": "M001", "Purpose": "Publication outputs", "Owner": "tester",
            "Compatibility": "Managed", "Notes": "",
        },
    ]


def route(route_id: str, module: str, path_type: str, role: str, relative: str, *, producers: str = "", required: str = "Yes", compatibility: str = "Managed", retention: str = "Working") -> dict[str, str]:
    return {
        "Route_ID": route_id, "Module_ID": module, "Path_Type": path_type, "Path_Role": role,
        "Relative_Path": relative, "Producer_Tasks": producers, "Consumer_Tasks": "",
        "Retention": retention, "Required": required, "Compatibility": compatibility,
        "Purpose": f"{module} {role}", "Notes": "",
    }


def base_routes() -> list[dict[str, str]]:
    return [
        route("R001", "M001", "Directory", "Script", "scripts/01_core", producers="T001"),
        route("R002", "M001", "Directory", "Log", "logs/01_core", producers="T001"),
        route("R003", "M001", "Directory", "Temporary", "tmp/01_core", producers="T001", retention="Disposable"),
        route("R004", "M001", "Directory", "Result", "results/01_core", producers="T001", retention="Retained"),
        route("R005", "M001", "Artifact", "Result", "results/01_core/Summary.tsv", producers="T001", retention="Retained"),
        route("R006", "M002", "Directory", "Script", "scripts/02_publication", producers="T002"),
        route("R007", "M002", "Directory", "Plot_Data", "results/02_publication", producers="T002", retention="Retained"),
        route("R008", "M002", "Directory", "Report", "reports/02_publication", producers="T002", retention="Delivery"),
        route("R009", "M002", "Directory", "Figure", "reports/02_publication/figures", producers="T002", retention="Delivery"),
    ]


def install_plan(project: Path, modules: list[dict[str, str]] | None = None, routes: list[dict[str, str]] | None = None) -> None:
    write_tsv(project / "config" / "Workspace_Modules.tsv", workspace.MODULE_COLUMNS, base_modules() if modules is None else modules)
    write_tsv(project / "config" / "Workspace_Routes.tsv", workspace.ROUTE_COLUMNS, base_routes() if routes is None else routes)


def write_tasks(project: Path, status: str = "Ready") -> None:
    rows = [
        {
            "Task_ID": "T001", "Stage": "M001", "Sample_ID": "NA", "Status": status, "Job_ID": "NA",
            "Dependency": "NA", "Script_Path": "scripts/01_core/job.slurm", "Log_Path": "logs/01_core/job.out",
            "Output_Path": "results/01_core", "Acceptance_Path": "NA", "Retry_Count": "0", "Updated_Time": "2026-08-10T00:00:00+08:00",
        },
        {
            "Task_ID": "T002", "Stage": "M002", "Sample_ID": "NA", "Status": "Planned", "Job_ID": "NA",
            "Dependency": "T001", "Script_Path": "scripts/02_publication/plot.slurm", "Log_Path": "NA",
            "Output_Path": "reports/02_publication/figures", "Acceptance_Path": "NA", "Retry_Count": "0", "Updated_Time": "2026-08-10T00:00:00+08:00",
        },
    ]
    columns = ("Task_ID", "Stage", "Sample_ID", "Status", "Job_ID", "Dependency", "Script_Path", "Log_Path", "Output_Path", "Acceptance_Path", "Retry_Count", "Updated_Time")
    write_tsv(project / "reports" / "Task_Status.tsv", columns, rows)


# Public surface remains bounded and has no mutation command for existing paths.
parser = workspace.build_parser()
subcommands = next(action.choices for action in parser._actions if isinstance(action, workspace.argparse._SubParsersAction))
assert set(subcommands) == {"bootstrap", "inspect", "plan", "route", "audit", "apply", "preflight", "migration-plan"}

with tempfile.TemporaryDirectory(prefix="bioflow-workspace-bootstrap.") as tmp_name:
    project = make_project(Path(tmp_name), plan=False)
    dry = cli(["bootstrap", "--project", str(project)])
    assert dry.returncode == 0 and "DRY_RUN" in dry.stdout
    assert not (project / "config" / "Workspace_Policy.tsv").exists()
    written = cli(["bootstrap", "--project", str(project), "--yes"])
    assert written.returncode == 0, written.stderr
    for name, header in (
        ("Workspace_Policy.tsv", workspace.POLICY_COLUMNS),
        ("Workspace_Modules.tsv", workspace.MODULE_COLUMNS),
        ("Workspace_Routes.tsv", workspace.ROUTE_COLUMNS),
    ):
        assert (project / "config" / name).is_file()
    sentinel = project / "config" / "Workspace_Modules.tsv"
    sentinel.write_text(sentinel.read_text() + "# sentinel\n")
    rerun = cli(["bootstrap", "--project", str(project), "--yes"])
    assert rerun.returncode == 0 and sentinel.read_text().endswith("# sentinel\n")
    protected = cli(["bootstrap", "--project", str(Path.home() / "data")])
    assert protected.returncode == 2
    unsafe_project = make_project(Path(tmp_name) / "unsafe", plan=False)
    dangling_target = Path(tmp_name) / "outside-lock"
    (unsafe_project / "config" / ".Workspace_Steward.lock").symlink_to(dangling_target)
    unsafe = cli(["bootstrap", "--project", str(unsafe_project), "--yes"])
    assert unsafe.returncode == 2 and "symbolic-link" in unsafe.stderr
    assert not dangling_target.exists()
passed("bootstrap dry-run, write, preserve, protected-root, and secure-lock gates")

with tempfile.TemporaryDirectory(prefix="bioflow-workspace-plan.") as tmp_name:
    project = make_project(Path(tmp_name))
    install_plan(project)
    write_tasks(project)
    planned = cli(["plan", "--project", str(project), "--format", "json"])
    assert planned.returncode == 0, planned.stderr
    payload = json.loads(planned.stdout)
    assert len(payload["Plan_SHA256"]) == 64
    assert {row["Module_ID"] for row in payload["Modules"]} == {"M001", "M002"}
    nested = base_modules()
    nested[0]["Module_ID"] = "M999"
    nested[0]["Short_Name"] = "parent"
    nested[0]["Module_Kind"] = "group"
    nested[1]["Module_ID"] = "M001"
    nested[1]["Parent_Module"] = "M999"
    nested[1]["Stage"] = "01"
    nested[1]["Short_Name"] = "child"
    nested[1]["Depends_On"] = ""
    nested[1]["Module_Kind"] = "analysis"
    nested_modules, _ = workspace.validate_modules(nested)
    assert workspace.topological_modules(nested_modules) == ["M999", "M001"]
    planned_again = cli(["plan", "--project", str(project), "--format", "json"])
    assert json.loads(planned_again.stdout)["Plan_SHA256"] == payload["Plan_SHA256"]
    resolved = cli(["route", "--project", str(project), "--module", "M001", "--role", "Log", "--path-type", "Directory"])
    assert resolved.returncode == 0 and read_tsv_text(resolved.stdout)[0]["Relative_Path"] == "logs/01_core"
    ambiguous_routes = base_routes() + [route("R010", "M001", "Directory", "Log", "logs/01_core/secondary", required="No")]
    install_plan(project, routes=ambiguous_routes)
    ambiguous = cli(["route", "--project", str(project), "--module", "M001", "--role", "Log", "--path-type", "Directory"])
    assert ambiguous.returncode == 2 and "ambiguous route" in ambiguous.stderr
passed("deterministic plan fingerprint and unique route resolution")

# Strict schema, hierarchy, stage, DAG, path, and role checks.
with tempfile.TemporaryDirectory(prefix="bioflow-workspace-invalid.") as tmp_name:
    project = make_project(Path(tmp_name))
    cases: list[tuple[list[dict[str, str]], list[dict[str, str]], str]] = []
    modules = base_modules(); modules[1]["Stage"] = "03"; cases.append((modules, base_routes(), "must be consecutive"))
    modules = base_modules(); modules[0]["Depends_On"] = "M002"; cases.append((modules, base_routes(), "dependency DAG cycle"))
    modules = base_modules(); modules[1]["Parent_Module"] = "M999"; cases.append((modules, base_routes(), "missing Parent_Module"))
    modules = base_modules(); modules[1]["Depends_On"] = "M002"; cases.append((modules, base_routes(), "cannot depend on itself"))
    routes = base_routes(); routes[0]["Relative_Path"] = "logs/01_core"; cases.append((base_modules(), routes, "role Script must be under scripts"))
    routes = base_routes(); routes[0]["Relative_Path"] = "/tmp/escape"; cases.append((base_modules(), routes, "project-relative"))
    routes = base_routes(); routes[0]["Relative_Path"] = "scripts/../escape"; cases.append((base_modules(), routes, "must not contain '..'"))
    routes = base_routes(); routes[1]["Route_ID"] = "R001"; cases.append((base_modules(), routes, "duplicate Route_ID"))
    routes = base_routes(); routes[4]["Relative_Path"] = "results/01_CORE"; cases.append((base_modules(), routes, "duplicate/case-colliding"))
    routes = [row for row in base_routes() if row["Path_Role"] != "Temporary"]; cases.append((base_modules(), routes, "missing Directory roles"))
    routes = base_routes(); routes[4]["Relative_Path"] = "results/02_publication/Cross_Module.tsv"; cases.append((base_modules(), routes, "must follow module path"))
    routes = base_routes() + [
        route("R010", "M002", "Directory", "Figure", "reports/02_publication/native", required="No", compatibility="Tool_managed"),
        route("R011", "M002", "Directory", "Figure", "reports/02_publication/native/figures", required="No"),
    ]; cases.append((base_modules(), routes, "requires a managed parent route"))
    modules = base_modules(); modules[0]["Parent_Module"] = "M002"; modules[0]["Stage"] = "01"; modules[1]["Stage"] = "01"; modules[1]["Module_Kind"] = "group"; cases.append((modules, base_routes(), "combined parent/dependency graph"))
    for modules, routes, fragment in cases:
        install_plan(project, modules, routes)
        result = cli(["plan", "--project", str(project)])
        assert result.returncode == 2 and fragment in result.stderr, (fragment, result.stderr)
    install_plan(project)
    (project / "config" / "Workspace_Policy.tsv").write_text("Bad\tHeader\n", encoding="utf-8")
    schema = cli(["plan", "--project", str(project)])
    assert schema.returncode == 2 and "[WS001]" in schema.stderr
    (project / "config" / "Workspace_Policy.tsv").write_bytes((TEMPLATES / "Workspace_Policy.tsv").read_bytes())
    modules = base_modules(); modules[1]["Stage"] = "03"; install_plan(project, modules, base_routes())
    module_error = cli(["plan", "--project", str(project)])
    assert "[WS002]" in module_error.stderr
    routes = base_routes(); routes[0]["Relative_Path"] = "logs/01_core"; install_plan(project, base_modules(), routes)
    route_error = cli(["plan", "--project", str(project)])
    assert "[WS003]" in route_error.stderr
    install_plan(project, [], [])
    empty = cli(["plan", "--project", str(project)])
    assert empty.returncode == 2 and "at least one module" in empty.stderr
passed("non-empty exact schemas, module tree, combined DAG, ownership, stage, path, role, and route gates")

with tempfile.TemporaryDirectory(prefix="bioflow-workspace-inspect.") as tmp_name:
    project = make_project(Path(tmp_name))
    install_plan(project)
    (project / "results" / "visible").mkdir()
    (project / "results" / "visible" / "deep").mkdir()
    outside = Path(tmp_name) / "outside"; outside.mkdir()
    (project / "results" / "outside_link").symlink_to(outside, target_is_directory=True)
    (project / "data" / "pruned").mkdir()
    inspected = cli(["inspect", "--project", str(project), "--max-depth", "2", "--format", "tsv"])
    assert inspected.returncode == 0
    entries = read_tsv_text(inspected.stdout)
    assert any(row["Relative_Path"] == "results/outside_link" and row["Entry_Type"] == "Symlink" for row in entries)
    assert not any(row["Relative_Path"].startswith("data/pruned") for row in entries)
    assert not any(row["Relative_Path"] == "results/visible/deep" for row in entries)
passed("bounded inventory depth, pruning, and no symlink traversal")

with tempfile.TemporaryDirectory(prefix="bioflow-workspace-apply.") as tmp_name:
    project = make_project(Path(tmp_name))
    install_plan(project)
    write_tasks(project)
    before_index = (project / "config" / "Directory_Index.tsv").read_bytes()
    before_policy = (project / "config" / "Workspace_Policy.tsv").read_bytes()
    dry = cli(["apply", "--project", str(project)])
    assert dry.returncode == 0 and "CREATE_DIR" in dry.stdout
    assert (project / "config" / "Directory_Index.tsv").read_bytes() == before_index
    assert (project / "config" / "Workspace_Policy.tsv").read_bytes() == before_policy
    assert not (project / "results" / "01_core").exists()
    lock_path = project / "config" / ".Workspace_Steward.lock"
    with lock_path.open("a+") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        locked = cli(["apply", "--project", str(project), "--yes"])
        assert locked.returncode == 2 and "lock is already held" in locked.stderr
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
    assert not (project / "results" / "01_core").exists()
    applied = cli(["apply", "--project", str(project), "--yes"])
    assert applied.returncode == 0, applied.stderr
    for relative in ("scripts/01_core", "logs/01_core", "tmp/01_core", "results/01_core", "scripts/02_publication", "results/02_publication", "reports/02_publication", "reports/02_publication/figures"):
        assert (project / relative).is_dir(), relative
    policy = workspace.read_policy(project)
    assert policy["Plan_Status"] == "Reviewed" and len(policy["Plan_SHA256"]) == 64
    _, index_rows = workspace.pm.load_index(project)
    assert [row["Directory_ID"] for row in index_rows] == [f"D{index:03d}" for index in range(1, 9)]
    clean_audit = cli(["audit", "--project", str(project), "--format", "json"])
    assert clean_audit.returncode == 0, clean_audit.stdout + clean_audit.stderr
    preflight = cli([
        "preflight", "--project", str(project), "--module", "M001", "--task-id", "T001",
        "--script-path", "scripts/01_core/job.slurm", "--log-path", "logs/01_core/%j_%x.out",
        "--output-path", "results/01_core", "--tmp-path", "tmp/01_core",
    ])
    assert preflight.returncode == 0, preflight.stdout + preflight.stderr
    assert all(row["Status"] in {"PASS", "EXEMPT"} for row in read_tsv_text(preflight.stdout))
    wrong_script = cli([
        "preflight", "--project", str(project), "--module", "M001", "--task-id", "T001",
        "--script-path", "scripts/01_core/other.slurm", "--log-path", "logs/01_core/%j_%x.out",
        "--output-path", "results/01_core",
    ])
    assert wrong_script.returncode == 2
    assert any("does not match Task_Status.Script_Path" in row["Detail"] for row in read_tsv_text(wrong_script.stdout))
    wrong = cli([
        "preflight", "--project", str(project), "--module", "M001", "--task-id", "T001",
        "--script-path", "scripts/01_core/job.slurm", "--log-path", "results/01_core/job.err",
        "--output-path", "results/01_core",
    ])
    assert wrong.returncode == 2 and any(row["Status"] == "BLOCK" for row in read_tsv_text(wrong.stdout))
    (project / "results" / "rogue").mkdir()
    (project / "results" / "01_core" / "nested_rogue").mkdir()
    (project / "stray.err").write_text("x")
    drift = cli(["audit", "--project", str(project), "--format", "json"])
    assert drift.returncode == 2
    findings = json.loads(drift.stdout)["Findings"]
    assert any(row["Rule_ID"] == "WS006" and row["Relative_Path"] == "results/01_core/nested_rogue" for row in findings)
    assert any(row["Rule_ID"] == "WS009" for row in findings)
    assert any(row["Rule_ID"] == "WS014" for row in findings)
    drift_preflight = cli([
        "preflight", "--project", str(project), "--module", "M001", "--task-id", "T001",
        "--script-path", "scripts/01_core/job.slurm", "--log-path", "logs/01_core/%j_%x.out",
        "--output-path", "results/01_core",
    ])
    assert drift_preflight.returncode == 2
    assert any(row["Path_Type"] == "Workspace_Audit" and row["Rule_ID"] == "WS006" for row in read_tsv_text(drift_preflight.stdout))
passed("apply lock/transaction, stable IDs, registered-script binding, and full-audit preflight blockers")

with tempfile.TemporaryDirectory(prefix="bioflow-workspace-symlink.") as tmp_name:
    project = make_project(Path(tmp_name))
    install_plan(project)
    write_tasks(project)
    outside = Path(tmp_name) / "outside"; outside.mkdir()
    (project / "results" / "01_core").symlink_to(outside, target_is_directory=True)
    blocked = cli(["apply", "--project", str(project), "--yes"])
    assert blocked.returncode == 2 and "symlink" in blocked.stderr.lower()
    assert not (outside / "Summary.tsv").exists()
passed("planned symlink target is blocked without traversal")

with tempfile.TemporaryDirectory(prefix="bioflow-workspace-root-symlink.") as tmp_name:
    project = make_project(Path(tmp_name))
    install_plan(project)
    write_tasks(project)
    assert cli(["apply", "--project", str(project), "--yes"]).returncode == 0
    saved_logs = Path(tmp_name) / "saved-logs"
    (project / "logs").rename(saved_logs)
    (project / "logs").symlink_to(saved_logs, target_is_directory=True)
    audited = cli(["audit", "--project", str(project), "--format", "json"])
    assert audited.returncode == 2
    assert any(row["Rule_ID"] == "WS013" and row["Relative_Path"] == "logs" for row in json.loads(audited.stdout)["Findings"])
    reapplied = cli(["apply", "--project", str(project), "--yes"])
    assert reapplied.returncode == 2 and "symbolic-link" in reapplied.stderr
passed("canonical-root symlink replacement blocks audit and re-apply without traversal")

with tempfile.TemporaryDirectory(prefix="bioflow-workspace-artifact.") as tmp_name:
    project = make_project(Path(tmp_name))
    install_plan(project)
    write_tasks(project, status="Ready")
    assert cli(["apply", "--project", str(project), "--yes"]).returncode == 0
    running = cli(["audit", "--project", str(project), "--format", "json"])
    assert not any(row["Rule_ID"] == "WS010" for row in json.loads(running.stdout)["Findings"])
    write_tasks(project, status="Validated")
    completed = cli(["audit", "--project", str(project), "--format", "json"])
    assert completed.returncode == 2
    assert any(row["Rule_ID"] == "WS010" for row in json.loads(completed.stdout)["Findings"])
passed("required key artifact blocks only after producer completion")

with tempfile.TemporaryDirectory(prefix="bioflow-workspace-exceptions.") as tmp_name:
    project = make_project(Path(tmp_name))
    modules = base_modules() + [{
        "Module_ID": "M003", "Parent_Module": "ROOT", "Stage": "", "Short_Name": "Old-Folder",
        "Module_Kind": "legacy", "Depends_On": "", "Purpose": "Historical output", "Owner": "tester",
        "Compatibility": "Legacy", "Notes": "",
    }]
    routes = base_routes() + [route("R010", "M003", "Directory", "Result", "results/Old-Folder", compatibility="Legacy")]
    install_plan(project, modules, routes)
    write_tasks(project)
    (project / "results" / "Old-Folder").mkdir()
    old = {
        "Directory_ID": "D001", "Relative_Path": "results/Old-Folder", "Directory_Kind": "legacy", "Stage": "",
        "Name_Tokens": "Old-Folder", "Purpose": "Historical output", "Owner": "tester", "Status": "Active", "Notes": "",
    }
    workspace.pm.atomic_write_index(project / "config" / "Directory_Index.tsv", [old])
    applied = cli(["apply", "--project", str(project), "--yes"])
    assert applied.returncode == 0, applied.stderr
    audited = cli(["audit", "--project", str(project), "--format", "json"])
    payload = json.loads(audited.stdout)
    assert audited.returncode == 1 and any(row["Rule_ID"] == "WS007" for row in payload["Findings"])
    assert (project / "results" / "Old-Folder").is_dir()
passed("legacy paths warn without migration or mutation")

with tempfile.TemporaryDirectory(prefix="bioflow-workspace-tool.") as tmp_name:
    project = make_project(Path(tmp_name))
    routes = base_routes() + [route("R010", "M001", "Directory", "Result", "results/01_core/NativeToolOutput", required="No", compatibility="Tool_managed")]
    install_plan(project, base_modules(), routes)
    write_tasks(project)
    assert cli(["apply", "--project", str(project), "--yes"]).returncode == 0
    tool_path = project / "results" / "01_core" / "NativeToolOutput"
    tool_path.mkdir()
    registered = cli(["apply", "--project", str(project), "--yes"])
    assert registered.returncode == 0, registered.stderr
    audited = cli(["audit", "--project", str(project), "--format", "json"])
    payload = json.loads(audited.stdout)
    assert audited.returncode == 0
    assert any(row["Rule_ID"] == "WS008" and row["Status"] == "EXEMPT" for row in payload["Findings"])
    _, index_rows = workspace.pm.load_index(project)
    assert any(row["Relative_Path"] == "results/01_core/NativeToolOutput" and row["Directory_Kind"] == "tool_managed" for row in index_rows)
passed("tool-managed output is explicitly registered and layout-exempt")

with tempfile.TemporaryDirectory(prefix="bioflow-workspace-task-contract.") as tmp_name:
    project = make_project(Path(tmp_name))
    routes = base_routes()
    routes[0]["Producer_Tasks"] = "T404"
    install_plan(project, base_modules(), routes)
    write_tasks(project)
    task_path = project / "reports" / "Task_Status.tsv"
    task_rows = list(csv.DictReader(task_path.read_text().splitlines(), delimiter="\t"))
    task_rows[0]["Acceptance_Path"] = "reports/02_publication/not_owned.md"
    task_rows.append({
        "Task_ID": "T999", "Stage": "M999", "Sample_ID": "NA", "Status": "Planned", "Job_ID": "NA",
        "Dependency": "NA", "Script_Path": "NA", "Log_Path": "NA", "Output_Path": "NA",
        "Acceptance_Path": "NA", "Retry_Count": "0", "Updated_Time": "2026-08-10T00:00:00+08:00",
    })
    write_tsv(task_path, tuple(task_rows[0]), task_rows)
    assert cli(["apply", "--project", str(project), "--yes"]).returncode == 0
    audited = cli(["audit", "--project", str(project), "--format", "json"])
    assert audited.returncode == 2
    findings = json.loads(audited.stdout)["Findings"]
    assert any(row["Rule_ID"] == "WS012" and "unknown Task_ID T404" in row["Detail"] for row in findings)
    assert any(row["Rule_ID"] == "WS012" and "unknown module in Stage" in row["Detail"] for row in findings)
    assert any(row["Rule_ID"] == "WS012" and "Acceptance_Path" in row["Detail"] for row in findings)
passed("task references, module stages, and acceptance routes are cross-audited")

# Inject a policy-write failure after Directory_Index replacement; both files and all
# newly created directories must be restored/removed.
with tempfile.TemporaryDirectory(prefix="bioflow-workspace-rollback.") as tmp_name:
    project = make_project(Path(tmp_name))
    install_plan(project)
    write_tasks(project)
    index_path = project / "config" / "Directory_Index.tsv"
    policy_path = project / "config" / "Workspace_Policy.tsv"
    os.chmod(index_path, 0o640)
    os.chmod(policy_path, 0o600)
    old_index = index_path.read_bytes()
    old_policy = policy_path.read_bytes()
    old_index_mode = workspace.stat.S_IMODE(index_path.stat().st_mode)
    old_policy_mode = workspace.stat.S_IMODE(policy_path.stat().st_mode)
    args = workspace.build_parser().parse_args(["apply", "--project", str(project), "--yes"])
    with mock.patch.object(workspace, "atomic_write_text", side_effect=OSError("simulated policy failure")):
        try:
            with redirect_stdout(io.StringIO()):
                workspace.run_apply(args)
        except OSError:
            pass
        else:
            raise AssertionError("simulated policy failure did not propagate")
    assert index_path.read_bytes() == old_index
    assert policy_path.read_bytes() == old_policy
    assert workspace.stat.S_IMODE(index_path.stat().st_mode) == old_index_mode
    assert workspace.stat.S_IMODE(policy_path.stat().st_mode) == old_policy_mode
    assert not (project / "results" / "01_core").exists()
passed("atomic policy/index failure restores bytes, modes, and new empty tree")

with tempfile.TemporaryDirectory(prefix="bioflow-workspace-migration.") as tmp_name:
    project = make_project(Path(tmp_name), plan=False)
    (project / "stray.err").write_text("error")
    (project / "job.slurm").write_text("#!/bin/bash\n")
    (project / "results" / "intermediate").mkdir()
    before = sorted(path.relative_to(project).as_posix() for path in project.rglob("*"))
    migrated = cli(["migration-plan", "--project", str(project), "--max-depth", "2", "--format", "json"])
    assert migrated.returncode == 0, migrated.stderr
    payload = json.loads(migrated.stdout)
    assert payload["Mutations"] == []
    rows = payload["Migration_plan"]
    assert any(row["Suggested_Path"] == "logs/unassigned/stray.err" for row in rows)
    assert any(row["Suggested_Path"] == "scripts/unassigned/job.slurm" for row in rows)
    assert any(row["Suggested_Path"] == "tmp/REVIEW_REQUIRED" for row in rows)
    after = sorted(path.relative_to(project).as_posix() for path in project.rglob("*"))
    assert before == after
passed("migration plan is bounded/read-only and only makes high-confidence placement suggestions")

print("PASS | workspace steward core regression fixtures")
