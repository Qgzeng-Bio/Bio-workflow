# Bioflow project layout and naming

Use this contract when starting a project, choosing output paths, organizing results, plotting, writing a manuscript, or reviewing directory drift. Layout v2 is the default for new/empty projects. Existing unmarked `data/` + `reports/` projects remain legacy and are never rearranged automatically.

## Layout v2: fixed project roots

`config/Project_Layout.tsv` is the authoritative marker. A v2 project has eight fixed roots:

```text
project/
├── README.md
├── PROJECT_STATUS.md
├── CHANGELOG.md
├── .gitignore
├── .github/
├── config/       # manifests, sample/reference metadata, parameters, environments
├── rawdata/      # read-only original inputs or links; never analysis outputs
├── scripts/      # executable scripts/workflows, mirrored by analysis module
├── logs/         # program and scheduler logs
├── tmp/          # disposable, reproducible intermediates only
├── results/      # retained scientific outputs; one entry per analysis type
├── docs/         # plans, status, decisions, methods, validation, delivery, handoff
└── manuscripts/  # one stable directory per paper and release snapshots
```

The flow is:

```text
rawdata -> scripts -> tmp -> results -> manuscripts
                  \-> logs
                  \-> docs
```

Do not add parallel roots such as `metadata/`, `envs/`, `workflows/`, or `reports/` in a v2 project:

- metadata and environment descriptions belong in `config/`;
- workflows belong below the owning `scripts/<module>/`;
- project records belong in `docs/`;
- paper sources and submission snapshots belong in `manuscripts/`.

## Root boundaries

### `config/`

Keep `Input_Manifest.tsv`, `Sample_Metadata.tsv`, `Reference_Manifest.tsv`, `Tool_Versions.tsv`, reviewed parameters, environment/container descriptions, result manifests, directory indexes, and Workspace contracts here. These are small text authorities suitable for Git when they contain no secrets.

### `rawdata/`

Keep only original, immutable inputs, immutable references, or explicit read-only links. Every input is identified by `config/Input_Manifest.tsv`. Analysis programs must not write outputs, temporary indexes, logs, modified derivatives, result tables, or figures here. The project `.gitignore` excludes raw contents while retaining `rawdata/README.md`.

Protected server sources such as `/data9/home/<user>/data/` remain protected. A project-local `rawdata/` name does not grant permission to copy, modify, or upload protected inputs.

### `scripts/`

Keep the single editable source of scripts and workflow definitions. Mirror the stable analysis-module path, for example `scripts/01-assembly/`. Snakemake/Nextflow definitions may use `scripts/<module>/workflow/`; helper code may use `scripts/<module>/helpers/` or `plotting/`. Do not copy changing scripts into results.

### `logs/`

Keep complete scheduler stdout/stderr and program logs under the owning module. Logs are run evidence, not scientific results. Use absolute `%j_%x.out` and `%j_%x.err` paths in SLURM scripts. Logs are normally excluded from Git.

### `tmp/`

Only content satisfying all three conditions belongs here:

1. it can be regenerated from recorded inputs, scripts, and parameters;
2. deleting it does not break any downstream reproducibility or paper evidence;
3. it is not the only copy of a retained or accepted output.

Formal result, figure, claim, acceptance, delivery, or manuscript records must never cite `tmp/`. A task's formal `--output` cannot be `tmp/`; pass temporary routes separately. Draft plot candidates, workflow caches, sorting/chunking intermediates, and disposable pilot output may use `tmp/<module>/`.

### `results/`

Store retained scientific outputs, accepted summaries, compact tables, and reproducible figure packages. Do not use `results/` as a cache or log directory. Every scientific analysis type has exactly one stable top-level module entry.

### `docs/`

Use `docs/Analysis_Plan.md`, `docs/status/`, `docs/research-log/`, `docs/decisions/`, `docs/methods/`, `docs/validation/`, and `docs/delivery/`. These records explain why work was done, current state, decisions, methods, acceptance, limitations, and handoff. They do not duplicate machine logs.

### `manuscripts/`

Create one stable directory per paper only when writing begins, for example `manuscripts/P01-genome/`. Keep Markdown/LaTeX/BibTeX sources, supplement, Claim–Evidence Map, and submission releases here. Do not maintain a second changing copy of analysis figures. A submission release may contain a frozen figure snapshot tied to a Git tag, commit, and checksum.

## One analysis, one result entry

A layout-v2 Workspace module has a stable lowercase `Analysis_Key`, for example `assembly`, `genome-qc`, or `gene-annotation`. It maps to exactly one retained directory:

```text
Analysis_Key=assembly -> results/01-assembly/
```

Correct:

```text
results/
├── 01-assembly/
├── 02-genome-qc/
├── 03-repeat-annotation/
└── 04-gene-annotation/
```

Forbidden:

```text
results/01-assembly/
results/02-assembly-v2/
results/assembly-final/
results/assembly-new/
```

