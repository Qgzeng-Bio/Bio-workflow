# Resume protocol

Use this protocol when taking over an existing qgzeng bioinformatics project from
any stage. The goal is to avoid restarting work unnecessarily. First classify the
current state from bounded evidence, then choose the smallest safe next action.

## Required response shape

```text
📌 当前阶段
🔎 证据
⚠️ 阻塞
🛠️ 下一步最小动作
```

Keep evidence concrete: paths, job IDs, exit codes, recent log snippets, result
files, and validation records. If evidence is mixed, name secondary candidates but
recommend one primary next action.

## Read-only state snapshot

Prefer the bundled audit script:

```bash
scripts/project_state_audit.sh --project <project_dir> --max-depth 3 --max-files 1000
```

Default to `--project .` when the user is already in the intended project. Do not
walk upward to parent directories to infer a larger root. Refuse broad roots such
as `/`, `/data9`, `/data9/home/qgzeng`, or `/data9/home/qgzeng/projects` unless the
user explicitly confirms a broader audit and provides a bounded plan.

Use `--check-queue` only when job IDs or SLURM log clues are present. Queue checks
may call `squeue` and `sacct`; they must not submit, cancel, resubmit, repair, or
write project status.

Bounded manual evidence sources:

- `config/`: manifests, parameters, sample sheets.
- `data/`: symlinks or staged inputs, not broad raw-data scans.
- `scripts/`: `.sh`, `.slurm`, `.sbatch`, workflow drivers.
- `logs/`: `.out`, `.err`, `.log`, job IDs, completion/failure lines.
- `results/`: expected output files and summary tables.
- `reports/`: acceptance reports and `workflow_status.tsv`.
- `tmp/`: only for clues; never treat tmp output as final success.

## State definitions

### Input_ready

**Decision evidence**

- Explicit inputs, manifests, or configuration files exist under `data/` or `config/`.
- No runnable SLURM/workflow script is present, or scripts are incomplete drafts.
- No job IDs, run logs, or final outputs show a submitted workflow.

**Forbidden actions**

- Do not submit jobs.
- Do not invent missing sample design, reference versions, or output criteria.
- Do not validate or interpret biology before the workflow exists.

**Next entry**

- Return to workflow steps 1-2: define the research question, input inventory,
  expected outputs, and success criteria.

**Common risks**

- Treating a file listing as a validated manifest.
- Missing paired-end naming, reference version, strandedness, or chromosome naming
  compatibility.

### Script_ready

**Decision evidence**

- Runnable scripts exist under `scripts/`, especially `.slurm`, `.sbatch`, or shell
  drivers with `#SBATCH`.
- No matching submitted job, queue state, or completion/failure log is found.
- Outputs are absent or clearly from an older unrelated run.

**Forbidden actions**

- Do not run `sbatch` before preflight and user confirmation.
- Do not silently add `#SBATCH --time`.
- Do not overwrite existing result directories.

**Next entry**

- Run `scripts/slurm_preflight.sh --script <script>`.
- Explain any `WARN` and treat any `FAIL` as a blocker.

**Common risks**

- Relative log paths, missing strict mode, uncapped arrays, protected-directory
  writes, and CPU/memory requests copied from unrelated jobs.

### Queued_or_running

**Decision evidence**

- `squeue` shows the job pending, running, configuring, or completing.
- Logs contain a job start line or job ID without normal completion or failure.
- `workflow_status.tsv` or handoff notes mark the stage as submitted/running.

**Forbidden actions**

- Do not edit scripts for a still-running job unless the user explicitly asks for
  a future rerun script.
- Do not resubmit, cancel, or change concurrency without confirmation.
- Do not declare success from partial outputs.

**Next entry**

- Monitor with `squeue`, `sacct`, and bounded log tails.
- Wait for terminal state before validation or failure triage.

**Common risks**

- Mistaking empty `tasks.txt` or partial output files for completion.
- Editing scripts after submission and losing reproducibility of the active job.

