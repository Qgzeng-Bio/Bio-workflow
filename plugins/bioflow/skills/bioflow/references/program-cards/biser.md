# BISER program card

Use this card when the user asks to run BISER directly for segmental duplication
discovery. For the full quinoa segmental-duplication workflow, read
`../playbook-segmental-duplications.md` first.

## Supported modes

- `single_reference_sd_catalog`: one soft-masked reference FASTA to one SD catalog.
- `batch_sample_sd_catalog`: multiple soft-masked FASTA files processed with a
  manifest and low-concurrency array.

## Environment preflight

- Check `command -v biser` or the explicit BISER binary/script path.
- Record `biser --help`, `biser -h`, or the wrapper help available in the local
  installation.
- Check required runtime dependencies only through explicit env/container paths.
- Confirm the working directory is writable because BISER-style workflows may write
  intermediate files relative to the current directory.
- Do not install Java, BISER, or dependencies without confirmation.

## Required inputs by mode

- `single_reference_sd_catalog`: soft-masked reference FASTA, output directory,
  output prefix, filter thresholds.
- `batch_sample_sd_catalog`: manifest with sample ID and soft-masked FASTA path,
  output root, array/concurrency plan, filter thresholds.
- Optional: chromosome allowlist, subgenome chromosome map, TE annotation for later
  composition analysis.

## Input preparation

- Confirm the FASTA is soft-masked. If repeat masking has not been done, route to
  RepeatModeler/RepeatMasker planning before BISER.
- Confirm the FASTA exists, is readable, and is non-empty.
- Use an existing `.fai` to identify chromosome IDs; state before creating one.
- Prepare a project-local writable working/output directory.
- Define the raw output path and filtered output schema before running.

## Parameter negotiation

- Must ask: reference FASTA, output root, mode, filter length cutoff, score cutoff,
  chromosome scope, and whether subgenome classification is needed.
- Default filter from local quinoa workflow: length `end - start >= 1000` and
  `score <= 10`, but record this as project-specific unless the user confirms it
  for a new organism.
- Can infer: intra/inter-chromosome split only after chromosome IDs are known.
- Must record: BISER version/help evidence, FASTA masking source, filters, column
  schema, and chromosome allowlist.

## Resource model

BISER is memory-heavy in the local segmental-duplication workflow. Use
`../software-resource-cards.md` for general sizing if a BISER section is added; for
now treat resource estimates as `project_history` plus `inferred` and prefer a
pilot or low-concurrency SLURM array. Do not run whole-genome BISER on `admin2`.

## Script generation notes

- Run from a controlled writable work directory.
- Log the environment, BISER help/version evidence, input FASTA, and filter command.
- Keep raw BISER output separate from filtered tables.
- Use explicit column names in downstream TSVs.
- Guard existing raw and filtered outputs against accidental overwrite.
- For batches, use one sample per array task and cap concurrency conservatively.

## Acceptance checks

- Raw `SDs_output` or the configured raw output exists and is non-empty.
- Filtered SD table exists and has the expected columns.
- Filtered count is reported.
- Intra-chromosome count plus inter-chromosome count equals total filtered count.
- Non-redundant SD bp is computed only after interval merge rules are recorded.
- Length uses `end - start` consistently with the local workflow.
- Coordinate and column-number assumptions are checked against the actual output.

## Common failures and recovery

- FASTA is not soft-masked: run or request RepeatMasker soft-mask preparation first.
- BISER writes to an unexpected directory: rerun from an explicit writable workdir.
- Empty raw output: inspect masking, chromosome scope, and BISER logs before
  relaxing filters.
- Column schema mismatch: stop and inspect the raw header/examples before applying
  filters.
- OOM or long runtime: use `sacct`/logs to resize or reduce array concurrency.

## Evidence grade

- BISER local mode, writable-workdir behavior, `score <= 10`, and `end - start`
  length convention: `project_history` for the local SD workflow.
- CLI syntax: `local_help` when captured from the local installation.
- Soft-masked FASTA requirement: `project_history` plus `inferred`.
- Resource model: `project_history` plus `inferred` until a fresh `local_run` is
  recorded.
- Acceptance checks: `local_run` after validated outputs exist.
