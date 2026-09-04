#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "scripts" / "init_project.sh"
STEWARD = ROOT / "scripts" / "workspace_steward.py"

MODULE_COLUMNS = (
    "Module_ID", "Analysis_Key", "Parent_Module", "Stage", "Short_Name",
    "Module_Kind", "Depends_On", "Purpose", "Owner", "Compatibility", "Notes",
)
ROUTE_COLUMNS = (
    "Route_ID", "Module_ID", "Path_Type", "Path_Role", "Relative_Path",
    "Producer_Tasks", "Consumer_Tasks", "Retention", "Required",
    "Compatibility", "Purpose", "Notes",
)
TASK_COLUMNS = (
    "Task_ID", "Stage", "Sample_ID", "Status", "Job_ID", "Dependency",
    "Script_Path", "Log_Path", "Output_Path", "Acceptance_Path", "Retry_Count", "Updated_Time",
)
FIGURE_COLUMNS = (
    "Figure_ID", "Figure_Title", "Figure_Directory", "Source_Result",
    "Plot_Script", "Status", "Manuscript_Target", "Notes",
)


def cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(STEWARD), *arguments], check=False, capture_output=True, text=True)


def write_tsv(path: Path, columns: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


def module(key: str = "assembly", short: str = "assembly", module_id: str = "M001", stage: str = "01") -> dict[str, str]:
    return {
        "Module_ID": module_id, "Analysis_Key": key, "Parent_Module": "ROOT", "Stage": stage,
        "Short_Name": short, "Module_Kind": "analysis", "Depends_On": "",
        "Purpose": "Assembly", "Owner": "tester", "Compatibility": "Managed", "Notes": "",
    }


def route(route_id: str, role: str, relative: str, path_type: str = "Directory", producer: str = "T001", retention: str = "Working") -> dict[str, str]:
    return {
        "Route_ID": route_id, "Module_ID": "M001", "Path_Type": path_type, "Path_Role": role,
        "Relative_Path": relative, "Producer_Tasks": producer, "Consumer_Tasks": "",
        "Retention": retention, "Required": "Yes", "Compatibility": "Managed",
        "Purpose": role, "Notes": "",
    }


def routes() -> list[dict[str, str]]:
    return [
        route("R001", "Script", "scripts/01-assembly"),
        route("R002", "Log", "logs/01-assembly"),
        route("R003", "Temporary", "tmp/01-assembly", retention="Disposable"),
        route("R004", "Result", "results/01-assembly", retention="Retained"),
        route("R005", "Result", "results/01-assembly/figures", retention="Retained"),
        route("R006", "Figure", "results/01-assembly/figures/F001_Assembly_Overview", retention="Retained"),
    ]


def task(project: Path, status: str) -> None:
    write_tsv(project / "docs/status/Task_Status.tsv", TASK_COLUMNS, [{
        "Task_ID": "T001", "Stage": "M001", "Sample_ID": "NA", "Status": status,
        "Job_ID": "NA", "Dependency": "NA", "Script_Path": "scripts/01-assembly/job.slurm",
        "Log_Path": "logs/01-assembly/job.out", "Output_Path": "results/01-assembly",
        "Acceptance_Path": "NA", "Retry_Count": "0", "Updated_Time": "2026-08-10T00:00:00+08:00",
    }])


with tempfile.TemporaryDirectory(prefix="bioflow-workspace-v2.") as tmp_name:
    project = Path(tmp_name) / "project"
    subprocess.run([str(INIT), "--project", str(project), "--workspace-steward", "--yes"], check=True, stdout=subprocess.DEVNULL)
    write_tsv(project / "config/Workspace_Modules.tsv", MODULE_COLUMNS, [module()])
    write_tsv(project / "config/Workspace_Routes.tsv", ROUTE_COLUMNS, routes())
    task(project, "Ready")

    planned = cli("plan", "--project", str(project), "--format", "json")
    assert planned.returncode == 0, planned.stderr
    payload = json.loads(planned.stdout)
    assert payload["Policy"]["Schema_Version"] == "workspace.v2"
    assert payload["Modules"][0]["Analysis_Key"] == "assembly"
    assert payload["Modules"][0]["Module_Path"] == "01-assembly"

    applied = cli("apply", "--project", str(project), "--yes")
    assert applied.returncode == 0, applied.stderr
    preflight = cli(
        "preflight", "--project", str(project), "--module", "M001", "--task-id", "T001",
        "--script-path", "scripts/01-assembly/job.slurm", "--log-path", "logs/01-assembly/%j_%x.out",
        "--output-path", "results/01-assembly", "--tmp-path", "tmp/01-assembly",
    )
    assert preflight.returncode == 0, preflight.stdout + preflight.stderr

    task(project, "Validated")
    incomplete = cli("audit", "--project", str(project), "--format", "json")
    assert incomplete.returncode == 2
    assert any(row["Rule_ID"] == "WS015" for row in json.loads(incomplete.stdout)["Findings"])

    package = project / "results/01-assembly/figures/F001_Assembly_Overview"
    (package / "source-data").mkdir()
    (package / "checks").mkdir()
    (package / "README.md").write_text("# figure\n", encoding="utf-8")
    (package / "F001_Assembly_Overview.pdf").write_text("pdf", encoding="utf-8")
    (package / "F001_Assembly_Overview.png").write_text("png", encoding="utf-8")
    (package / "source-data/F001_Assembly_Overview.tsv").write_text("Metric\tValue\nN50\t1\n", encoding="utf-8")
    (package / "checks/Figure_Check.md").write_text("pass\n", encoding="utf-8")
    (package / "checks/Final_Review.json").write_text("{}\n", encoding="utf-8")
    write_tsv(project / "results/01-assembly/figures/Figure_Index.tsv", FIGURE_COLUMNS, [{
        "Figure_ID": "F001", "Figure_Title": "Assembly overview",
        "Figure_Directory": "F001_Assembly_Overview", "Source_Result": "results/01-assembly/tables/Assembly.tsv",
        "Plot_Script": "scripts/01-assembly/plotting/plot_F001.R", "Status": "Validated",
        "Manuscript_Target": "NA", "Notes": "",
    }])
    clean = cli("audit", "--project", str(project), "--format", "json")
    assert clean.returncode == 0, clean.stdout + clean.stderr

    duplicate = [module(), module(key="assembly", short="assembly-alt", module_id="M002", stage="02")]
    write_tsv(project / "config/Workspace_Modules.tsv", MODULE_COLUMNS, duplicate)
    duplicated = cli("plan", "--project", str(project))
    assert duplicated.returncode == 2 and "duplicate Analysis_Key" in duplicated.stderr

    write_tsv(project / "config/Workspace_Modules.tsv", MODULE_COLUMNS, [module(key="assembly-v2", short="assembly-v2")])
    versioned_name = cli("plan", "--project", str(project))
    assert versioned_name.returncode == 2 and "version/status tokens" in versioned_name.stderr

    write_tsv(project / "config/Workspace_Modules.tsv", MODULE_COLUMNS, [module()])
    bad_routes = routes(); bad_routes[3]["Relative_Path"] = "results/02-assembly-v2"
    write_tsv(project / "config/Workspace_Routes.tsv", ROUTE_COLUMNS, bad_routes)
    duplicate_entry = cli("plan", "--project", str(project))
    assert duplicate_entry.returncode == 2 and "must follow module path" in duplicate_entry.stderr

    publication = module(key="publication-data", short="publication-data")
    publication["Module_Kind"] = "publication"
    publication_routes = [
        route("R001", "Script", "scripts/01-publication-data"),
        route("R002", "Plot_Data", "results/01-publication-data", retention="Retained"),
        route("R003", "Result", "results/01-publication-data/figures", retention="Retained"),
        route("R004", "Figure", "results/01-publication-data/figures/F001_Main_Overview", retention="Retained"),
        route("R005", "Manuscript", "manuscripts/P01-genome", retention="Delivery"),
    ]
    write_tsv(project / "config/Workspace_Modules.tsv", MODULE_COLUMNS, [publication])
    write_tsv(project / "config/Workspace_Routes.tsv", ROUTE_COLUMNS, publication_routes)
    paper_plan = cli("plan", "--project", str(project))
    assert paper_plan.returncode == 0, paper_plan.stderr
    publication_routes[-1]["Relative_Path"] = "manuscripts/final-paper-v2"
    write_tsv(project / "config/Workspace_Routes.tsv", ROUTE_COLUMNS, publication_routes)
    bad_paper = cli("plan", "--project", str(project))
    assert bad_paper.returncode == 2 and "manuscripts/PNN-short-name" in bad_paper.stderr

print("PASS | workspace v2 analysis-key, route, tmp, figure-package, manuscript, and legacy-independent gates")
