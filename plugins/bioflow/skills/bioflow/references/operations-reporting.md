# Operations, downloads, qp mode, and reporting

Use this reference for operational details that are not part of the core routing
logic: safe raw-data downloads, the user's qp mode, and plotting/reporting
handoff expectations.

## Monitor and diagnose

After submission, record job ID, script path, config path, resource request, and
submit time.

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
confirmation.

## Plot and report

For publication figures, follow the user's Nature-style plotting rules from
`AGENTS.md`: Arial fonts, white background, no grids, clean axes,
colorblind-aware palettes, PDF first, PNG/JPEG at 300 dpi, and figure legends in
English.

Always save plotting data, code, and parameters. Report what the figure proves
and what it does not prove. For figure acceptance, read
`references/validation-checklists.md`.

