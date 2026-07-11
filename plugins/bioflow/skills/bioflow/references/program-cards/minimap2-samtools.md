# minimap2 and samtools program card

Use this card when the user asks to run minimap2 mapping/alignment directly, with
or without downstream samtools sorting/indexing.

## Supported modes

- `reads_to_ref_hifi`: HiFi reads to reference, usually minimap2 preset `map-hifi`.
- `reads_to_ref_ont`: ONT reads to reference, usually minimap2 preset `map-ont`.
- `asm_to_asm_syri`: assembly-to-assembly SAM for SyRI, usually `-ax asm5 --eqx`
  for close assemblies.
- `asm_to_asm_paf`: assembly-to-assembly PAF for dot plots or non-SyRI inspection.
- `reads_to_ref_bam`: read mapping followed by `samtools sort` and `samtools index`.

## Environment preflight

- Check `command -v minimap2` and `command -v samtools` when BAM output is needed.
- Record `minimap2 --version` and `samtools --version`.
- Record `minimap2 --help`/`samtools sort --help` when preset or sort memory syntax
  needs confirmation.
- Check only explicit envs, modules, containers, or binary paths.

## Required inputs by mode

- `reads_to_ref_hifi`: reference FASTA, HiFi FASTQ/FASTA or manifest, output target.
- `reads_to_ref_ont`: reference FASTA, ONT FASTQ/FASTA or manifest, output target.
- `reads_to_ref_bam`: reference FASTA, reads, BAM prefix, temp directory.
- `asm_to_asm_syri`: reference FASTA, query FASTA, target SAM path, SyRI naming and
  orientation plan.
- `asm_to_asm_paf`: reference FASTA, query FASTA, target PAF path.

## Input preparation

- Confirm reference and query/read paths are explicit, readable, and non-empty.
- Use an existing `.fai` when available to inspect sequence names and sizes. State
  before creating a new `.fai` because it writes a file.
- For SyRI mode, chromosome IDs must be compatible between FASTA files and the
  downstream naming/orientation plan.
- For BAM output, define a project-local temp directory for `samtools sort -T`.
- Decide output type before scripting: SAM, sorted BAM plus BAI, or PAF.

## Parameter negotiation

- Must ask: mode, reference, query/reads, preset, output type, output path, threads.
- Must ask for BAM: sort memory per thread (`samtools sort -m`) or approve a
  conservative default.
- Must ask for assembly comparison: whether `asm5`, `asm10`, or `asm20` fits the
  expected divergence; use `asm5` only when close assemblies are expected.
- Can infer: `map-hifi` for confirmed HiFi reads and `map-ont` for confirmed ONT
  reads, after stating the inference.
- Must record: minimap2 version, samtools version, preset, `--eqx` use, sort memory,
  threads, and output format.

## Resource model

Use `../software-resource-cards.md` under `minimap2` and `samtools sort`. Treat
mapping and sorting separately. `samtools sort -m` is per thread, so total memory is
approximately `threads * -m` plus headroom.

## Script generation notes

- Use `THREADS="${SLURM_CPUS_PER_TASK:-N}"` and pass it to minimap2 with `-t`.
- For sorted BAM, pipe carefully under `set -euo pipefail` and set
  `samtools sort -@ "$SORT_THREADS" -m "$SORT_MEM" -T "$TMP_PREFIX"`.
- Avoid producing huge unsorted SAM files unless the downstream tool requires SAM.
- For SyRI, preserve SAM output and record the exact minimap2 command.
- Use output guards so existing BAM/BAI/SAM/PAF files are not overwritten without
  confirmation.

## Acceptance checks

- SAM/PAF/BAM exists and is non-empty.
- Sorted BAM has a matching `.bai`.
- `samtools flagstat` is generated for read-mapping BAMs.
- Logs include minimap2 and samtools versions plus the preset.
- For PAF/SAM, line count is non-zero and reference/query IDs match expected FASTA
  IDs.
- For SyRI mode, confirm `--eqx` was used and chromosome naming/orientation is
  compatible before running SyRI.

## Common failures and recovery

- OOM during sorting: reduce threads or `-m`, move to a higher-memory partition only
  with evidence.
- Broken pipe under `pipefail`: inspect both minimap2 and samtools logs before
  changing resources.
- Massive SAM output: switch to sorted BAM or PAF if the downstream tool allows it.
- Wrong preset: re-run alignment after confirming read type or assembly divergence.
- Chromosome name mismatch: fix names/manifests before downstream SyRI or plotting.

## Evidence grade

- Preset and CLI syntax: `local_help` when verified, otherwise `official_doc`.
- SyRI alignment recommendation `-ax asm5 --eqx`: `project_history` for local SyRI
  workflows plus `official_doc`/`github_readme` when cited.
- Resource and sort-memory model: `project_history` plus `inferred` from
  `../software-resource-cards.md`.
- Acceptance checks: `local_run` after output validation, otherwise `inferred`.
