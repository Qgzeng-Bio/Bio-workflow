---
name: bio-workflow
description: "规划、接管、实现、提交前检查、监控和验收 qgzeng 个人分析服务器上的生物信息学工作流。Use when working under /data9/home/qgzeng/projects on quinoa genomics, assembly, annotation, repeat, pan-genome, RNA-seq, GWAS, SNP/INDEL/SV, synteny, centromere, plotting, SLURM scripts, Singularity/Conda environments, raw-data downloads, CPU/memory estimation, job arrays, failure diagnosis, project resume/takeover, result validation, or reproducible reports. This skill emphasizes server-specific safety: no broad filesystem scans, no compute on admin2/login nodes, no wasteful CPU or memory requests, no external proxy for raw-data downloads, and no default SLURM --time except debug-style jobs when needed."
---

# Bio-workflow

## Mission

Plan and execute reproducible bioinformatics work on qgzeng's server without wasting shared resources. Start from the research question, explicit input paths, expected outputs, resource model, and validation criteria. Do not start by writing a command.

## Non-negotiable startup

Before substantive work:

1. Read `/data9/home/qgzeng/.codex/memories/user_output_format_preferences.md`.
2. Read `/data9/home/qgzeng/.codex/memories/slurm_preferences.md`.
3. Read the nearest `AGENTS.md` in the current directory or parent directories.
4. If any required file is missing, state the missing item briefly and continue with available context.
5. Reply in Chinese by default, with conclusion first and compact status markers.

## Server safety boundaries

Use only explicit paths from the user or the current project. Keep probes narrow and cheap.

### Allowed lightweight probes

Use these freely when they answer the task:

- `pwd`
- `hostname`
- `df -h .`
- `sinfo`
- `squeue -u "$USER"` or plain `squeue` when user-wide context matters
- `sacct -j <jobid> --format=JobID,State,ExitCode,MaxRSS,Elapsed`
- `scontrol show job <jobid>`
- `command -v <tool>`
- `<tool> --version`, `<tool> -h`, or `<tool> --help`
- `rg`, `rg --files`, `find . -maxdepth N` scoped to the project
- `ls -lh`, `wc -l`, `head`, `tail`, `file` on explicit files
- `du -sh <explicit_project_or_output_path>` only for user-specified paths

### Avoid resource-heavy discovery

Do not run broad scans such as:

- `find /data9`, `find /data9/home/qgzeng`, or unbounded `find` on large project roots
- `du -sh /data9/*`, `du -sh /data9/home/qgzeng/*`, or recursive size checks over broad trees
- `ls -R` on large directories
- full-file `grep`, `zcat`, `awk`, `seqkit stats`, `samtools view`, or decompression over large FASTQ/BAM/VCF files unless the task requires it and the cost is explained
- any compute-heavy tool on a login/admin node

When information may require a large scan, ask the user to provide the exact target path or propose a bounded command first.

## admin2 and login-node rule

Treat `admin2` as a login/admin node. On `admin2`, run only planning, script edits, syntax checks, light metadata checks, and SLURM control commands. Do not run aligners, assemblers, sorters, repeat annotation, pangenome tools, compression/decompression over large files, or full-data QC directly on `admin2`.

If a command may use more than one CPU, run for more than about 3 minutes, stream large genomic files, or produce large output, route it through SLURM or ask the user for confirmation before an interactive compute allocation.

## Permission and confirmation rules

Always apply the nearest `AGENTS.md` first. If an `AGENTS.md` requires write
disclosure or confirmation, follow it even for low-risk project files. If no
applicable `AGENTS.md` adds stricter limits, use the lower-risk defaults below.

Low-risk actions inside the working project:

- read files and inspect small explicit inputs
- create or edit scripts, configs, manifests, reports, and small check files
- run syntax checks such as `bash -n`, R parse checks, or Python import/compile checks
- inspect queue state and existing logs

Require user confirmation before:

- `sbatch`, `scancel`, resubmission, or changing job concurrency
- starting high CPU, high memory, long-running, or large-I/O work
- installing, upgrading, removing, or changing Conda, modules, tools, or containers
- writing into `/data9/home/qgzeng/data/` or `/data9/home/qgzeng/tools/`
- overwriting, moving, deleting, or replacing existing results
- changing formal analysis parameters after a plan has been agreed
- downloading large raw data

