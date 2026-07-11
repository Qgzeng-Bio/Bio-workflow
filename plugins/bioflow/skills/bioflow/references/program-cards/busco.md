# BUSCO program card

Use this card when the user asks to run BUSCO directly. For BUSCO inside a genome
assembly or genome-evaluation workflow, read the relevant playbook first and use
this card for tool-level details.

## Supported modes

- `genome`: assess a genome assembly FASTA with `--mode genome`.
- `protein`: assess predicted protein FASTA with `--mode proteins`.
- `transcriptome`: assess transcript/transcriptome FASTA with `--mode transcriptome`.

## Environment preflight

- Check `command -v busco`.
- Record `busco --version`.
- Record `busco --help` if CLI syntax or mode names are uncertain.
- If an explicit Conda env, module, or container path is provided, test that route
  rather than searching broadly.
- If the run is offline, check the user-provided lineage directory exists and is
  readable. Do not download lineage databases without confirmation.

## Required inputs by mode

- `genome`: assembly FASTA, mode, lineage dataset, output directory.
- `protein`: protein FASTA, lineage dataset, output directory.
- `transcriptome`: transcript FASTA, lineage dataset, output directory.
- Optional for all modes: explicit config file, offline lineage directory, CPU
  count, sample/output label.

## Input preparation

- Confirm the FASTA path is explicit, readable, and non-empty.
- Check that the selected lineage matches the organism question; for quinoa and
  other plants, do not silently use a distant lineage when a better plant lineage
  is available.
- Choose a new output label for each input and each lineage. BUSCO output labels
  should not collide across multiple lineage tests.
- Keep the output directory project-local unless the user confirms otherwise.

## Parameter negotiation

- Must ask: mode, input FASTA, lineage dataset, output label, output directory,
  offline versus download behavior.
- Ask when relevant: whether high duplicated BUSCOs are expected from polyploidy or
  haplotype redundancy.
- Can infer: `--mode` from the confirmed input type only after stating the
  inference.
- Must record: BUSCO version, lineage name/version, mode, CPU count, config/env,
  and whether the lineage was local or downloaded.

## Resource model

Use `../software-resource-cards.md` under the BUSCO section. BUSCO is usually a
moderate CPU job, but lineage database, input size, and gene prediction mode can
change runtime. For large plant genomes, use SLURM rather than running on
`admin2`.

## Script generation notes

- Activate the environment or call an absolute BUSCO binary path.
- Pass threads through a shell variable such as `THREADS="${SLURM_CPUS_PER_TASK:-N}"`.
- Write logs under project `logs/` and BUSCO outputs under explicit
  `results/.../busco/`.
- Guard against an existing BUSCO output label unless the user confirms rerun or
  cleanup behavior.
- For multiple inputs or lineages, prefer a manifest-driven array with a concurrency
  cap.

## Acceptance checks

- `short_summary*` exists and is non-empty for every run.
- `full_table.tsv` exists and is non-empty.
- Parse and report `C`, `S`, `D`, `F`, and `M` percentages/counts.
- Confirm the summary records the expected mode and lineage.
- Inspect logs for normal completion, not only exit code 0.
- For polyploid genomes, do not treat high `Duplicated` as failure by itself; state
  whether it is biologically expected or suggests duplicated haplotigs.

## Common failures and recovery

- Existing output label: choose a new label or confirm cleanup/rerun.
- Missing lineage dataset: ask before download or point BUSCO to a confirmed local
  lineage path.
- Wrong mode for input: switch mode after confirming the file type.
- AUGUSTUS/config errors in genome mode: capture the BUSCO log and fix environment
  or config before resubmitting.
- Empty or malformed FASTA: stop and repair input rather than changing BUSCO
  parameters.

## Evidence grade

- Mode names and CLI syntax: `local_help` when verified on this server, otherwise
  `official_doc`.
- Resource starting points: `project_history` plus `inferred` from
  `../software-resource-cards.md`.
- Polyploid duplicated-BUSCO interpretation: `project_history` for quinoa-like
  work, otherwise `inferred`.
- Acceptance files: `local_run` when confirmed after a run, otherwise
  `official_doc`/`local_help`.
