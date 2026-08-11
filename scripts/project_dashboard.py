#!/usr/bin/env python3
"""Read-only task dashboard for a bioflow project.

The dashboard reconciles project-local task/submission records with bounded
squeue/sacct queries for registered Job IDs. It never writes project files or
changes scheduler state.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

TASK_FIELDS = [
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

DISPLAY_ORDER = [
    "Running",
    "Queued",
    "Failed",
    "Blocked",
    "Ready",
    "Complete_unvalidated",
    "Validated",
    "Planned",
    "Cancelled",
    "Skipped",
    "Unknown",
    "Submitted_recorded",
]

ACTIVE_SLURM = {"RUNNING", "COMPLETING", "CONFIGURING", "SUSPENDED"}
QUEUED_SLURM = {"PENDING", "REQUEUED", "RESIZING", "REVOKED"}
FAILED_SLURM = {
    "FAILED",
    "TIMEOUT",
    "OUT_OF_MEMORY",
    "NODE_FAIL",
    "BOOT_FAIL",
    "DEADLINE",
    "PREEMPTED",
}
CANCELLED_SLURM = {"CANCELLED"}
SUCCESS_SLURM = {"COMPLETED"}


class DashboardError(RuntimeError):
    """Input or safety error that should stop the dashboard."""


@dataclass
class SchedulerEvidence:
    state: str = "NA"
    detail: str = "NA"
    exit_code: str = "NA"
    max_rss: str = "NA"
    elapsed: str = "NA"
    reason: str = "NA"
    partition: str = "NA"
    requested_cpus: str = "NA"
    requested_mem: str = "NA"


@dataclass
class Task:
    task_id: str
    stage: str = "NA"
    sample_id: str = "NA"
    recorded_status: str = "Unknown"
    effective_status: str = "Unknown"
    job_id: str = "NA"
    dependency: str = "NA"
    script_path: str = "NA"
    log_path: str = "NA"
    output_path: str = "NA"
    acceptance_path: str = "NA"
    retry_count: str = "NA"
    updated_time: str = "NA"
    source: str = "NA"
    scheduler_state: str = "NA"
    scheduler_detail: str = "NA"
    scheduler_reason: str = "NA"
    partition: str = "NA"
    requested_cpus: str = "NA"
    requested_mem: str = "NA"
    exit_code: str = "NA"
    max_rss: str = "NA"
    elapsed: str = "NA"
    output_state: str = "Not_declared"
    acceptance_state: str = "Not_declared"
    next_action: str = "Inspect registered evidence."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only bioflow project dashboard. Reconcile Task_Status.tsv, "
            "run_record.tsv, workflow_status.tsv, and optionally registered "
            "SLURM Job IDs."
        )
    )
    parser.add_argument("--project", default=".", help="Project directory (default: current directory)")
    parser.add_argument(
        "--check-queue",
        action="store_true",
        help="Query squeue/sacct for registered Job IDs only",
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        default=200,
        help="Maximum distinct registered Job IDs queried (default: 200; max: 1000)",
    )
    parser.add_argument(
        "--format",
        choices=("text", "tsv", "json"),
        default="text",
        help="Output format (default: text)",
    )
    return parser.parse_args()


def resolve_project(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise DashboardError(f"project directory does not exist: {path}")

    home = Path.home().resolve()
    broad = {Path("/"), Path("/data9"), Path("/data9/home"), home, home / "projects"}
    if path in broad:
        raise DashboardError(f"refusing broad project root: {path}")

    parts = path.parts
    if len(parts) in {4, 5} and parts[:3] == ("/", "data9", "home"):
        # /data9/home/<user> or /data9/home/<user>/projects
        if len(parts) == 4 or (len(parts) == 5 and parts[4] == "projects"):
            raise DashboardError(f"refusing broad account root: {path}")
    return path


def clean(value: object, default: str = "NA") -> str:
    text = "" if value is None else str(value).strip()
    return text if text and text != "-" else default


def read_tsv(path: Path, required: Iterable[str] = ()) -> tuple[list[dict[str, str]], list[str]]:
    warnings: list[str] = []
    if not path.exists():
        return [], warnings
    if not path.is_file() or not os.access(path, os.R_OK):
        raise DashboardError(f"registered table is not a readable file: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fields = reader.fieldnames or []
        missing = [field for field in required if field not in fields]
        if missing:
            raise DashboardError(
                f"{path.relative_to(path.parent.parent)} missing required columns: "
                + ", ".join(missing)
            )
        rows: list[dict[str, str]] = []
        for line_number, row in enumerate(reader, start=2):
            if None in row:
                warnings.append(f"{path}: line {line_number} has extra tab-separated fields and was ignored")
                continue
            normalized = {key: clean(value, "") for key, value in row.items() if key is not None}
            if not any(normalized.values()):
                continue
            rows.append(normalized)
    return rows, warnings


def normalize_recorded_status(value: str) -> str:
    key = re.sub(r"[\s-]+", "_", clean(value, "Unknown")).lower()
    aliases = {
        "planned": "Planned",
        "draft": "Planned",
        "ready": "Ready",
        "needs_preflight": "Ready",
        "script_ready": "Ready",
        "blocked": "Blocked",
        "waiting": "Blocked",
        "queued": "Queued",
        "pending": "Queued",
        "submitted": "Queued",
        "running": "Running",
        "needs_monitoring": "Running",
        "configuring": "Running",
        "completing": "Running",
        "failed": "Failed",
        "failure": "Failed",
        "needs_triage": "Failed",
        "complete": "Complete_unvalidated",
        "completed": "Complete_unvalidated",
        "done": "Complete_unvalidated",
        "complete_unvalidated": "Complete_unvalidated",
        "needs_validation": "Complete_unvalidated",
        "validated": "Validated",
        "accepted": "Validated",
        "passed": "Validated",
        "analysis_ready": "Validated",
        "delivered": "Validated",
        "skipped": "Skipped",
        "cancelled": "Cancelled",
        "canceled": "Cancelled",
        "unknown": "Unknown",
        "na": "Unknown",
    }
    return aliases.get(key, clean(value, "Unknown"))


def extract_job_id(value: str) -> str:
    text = clean(value, "")
    match = re.match(r"^(\d+)(?:[_\.]\d+)?(?:;[^\s]+)?$", text)
    return match.group(1) if match else "NA"


def load_tasks(project: Path) -> tuple[list[Task], dict[str, str], list[str], list[str]]:
    warnings: list[str] = []
    sources: list[str] = []
    tasks_by_id: dict[str, Task] = {}
    job_to_task: dict[str, str] = {}
    project_status = {"Stage": "UNKNOWN", "Status": "Unknown", "Evidence_Path": "NA", "Updated_Time": "NA"}

    task_path = project / "reports" / "Task_Status.tsv"
    task_rows, row_warnings = read_tsv(task_path, TASK_FIELDS)
    warnings.extend(row_warnings)
    if task_path.exists():
        sources.append("reports/Task_Status.tsv")
    for index, row in enumerate(task_rows, start=1):
        task_id = clean(row.get("Task_ID"), "")
        if not task_id:
            warnings.append(f"{task_path}: data row {index} has no Task_ID and was ignored")
            continue
        status = normalize_recorded_status(row.get("Status", "Unknown"))
        task = Task(
            task_id=task_id,
            stage=clean(row.get("Stage")),
            sample_id=clean(row.get("Sample_ID")),
            recorded_status=status,
            effective_status=status,
            job_id=clean(row.get("Job_ID")),
            dependency=clean(row.get("Dependency")),
            script_path=clean(row.get("Script_Path")),
            log_path=clean(row.get("Log_Path")),
            output_path=clean(row.get("Output_Path")),
            acceptance_path=clean(row.get("Acceptance_Path")),
            retry_count=clean(row.get("Retry_Count")),
            updated_time=clean(row.get("Updated_Time")),
            source="Task_Status.tsv",
        )
        tasks_by_id[task_id] = task

    for task in tasks_by_id.values():
        job_id = extract_job_id(task.job_id)
        if job_id != "NA":
            job_to_task[job_id] = task.task_id

    run_path = project / "reports" / "run_record.tsv"
    run_rows, row_warnings = read_tsv(run_path)
    warnings.extend(row_warnings)
    if run_path.exists():
        sources.append("reports/run_record.tsv")
    for row in run_rows:
        job_raw = clean(row.get("Job_ID"))
        job_id = extract_job_id(job_raw)
        if job_id == "NA" or job_id in job_to_task:
            continue
        task_id = f"Job_{job_id}"
        suffix = 2
        while task_id in tasks_by_id:
            task_id = f"Job_{job_id}_{suffix}"
            suffix += 1
        tasks_by_id[task_id] = Task(
            task_id=task_id,
            stage=clean(row.get("Job_Name"), "Submitted"),
            recorded_status="Submitted_recorded",
            effective_status="Submitted_recorded",
            job_id=job_raw,
            script_path=clean(row.get("Script")),
            partition=clean(row.get("Partition")),
            requested_cpus=clean(row.get("CPUs")),
            requested_mem=clean(row.get("Mem")),
            updated_time=clean(row.get("Submit_Time")),
            source="run_record.tsv",
        )
        job_to_task[job_id] = task_id

    workflow_path = project / "reports" / "workflow_status.tsv"
    workflow_rows, row_warnings = read_tsv(workflow_path)
    warnings.extend(row_warnings)
    if workflow_path.exists():
        sources.append("reports/workflow_status.tsv")
    if workflow_rows:
        latest = workflow_rows[-1]
        project_status = {
            "Stage": clean(latest.get("Stage"), "UNKNOWN"),
            "Status": clean(latest.get("Status"), "Unknown"),
            "Evidence_Path": clean(latest.get("Evidence_Path")),
            "Updated_Time": clean(latest.get("Updated_Time")),
        }
    for row in workflow_rows:
        job_raw = clean(row.get("Job_ID"))
        job_id = extract_job_id(job_raw)
        if job_id == "NA" or job_id in job_to_task:
            continue
        task_id = f"Workflow_{job_id}"
        tasks_by_id[task_id] = Task(
            task_id=task_id,
            stage=clean(row.get("Stage")),
            recorded_status=normalize_recorded_status(row.get("Status", "Unknown")),
            effective_status=normalize_recorded_status(row.get("Status", "Unknown")),
            job_id=job_raw,
            output_path=clean(row.get("Output_Path")),
            updated_time=clean(row.get("Updated_Time")),
            source="workflow_status.tsv",
        )
        job_to_task[job_id] = task_id

    return list(tasks_by_id.values()), project_status, sources, warnings


def run_scheduler(command: list[str], label: str, warnings: list[str]) -> str:
    if shutil.which(command[0]) is None:
        warnings.append(f"{label} unavailable: {command[0]} not found in PATH")
        return ""
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        warnings.append(f"{label} query failed: {exc}")
        return ""
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().replace("\t", " ")
        warnings.append(f"{label} query exit {result.returncode}: {detail or 'no diagnostic'}")
        return ""
    return result.stdout


def normalized_slurm_state(value: str) -> str:
    return clean(value, "UNKNOWN").upper().split()[0].rstrip("+")


def root_job_id(value: str) -> str:
    match = re.match(r"^(\d+)", clean(value, ""))
    return match.group(1) if match else "NA"


def effective_from_slurm(states: Iterable[str]) -> str:
    state_set = {normalized_slurm_state(state) for state in states}
    if state_set & ACTIVE_SLURM:
        return "Running"
    if state_set & QUEUED_SLURM:
        return "Queued"
    if state_set & FAILED_SLURM:
        return "Failed"
    if state_set & CANCELLED_SLURM:
        return "Cancelled"
    if state_set and state_set <= SUCCESS_SLURM:
        return "Complete_unvalidated"
    if state_set & SUCCESS_SLURM and not (state_set - SUCCESS_SLURM):
        return "Complete_unvalidated"
    return "Unknown"


def state_detail(rows: list[list[str]]) -> str:
    counts = Counter(normalized_slurm_state(row[1]) for row in rows)
    return ",".join(f"{state}={counts[state]}" for state in sorted(counts)) or "NA"


def unique_values(values: Iterable[str]) -> str:
    result: list[str] = []
    for value in values:
        item = clean(value, "")
        if item and item not in result:
            result.append(item)
    return ",".join(result) or "NA"


def memory_value(value: str) -> float:
    text = clean(value, "").upper()
    match = re.fullmatch(r"([0-9]+(?:[.][0-9]+)?)([KMGTPE]?)(?:I?B)?", text)
    if not match:
        return -1.0
    units = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4, "P": 1024**5, "E": 1024**6}
    return float(match.group(1)) * units[match.group(2)]


def max_memory(values: Iterable[str]) -> str:
    candidates = [(memory_value(value), clean(value, "")) for value in values]
    candidates = [item for item in candidates if item[0] >= 0 and item[1]]
    return max(candidates, default=(-1.0, "NA"), key=lambda item: item[0])[1]


def query_scheduler(job_ids: list[str], warnings: list[str]) -> dict[str, SchedulerEvidence]:
    evidence: dict[str, SchedulerEvidence] = {}
    if not job_ids:
        return evidence
    ids_csv = ",".join(job_ids)

    queue_out = run_scheduler(
        ["squeue", "-j", ids_csv, "-h", "-r", "-o", "%i|%T|%M|%R|%C|%m|%P|%j"],
        "squeue",
        warnings,
    )
    queue_rows: dict[str, list[list[str]]] = defaultdict(list)
    for line in queue_out.splitlines():
        fields = line.strip().split("|", 7)
        if len(fields) != 8:
            continue
        root = root_job_id(fields[0])
        if root != "NA":
            queue_rows[root].append(fields)

    for root, rows in queue_rows.items():
        states = [row[1] for row in rows]
        evidence[root] = SchedulerEvidence(
            state=effective_from_slurm(states),
            detail=state_detail(rows),
            elapsed=clean(rows[0][2]),
            reason=unique_values(row[3] for row in rows),
            partition=unique_values(row[6] for row in rows),
            requested_cpus=clean(rows[0][4]),
            requested_mem=clean(rows[0][5]),
        )

    acct_out = run_scheduler(
        [
            "sacct",
            "-j",
            ids_csv,
            "--format=JobIDRaw,State,ExitCode,MaxRSS,Elapsed,ReqCPUS,ReqMem,Partition",
            "-n",
            "-P",
        ],
        "sacct",
        warnings,
    )
    acct_rows: dict[str, list[list[str]]] = defaultdict(list)
    for line in acct_out.splitlines():
        fields = line.strip().split("|", 7)
        if len(fields) != 8:
            continue
        root = root_job_id(fields[0])
        if root != "NA":
            acct_rows[root].append(fields)

    for root, rows in acct_rows.items():
        if root in queue_rows:
            continue
        exact = [row for row in rows if clean(row[0]) == root]
        array_rows = [
            row for row in rows if "_" in clean(row[0], "") and "." not in clean(row[0], "")
        ]
        usable = array_rows or exact or [row for row in rows if "." not in clean(row[0], "")]
        usable = usable or rows
        status = effective_from_slurm(row[1] for row in usable)
        representative = usable[0]
        failing = next(
            (row for row in usable if normalized_slurm_state(row[1]) in FAILED_SLURM | CANCELLED_SLURM),
            representative,
        )
        evidence[root] = SchedulerEvidence(
            state=status,
            detail=state_detail(usable),
            exit_code=clean(failing[2]),
            max_rss=max_memory(row[3] for row in usable),
            elapsed=clean(failing[4]),
            partition=unique_values(row[7] for row in usable),
            requested_cpus=clean(failing[5]),
            requested_mem=clean(failing[6]),
        )
    return evidence


def cheap_path_state(project: Path, value: str) -> str:
    text = clean(value, "")
    if not text or text == "NA":
        return "Not_declared"
    if any(token in text for token in ("*", "?", "[", "]", "%j", "%x")):
        return "Pattern_not_checked"
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = project / path
    try:
        if not path.exists():
            return "Missing"
        if path.is_file():
            return "Present" if path.stat().st_size > 0 else "Empty"
        if path.is_dir():
            try:
                next(path.iterdir())
            except StopIteration:
                return "Empty_directory"
            except OSError:
                return "Unreadable"
            return "Present_directory"
        return "Present_other"
    except OSError:
        return "Unreadable"


def next_action(task: Task) -> str:
    status = task.effective_status
    actions = {
        "Running": "Monitor squeue/sacct and bounded log tails; do not edit or resubmit active work.",
        "Queued": "Monitor queue reason and wait; do not duplicate the submission.",
        "Failed": "Read accounting and logs, triage the smallest fix, and ask before resubmission.",
        "Blocked": "Resolve the registered dependency or blocker before execution.",
        "Ready": "Run preflight/resource review, then ask before submission.",
        "Complete_unvalidated": "Run the declared acceptance checks before interpretation or downstream use.",
        "Validated": "Proceed to the next declared dependency, interpretation, or delivery step.",
        "Planned": "Complete inputs, dependencies, and execution plan before preflight.",
        "Cancelled": "Record cancellation reason and decide whether a new run is authorized.",
        "Skipped": "Preserve the skip reason and check downstream consequences.",
        "Submitted_recorded": "Check squeue/sacct or logs; submission is recorded but terminal state is unknown.",
        "Unknown": "Inspect the registered status, Job ID, logs, output, and acceptance evidence.",
    }
    return actions.get(status, actions["Unknown"])


def reconcile_tasks(
    project: Path,
    tasks: list[Task],
    scheduler: dict[str, SchedulerEvidence],
    warnings: list[str],
) -> None:
    task_by_id = {task.task_id: task for task in tasks}

    for task in tasks:
        job_id = extract_job_id(task.job_id)
        sched = scheduler.get(job_id)
        if sched:
            task.scheduler_state = sched.state
            task.scheduler_detail = sched.detail
            task.scheduler_reason = sched.reason
            if sched.partition != "NA":
                task.partition = sched.partition
            if sched.requested_cpus != "NA":
                task.requested_cpus = sched.requested_cpus
            if sched.requested_mem != "NA":
                task.requested_mem = sched.requested_mem
            task.exit_code = sched.exit_code
            task.max_rss = sched.max_rss
            task.elapsed = sched.elapsed
            if sched.state in {"Running", "Queued", "Failed", "Cancelled"}:
                task.effective_status = sched.state
            elif sched.state == "Complete_unvalidated" and task.recorded_status != "Validated":
                task.effective_status = "Complete_unvalidated"

    # Resolve dependencies only after every registered task has scheduler evidence.
    for task in tasks:
        dependencies = [item.strip() for item in clean(task.dependency, "").split(",") if item.strip()]
        if dependencies and task.effective_status in {"Planned", "Ready", "Unknown", "Submitted_recorded"}:
            unresolved = [
                dependency
                for dependency in dependencies
                if dependency not in task_by_id
                or task_by_id[dependency].effective_status not in {"Validated", "Skipped"}
            ]
            if unresolved:
                task.effective_status = "Blocked"
                warnings.append(
                    f"Task_ID={task.task_id} has unresolved dependencies: {', '.join(unresolved)}"
                )

        task.output_state = cheap_path_state(project, task.output_path)
        task.acceptance_state = cheap_path_state(project, task.acceptance_path)
        if task.effective_status in {"Complete_unvalidated", "Validated"} and task.output_state in {
            "Missing",
            "Empty",
            "Empty_directory",
            "Unreadable",
        }:
            warnings.append(
                f"Task_ID={task.task_id} is {task.effective_status} but Output_Path is {task.output_state}: "
                f"{task.output_path}"
            )
            task.effective_status = "Failed"
        if task.effective_status == "Validated" and task.acceptance_state in {
            "Not_declared",
            "Missing",
            "Empty",
            "Empty_directory",
            "Unreadable",
        }:
            warnings.append(
                f"Task_ID={task.task_id} is Validated but Acceptance_Path is "
                f"{task.acceptance_state}: {task.acceptance_path}"
            )
            task.effective_status = "Complete_unvalidated"
        task.next_action = next_action(task)


def summary_counts(tasks: list[Task]) -> dict[str, int]:
    counts = Counter(task.effective_status for task in tasks)
    ordered: dict[str, int] = {}
    for status in DISPLAY_ORDER:
        if counts.get(status):
            ordered[status] = counts[status]
    for status in sorted(set(counts) - set(ordered)):
        ordered[status] = counts[status]
    return ordered


def task_sort_key(task: Task) -> tuple[int, str]:
    try:
        rank = DISPLAY_ORDER.index(task.effective_status)
    except ValueError:
        rank = len(DISPLAY_ORDER)
    return rank, task.task_id


def load_workspace_status(project: Path, sources: list[str], warnings: list[str]) -> dict[str, object]:
    policy = project / "config" / "Workspace_Policy.tsv"
    if not policy.exists():
        return {"Enabled": False, "Status": "NA", "Modules": 0, "Routes": 0, "Findings": 0}
    sources.extend([
        "config/Workspace_Policy.tsv",
        "config/Workspace_Modules.tsv",
        "config/Workspace_Routes.tsv",
        "config/Directory_Index.tsv",
    ])
    try:
        import workspace_steward

        summary = workspace_steward.workspace_summary(project)
        return {"Enabled": True, **summary}
    except Exception as exc:  # malformed optional contract is dashboard evidence, not a crash
        message = f"Workspace Steward contract could not be audited: {exc}"
        warnings.append(message)
        return {"Enabled": True, "Status": "BLOCK", "Modules": 0, "Routes": 0, "Findings": 1, "Error": str(exc)}


def render_text(
    project: Path,
    project_status: dict[str, str],
    sources: list[str],
    tasks: list[Task],
    counts: dict[str, int],
    warnings: list[str],
    checked_queue: bool,
    workspace: dict[str, object],
) -> None:
    print(f"[INFO] Project: {project}")
    print(f"[INFO] Check_queue: {str(checked_queue).lower()}")
    print(f"[INFO] Sources: {', '.join(sources) if sources else 'NA'}")
    print(
        "[INFO] Project_stage: "
        f"{project_status['Stage']} | Status={project_status['Status']} | "
        f"Evidence={project_status['Evidence_Path']} | Updated={project_status['Updated_Time']}"
    )
    print(
        "[INFO] Workspace: "
        f"{workspace.get('Status', 'NA')} | Enabled={str(workspace.get('Enabled', False)).lower()} | "
        f"Modules={workspace.get('Modules', 0)} | Routes={workspace.get('Routes', 0)} | "
        f"Missing={workspace.get('Missing', 0)} | Unplanned={workspace.get('Unplanned', 0)} | "
        f"Findings={workspace.get('Findings', 0)}"
    )
    if counts:
        print("[SUMMARY] " + " ".join(f"{status}={count}" for status, count in counts.items()))
    else:
        print("[SUMMARY] No_registered_tasks=1")

    print("[TASKS]")
    if not tasks:
        print("  - NA | Register tasks in reports/Task_Status.tsv or submit through submit_and_log.sh.")
    for task in sorted(tasks, key=task_sort_key):
        print(
            f"  - {task.task_id} | Status={task.effective_status} | Recorded={task.recorded_status} | "
            f"Stage={task.stage} | Sample={task.sample_id} | Job_ID={task.job_id} | "
            f"Scheduler={task.scheduler_state} ({task.scheduler_detail}) | "
            f"Reason_or_Node={task.scheduler_reason} | Partition={task.partition} | "
            f"ReqCPUs={task.requested_cpus} | ReqMem={task.requested_mem} | "
            f"Exit={task.exit_code} | MaxRSS={task.max_rss} | Elapsed={task.elapsed} | "
            f"Output={task.output_state} | "
            f"Acceptance={task.acceptance_state} | Next_Action={task.next_action}"
        )

    if warnings:
        print("[WARNINGS]")
        for warning in warnings:
            print(f"  - {warning}")


def render_tsv(tasks: list[Task]) -> None:
    fields = [
        "Task_ID",
        "Stage",
        "Sample_ID",
        "Recorded_Status",
        "Effective_Status",
        "Job_ID",
        "Scheduler_State",
        "Scheduler_Detail",
        "Scheduler_Reason_Or_Node",
        "Partition",
        "Requested_CPUs",
        "Requested_Mem",
        "Exit_Code",
        "MaxRSS",
        "Elapsed",
        "Output_State",
        "Acceptance_State",
        "Source",
        "Next_Action",
    ]
    writer = csv.DictWriter(sys.stdout, fieldnames=fields, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    for task in sorted(tasks, key=task_sort_key):
        writer.writerow(
            {
                "Task_ID": task.task_id,
                "Stage": task.stage,
                "Sample_ID": task.sample_id,
                "Recorded_Status": task.recorded_status,
                "Effective_Status": task.effective_status,
                "Job_ID": task.job_id,
                "Scheduler_State": task.scheduler_state,
                "Scheduler_Detail": task.scheduler_detail,
                "Scheduler_Reason_Or_Node": task.scheduler_reason,
                "Partition": task.partition,
                "Requested_CPUs": task.requested_cpus,
                "Requested_Mem": task.requested_mem,
                "Exit_Code": task.exit_code,
                "MaxRSS": task.max_rss,
                "Elapsed": task.elapsed,
                "Output_State": task.output_state,
                "Acceptance_State": task.acceptance_state,
                "Source": task.source,
                "Next_Action": task.next_action,
            }
        )


def render_json(
    project: Path,
    project_status: dict[str, str],
    sources: list[str],
    tasks: list[Task],
    counts: dict[str, int],
    warnings: list[str],
    checked_queue: bool,
    workspace: dict[str, object],
) -> None:
    payload = {
        "Project": str(project),
        "Check_queue": checked_queue,
        "Sources": sources,
        "Project_status": project_status,
        "Summary": counts,
        "Workspace": workspace,
        "Tasks": [asdict(task) for task in sorted(tasks, key=task_sort_key)],
        "Warnings": warnings,
    }
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def main() -> int:
    args = parse_args()
    if args.max_jobs < 1 or args.max_jobs > 1000:
        raise DashboardError("--max-jobs must be between 1 and 1000")

    project = resolve_project(args.project)
    tasks, project_status, sources, warnings = load_tasks(project)
    job_ids = sorted(
        {job_id for task in tasks if (job_id := extract_job_id(task.job_id)) != "NA"},
        key=int,
    )
    if len(job_ids) > args.max_jobs:
        warnings.append(
            f"registered Job IDs={len(job_ids)} exceeds --max-jobs={args.max_jobs}; "
            "queue/accounting query was truncated"
        )
        job_ids = job_ids[: args.max_jobs]

    scheduler = query_scheduler(job_ids, warnings) if args.check_queue else {}
    reconcile_tasks(project, tasks, scheduler, warnings)
    counts = summary_counts(tasks)
    workspace = load_workspace_status(project, sources, warnings)

    if args.format == "json":
        render_json(project, project_status, sources, tasks, counts, warnings, args.check_queue, workspace)
    elif args.format == "tsv":
        render_tsv(tasks)
    else:
        render_text(project, project_status, sources, tasks, counts, warnings, args.check_queue, workspace)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DashboardError as exc:
        print(f"FAIL | {exc}", file=sys.stderr)
        raise SystemExit(2)