Before any write or job action, state:

1. purpose and logic
2. exact command or edit method
3. affected paths and approximate size
4. expected outputs
5. risks, including overwrite, disk, runtime, and queue impact

## Project layout

Prefer this structure unless the project already has a stronger convention:

```text
project/
├── config/
├── data/       # symlinks or manifests only; raw data remains protected
├── scripts/
├── logs/
├── results/
├── reports/
└── tmp/
```

Use tab-separated tables for intermediate and final tabular outputs. Use English column names with initial capitals and underscores, for example `Gene_ID`, `Sample_Name`, and `Read_Count`.

## Resume an existing project

When the user asks to continue, check, recover, validate, explain, or take over an
existing project, do not default to planning from scratch. First decide the current
project state, then take the smallest safe next step.

Use this read-only entry before task routing when project artifacts already exist
or the request is ambiguous. The default project is the current directory; do not
walk upward to parent roots or scan account/project roots unless the user confirms
a deliberately broader audit:

```bash
scripts/project_state_audit.sh --project <project_dir> --max-depth 3
```

Add `--check-queue` only when the audit or user-provided evidence contains job IDs
or SLURM log clues. This may call `squeue`/`sacct`, but it must not submit, cancel,
resubmit, repair, or write status files.

Read `references/resume-protocol.md` when resuming a project. Classify the project
into one primary state, while noting secondary candidates when evidence is mixed:

- `Input_ready`: inputs or manifests exist, but no runnable workflow is ready.
- `Script_ready`: scripts exist and need preflight before submission.
- `Queued_or_running`: SLURM evidence shows work is pending, running, or incomplete.
- `Failed`: logs or accounting show a failed job or failed workflow step.
- `Complete_unvalidated`: outputs and completion logs exist, but result acceptance is missing.
- `Analysis_ready`: results have been validated and are ready for interpretation, plotting, or reporting.

Use this fixed response shape for resume work:

```text
📌 当前阶段
🔎 证据
⚠️ 阻塞
🛠️ 下一步最小动作
```

Minimum next actions:

- `Input_ready`: return to workflow steps 1-2 and define missing manifests, methods, and success criteria.
- `Script_ready`: run `scripts/slurm_preflight.sh --script <file>` and ask before `sbatch`.
- `Queued_or_running`: monitor with `squeue`/`sacct`; do not edit scripts or resubmit while state is active.
- `Failed`: run `scripts/slurm_failure_triage.sh --jobid <id>` or `--err <file>`, then propose the smallest fix.
- `Complete_unvalidated`: run result acceptance from `references/validation-checklists.md` before biological interpretation.
- `Analysis_ready`: proceed to plotting/reporting/biological interpretation with concrete validated evidence.

Do not write `reports/workflow_status.tsv` automatically. The audit script only
prints a suggested TSV row; write the status file only after user confirmation.

## Task routing

Pick the narrowest route before reading detailed references or writing scripts:

