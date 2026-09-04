# Task monitoring and project dashboard

Use this contract when the user asks what is running, whether jobs finished, what
failed, what is blocked, or what should happen next. Project lifecycle and task
status are related but different:

- Layout v2 uses `docs/status/workflow_status.tsv` for the primary project stage,
  `docs/status/Task_Status.tsv` for concurrent work units, and
  `docs/status/run_record.tsv` for submissions.
- Legacy projects retain the equivalent three files under `reports/`.
- An enabled Workspace Steward supplies static module/route expectations; it does
  not own task runtime status.

Do not collapse a mixed project into one task state. A project may have running,
failed, validated, and blocked tasks at the same time.

## Read-only dashboard

Run from any directory by resolving the script relative to the bioflow skill root:

```bash
python3 scripts/project_dashboard.py --project <project_dir>
python3 scripts/project_dashboard.py --project <project_dir> --check-queue
python3 scripts/project_dashboard.py --project <project_dir> --check-queue --format json
```

The dashboard detects `config/Project_Layout.tsv` and reads only the active
profile's three registered status files above; it never merges v2 and legacy
copies. It does not
search for unknown biological inputs, crawl parent directories, write status,
submit, cancel, resubmit, or change concurrency. `--check-queue` queries only
registered numeric Job IDs and caps the query with `--max-jobs` (default 200).

The dashboard reconciles recorded state with `squeue`/`sacct` when available,
reports scheduler state/detail, pending reason or running node, partition,
requested CPU/memory, maximum observed array-element `MaxRSS`, elapsed time, and
exit code separately from acceptance. It never treats SLURM `COMPLETED` as
biological validation. A completed scheduler job becomes
`Complete_unvalidated` unless a project-local task row already cites validation.
A terminal failure or a missing explicitly registered output remains a blocker.

When `config/Workspace_Policy.tsv` exists, the dashboard also performs the
bounded read-only Workspace audit. Text reports Workspace PASS/WARN/BLOCK plus
module/route/missing/unplanned counts; JSON adds a `Workspace` object. Task TSV
remains unchanged. A malformed workspace is reported as a dashboard warning and
Workspace BLOCK, not silently ignored.

## Task status table

Use tab-separated columns:

```text
Task_ID\tStage\tSample_ID\tStatus\tJob_ID\tDependency\tScript_Path\tLog_Path\tOutput_Path\tAcceptance_Path\tRetry_Count\tUpdated_Time
```

Recommended `Status` values:

- `Planned`: defined but not ready.
- `Ready`: inputs and dependencies are ready; preflight or execution is next.
- `Blocked`: waiting for a decision, input, dependency, environment, or repair.
- `Queued`: submitted and pending.
- `Running`: actively executing.
- `Failed`: terminal scheduler/program/output-integrity failure.
- `Complete_unvalidated`: execution completed; acceptance is still required.
- `Validated`: task outputs passed their declared acceptance gate.
- `Skipped`: deliberately omitted with a reason.
- `Cancelled`: cancelled with provenance; do not imply failure or success.
- `Unknown`: evidence is insufficient.

Use `NA` for fields that do not apply. `Task_ID` must be stable and unique.
In a managed workspace, `Stage` is an existing stable `Module_ID` (`M001`), and
`Script_Path`, `Log_Path`, `Output_Path`, and `Acceptance_Path` must resolve under
that module's reviewed roles. Submission must use exactly the registered
`Script_Path`. Every ID in Workspace `Producer_Tasks`/`Consumer_Tasks` must exist
in this table, and a producer task's `Stage` must equal the owning route module;
consumers may belong to downstream modules.
Repeated rows for one `Task_ID` are allowed as an append-only history; the last
row is the current record. Separate multiple dependencies with commas; an empty,
`NA`, `N/A`, `None`, or `Null` dependency value means that no dependency is
declared and must never be interpreted as a Task ID. A task
with unresolved dependencies is reported as `Blocked` unless scheduler evidence
shows that it is already queued or running.

Paths may be project-relative or absolute explicit paths. Do not put filename
globs or recursive search expressions in the table. `Output_Path` is the expected
artifact or directory whose existence can be checked cheaply; acceptance still
comes from `Acceptance_Path`, not existence alone.

## Evidence and precedence

For each registered task, use this precedence:

1. active `squeue` evidence;
2. terminal `sacct` failure/cancellation evidence;
3. terminal `sacct` completion evidence;
4. the latest project-local task row;
5. submission-only evidence from `run_record.tsv`;
6. project-wide workflow status as a final registration clue.

A manually validated task remains `Validated` when accounting says `COMPLETED`,
but failure evidence overrides stale optimistic status. Missing or empty explicit
outputs after completion are reported as failed integrity checks. Queue/accounting
unavailability is a warning, not proof that a job finished.

## Reporting contract

A progress answer should cover:

- project-wide lifecycle stage when available;
- counts of queued, running, failed, complete-unvalidated, validated, and blocked
  tasks;
- concrete Job IDs and scheduler evidence;
- missing outputs, logs, or acceptance evidence;
- the smallest safe next action for each blocker class.

Do not automatically append or rewrite `Task_Status.tsv` or
`workflow_status.tsv`. Show a proposed TSV row and obtain confirmation before a
persistent status update. Workspace audit/preflight reads the latest row only;
it never copies task state into Workspace tables. Ask before `sbatch`, `scancel`, resubmission, changing
concurrency, deleting partial output, or overwriting results.

## qp compatibility

The user's qp directory still uses `tasks.txt`, `task_log.txt`, and
`run_record.txt`. These files remain authoritative for qp itself. Do not infer
that qp is idle from an empty `tasks.txt`; inspect its task log and SLURM evidence.
For unified dashboard reporting, register qp manager or child Job IDs in
`Task_Status.tsv` rather than parsing arbitrary command text or recursively
searching qp outputs.
