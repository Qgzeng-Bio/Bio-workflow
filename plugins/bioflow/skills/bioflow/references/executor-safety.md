# Executor safety and SLURM gates

Use this reference when generating, reviewing, preflighting, or submitting SLURM
scripts. It supports `scripts/gen_sbatch.sh`, `scripts/slurm_preflight.sh`,
`scripts/prepare_submission.sh`, `scripts/parallelization_audit.sh`,
`scripts/resource_usage_audit.sh`, and `scripts/submit_and_log.sh`.

## Contents

- Generate robust scripts
- Workflow engines
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

Do not use recursive `find`, `grep`, or `rg` inside run scripts to discover
unknown biological inputs. Input lists must come from an explicit manifest,
explicit paths, or a user-approved bounded search root with filename pattern and
max depth. Targeted code/config/log checks are fine; hidden data discovery is not.

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

## Conda environment activation

`sbatch` defaults to `--export=ALL`, so the job inherits the submitting shell's
PATH. If a parent process bare-exported a conda env's `bin` to the front of PATH
(common when an agent runs inside its own env), `conda activate <env>` updates
`CONDA_PREFIX` but cannot evict that foreign `bin` — `python` and tools then
resolve to the wrong env and crash on import. Guard every in-script activation:

```bash
set +u                                            # activate.d hooks read unbound vars under set -u
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate <env>
set -u
export PATH="$CONDA_PREFIX/bin:$PATH"             # pin this env's bin to the FRONT of PATH
command -v python >/dev/null 2>&1 || { echo "[FATAL] python not found after activate" >&2; exit 1; }
case "$(command -v python)" in "$CONDA_PREFIX"/bin/*) : ;; *) echo "[FATAL] python outside $CONDA_PREFIX" >&2; exit 1 ;; esac
# python -c 'import pysam' || { echo "[FATAL] key module missing" >&2; exit 1; }   # add for tools that import
```

`slurm_preflight.sh` (`check_conda_activation`) WARNs on an activation that lacks
the PATH guard or the self-check. Generate a compliant block with
`gen_sbatch.sh --conda-env <env> [--conda-check pysam]`. When the job genuinely
does not resolve via PATH (absolute-path binaries, or `conda run -n <env>`), add
a `# ALLOW_NO_PATH_GUARD` comment to the script to waive the rule.

## Workflow engines

For Nextflow, Snakemake, WDL/Cromwell, or similar workflow engines, do not judge
the workflow by the outer driver SLURM script alone. Review both layers:

- driver resources: launcher `#SBATCH` CPUs, memory, partition, logs, and whether
  it mostly schedules work rather than doing the heavy computation itself
- executor config: SLURM executor, queue/partition mapping, `queueSize` or
  submit concurrency, retry behavior, and any local executor fallback
- process resources: per-process `cpus`, `memory`, time directives if present,
  containers/environments, and whether thread variables are passed to tools
- paths and reports: `workDir`, publish/output directories, trace/report/timeline
  files, and cleanup behavior

Pre-submit reporting must separate driver resources from child process resources.
For example, `2 CPU / 8G` on the driver is acceptable only if the workflow config
sets realistic process-level CPU/memory and a capped `queueSize`; it is not the
resource request for the full pipeline. If process resources or executor settings
are missing, treat that as a review blocker or require a small pilot before scale-up.

## Preflight gate

For a single read-only GO/NO-GO gate:

```bash
scripts/prepare_submission.sh --script <slurm_script> [--manifest <manifest.tsv>] \
    [--input-list <filelist.txt>] [--output <output_dir>] [--mode <partition>] [--conc <N>]
```

It bundles input checks, SLURM preflight, lightweight resource sanity, array/manifest
checks, quota checks, and overwrite checks into one verdict and prints the exact
unsubmitted `sbatch` command.

Hard blockers include:

- preflight `FAIL`
- missing or empty inputs
- header row in bundled-template manifests
- `--output` under `~/data` or `~/tools` (or any `/data9/home/*/data|tools`)
- quota submit-cap overrun

Warnings to acknowledge include preflight `WARN`, resource-sanity WARN, non-empty
output directories, and unknown quota/header status. The gate never submits.

To run underlying checks individually:

```bash
scripts/slurm_preflight.sh --script <slurm_script>
scripts/parallelization_audit.sh --script <slurm_script> --manifest <manifest.tsv> --mode auto
scripts/resource_usage_audit.sh --script <slurm_script> --time-log <stage.time.log> --stage <stage_name>
```

Both audit scripts are read-only and print recommendations only. Do not write
`reports/resource_usage.tsv`, generate replacement scripts, or submit arrays
without user confirmation.

`slurm_preflight.sh` only performs a lightweight sanity pass. A clean preflight
does not prove that CPU and memory are optimal. For new tools, large inputs, or
uncertain scaling, add an explicit estimate from `resource-feedback.md` and
`software-resource-cards.md`, or run a pilot before full submission.

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

For arrays that would exceed the submit cap, use the safe chunked wrapper:

```bash
scripts/submit_chunked.sh -s <slurm_script> -N <tasks> -k <chunk_size> -j <cap> \
    [gate options] [--yes]
```

It is dry-run by default. With `--yes`, it writes persistent chunk scripts under
the current project `reports/submitted_scripts/chunked/` by default, or under an
explicit `--chunk-dir <dir>` when needed. The directory must not be under
`~/data/` or `~/tools/` (or any `/data9/home/*/data|tools`). Each chunk embeds the
actual `#SBATCH --array=start-end%cap` and delegates to `submit_and_log.sh`. It
must not pass arbitrary sbatch flags or call `sbatch` directly.
