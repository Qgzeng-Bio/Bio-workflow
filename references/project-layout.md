# Project layout and naming

Use these defaults for new bioinformatics projects. Preserve an established
project convention when it is clear, reproducible, and compatible with the safety
rules; do not rename a live project merely for style.

## Contents

- [Canonical directories](#canonical-directories)
- [Artifact boundaries](#artifact-boundaries)
- [Naming rules](#naming-rules)
- [Executable path management](#executable-path-management)
- [Identifiers and versions](#identifiers-and-versions)
- [Examples](#examples)
- [Compatibility and migration](#compatibility-and-migration)

## Canonical directories

```text
project/
├── config/   # manifests, parameters, environment references
├── data/     # links and project-local manifests, not protected raw-data copies
├── scripts/  # numbered workflow stages and submitted snapshots
├── logs/     # scheduler and program logs
├── tmp/      # disposable intermediates
├── results/  # analysis outputs
└── reports/  # plans, project/task status, acceptance, methods, figures, delivery index
```

Do not add an empty directory hierarchy beyond these seven defaults. Add a
task-specific subdirectory only when a real tool or workflow stage needs it.

## Artifact boundaries

- **Raw data:** keep under the protected data source selected by the user. Record
  paths/checksums in `config/Input_Manifest.tsv`; link into `data/` only when it
  improves tool compatibility.
- **Configuration:** keep manifests, reviewed parameters, reference/version
  identity, and environment/container references under `config/`.
- **Scripts:** keep editable workflow code under `scripts/`. Preserve the exact
  submitted script/config in the run record or a project-local snapshot.
- **Logs:** write complete stdout/stderr and scheduler identifiers under `logs/`.
  A log is evidence, not a final result.
- **Temporary output:** write restartable, disposable intermediates under `tmp/`.
  Never make `tmp/` the only location of an accepted result or provenance record.
- **Results:** store scientific outputs and compact summary tables under
  `results/`. Separate stages with short topic/tool subdirectories only when name
  collisions or rerun boundaries require it.
- **Reports:** store plans, project/task status, run records, acceptance evidence,
  interpretation, methods, figures, and delivery indexes under `reports/`.
  Keep project-wide lifecycle in `workflow_status.tsv` and concurrent work units
  in `Task_Status.tsv`; read `references/task-monitoring.md` before changing the
  task schema.

## Naming rules

### Managed analysis directories

For newly created stage/result subdirectories, use the executable contract in
`references/path-management.md`: one to three short semantic tokens, a
24-character basename budget, and an optional two-digit stage prefix. Within a
new sibling set, determine data dependencies/scientific reading order first and
then number directories consecutively: `01_prep`, `02_QC`, `03_RNA_DE`,
`04_figures`. Do not alphabetically number or default to `10`, `20`, `30` gaps.
This consecutive-directory rule is separate from the stable script-prefix rule
below.

Do not turn a long Chinese or English purpose sentence into a basename. Keep the
short operational identity in the directory and record the full purpose in
`config/Directory_Index.tsv`. Existing active/tool-controlled names are
compatibility surfaces and are never renamed only for style.

Before creating a new managed directory, run `path_manager.py suggest`; for an
existing project, use its bounded read-only `audit`. `create` and `register` are
dry-run by default and still require write disclosure/confirmation before
`--yes`.

### Scripts

- Use a two-digit step prefix and a short lowercase verb/topic:
  `10_prepare_inputs.sh`, `20_align.slurm`, `30_call_sv.py`.
- Use the same prefix for one logical stage; add a minimal discriminator when
  needed: `20_align_hifi.slurm`, `20_align_hic.slurm`.
- Do not renumber stable scripts only to fill gaps. Leave increments of 10 for
  later inserted stages.

### Human-facing files

- Use ASCII letters, digits, and underscores; keep a file basename to roughly
  4–5 segments and 60 characters. Managed directory names use the stricter
  24-character contract above.
- Use artifact/topic -> content/metric -> minimum discriminator:
  `BUSCO_Summary_LM134.tsv`, `FigA_Nx_Curves.pdf`.
- Preserve atomic identifiers exactly: `LM134`, `FigA`, `N50`, `Nx`, `BUSCO`,
  `LTR`, `TE`, chromosome IDs, and accessions.
- Avoid narrative names, unexplained abbreviations, and redundant words already
  implied by the directory or extension.
- Do not append `_Final`, `_New`, `_Latest`, `_Result`, `_Report`, `_Run`, or
  style labels. Use a real version or date only when two retained artifacts would
  otherwise collide.

### Logs and tool-controlled names

- Prefer absolute scheduler patterns such as `logs/%j_%x.out` and
  `logs/%j_%x.err`.
- Keep tool-mandated filenames unchanged inside a clearly named stage directory.
  Add a manifest or wrapper-level index instead of breaking tool compatibility.

### Tables

- Use tab-separated TSV for project tables unless a tool requires another format.
- Use English initial-capital underscore columns: `Sample_ID`, `Input_Path`,
  `Read_Count`, `Job_ID`.
- Keep atomic identifiers/acronyms exact. Never mix spaces and tabs as delimiters.
- Include units in names when ambiguity matters: `Length_bp`, `Size_GB`.

## Executable path management

Use:

```bash
python3 scripts/path_manager.py suggest --kind stage --step 3 --token RNA --token DE
python3 scripts/path_manager.py audit --project /abs/project --max-depth 3
```

For the complete dependency-order procedure, CLI, index schema, rule IDs,
dry-run writes, protected-path checks, and rollback behavior, read
`references/path-management.md`. The manager has no rename/move/delete operation
and does not follow symlinks during audit.

## Identifiers and versions

- **Sample IDs:** use the authoritative sample/accession ID; do not silently
  normalize case or punctuation. Keep display labels in reports, not filenames.
- **Species:** add a species token only when a project contains multiple species or
  collision is likely. Prefer a documented short token such as `Cqu` over a long
  binomial in every filename.
- **Reference:** record assembly name, release/version, source, checksum, and
  chromosome convention in config/manifest files. Add the reference token to an
  artifact name only when multiple references coexist.
- **Dates:** use `YYYYMMDD` for snapshots, dated releases, or colliding reruns, not
  as a default suffix.
- **Versions:** use `V2` or semantic `v1.1` only for a maintained version series.
  A version does not replace provenance or a checksum.

## Examples

| Purpose | Prefer | Avoid |
|---|---|---|
| Analysis plan | `Analysis_Plan.md` | `my_new_final_analysis_plan_latest.md` |
| Input manifest | `Input_Manifest.tsv` | `all_samples_files_new.txt` |
| SLURM stage | `20_align.slurm` | `run_alignment_final_version2.sh` |
| Result summary | `SV_Summary.tsv` | `structural_variant_analysis_results_final.tsv` |
| Figure | `FigA_Nx_Curves.pdf` | `figa_contig_nx_curves_lm_litstyle.pdf` |
| Snapshot | `BUSCO_Summary_20260711.tsv` | `BUSCO_Summary_Final.tsv` |

## Compatibility and migration

- Apply these rules to new artifacts first. Do not bulk-rename active inputs,
  submitted scripts, logs, or tool outputs.
- Before renaming an existing artifact, inspect every caller, manifest, report,
  symlink, and downstream consumer. Preserve an ID mapping when names are published
  or externally referenced.
- Treat naming lint as advisory for legacy/tool-controlled paths. Safety,
  reproducibility, and compatibility outrank cosmetic uniformity.
- Use `scripts/init_project.sh` to preview or create the minimal new-project
  skeleton and templates, including `config/Directory_Index.tsv`. It is dry-run
  by default and never overwrites files.
- Use `scripts/path_manager.py audit` for advisory legacy checks. Register
  tool-mandated names as `tool_managed` and incompatible established names as
  `legacy`; do not bulk-rename them.