A repeated attempt with the same scientific purpose is a version inside the existing module. A genuinely different question/product is a new module. Module numbering represents dependency or scientific reading order, never version.

## Retained versions inside a module

When more than one scientifically useful run must be retained:

```text
results/01-assembly/
├── README.md
├── Version_Index.tsv
├── versions/
│   ├── V01/
│   └── V02/
├── tables/
└── figures/
```

Rules:

- use `versions/VNN`; do not create a sibling module;
- only successful, comparison-worthy, downstream-used, or acceptance-relevant runs enter `versions/`;
- ordinary tests, failed output, and layout alternatives stay in `tmp/` plus `logs/`;
- each retained version is registered in `Version_Index.tsv`;
- at most one version is `Selected=Yes`;
- state is recorded in the index, never encoded as `final`, `new`, `latest`, or `best` in a directory name;
- Git records text/config changes; it does not replace version identity for large scientific outputs.

## Figure packages

A module's `figures/` root contains only `Figure_Index.tsv` and stable figure-package directories:

```text
results/01-assembly/figures/
├── Figure_Index.tsv
└── F001_Assembly_Overview/
    ├── README.md
    ├── F001_Assembly_Overview.pdf
    ├── F001_Assembly_Overview.png
    ├── source-data/
    │   └── F001_Assembly_Overview.tsv
    └── checks/
        ├── Figure_Check.md
        └── Final_Review.json
```

- `FNNN` is a stable internal ID; paper labels such as `Fig1A` are mutable mappings in `Figure_Index.tsv`.
- Formal PDF/PNG stay at package root so they are immediately visible.
- `source-data/` contains the exact TSV used for plotting, not raw input or unrelated analysis output.
- `checks/` contains generated Markdown/JSON metadata, visual checks, and review sidecars.
- `README.md` explains purpose, source result, plot script, message, claim, limits, and status in plain language.
- the one editable plotting script stays under `scripts/<module>/plotting/`.
- candidate layouts and old/new experiments stay under `tmp/<module>/plotting/FNNN/`.
- Draft packages may be incomplete and generate WARN. `Validated`, `Manuscript_ready`, `Frozen`, completed-producer, or delivered packages must have the complete contract.

## Module and file naming

Layout-v2 managed module directories use:

```text
NN-analysis-key
```

Examples: `01-assembly`, `02-genome-qc`, `03-rna-de`. Use consecutive two-digit stages among siblings and short lowercase hyphenated analysis keys. `Analysis_Key` and `Short_Name` are stable and equal in Workspace v2. Do not include `V2`, `final`, `new`, `latest`, `best`, `revised`, or `rerun`.

Formal files use clear Initial_Capital underscore names and preserve scientific IDs/acronyms:

```text
Assembly_Summary.tsv
BUSCO_Summary_LM134.tsv
F001_Assembly_Overview.pdf
```

Project tables are true TSV with English Initial_Capital underscore columns and explicit units such as `Length_bp` or `Size_GB`.

## Git/GitHub boundary

Read `references/git-collaboration.md`. In brief: track code, configuration, manifests, Markdown/LaTeX/BibTeX, small source tables, figure code, and reviewed small figure outputs. Do not track raw sequencing data, protected/sensitive content, credentials, caches, Conda environments, logs, disposable intermediates, or large reproducible output by default.

## Tools and checks

Initialize a new v2 project (dry-run first):

```bash
scripts/init_project.sh --project /abs/project --workspace-steward
```

For an existing reviewed Git root that should explicitly adopt v2:

```bash
scripts/init_project.sh --project /abs/project --layout-v2 --workspace-steward
```

After disclosure and confirmation, add `--yes`. The initializer creates only missing paths and never overwrites. Use:

```bash
python3 scripts/path_manager.py audit --project /abs/project --max-depth 3
python3 scripts/project_structure_audit.py --project /abs/project
python3 scripts/workspace_steward.py inspect --project /abs/project
python3 scripts/workspace_steward.py audit --project /abs/project
```

`project_structure_audit.py` is bounded/read-only. It checks root boundaries, one-analysis-one-entry, version placement/indexing, formal `tmp/` references, and figure packages. Before any Git staging/commit review, run `scripts/git_project_audit.py --project /abs/project`; it blocks rawdata/runtime/cache/raw-alignment/credential/symlink/oversize candidates without running Git write or network operations. Workspace Steward additionally validates the Agent-authored module DAG, `Analysis_Key`, role routes, tasks, and reviewed plan fingerprint.

## Legacy compatibility

An existing project without `config/Project_Layout.tsv` remains on the legacy roots `config/data/scripts/logs/tmp/results/reports`. Existing paths, inputs, scripts, logs, results, and tool-controlled outputs are never bulk-renamed or moved for style. Use read-only `migration-plan` when requested; actual moves require separate impact analysis and confirmation. New artifacts in a legacy project should remain compatible with its established paths unless a reviewed v2 migration is explicitly scoped.
