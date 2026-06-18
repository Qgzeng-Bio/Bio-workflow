# Executor safety and SLURM gates

Use this reference when generating, reviewing, preflighting, or submitting SLURM
scripts. It supports `scripts/gen_sbatch.sh`, `scripts/slurm_preflight.sh`,
`scripts/prepare_submission.sh`, `scripts/parallelization_audit.sh`,
`scripts/resource_usage_audit.sh`, and `scripts/submit_and_log.sh`.

## Contents

- Generate robust scripts
- Preflight gate
- Arrays and submission

## Generate robust scripts

To generate a SLURM skeleton that already satisfies core rules, use:

```bash
scripts/gen_sbatch.sh --job-name NAME --cpus N --mem SIZE --log-dir ABS_DIR \
    [--partition P] [--array RANGE] [--manifest FILE] [--cmd 'COMMAND'] [--out FILE]
```

It prints to stdout by default, runs `bash -n`, runs `slurm_preflight.sh`, and
refuses to emit output that would FAIL. Use `"$THREADS"` for tool thread count
and `"$TASK_LINE"` for the per-task manifest row. The generator checks the SLURM
envelope; it does not prove that the biological command is correct.

Use strict shell mode:

```bash
set -euo pipefail
```

With `pipefail`, diagnostic preview pipelines can fail whole jobs. Avoid
unguarded `ls ... | head`, `find ... | head`, or `tool ... | head`. If preview
output is only diagnostic, guard it with `|| true` or write a bounded loop.

For SLURM scripts:

- set absolute log paths with `%j_%x.out` and `%j_%x.err`
- echo host, date, job ID, partition, CPUs, memory, and working directory
- record tool versions
- quote paths safely
- fail early on missing inputs
- write temporary outputs under `tmp/`
- avoid overwriting existing final outputs unless explicitly confirmed
- preserve full stderr/time logs for each stage
- stop after workflow generation if the generator warns about incompatibility or
  says to inspect/submit manually

Default skeleton:

```bash
#!/bin/bash
#SBATCH --partition=normal
#SBATCH --job-name=job_name
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --output=/full/path/to/logs/%j_%x.out
#SBATCH --error=/full/path/to/logs/%j_%x.err

set -euo pipefail

echo "[INFO] Job started | Host: $(hostname) | Time: $(date)"
echo "[INFO] Job ID: ${SLURM_JOB_ID:-NA} | Partition: ${SLURM_JOB_PARTITION:-NA}"
echo "[INFO] CPUs: ${SLURM_CPUS_PER_TASK:-NA} | Workdir: $(pwd)"
```

Do not include `#SBATCH --time` in this skeleton.

## Preflight gate

For a single read-only GO/NO-GO gate:

```bash
scripts/prepare_submission.sh --script <slurm_script> [--manifest <manifest.tsv>] \
    [--input-list <filelist.txt>] [--output <output_dir>] [--mode <partition>] [--conc <N>]
```

It bundles input checks, SLURM preflight, array/manifest checks, quota checks, and
overwrite checks into one verdict and prints the exact unsubmitted `sbatch`
command.

Hard blockers include:

- preflight `FAIL`
- missing or empty inputs
- header row in bundled-template manifests
- `--output` under `/data9/home/qgzeng/data` or `/data9/home/qgzeng/tools`
- quota submit-cap overrun

Warnings to acknowledge include preflight `WARN`, non-empty output directories,
and unknown quota/header status. The gate never submits.

To run underlying checks individually:

```bash
scripts/slurm_preflight.sh --script <slurm_script>
scripts/parallelization_audit.sh --script <slurm_script> --manifest <manifest.tsv> --mode auto
scripts/resource_usage_audit.sh --script <slurm_script> --time-log <stage.time.log> --stage <stage_name>
```

Both audit scripts are read-only and print recommendations only. Do not write
`reports/resource_usage.tsv`, generate replacement scripts, or submit arrays
without user confirmation.

## Arrays and submission

Bundled array templates:

- `assets/slurm-templates/per_sample_array.sbatch`: one sample/accession per task.
- `assets/slurm-templates/per_chunk_array.sbatch`: one chunk per task when files
  are too light or too numerous.

Templates must be adapted with absolute project paths, manifest columns,
per-task output directories, headerless manifests, and explicit tool CPU flags.

Before `sbatch`, show the user:

- exact command to submit
- script path and log paths
- input manifest and sample count
- output directory and overwrite status
- CPU, memory, partition, array range, and array concurrency
- whether `--time` is absent or why it is present
- expected runtime and disk growth
- validation checks after completion

Submit only after confirmation.

To submit a confirmed job and record it:

```bash
scripts/submit_and_log.sh --script <slurm_script> [gate options] [--record FILE] [--yes]
```

It re-runs `prepare_submission.sh` as the final gate and is dry-run by default.
Only `--yes` calls `sbatch` and appends `reports/run_record.tsv`. A NO-GO gate,
missing `--yes`, unwritable record path, or script change since the gate blocks
submission. Arrays must live in the script itself; there is no `--array`
override on the submitter.
