# Operations, downloads, qp mode, and reporting

Use this reference for operational details that are not part of the core routing
logic: safe raw-data downloads, the user's qp mode, and plotting/reporting
handoff expectations.

## Monitor and diagnose

After submission, record job ID, script/config paths, resource request, submit
time, expected output, and task identity. For a progress, running-task, or mixed
project request, read `references/task-monitoring.md` and start with the read-only
dashboard:

```bash
python3 scripts/project_dashboard.py --project <project_dir>
python3 scripts/project_dashboard.py --project <project_dir> --check-queue
```

The dashboard reconciles `Task_Status.tsv`, `run_record.tsv`, project status, and
only registered Job IDs. It never writes status or changes the queue. Preserve the
difference between scheduler `COMPLETED`, task `Complete_unvalidated`, and
accepted `Validated`; report concurrent failed/running/blocked tasks separately.

For failures:

1. Check `sacct` state, exit code, MaxRSS, and elapsed time.
2. Read the matching `.err` and relevant `.out`.
3. Classify the failure: missing input, permission, module/env, OOM, TIMEOUT,
   segfault, disk full, shell/pipefail error, software format incompatibility, or
   biological/data issue.
4. Propose the smallest justified fix.
5. Ask before resubmitting.

Treat `TIMEOUT` as a script/resource-policy problem first. Do not wrap long
bioinformatics commands with shell `timeout` as a completion mechanism.

## Download raw data safely

Do not route original data downloads through external proxies. Avoid
`proxychains`, `http_proxy`, `https_proxy`, and `all_proxy` for SRA/ENA/NCBI-style
raw data unless the user explicitly confirms.

Before large downloads:

- confirm destination and expected size
- avoid writing into protected raw-data directories unless confirmed
- prefer project staging directories with manifests and checksums
- use direct, cluster-appropriate tools
- if proxy variables appear necessary or already set, warn and ask first

After download, validate checksums or file integrity when available.

## qp mode

Use qp mode for the user's multi-task queue pattern:

- working directory: `/data9/home/qgzeng/projects/2-C_quinoa/12-jobs/`
- entry script: `manager_parallel.slurm`
- manager: `run_task_manager_parallel.sh`
- task list: `tasks.txt`
- history: `run_record.txt`

Each task command must include environment activation and explicit output paths.
Empty `tasks.txt` does not prove no work is running; inspect `task_log.txt` and
SLURM state. Do not change `MAX_PARALLEL` for large-memory jobs without
confirmation. For a unified bioflow dashboard, register the qp manager or child Job IDs in the
active layout's `Task_Status.tsv`; do not parse arbitrary task commands or
recursively discover qp outputs.

## Plot and report

Delegate scientific plotting, redesign, export, rendered-image QA, and
old-vs-new comparison to the installed skill named `paperplot-skills`. Codex
invokes `$paperplot-skills`; Pi must load the discovered PaperPlot skill before
drawing (`/skill:paperplot-skills` is the user's force-load command). Do not
substitute another plotting skill or duplicate PaperPlot's visual workflow inside
bioflow. If it is unavailable on the active surface, state the blocker before
drawing or claiming PaperPlot QA.

Bioflow still owns biological readiness and provenance: identify whether the
figure is QC, exploratory, or publication-grade; verify data source,
reference/version, coordinates, units, transforms, sample design, statistics,
and claim status before delegation. For a multi-metric genome-quality figure,
read `references/paperplot-handoff-contract.md` and first run
`scripts/prepare_paperplot_handoff.py`. PaperPlot receives that strict TSV plus
readiness JSON and uses its explicit `Key_Sample`; it must not select labels by
averaging heterogeneous raw values. In qgzeng project-local plotting scripts,
read the sidecar with `read.delim` (or an equivalent explicit TSV reader), not a
stock CSV path. Unit conversion is allowed only when the handoff converts both
number and label and records the factor.

In layout v2, save each retained figure as the package defined by
`references/project-layout.md`: PDF/PNG and README at package root, exact plotting
TSV under `source-data/`, generated metadata/check/review MD/JSON under `checks/`,
and the one editable plot script under `scripts/<module>/plotting/`. Draft
alternatives stay in tmp. Read `references/validation-checklists.md` for
bioinformatics figure acceptance. Visual design, export, and rendered-image QA
remain entirely in PaperPlot; Bioflow does not modify its templates or runtime.

