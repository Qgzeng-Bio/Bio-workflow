# Concise project path management

Use this contract when a user asks to create or name an analysis directory,
complains that folder names are too long, wants to inspect project naming, or
needs a compact explanation of result directories.

## Contents

- [Design boundary](#design-boundary)
- [Managed naming rules](#managed-naming-rules)
- [Continuous dependency-driven order](#continuous-dependency-driven-order)
- [Suggest one name](#suggest-one-name)
- [Audit an explicit project](#audit-an-explicit-project)
- [Create one directory](#create-one-directory)
- [Register an existing directory](#register-an-existing-directory)
- [Directory index](#directory-index)
- [Audit rule IDs](#audit-rule-ids)
- [Safety and acceptance](#safety-and-acceptance)

## Design boundary

`scripts/path_manager.py` has four subcommands:

- `suggest`: read-only, emits one deterministic short name;
- `audit`: read-only, bounded directory-name and index check;
- `create`: dry-run by default, creates one directory and one index row only with
  `--yes`;
- `register`: dry-run by default, indexes one existing directory only with
  `--yes`.

There is deliberately no rename, move, delete, cleanup, archive mutation, or
bulk-fix command. Existing long names are evidence and compatibility surfaces;
report them instead of changing them. A future `rename-plan` requires a separate
review, and an actual `mv` always requires a new risk disclosure and confirmation.

The tool uses only the Python standard library. It never infers unrestricted
English names from a long Chinese sentence. The agent first reduces the purpose
to one to three short semantic tokens; the script validates and combines them.

## Managed naming rules

New managed names have a 24-character maximum.

### Analysis-module directories

Layout-v2 format:

```text
NN-analysis-key
```

Examples:

```text
01-assembly
02-genome-qc
03-rna-de
04-publication-data
```

The stable lowercase `Analysis_Key` occurs only once and equals Workspace v2
`Short_Name`. A module name never contains a version/status token; repeated work
uses `<module>/versions/VNN`. Legacy projects continue to recognize established
`NN_token` names without renaming them.

`NN` is a zero-padded two-digit stage number (`00`–`99`). Within one newly
planned sibling set, assign stages consecutively (`01`, `02`, `03`, ...); do not
default to directory gaps such as `10`, `20`, `30`. Semantic tokens contain ASCII
letters/digits only. Ordinary action/topic words are short lowercase words;
established scientific abbreviations retain standard casing; atomic sample,
chromosome, figure, and accession IDs remain exact.

### Result directories

Non-module helper/result subdirectories may omit a stage only when they do not
create a second analysis entry, for example `tables`, `figures`, `source-data`,
or a registered tool-owned directory. They live below the one stable
`results/NN-analysis-key/` module, not beside it. Retained analysis versions use
only `versions/VNN`.

### Forbidden redundancy

These tokens are refused case-insensitively:

```text
Final  New  Latest  Result  Results  Report  Reports  Output  Outputs  Run
```

A version token is not allowed in an analysis-module name. Retained scientific
iterations use `versions/VNN` plus `Version_Index.tsv`. Dates/semantic versions
remain available for non-module artifact snapshots only when a real collision or
release requires them; they never replace provenance.

### Exempt and legacy names

Layout-v2 fixed roots are exempt:

```text
config  rawdata  scripts  logs  tmp  results  docs  manuscripts
```

Legacy fixed roots remain exempt:

```text
config  data  scripts  logs  tmp  results  reports
```

Register tool-mandated output directories as `tool_managed`; audit reports them
as exempt. Register an incompatible established path as `legacy`; audit emits an
advisory warning and never proposes an automatic rename.

## Continuous dependency-driven order

A stage number is a compact dependency/read-order label, not decoration. Before
choosing `--step` for multiple sibling directories, the agent must:

1. define the sibling scope that will share one sequence;
2. inspect bounded, explicit project evidence such as plans, scripts, manifests,
   handoffs, accepted summaries, and shallow directory contents;
3. identify inputs/preparation, QC gates, accepted core results, downstream
   branches, plot-ready data, figures, and reports;
4. order actual prerequisites before their consumers and place final reporting
   after accepted evidence;
5. assign consecutive stages `01`, `02`, `03`, ... in that evidence-based order.

Never derive stage order from alphabetic sorting, locale/`ls` order, modification
time, inode order, or the accidental order of an existing untidy directory. Do
not assign numbers first and invent a rationale afterwards.

Some analyses are parallel rather than dependent. Use the intended execution or
scientific reading order when that order is supported. If a flat sequence would
falsely imply dependency, create a short branch parent and use a consecutive
sequence within each branch instead of forcing unrelated tasks into one chain.
Record the branch and purpose in `Directory_Index.tsv`.

The decision boundary is explicit: the agent establishes the dependency order;
`path_manager.py suggest/create` only validate and format the selected step. The
tool does not infer biology or chronology from names.

### Real read-only tuning example: TEMR results

A bounded inspection of an existing quinoa TEMR result directory first showed
that alphabetic ordering was wrong. It also showed that putting
`intermediate/QC/tables/Cq3B analyses/plot_data/figures/docs` into one numbered
flat `results/` list is still not project management: it mixes artifact roles
with scientific modules.

The corrected hypothetical v2 structure starts with modules:

```text
01-temr-core
02-cq3b-inv/
├── 01-grouping
├── 02-phenotype
├── 03-ld-fst
├── 04-gene-impact
└── 05-evolution
03-publication-data
```

Then Workspace Steward routes modules by role:

```text
scripts/<module>/     logs/<module>/       tmp/<module>/
results/<module>/     docs/...             manuscripts/P01-.../
```

Intermediate BEDs belong in `tmp`, `.out/.err` in `logs`, retained QC/tables and
figure packages in `results`, project records in `docs`, and paper sources in
`manuscripts`. Grouping precedes consumers of INV/WT membership. The actual
legacy TEMR project remains unchanged and is not a migration target.
Read `references/workspace-steward.md` for that architecture. This file remains
the lower-level one-directory naming contract.

For existing active directories, do not renumber merely to make the sequence
continuous. Apply consecutive numbering when planning a new sibling module set;
later insertions use a reviewed next stage or branch rather than automatic
renaming. The protected real TEMR project was read only and is not a migration
target.

## Suggest one name

```bash
python3 scripts/path_manager.py suggest \
  --kind stage --step 3 --token rna --token de
```

Output is true TSV for the v2 default:

```text
Recommended_Name	Name_Length	Token_Count	Status	Rule_ID	Detail
03-rna-de	9	2	PASS	OK	name satisfies managed-directory rules
```

When `--project` is supplied, the manager uses that project's v2 or legacy
separator/profile.

The command emits one recommendation, not a list of increasingly long options.
Casing is preserved from each explicit token.

Optional read-only sibling collision check:

```bash
python3 scripts/path_manager.py suggest \
  --kind result --token BUSCO \
  --project /abs/project --parent results
```

`--project` and `--parent` must be supplied together. A case-insensitive sibling
collision returns `WARN` and exit 1. Invalid token/step/version or unsafe input
returns exit 2.

## Audit an explicit project

```bash
python3 scripts/path_manager.py audit \
  --project /abs/project --max-depth 3
```

Behavior:

- explicit existing project root only;
- default depth 3, hard maximum 5;
- no symlink traversal;
- hidden/cache paths skipped;
- the active raw-input root (`rawdata/` in v2 or `data/` in legacy), `logs/`, and
  `tmp/` are listed but their contents are not traversed;
- project index is read when present;
- deterministic path/rule sorting;
- no files or directories are written.

Output columns:

```text
Relative_Path	Directory_Kind	Name_Length	Token_Count	Status	Rule_ID	Detail	Suggested_Name
```

Default exit 0 means the audit completed, not that every row passed. Add
`--strict` to return 1 when any `WARN` exists. Unsafe input, malformed index, or
invalid depth returns 2.

`Suggested_Name` is emitted only for an unambiguous mechanical cleanup such as
separator normalization or redundant-token removal. Overlong or semantically
ambiguous names return `REVIEW_REQUIRED`; the tool does not guess a biological
replacement.

## Create one directory

Preview:

```bash
python3 scripts/path_manager.py create \
  --project /abs/project --parent results \
  --kind stage --step 3 --token RNA --token DE \
  --purpose "RNA-seq differential expression" --owner qgzeng
```

The preview prints `DRY_RUN`, the exact target, index path, stable directory ID,
and complete proposed TSV row. It writes nothing.

After the agent discloses purpose, exact command, target/index paths, expected
outputs, and risks—and receives `confirm_action` approval—the same command may be
run with `--yes`.

Write behavior:

1. require an existing project `config/` and existing non-symlink parent;
2. validate project boundary, protected paths, name budget, existing target, and
   case-insensitive sibling collisions;
3. create exactly one directory (no implicit parent hierarchy);
4. atomically replace `config/Directory_Index.tsv` with one added row;
5. if index commit fails, restore the old index and remove the newly created empty
   directory.

`--yes` is an executor switch, not user authorization. The agent confirmation
gate remains mandatory.

## Register an existing directory

Preview:

```bash
python3 scripts/path_manager.py register \
  --project /abs/project \
  --relative results/BUSCO \
  --kind tool_managed \
  --purpose "BUSCO native outputs"
```

Add `--yes` only after write disclosure and confirmation. Registration writes one
index row and does not touch directory contents.

Kinds:

- `stage`: path name must satisfy managed stage syntax; `--step` required;
- `result`: path name must satisfy managed result syntax;
- `tool_managed`: existing tool-controlled name; audit exemption;
- `legacy`: established incompatible name; audit advisory.

For a conforming stage/result, `Name_Tokens` can be inferred from the basename or
supplied via repeated `--token`. An incompatible path must be registered as
`legacy`, not forced through a false clean status.

Duplicate/case-colliding relative paths and duplicate IDs are refused. Optional
`--directory-id D123` is accepted only when unique; otherwise the next stable ID
is allocated.

## Directory index

New projects receive:

```text
config/Directory_Index.tsv
```

Exact header:

```text
Directory_ID	Relative_Path	Directory_Kind	Stage	Name_Tokens	Purpose	Owner	Status	Notes
```

Field contract:

- `Directory_ID`: stable `D001`, `D002`, ... identifier;
- `Relative_Path`: project-relative directory, unique case-insensitively;
- `Directory_Kind`: `stage`, `result`, `tool_managed`, or `legacy`;
- `Stage`: two-digit stage for `stage`, otherwise empty;
- `Name_Tokens`: comma-separated compact tokens used by the name;
- `Purpose`: full human explanation that does not belong in the basename;
- `Owner`: responsible user/team;
- `Status`: `Active`, `Archived`, or `External`;
- `Notes`: optional compatibility or provenance note.

The index explains paths only. It does not replace:

- the active layout's `Task_Status.tsv` for concurrent task state;
- the active layout's `workflow_status.tsv` for project lifecycle;
- the Delivery Index for delivered artifacts;
- `Version_Index.tsv` for retained versions;
- `Figure_Index.tsv` for retained figures;
- `config/result_manifest.yaml` for evidence and claims.

`init_project.sh` creates the empty header only when absent and never overwrites an
existing index.

## Audit rule IDs

| Rule | Meaning | Result |
|---|---|---|
| `PATH001` | basename exceeds 24 characters | WARN |
| `PATH002` | more than three semantic tokens | WARN |
| `PATH003` | redundant status/context token | WARN |
| `PATH004` | invalid characters/separators or missing two-digit stage prefix | WARN |
| `PATH005` | case-insensitive sibling collision | WARN |
| `PATH006` | index marks established directory as `legacy` | WARN, no rename |
| `PATH007` | indexed directory is missing | WARN |
| `PATH008` | symlink encountered | EXEMPT, not followed |
| `PATH009` | index marks path `tool_managed` | EXEMPT |
| `PATH010` | fixed Bioflow root directory | EXEMPT |
| `OK` | managed name satisfies active syntax/budget | PASS |

## Safety and acceptance

Hard boundaries:

- refuse `/`, `/data9`, `/data9/home`, `$HOME`, and `$HOME/projects` as projects;
- refuse `/data9/home/<user>/data|tools` project/target paths;
- reject absolute or `..` relative parent/registered paths;
- reject symlink components for write targets and never follow audit symlinks;
- reject existing targets, output overwrite, duplicate index IDs/paths, and
  malformed TSV;
- do not run concurrent `create/register` writers against one project index;
- do not expose rename/move/delete operations.

Acceptance requires:

- `suggest` returns the expected one-line name;
- `audit` is deterministic and read-only at the bounded depth;
- `create/register` dry-run changes no path;
- confirmed fixture writes produce one directory/index row or roll back both;
- `Directory_Index.tsv` remains valid true TSV;
- the full Bioflow maintenance suite and source/plugin/runtime drift checks pass.
