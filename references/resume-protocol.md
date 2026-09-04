# Resume protocol

Use this protocol to take over an existing qgzeng bioinformatics project without
restarting valid work. Read `references/project-lifecycle.md` first; it is the
single source of truth for stages, transition gates, startup planning, management
artifacts, and `workflow_status.tsv`.

## Response content

Report the primary stage, concrete evidence, blockers, and smallest safe next
action. Use paths, job IDs, exit codes, recent log lines, outputs, and acceptance
records. If evidence is mixed, name secondary candidates and strategy switches.

## Read-only state snapshot

Prefer:

```bash
scripts/project_state_audit.sh --project <project_dir> --max-depth 3 --max-files 1000
```

Default to `--project .` in the intended project. Do not walk upward or audit `/`,
`/data9`, an account home, or a broad projects root. Add `--check-queue` only when
job IDs or SLURM clues exist. Queue checks may read `squeue`/`sacct`; they must not
submit, cancel, resubmit, repair, or write status.

Inspect only bounded project-local evidence. Layout v2 uses `config/`,
`rawdata/`, `scripts/`, `logs/`, `tmp/`, `results/`, `docs/`, and
`manuscripts/`; legacy projects retain `data/` and `reports/`. Raw inputs are
explicit entries/links only, not a broad data scan. `tmp/` provides clues only
and is never formal result, figure, claim, acceptance, delivery, or manuscript
evidence. Run `project_structure_audit.py` for a v2 project before accepting its
layout.

If the biological input location is unknown, ask for an exact path, manifest,
pattern, or approved bounded root. Do not recursively search parent directories,
project collections, or `$HOME` to infer it.

## Mixed-evidence precedence

Confirm the audit's primary stage against the lifecycle transition gate. Prefer:

1. active queue or newest incomplete-run evidence;
2. terminal failure evidence;
3. delivered package whose validation/provenance links are readable;
4. validated analysis outputs;
5. completed but unvalidated outputs;
6. runnable scripts;
7. reviewed plan;
8. validated inputs;
9. intake only.

Do not let an older failure override a newer documented fallback or successful
route. Record the obsolete route, active route, evidence paths, and next action.

## Stage-specific resume routes

- `Project_intake`: resolve the missing question, scope, design, or explicit input.
- `Input_ready`: complete the startup planning contract.
- `Plan_ready`: generate the smallest runnable workflow linked to the plan.
- `Script_ready`: run `prepare_submission.sh` with known input/output context, or
  `slurm_preflight.sh` as fallback; assess CPU, memory, partition, and concurrency.
- `Queued_or_running`: monitor only; do not edit or resubmit active work.
- `Failed`: run `slurm_failure_triage.sh`, propose the smallest fix, and ask before
  rerunning or modifying partial output.
- `Complete_unvalidated`: run layered result acceptance before interpretation.
- `Analysis_ready`: interpret only validated evidence and preserve claim caveats.
- `Delivered`: preserve the snapshot; reopen only with an explicit scope/version.

The audit script is a bounded heuristic. A directory, status row, or exit code is
never sufficient proof by itself. Do not write the active layout's
`workflow_status.tsv` without user confirmation.
