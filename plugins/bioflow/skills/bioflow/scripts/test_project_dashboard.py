#!/usr/bin/env python3
"""Regression fixtures for the read-only bioflow project dashboard."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DASHBOARD = ROOT / "scripts" / "project_dashboard.py"
STEWARD = ROOT / "scripts" / "workspace_steward.py"
TEMPLATES = ROOT / "assets" / "project-templates"
PYTHON = sys.executable


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def run(project: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    command = [PYTHON, str(DASHBOARD), "--project", str(project), *args]
    return subprocess.run(command, check=False, capture_output=True, text=True, env=env)


def fake_scheduler(bin_dir: Path) -> dict[str, str]:
    squeue = bin_dir / "squeue"
    sacct = bin_dir / "sacct"
    write(
        squeue,
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "case \"$*\" in\n"
        "  *12345*) printf '12345|RUNNING|00:10|node01|4|16G|normal|align\\n' ;;\n"
        "esac\n",
    )
    write(
        sacct,
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "case \"$*\" in\n"
        "  *777*) printf '777|COMPLETED|0:0|8G|00:20:00|4|16G|normal\\n' ;;\n"
        "  *888*) printf '888|COMPLETED|0:0|NA|00:20:00|4|16G|normal\\n888_1|COMPLETED|0:0|4G|00:10:00|4|16G|normal\\n888_2|FAILED|1:0|8G|00:05:00|4|16G|normal\\n' ;;\n"
        "  *12345*) printf '12345|RUNNING|0:0|2G|00:10|4|16G|normal\\n' ;;\n"
        "esac\n",
    )
    squeue.chmod(0o755)
    sacct.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    return env


def make_project(root: Path, name: str) -> Path:
    project = root / name
    for directory in ("config", "data", "scripts", "logs", "results", "reports", "tmp"):
        (project / directory).mkdir(parents=True, exist_ok=True)
    return project


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def setup_workspace(project: Path, *, legacy: bool = False) -> None:
    for name in ("Directory_Index.tsv", "Workspace_Policy.tsv"):
        target = project / "config" / name
        if not target.exists():
            target.write_bytes((TEMPLATES / name).read_bytes())
    modules = (
        "Module_ID\tParent_Module\tStage\tShort_Name\tModule_Kind\tDepends_On\tPurpose\tOwner\tCompatibility\tNotes\n"
        "M001\tROOT\t01\tcore\tanalysis\t\tCore analysis\ttester\tManaged\t\n"
    )
    routes = (
        "Route_ID\tModule_ID\tPath_Type\tPath_Role\tRelative_Path\tProducer_Tasks\tConsumer_Tasks\tRetention\tRequired\tCompatibility\tPurpose\tNotes\n"
        "R001\tM001\tDirectory\tScript\tscripts/01_core\tT001\t\tWorking\tYes\tManaged\tCore scripts\t\n"
        "R002\tM001\tDirectory\tLog\tlogs/01_core\tT001\t\tWorking\tYes\tManaged\tCore logs\t\n"
        "R003\tM001\tDirectory\tTemporary\ttmp/01_core\tT001\t\tDisposable\tYes\tManaged\tCore temporary\t\n"
        "R004\tM001\tDirectory\tResult\tresults/01_core\tT001\t\tRetained\tYes\tManaged\tCore results\t\n"
    )
    if legacy:
        modules += "M002\tROOT\t\tOld-Folder\tlegacy\t\tHistorical output\ttester\tLegacy\t\n"
        routes += "R005\tM002\tDirectory\tResult\tresults/Old-Folder\t\t\tRetained\tYes\tLegacy\tHistorical output\t\n"
        (project / "results" / "Old-Folder").mkdir(exist_ok=True)
    write(project / "config" / "Workspace_Modules.tsv", modules)
    write(project / "config" / "Workspace_Routes.tsv", routes)
    write(
        project / "reports" / "Task_Status.tsv",
        "Task_ID\tStage\tSample_ID\tStatus\tJob_ID\tDependency\tScript_Path\tLog_Path\tOutput_Path\tAcceptance_Path\tRetry_Count\tUpdated_Time\n"
        "T001\tM001\tNA\tReady\tNA\tNA\tscripts/01_core/job.slurm\tlogs/01_core/job.out\tresults/01_core\tNA\t0\t2026-08-10T00:00:00+08:00\n",
    )
    applied = subprocess.run([PYTHON, str(STEWARD), "apply", "--project", str(project), "--yes"], check=False, capture_output=True, text=True)
    assert_true(applied.returncode == 0, applied.stdout + applied.stderr)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="bioflow-dashboard-test.", dir="/tmp") as tmp_value:
        tmp = Path(tmp_value)
        env = fake_scheduler(tmp / "fake-bin")

        project = make_project(tmp, "mixed")
        write(
            project / "reports" / "workflow_status.tsv",
            "Stage\tStatus\tEvidence_Path\tJob_ID\tExit_Code\tInput_Path\tOutput_Path\tNext_Action\tUpdated_Time\n"
            "Queued_or_running\tRunning\treports/Task_Status.tsv\t12345\tNA\tNA\tNA\tMonitor\t2026-08-10T00:00:00+0800\n",
        )
        write(
            project / "reports" / "Task_Status.tsv",
            "\t".join(
                [
                    "Task_ID",
                    "Stage",
                    "Sample_ID",
                    "Status",
                    "Job_ID",
                    "Dependency",
                    "Script_Path",
                    "Log_Path",
                    "Output_Path",
                    "Acceptance_Path",
                    "Retry_Count",
                    "Updated_Time",
                ]
            )
            + "\n"
            + "T1\tAlign\tS1\tQueued\t12345\tNA\tscripts/20_align.slurm\tlogs/12345.out\tNA\tNA\t0\t2026-08-10T00:00:00+0800\n"
            + "T2\tCall\tS1\tReady\tNA\tT1\tscripts/30_call.slurm\tNA\tresults/S1.vcf.gz\tNA\t0\t2026-08-10T00:00:00+0800\n"
            + "T3\tInputs\tS1\tValidated\tNA\tNA\tNA\tNA\tconfig/Input_Manifest.tsv\treports/Input_Acceptance.md\t0\t2026-08-10T00:00:00+0800\n",
        )
        write(project / "config" / "Input_Manifest.tsv", "Sample_ID\tInput_Path\nS1\t/data/example.fastq.gz\n")
        write(project / "reports" / "Input_Acceptance.md", "Acceptance_Status: Accepted\n")

        before = fingerprint(project)
        result = run(project, "--check-queue", "--format", "json", env=env)
        after = fingerprint(project)
        assert_true(result.returncode == 0, result.stderr)
        assert_true(before == after, "dashboard modified the project")
        payload = json.loads(result.stdout)
        tasks = {task["task_id"]: task for task in payload["Tasks"]}
        assert_true(tasks["T1"]["effective_status"] == "Running", tasks["T1"])
        assert_true(tasks["T1"]["scheduler_reason"] == "node01", tasks["T1"])
        assert_true(tasks["T1"]["partition"] == "normal", tasks["T1"])
        assert_true(tasks["T1"]["requested_cpus"] == "4", tasks["T1"])
        assert_true(tasks["T1"]["requested_mem"] == "16G", tasks["T1"])
        assert_true(tasks["T2"]["effective_status"] == "Blocked", tasks["T2"])
        assert_true(tasks["T3"]["effective_status"] == "Validated", tasks["T3"])
        assert_true(payload["Summary"] == {"Running": 1, "Blocked": 1, "Validated": 1}, payload["Summary"])
        print("PASS | mixed running, blocked, and validated tasks")
        print("PASS | dashboard is read-only")

        project = make_project(tmp, "run-record")
        write(
            project / "reports" / "run_record.tsv",
            "Job_ID\tJob_Name\tScript\tPartition\tCPUs\tMem\tArray\tSubmit_Time\tUser\tChecker_Status_AtSubmit\n"
            "777\tpilot\tscripts/10_pilot.slurm\tnormal\t4\t16G\tNA\t2026-08-10 00:00:00\ttester\tNA\n",
        )
        result = run(project, "--check-queue", "--format", "json", env=env)
        assert_true(result.returncode == 0, result.stderr)
        payload = json.loads(result.stdout)
        assert_true(payload["Tasks"][0]["effective_status"] == "Complete_unvalidated", payload["Tasks"])
        assert_true(payload["Tasks"][0]["exit_code"] == "0:0", payload["Tasks"])
        print("PASS | run record reconciled with completed accounting")

        project = make_project(tmp, "array-failure")
        write(
            project / "reports" / "run_record.tsv",
            "Job_ID\tJob_Name\tScript\tPartition\tCPUs\tMem\tArray\tSubmit_Time\tUser\tChecker_Status_AtSubmit\n"
            "888\tarray\tscripts/20_array.slurm\tnormal\t4\t16G\t1-2%2\t2026-08-10 00:00:00\ttester\tNA\n",
        )
        result = run(project, "--check-queue", "--format", "json", env=env)
        assert_true(result.returncode == 0, result.stderr)
        payload = json.loads(result.stdout)
        task = payload["Tasks"][0]
        assert_true(task["effective_status"] == "Failed", task)
        assert_true(task["scheduler_detail"] == "COMPLETED=1,FAILED=1", task)
        assert_true(task["max_rss"] == "8G", task)
        print("PASS | failed array element overrides completed parent row")
        print("PASS | array MaxRSS uses the maximum observed element")

        project = make_project(tmp, "missing-output")
        write(
            project / "reports" / "Task_Status.tsv",
            "\t".join(
                [
                    "Task_ID",
                    "Stage",
                    "Sample_ID",
                    "Status",
                    "Job_ID",
                    "Dependency",
                    "Script_Path",
                    "Log_Path",
                    "Output_Path",
                    "Acceptance_Path",
                    "Retry_Count",
                    "Updated_Time",
                ]
            )
            + "\nT4\tSummarize\tNA\tComplete_unvalidated\tNA\tNA\tNA\tNA\tresults/Missing.tsv\tNA\t0\t2026-08-10T00:00:00+0800\n",
        )
        result = run(project, "--format", "json")
        assert_true(result.returncode == 0, result.stderr)
        payload = json.loads(result.stdout)
        assert_true(payload["Tasks"][0]["effective_status"] == "Failed", payload["Tasks"])
        assert_true(any("Output_Path is Missing" in item for item in payload["Warnings"]), payload["Warnings"])
        print("PASS | missing registered output blocks completion")

        project = make_project(tmp, "workspace")
        setup_workspace(project)
        result = run(project, "--format", "json")
        assert_true(result.returncode == 0, result.stderr)
        payload = json.loads(result.stdout)
        assert_true(payload["Workspace"]["Enabled"] is True, payload["Workspace"])
        assert_true(payload["Workspace"]["Status"] == "PASS", payload["Workspace"])
        text_result = run(project)
        assert_true("[INFO] Workspace: PASS" in text_result.stdout, text_result.stdout)
        setup_workspace(project, legacy=True)
        legacy_result = run(project, "--format", "json")
        legacy_payload = json.loads(legacy_result.stdout)
        assert_true(legacy_payload["Workspace"]["Status"] == "WARN", legacy_payload["Workspace"])
        assert_true(any(item["Rule_ID"] == "WS007" for item in legacy_payload["Workspace"]["Findings_detail"]), legacy_payload["Workspace"])
        write(project / "config" / "Workspace_Modules.tsv", "Bad\tHeader\n")
        malformed_workspace = run(project, "--format", "json")
        malformed_payload = json.loads(malformed_workspace.stdout)
        assert_true(malformed_payload["Workspace"]["Status"] == "BLOCK", malformed_payload["Workspace"])
        assert_true(any("Workspace Steward contract" in warning for warning in malformed_payload["Warnings"]), malformed_payload["Warnings"])
        print("PASS | dashboard reports workspace PASS/WARN/BLOCK without writing")

        project = make_project(tmp, "malformed")
        write(project / "reports" / "Task_Status.tsv", "Task_ID\tStatus\nT1\tRunning\n")
        result = run(project)
        assert_true(result.returncode == 2, result.stdout + result.stderr)
        assert_true("missing required columns" in result.stderr, result.stderr)
        print("PASS | malformed task schema refused")

        result = run(Path.home())
        assert_true(result.returncode == 2, result.stdout + result.stderr)
        assert_true("refusing broad" in result.stderr, result.stderr)
        print("PASS | broad project root refused")

    print("PASS | project dashboard regression fixtures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