### Failed

**Decision evidence**

- `sacct` reports `FAILED`, `TIMEOUT`, `OUT_OF_MEMORY`, non-zero exit code, or a
  comparable terminal failure state.
- `.err` or `.out` contains OOM, time limit, missing input, permission, tool/env,
  segfault, disk full, format/chromosome mismatch, or network/proxy errors.
- Expected outputs are absent, empty, truncated, or marked failed by the workflow.

**Forbidden actions**

- Do not rerun with bigger resources by habit.
- Do not resubmit before reading `.err` and relevant `.out`.
- Do not delete or overwrite failed outputs unless the user confirms.

**Next entry**

- Run `scripts/slurm_failure_triage.sh --jobid <id>` or
  `scripts/slurm_failure_triage.sh --err <file> [--out <file>]`.
- Propose the smallest justified fix and ask before resubmission.

**Common risks**

- Treating `TIMEOUT` as a reason to wrap commands with shell `timeout`.
- Ignoring `MaxRSS`, array concurrency, temporary disk growth, or chromosome-name
  mismatches.

### Complete_unvalidated

**Decision evidence**

- Expected result files exist and are non-empty.
- Logs show normal completion or all planned jobs reached a successful terminal state.
- `reports/workflow_status.tsv` is absent, incomplete, or lacks result-acceptance
  evidence for the current stage.

**Forbidden actions**

- Do not proceed directly to biological interpretation.
- Do not call final results accepted from exit code 0 alone.
- Do not make publication figures until data-layer checks pass.

**Next entry**

- Use the result acceptance checklist in `references/validation-checklists.md`.
- Record concrete counts, paths, versions, and caveats before analysis.

**Common risks**

- Empty files, wrong sample counts, coordinate-system mismatches, silently dropped
  samples, or successful logs from only part of an array.

### Analysis_ready

**Decision evidence**

- Result files exist and have passed run/data/analysis-layer acceptance.
- `reports/workflow_status.tsv`, an acceptance report, or handoff notes record
  validation evidence for the current stage.
- The next unresolved task is interpretation, plotting, reporting, or downstream
  biological analysis.

**Forbidden actions**

- Do not re-run upstream work without a specific reason.
- Do not present speculative biology as validated fact.
- Do not omit methods, filters, or result-count caveats from reports.

**Next entry**

- Proceed to plotting/reporting or biological interpretation.
- For quinoa, connect evidence to stress tolerance, salinity, drought response,
  mineral accumulation, subgenome differentiation, structural variation, or
  pangenome variability only when the data support it.

**Common risks**

- Overstating weak associations, mixing validated and speculative conclusions, or
  generating figures from unversioned intermediate tables.

## `reports/workflow_status.tsv`

Use this standard status table only after user confirmation. The audit script prints
a suggested row but must not write the file by default.

Required columns, tab-separated:

```text
Stage	Status	Evidence_Path	Job_ID	Exit_Code	Input_Path	Output_Path	Next_Action	Updated_Time
```

Column rules:

- `Stage`: one of `Input_ready`, `Script_ready`, `Queued_or_running`, `Failed`,
  `Complete_unvalidated`, or `Analysis_ready`.
- `Status`: short machine-readable status such as `Needs_planning`,
  `Needs_preflight`, `Running`, `Needs_triage`, `Needs_validation`, or `Validated`.
- `Evidence_Path`: most important file/log/report supporting the state.
- `Job_ID`: SLURM job ID or `NA`.
- `Exit_Code`: SLURM or process exit code, or `NA`.
- `Input_Path`: primary manifest/input path or `NA`.
- `Output_Path`: primary result/output path or `NA`.
- `Next_Action`: concise next action without tabs.
- `Updated_Time`: timestamp in ISO-like local form, for example
  `2026-06-15T18:30:00+0800`.

Do not use `workflow_status.tsv` as proof by itself. It points to evidence; the
evidence path must remain readable.
