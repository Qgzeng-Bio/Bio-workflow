# Validation checklists

Use these checklists as a compact acceptance gate for qgzeng bioinformatics
workflows. Keep evidence concrete: paths, counts, job IDs, versions, and short log
snippets. Do not treat a zero exit code as enough.

## Resume checklist

- First classify the project with `references/resume-protocol.md` before planning
  new work.
- Prefer the read-only audit:
  `scripts/project_state_audit.sh --project <dir> --max-depth 3 --max-files 1000`.
- Default to the current project directory. Do not audit `/`, `/data9`,
  `/data9/home/qgzeng`, or `/data9/home/qgzeng/projects` without explicit
  confirmation and a bounded plan.
- Use `--check-queue` only when job IDs or SLURM log clues exist.
- Assign one primary state: `Input_ready`, `Script_ready`, `Queued_or_running`,
  `Failed`, `Complete_unvalidated`, or `Analysis_ready`.
- For `Script_ready`, run `scripts/slurm_preflight.sh --script <file>` before
  proposing `sbatch`.
- For `Queued_or_running`, monitor with `squeue`/`sacct`; do not edit active-run
  scripts or resubmit without confirmation.
- If `squeue`/`sacct` are unavailable but the newest log has a job ID/start line
  without a terminal marker, keep the state at `Queued_or_running`/unknown instead
  of validating older outputs.
- For `Failed`, run `scripts/slurm_failure_triage.sh --jobid <id>` or `--err <file>`
  before changing resources.
- For `Complete_unvalidated`, run result acceptance checks before any biological
  interpretation, figure generation, or downstream analysis.
- For `Analysis_ready`, cite the validation evidence path before interpreting
  biology or plotting.
- Do not write `reports/workflow_status.tsv` automatically; write it only after
  user confirmation, using the standard columns from `references/resume-protocol.md`.

## Input checklist

- Research question, organism, reference version, sample design, and expected outputs
  are stated.
- Input paths are explicit and scoped to the project or user-provided locations.
- Required files exist, are readable, and are non-empty.
- File types match the planned tools: FASTA/FASTQ/BAM/VCF/GFF/GTF/BED/TSV.
- Indexes are present when required: `.fai`, `.bai/.crai`, `.tbi/.csi`, sequence
  dictionary, or tool-specific indexes.
- Sample count, group labels, and paired-end naming match the manifest.
- Chromosome/scaffold names are compatible across FASTA, BAM, VCF, and annotation.
- Raw data under `/data9/home/qgzeng/data/` are treated as protected read-only input
  unless the user explicitly confirms otherwise.

## Lightweight environment checklist

- Current host is identified; compute-heavy work is not run on `admin2` or login nodes.
- Tool discovery is cheap: `command -v`, `--version`, known env path, or explicit
  Singularity image.
- No installation, upgrade, or environment mutation is attempted without confirmation.
- Proxy variables or `proxychains` are not used for raw-data downloads without
  explicit user confirmation.
- Broad scans such as `find /data9` or unbounded `du` are avoided.

## Resource-estimation checklist

- Tool mode is identified, not just the tool name.
- For generated workflows, generator warnings are reviewed before the generated
  stage scripts are executed.
- For KMERIA/k-mer GWAS, count output format is confirmed to be compatible with the
  matrix-construction stage before scaling beyond a pilot.
- Input scale evidence is recorded: file sizes, `.fai`, sample count, database size,
  or previous `sacct`.
- Parallelism is classified: single-threaded, moderate, strong, memory-bound, or
  I/O-bound.
- Memory estimate names the main driver and includes headroom.
- CPU request explains why more CPUs would or would not help.
- Partition follows estimated memory: usually `normal` below 200G; consider `fat` or
  `fat2` at or above 200G after confirmation.
- Array concurrency has a `%N` cap chosen from memory, disk I/O, and queue pressure.
- Expected runtime and disk growth are stated when they may be material.
- `#SBATCH --time` is absent by default, or its presence is explicitly justified.

## SLURM pre-submit checklist

- Run `scripts/slurm_preflight.sh --script <file>` before proposing `sbatch`.
- Script uses strict mode: `set -euo pipefail` or equivalent.
- Log paths are absolute and include `%j` or `%x`.
- Output directories are explicit and overwrite behavior is known.
- Temporary directories are project-local and sized for the tool.
- Inputs, outputs, tools, and versions are echoed or logged.
- Job name, partition, CPU, memory, array range, and array concurrency are reported.
- No active `rm -rf` pattern is present unless the user explicitly approved it.
- No unguarded display-only pipe to `head` is present under `set -euo pipefail`.
- Stage wrappers keep full stderr/time logs, not only filtered `error` lines.
- No write-like command targets `/data9/home/qgzeng/data/` or
  `/data9/home/qgzeng/tools/`.
- User confirmation is obtained before `sbatch`, resubmission, `scancel`, high-memory,
  long-running, or large-download actions.

## Failure-diagnosis checklist

- Record job ID, script path, submit time, and log paths.
- Query `sacct -j <jobid> --format=JobID,State,ExitCode,MaxRSS,Elapsed`.
- Read the matching `.err` and relevant `.out` before changing resources.
- Classify the failure: missing input, permission, env/tool, OOM, TIMEOUT, segfault,
  disk full, software bug, or biological/data issue.
- Treat `TIMEOUT` as a script/resource-policy problem; do not add shell `timeout` to
  force long bioinformatics work to stop.
- For OOM, compare `MaxRSS` to requested memory and adjust only with evidence.
- For format or naming errors, validate a small explicit subset before rerunning.
- For exit code 13/141, empty `.err`, or logs ending at a harmless preview command,
  inspect unguarded `| head`/pipefail patterns before changing resources.
- For KMERIA failures, distinguish count-stage input/tool failures from `count` to
  `kctm` format incompatibility; do not resubmit the same stage order when the
  wrapper already warned about incompatible formats.
- Ask before resubmitting or changing concurrency.

## Result acceptance checklist

- Run layer: expected files exist, are non-empty, and logs show normal completion.
- Data layer: sample count, record count, format, coordinate system, and chromosome
  names match expectations.
- Analysis layer: QC metrics, filters, controls, and parameter choices are documented.
- Reproducibility layer: exact commands, tool versions, scripts, configs, and manifests
  are saved.
- Biological layer: conclusions answer the research question and separate evidence
  from speculative hypotheses.
- For quinoa, interpretation considers stress tolerance, salinity, drought response,
  mineral accumulation, subgenome differentiation, structural variation, and
  pangenome variability when relevant.

## Figure acceptance checklist

- Arial or acceptable sans-serif font is used consistently.
- Background is pure white; major and minor grids are removed.
- Top and right spines are removed unless the plot type requires them.
- Tick marks point outward and axis linewidth is 0.5-0.75 pt.
- Palette is colorblind-aware and avoids pure red/pure blue as dominant colors.
- Legend does not hide data and repeated groups keep the same colors across panels.
- Axis labels include units where relevant, such as Mb, FPKM, or `-log10(P)`.
- PDF is exported first; PNG/JPEG is at least 300 dpi when raster output is needed.
- Plotting data, code, and parameters are saved with the figure.
- English figure legend draft states design, data source, and statistical method.

## Skill-maintenance checklist

- Keep `SKILL.md` as the official entry point.
- Keep `skills.md` as a byte-for-byte mirror when it is retained for user habit.
- After edits, run `cmp -s SKILL.md skills.md`.
- Run quick validation:
  `python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py /data9/home/qgzeng/projects/3-Biotools_create/bio-workflow`.
- For script changes, run `bash -n` and at least one representative positive and
  negative test.