- **Genome survey & primary assembly (PacBio HiFi ± ONT):** start from `references/playbook-genome-survey-and-assembly.md` — it covers read QC → k-mer survey (genome size / heterozygosity / ploidy) → hifiasm primary assembly → QUAST/BUSCO/telomere QC, with quinoa-specific decisions and acceptance numbers. Use `references/software-resource-cards.md` (`hifiasm`, `BUSCO`, `QUAST`) for per-tool detail and `validation-checklists.md` for the acceptance gates.
- **Chromosome scaffolding:** for Pore-C / Hi-C / polyploid, start from `references/playbook-chromosome-scaffolding-cphasing.md` (C-Phasing; pick `-n` by allo-/auto-polyploidy; anchoring + contact-map QC + Juicebox curation). For short-read Hi-C via 3D-DNA, read the `Juicer and 3D-DNA` card. Confirm enzyme/layout and require contact-map review criteria.
- **Genome finishing (reference scaffolding / gap filling / polishing):** read `references/playbook-genome-finishing.md` — RagTag reference-based scaffolding (+ dot-plot & LAI QC) for accessions without 3C; TGS-GapCloser+ONT manual per-gap gap filling; NextPolish2+HiFi polishing with merqury QV. Polishing is optional (whole-genome when ONT was used, or local around filled gaps).
- **Annotation:** read `BRAKER and MAKER`, `EDTA`, `RepeatModeler`, `BUSCO`, and `validation-checklists.md`; confirm repeat masking and evidence naming.
- **RNA-seq:** read `fastp, FastQC, and MultiQC`, `STAR`, and `featureCounts`; confirm strandedness, paired-end naming, and index reuse.
- **Structural variation & synteny (assembly-vs-assembly):** start from `references/playbook-variant-synteny-syri.md` — SyRI SV calling (minimap2 `-ax asm5 --eqx` → `syri -F S -k`) in two topologies (chained multi-genome plotsr panorama vs all-to-reference → SURVIVOR population SV set → hotspots), with the chromosome-orientation fix and the mandatory SVLEN+SVTYPE VCF patch, plus quinoa acceptance numbers. For per-tool detail use the `SyRI`, `MUMmer and plotsr`, and `minimap2` cards. (Graph-based complex SV via Swave and read-based SV via sniffles2/svim-asm are out of this playbook's scope.)
- **Read-based / population SNP·INDEL·SV:** read `bcftools and GATK`; confirm reference compatibility and chromosome names before calling.
- **Pangenome/orthology:** read `OrthoFinder`, `PanGenie`, and search-tool cards; estimate database/output growth and array concurrency.
- **K-mer GWAS / KMERIA:** read the `KMERIA` card; run a format-compatibility pilot before scaling, and treat wrapper warnings about `count`/`kctm` output formats as blockers.
- **Download:** use section 10 first; avoid `proxychains`, `http_proxy`, `https_proxy`, and `all_proxy` for raw-data downloads unless confirmed.
- **Plotting/reporting:** use section 12 and the figure checks in `references/validation-checklists.md`.

## Workflow

### 1. Define the task

Record:

- research question and biological purpose
- organism, reference version, samples, groups, and replicate design
- exact input paths and file types
- expected outputs and final deliverables
- method preferences or constraints
- success criteria and failure conditions

If key biological or experimental information is missing, list missing items instead of inventing assumptions.

### 2. Build a narrow input inventory

Inspect only explicit inputs. Prefer metadata and indexes over reading full files:

- FASTQ: use file sizes and file names first; avoid full decompression unless needed
- FASTA: use `.fai` if present; creating a new index writes a file, so state impact first
- BAM/CRAM: use `.bai/.crai` and `samtools idxstats` only when indexes exist and the tool is available
- VCF/BCF: use header, tabix index, and small targeted regions when possible
- GFF/GTF/BED/TSV: use `head`, `wc -l`, and format-specific sanity checks on explicit files

Stop and warn if files are missing, empty, inconsistent, damaged, or biologically ambiguous.

### 3. Discover tools without installing

Check tools in this order:

1. current `PATH`
2. active Conda environment
3. known Conda environments only when explicitly named or cheap to inspect
4. cluster module system if available
5. project or user tool paths when explicitly provided
6. Singularity images when explicitly provided or already used by the project
7. installation only after user confirmation

Record tool versions and exact commands used for reproducibility.

### 4. Estimate resources from software behavior

Do not request CPU or memory by habit. Estimate from:

- input size and record count
- algorithm memory model
- thread scalability
- temporary file expansion
- per-thread memory settings
- array concurrency
- current queue state
- previous job history when available

Use this reasoning pattern:

```text
Resource request = base memory for input/index/database
                 + per-thread memory * useful threads
                 + temporary/output headroom
```

Classify software before choosing CPU:

- mostly single-threaded: request 1-4 CPUs
- moderately parallel: request 4-16 CPUs
- strongly parallel and proven to scale: request 16-32 CPUs
- I/O-bound or memory-bound: keep CPUs conservative and protect disk bandwidth
- tools with per-thread memory such as sorting: calculate `threads * memory_per_thread`

Examples to remember:

- `samtools sort`: total memory is approximately `-m * threads`; do not request many threads with large `-m` blindly.
- aligners such as `minimap2`, `bwa`, `hisat2`, and `STAR`: CPU can help, but memory depends on reference/index size and mode.
- `blast`, `diamond`, and HMM searches: database size and output volume often dominate memory and disk.
- assemblers, repeat annotation, pangenome construction, and orthology clustering can be memory-heavy; require explicit sizing or a pilot.
- R/Python plotting and summarization usually need 1-4 CPUs unless using real parallel code.
- gzip-like compression should use `pigz` only when parallel I/O is helpful; otherwise avoid tying up many CPUs.

When uncertain, propose a small pilot or benchmark before the full run.

### 4.1 Resource feedback loop

Unknown or poorly characterized tools must go through a feedback loop before the
full run:

1. Run a small pilot or benchmark with `/usr/bin/time -v` and preserved stderr.
2. After completion, parse both SLURM accounting and time logs:

   ```bash
   scripts/resource_usage_audit.sh --script <slurm_script> --jobid <jobid> --time-log <stage.time.log> --stage <stage_name>
   ```

3. Use observed `Percent of CPU`, `MaxRSS`, and walltime to choose the next
   `--cpus-per-task`, `--mem`, and array `%N` cap. Do not keep high CPU requests
   just because the original template used them.

Decision rules:

- If `Estimated_Used_CPUs ~= PercentCPU / 100` is far below requested CPUs, reduce
  the next CPU request toward the measured effective CPU count.
- If `/usr/bin/time -v` reports non-zero `Exit status`, do not use that log to
  down-tune resources. Triage the failure first.
- If requested CPUs are `> 4` and CPU efficiency is `< 50%`, treat the job as
  `CPU_OVERREQUEST` unless there is a known bursty or phased parallel step.
- If 4/8/16-thread benchmark walltime improves by `< 15%` at higher thread counts,
  choose the smallest thread count within 15% of the fastest run.
- If `MaxRSS / requested memory < 35%`, warn as `MEM_OVERREQUEST`, but do not
  automatically lower memory without another pilot or input-size scaling evidence.
- For independent samples, chromosomes, or files, prefer a SLURM array with a
  concurrency cap over one oversized serial job. Use node-local/thread parallelism
  only when the tool demonstrably scales better inside one task.
- Bundled array templates expect manifest files without a header. If a manifest has
  a `Sample_ID`, `Input_1`, `Chunk_ID`, or similar header row, remove it or adjust
  task-line indexing before submission.

Use this read-only audit before rewriting real project scripts:

```bash
scripts/parallelization_audit.sh --script <slurm_script> --manifest <manifest.tsv> --mode auto
```

For tool-specific estimates, read `references/software-resource-cards.md` when the
task involves minimap2, samtools sort, SyRI, OrthoFinder, EDTA, RepeatModeler,
STAR, featureCounts, PanGenie, BLAST, DIAMOND, HMMER-family searches, hifiasm,
Juicer/3D-DNA, BRAKER/MAKER, bcftools/GATK, fastp/FastQC/MultiQC, MUMmer/plotsr,
BUSCO, or QUAST. Use the cards as starting points, then adjust with explicit input
size, queue state, and previous `sacct` evidence.

### 5. Choose SLURM resources for this server

Use current queue and memory estimate, not a fixed template.

- `< 200G` memory: prefer `normal`, usually up to about 16 CPUs.
- `>= 200G` memory: consider `fat` or `fat2`, often 16-32 CPUs, after checking queue state.
- `debug`: use only tiny tests, dry runs, and fast validation. A short `--time` is acceptable here when helpful or required.
- `high`: use only when user/project policy or queue state justifies it.
- unknown memory: ask or run a bounded pilot; do not guess with maximum resources.

Do not add `#SBATCH --time` by default for `normal`, `fat`, `fat2`, or `high`. If an existing script has a short walltime, warn that it may cause `TIMEOUT`. Add or keep `--time` only when the user explicitly asks, cluster policy requires it, or the job is a debug-style test.

Use job arrays for independent samples, but always set a concurrency cap such as `%2`, `%4`, or `%5`. Choose the cap from combined memory, disk I/O, database contention, and current queue pressure.

### 6. Write robust scripts

To generate a skeleton that already satisfies the rules in this section — absolute
`%j_%x` logs, strict mode, CPU forwarding, no default `--time`, an array `%N` cap, and
protected-path guards — use `gen_sbatch.sh`. It runs `slurm_preflight.sh` on its own
output and refuses to emit anything that would FAIL (and `bash -n`-checks it), so a
generated script is preflight-clean by construction:

```bash
scripts/gen_sbatch.sh --job-name NAME --cpus N --mem SIZE --log-dir ABS_DIR \
    [--partition P] [--array RANGE] [--manifest FILE] [--cmd 'COMMAND'] [--out FILE]
```

It prints to stdout by default; fill in `--cmd` (use `"$THREADS"` for the thread count and
`"$TASK_LINE"` for the per-task manifest row). The generator is a convenience for the SLURM
envelope, not a substitute for reviewing the tool command itself.

Use strict shell mode:

```bash
set -euo pipefail
```

With `pipefail`, display-only preview pipelines can become real failures. Avoid
unguarded patterns such as `ls ... | head`, `find ... | head`, or `tool ... | head`
inside SLURM scripts. If a preview is only diagnostic, guard it with `|| true`, use
a bounded loop/array, or write the preview so every command in the pipeline can
complete normally. This is especially important in helper scripts called from an
sbatch script, because their exit status can fail the whole job.

For SLURM scripts:

- set absolute log paths with `%j_%x.out` and `%j_%x.err`
- echo host, date, job ID, partition, CPUs, memory, and working directory
- record tool versions
- quote paths safely
- fail early on missing inputs
- write temporary outputs under `tmp/`
- avoid overwriting existing final outputs unless explicitly confirmed
- make rerun behavior clear
- preserve full stderr/time logs for each stage; do not reduce failure evidence to
  only `grep error` snippets
- stop after workflow generation if the generator prints an incompatibility warning
  or tells the user to submit/inspect steps manually

Default SLURM skeleton:

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

### 7. Preflight before submitting

For a single read-only "green-light" gate, run `prepare_submission.sh`. It bundles the
input, preflight, array/manifest, quota, and overwrite checks into one GO/NO-GO verdict
and prints the exact, UNSUBMITTED `sbatch` command:

```bash
scripts/prepare_submission.sh --script <slurm_script> [--manifest <manifest.tsv>] \
    [--input-list <filelist.txt>] [--output <output_dir>] [--mode <partition>] [--conc <N>]
```

It hard-blocks (NO-GO, exit 1) on: preflight FAIL, missing/empty inputs, a manifest
header row (bundled templates are 1-indexed), `--output` under `/data9/home/qgzeng/data`
or `/data9/home/qgzeng/tools`, or a quota submit-cap overrun. Everything else (preflight
WARN, non-empty output directory, unknown quota/header) is a WARN to acknowledge. It
never submits — pressing `sbatch` stays a user-confirmed action.

To run the underlying checks individually, or if `prepare_submission.sh` is unavailable:

```bash
scripts/slurm_preflight.sh --script <slurm_script>
```

Use `--mode debug|normal|fat|fat2|high` when the intended partition differs from the
script or cannot be inferred. Treat any `FAIL` as a blocker. Treat `WARN` as an item
to explain to the user before submission. If preflight warns about serial independent
tasks or high CPUs not being passed to the tool, run:

```bash
scripts/parallelization_audit.sh --script <slurm_script> --manifest <manifest.tsv> --mode auto
```

For pilot or benchmark logs, run:

```bash
scripts/resource_usage_audit.sh --script <slurm_script> --time-log <stage.time.log> --stage <stage_name>
```

Both audit scripts are read-only and print TSV recommendations only; do not write
`reports/resource_usage.tsv`, generate project-specific replacement scripts, or
submit arrays without user confirmation. Also consult
`references/validation-checklists.md` for the full pre-submit checklist.

SLURM array templates are bundled as starting points:

- `assets/slurm-templates/per_sample_array.sbatch`: one sample/accession per task.
- `assets/slurm-templates/per_chunk_array.sbatch`: one chunk per task when files are
  too light or too numerous.

Templates must be adapted with absolute project paths, manifest columns, per-task
output directories, no-header manifest files, and explicit tool CPU flags before
submission.

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

To execute the confirmed submission and record it, use `submit_and_log.sh`. It re-runs
`prepare_submission.sh` as the final gate and is DRY-RUN by default; only with `--yes` does
it submit (via `sbatch`) and append a row to `reports/run_record.tsv`. A NO-GO gate, a
missing `--yes`, an unwritable record path, or a script changed since the gate each block
the submission:

```bash
scripts/submit_and_log.sh --script <slurm_script> [gate options] [--record FILE] [--yes]
```

The array, if any, must live in the script itself (which the gate inspects); there is no
`--array` override on the submitter, by design.

### 8. Monitor and diagnose

After submission, record job ID, script path, config path, resource request, and submit time.

For failures:

1. check `sacct` state, exit code, MaxRSS, and elapsed time
2. read the matching `.err` and relevant `.out`
3. classify the failure: missing input, permission, module/env, OOM, TIMEOUT,
   segfault, disk full, shell/pipefail error, software format incompatibility, or
   biological/data issue
4. propose the smallest justified fix
5. ask before resubmitting

Treat `TIMEOUT` as a script/resource-policy problem first. Do not wrap long bioinformatics commands with `timeout` as a completion mechanism.

### 9. Validate results in layers

Read `references/validation-checklists.md` for the relevant acceptance gate. Do not
treat exit code 0 as success. Validate:

1. run layer: exit code, logs, expected files, non-empty outputs
2. data layer: sample count, record count, format, coordinate system, chromosome names
3. analysis layer: QC metrics, expected controls, known biological patterns, parameter sensitivity
4. biology layer: whether conclusions answer the research question and what remains speculative

For quinoa work, connect interpretation to plausible biology such as stress tolerance, salinity, drought response, mineral accumulation, subgenome differentiation, structural variation, and pangenome variability. Mark hypotheses as speculative unless experimentally validated.

### 10. Download raw data safely

Do not route original data downloads through external proxies. Avoid `proxychains` and avoid relying on `http_proxy`, `https_proxy`, or `all_proxy` for SRA/ENA/NCBI-style raw data downloads.

Before large downloads:

- confirm destination and expected size
- avoid writing into protected raw-data directories unless the user explicitly confirms
- prefer project staging directories with manifests and checksums
- use direct, cluster-appropriate tools
- if proxy variables appear necessary or already set, warn the user and ask before proceeding

After download, validate checksums or file integrity when available.

### 11. Use qp mode when appropriate

For the user's multi-task queue pattern:

- working directory: `/data9/home/qgzeng/projects/2-C_quinoa/12-jobs/`
- entry script: `manager_parallel.slurm`
- manager: `run_task_manager_parallel.sh`
- task list: `tasks.txt`
- history: `run_record.txt`

Each task command must include environment activation and explicit output paths. Empty `tasks.txt` does not prove no work is running; inspect `task_log.txt` and SLURM state. Do not change `MAX_PARALLEL` for large-memory jobs without confirmation.

### 12. Plot and report

For publication figures, follow the user's Nature-style plotting rules from `AGENTS.md`: Arial fonts, white background, no grids, clean axes, colorblind-aware palettes, PDF first, PNG/JPEG at 300 dpi, and figure legends in English.

Always save plotting data, code, and parameters. Report what the figure proves and what it does not prove.

## Skill maintenance

`SKILL.md` is the single official entry point — the skill loader reads only this file.

Run `quick_validate.py` after structural changes and `bash -n` for any bundled shell
script changes. For `scripts/slurm_preflight.sh`, test at least one passing script
and one failing script before trusting the rule changes.

## Default response shape

Use a compact Chinese structure:

```text
📌 结论
🔎 已确认
⚠️ 风险
🧮 资源判断
🛠️ 将执行/已执行
✅ 验收
▶️ 下一步
```

Keep tables short. Prefer clear bullets with concrete paths, commands, job IDs, and validation criteria.
