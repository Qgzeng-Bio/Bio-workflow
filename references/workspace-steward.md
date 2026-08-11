# Workspace Steward

Use this contract when Bioflow starts or takes over a project, designs analysis
modules, chooses script/log/tmp/result/report locations, prepares execution, or
checks whether a workspace has drifted from its reviewed structure.

Workspace Steward manages the project architecture. `path_manager.py` remains
the lower-level concise-name, single-directory, safety, and `Directory_Index.tsv`
engine.

## Contents

- [Operating model](#operating-model)
- [Metadata contracts](#metadata-contracts)
- [Module and route rules](#module-and-route-rules)
- [CLI workflow](#cli-workflow)
- [Execution-gate integration](#execution-gate-integration)
- [Hybrid enforcement](#hybrid-enforcement)
- [TEMR reasoning example](#temr-reasoning-example)
- [Safety and acceptance](#safety-and-acceptance)

## Operating model

The steward is event-driven, not a daemon:

```text
project intake/takeover -> inspect
reviewed scientific plan -> module DAG + routes -> plan
before script generation -> route
approved workspace tree -> apply (dry-run first)
before submission -> preflight
monitoring -> project_dashboard workspace summary
acceptance/delivery -> audit
existing project cleanup request -> migration-plan only
```

The Agent—not the deterministic script—reads the research plan, scripts,
manifests, handoffs, accepted summaries, and bounded project evidence. The Agent
proposes modules, dependencies, roles, and critical artifacts. The user reviews
the proposal. `workspace_steward.py` validates and executes that explicit
contract; it never guesses biological chronology from names, extensions, mtime,
or directory listing order.

Management granularity is deliberately bounded:

- manage module hierarchy and script/log/tmp/result/plot/report directories;
- register exact key delivery or acceptance artifacts;
- do not index every FASTQ/BAM/VCF shard or tool intermediate;
- use `Task_Status.tsv` for execution state rather than duplicating it;
- do not run watchers or intercept system `mkdir`.

## Metadata contracts

All files are true TSV with exact headers.

### `config/Workspace_Policy.tsv`

```text
Schema_Version	Enforcement_Mode	Plan_Status	Plan_SHA256	Max_Audit_Depth	Updated_Time
```

v1 values:

- `Schema_Version`: `workspace.v1`;
- `Enforcement_Mode`: `Hybrid`;
- `Plan_Status`: `Draft` or `Reviewed`;
- `Plan_SHA256`: empty while Draft; reviewed plan fingerprint after `apply --yes`;
- `Max_Audit_Depth`: default 3, maximum 5;
- `Updated_Time`: reviewed-plan time.

Any module/route byte-level normalized-content change after review produces a new
fingerprint. Managed preflight then blocks until the changed plan is reviewed and
applied again.

### `config/Workspace_Modules.tsv`

```text
Module_ID	Parent_Module	Stage	Short_Name	Module_Kind	Depends_On	Purpose	Owner	Compatibility	Notes
```

- `Module_ID`: stable `M001`, `M002`, ... ID;
- `Parent_Module`: `ROOT` or another declared module;
- `Stage`: managed sibling stage `01`–`99`;
- `Short_Name`: one to three concise semantic tokens;
- `Module_Kind`: `group`, `analysis`, `publication`, `management`, or `legacy`;
- `Depends_On`: comma-separated existing Module IDs;
- `Compatibility`: `Managed` or `Legacy`.

Managed sibling stages must be exactly consecutive (`01..N`). Parent links and
dependencies must be acyclic. A dependency between siblings must point to an
earlier stage. Parallel work may share a parent without depending on each other;
do not invent a false dependency merely to justify numbering.

### `config/Workspace_Routes.tsv`

```text
Route_ID	Module_ID	Path_Type	Path_Role	Relative_Path	Producer_Tasks	Consumer_Tasks	Retention	Required	Compatibility	Purpose	Notes
```

- `Route_ID`: stable `R001`, `R002`, ... ID;
- `Path_Type`: `Directory` or exact key `Artifact`;
- `Producer_Tasks`/`Consumer_Tasks`: comma-separated stable IDs from
  `reports/Task_Status.tsv`;
- `Retention`: `Disposable`, `Working`, `Retained`, or `Delivery`;
- `Required`: `Yes` or `No`;
- `Compatibility`: `Managed`, `Tool_managed`, or `Legacy`.

Globs are forbidden. An Artifact route names one exact critical path. Ordinary
files below a planned directory route do not each require a route row.

The steward does not replace these authorities:

- `Directory_Index.tsv`: directories actually created/adopted;
- `Task_Status.tsv`: task runtime state;
- `workflow_status.tsv`: project lifecycle;
- `result_manifest.yaml`: evidence-to-claim contract;
- `Delivery_Index.md`: delivery package.

## Module and route rules

### Canonical role boundaries

| Path role | Required root |
|---|---|
| `Config`, `Manifest` | `config/` |
| `Input_Link` | `data/` |
| `Script` | `scripts/` |
| `Log` | `logs/` |
| `Temporary` | `tmp/` |
| `Result`, `QC`, `Plot_Data`, `Source_Table` | `results/` |
| `Figure`, `Report`, `Acceptance`, `Delivery` | `reports/` |

Managed Directory routes follow the module path under their canonical root. For
example module `M002` with stage/name `02_Cq3B_INV`, child `M004` with
`03_LD_Fst`, and a result role maps to:

```text
results/02_Cq3B_INV/03_LD_Fst
```

The same module can have coordinated routes under several roots:

```text
scripts/02_Cq3B_INV/03_LD_Fst
logs/02_Cq3B_INV/03_LD_Fst
tmp/02_Cq3B_INV/03_LD_Fst
results/02_Cq3B_INV/03_LD_Fst
```

Analysis modules require managed Script, Log, Temporary, and Result Directory
routes. Publication modules require Script, Plot_Data, Figure, and Report routes.
Management modules require Config and Report routes. A group module requires at
least one directory container. Every non-canonical planned parent must itself be
a Directory route, so `apply` never invents an implicit hierarchy.

`Tool_managed` and `Legacy` may be explicit layout exceptions, but remain inside
the project/canonical roots and still obey protected-path and symlink safety.

## CLI workflow

Resolve the skill root once when calling from another project:

```bash
BIOFLOW=/data9/home/qgzeng/projects/3-Biotools_create/bio-workflow
STEWARD="$BIOFLOW/scripts/workspace_steward.py"
```

### Bootstrap

For a new project, explicitly enable templates:

```bash
bash "$BIOFLOW/scripts/init_project.sh" \
  --project /abs/project --workspace-steward
```

The command is dry-run by default. After write disclosure and confirmation, add
`--yes`. Existing projects can install only the workspace contracts with:

```bash
python3 "$STEWARD" bootstrap --project /abs/project
```

Bootstrap never creates analysis-module directories or overwrites an existing
contract.

### Inspect

```bash
python3 "$STEWARD" inspect --project /abs/project --max-depth 3 --format tsv
```

Inspection is bounded/read-only, does not follow symlinks, skips hidden/cache
entries, and does not recurse into root `data/`, `logs/`, or `tmp/`. Observed
roles are strong mechanical hints only; no biological dependency is inferred.

### Plan

After the Agent writes reviewed proposal rows to Workspace Modules/Routes:

```bash
python3 "$STEWARD" plan --project /abs/project
python3 "$STEWARD" plan --project /abs/project --format json
```

`plan` checks exact schemas, IDs, module tree, continuous stages, DAG, route
roots, module path prefixes, parent route coverage, duplicate/case collisions,
and minimum role sets. It prints the deterministic plan fingerprint and writes
nothing.

### Resolve a route

```bash
python3 "$STEWARD" route \
  --project /abs/project --module M001 \
  --role Log --path-type Directory
```

Exactly one match is required. Missing or ambiguous routing is a plan defect; the
tool does not choose one silently.

### Apply a reviewed tree

Preview all actions:

```bash
python3 "$STEWARD" apply --project /abs/project
```

After disclosure/confirmation, add `--yes`. The write run:

1. revalidates under `config/.Workspace_Steward.lock`;
2. creates missing Managed Directory routes in depth order;
3. registers directories in `Directory_Index.tsv` with stable IDs;
4. atomically updates index and Reviewed policy/fingerprint;
5. restores previous bytes and removes only this run's new empty directories on
   failure.

Existing unindexed Managed paths are refused. Explicit existing Legacy or
Tool_managed routes can be registered, but missing exception paths are never
created. Artifact routes are never created by `apply`.

### Audit

```bash
python3 "$STEWARD" audit --project /abs/project --format json
```

The audit joins policy, modules/routes, Directory Index, bounded filesystem,
latest Task Status rows, and project lifecycle. Exit codes:

- 0: PASS;
- 1: WARN only;
- 2: BLOCK, malformed contract, or unsafe input.

Stable findings include `WS001` schema, `WS002` module/DAG/order, `WS003`
role/root, `WS004` review/fingerprint, `WS005` required directory,
`WS006` unplanned path, `WS007` legacy, `WS008` tool-managed, `WS009` strong
file-placement evidence, `WS010` key artifact timing, `WS011` Directory Index,
`WS012` Task Status route, `WS013` symlink, and `WS014` root clutter.

A required Artifact is not considered failed merely because it does not exist
during planning/running. It becomes BLOCK when a declared producer is
`Complete_unvalidated`/`Validated` or the project reaches Delivered.

### Execution preflight

```bash
python3 "$STEWARD" preflight \
  --project /abs/project --module M001 --task-id T001 \
  --script-path /abs/project/scripts/01_core/job.slurm \
  --log-path '/abs/project/logs/01_core/%j_%x.out' \
  --log-path '/abs/project/logs/01_core/%j_%x.err' \
  --output-path /abs/project/results/01_core \
  --tmp-path /abs/project/tmp/01_core
```

Policy must be Reviewed and unmodified. The latest Task row must use the Module
ID in `Stage`. Every explicit path must match that module's allowed role and, if
the route lists producers, the Task ID must be listed. Scheduler `%j/%x`
basenames are legal.

### Existing-project migration plan

```bash
python3 "$STEWARD" migration-plan \
  --project /abs/project --max-depth 3 --format tsv
```

Only high-confidence mechanical cases such as `.out/.err/.log` outside logs and
`.slurm/.sbatch` outside scripts get concrete suggestions. Ambiguous content is
`REVIEW_REQUIRED`. Output action is always `PLAN_ONLY`; there is no mutation or
reference rewriting.

## Execution-gate integration

For a steward-enabled project, generate scripts with explicit context:

```bash
scripts/gen_sbatch.sh \
  --job-name NAME --cpus N --mem 16G \
  --log-dir /abs/project/logs/01_core \
  --out /abs/project/scripts/01_core/job.slurm \
  --project /abs/project --module M001 --task-id T001 \
  --output-dir /abs/project/results/01_core \
  --tmp-dir /abs/project/tmp/01_core \
  --cmd 'tool ...'
```

`prepare_submission.sh` and `submit_and_log.sh` accept/forward:

```text
--project DIR --module M001 --task-id T001 --tmp PATH
```

They use existing `--script` and `--output`, parse only explicit SBATCH log
paths, and call Workspace preflight. They do not parse arbitrary shell commands
to guess hidden outputs. When current working directory contains a Workspace
Policy, omission of module/task/output is a hard gate failure. Non-steward
projects retain the legacy behavior.

`project_dashboard.py` adds a read-only Workspace summary to text/JSON. JSON gets
a `Workspace` object; task TSV remains unchanged.

## Hybrid enforcement

- Steward absent: existing Bioflow behavior; inspect/migration-plan remain
  available.
- Draft: planning/audit allowed, managed execution blocked.
- Reviewed and matching fingerprint: Managed paths are strict.
- Explicit Legacy: WARN, no automatic migration.
- Explicit Tool_managed: layout/name exempt, boundary checks still strict.
- Unplanned/unregistered path in a Reviewed workspace: BLOCK.

This is “new strict, old wide” only after old paths are explicitly classified.
The steward does not decide that an unknown existing path is legacy by itself.

## TEMR reasoning example

A flat sequence such as `01_intermediate`, `02_QC`, `03_tables`, ... mixes path
roles with scientific modules and is not sufficient workspace management. A
hypothetical from-scratch interpretation of the read-only TEMR evidence is:

```text
Modules
├── 01_TEMR_core
├── 02_Cq3B_INV
│   ├── 01_grouping
│   ├── 02_phenotype
│   ├── 03_LD_Fst
│   ├── 04_gene_impact
│   └── 05_evolution
└── 03_publication
```

Routes mirror those modules by role:

```text
scripts/<module path>/       # runnable code
logs/<module path>/          # .out/.err/.log
tmp/<module path>/           # intermediate BED and disposable files
results/<module path>/       # accepted analysis/QC/tables
results/03_publication/...   # plot data and source tables
reports/03_publication/...   # figures, methods, summaries, handoff
```

Thus `intermediate` belongs under `tmp`, scheduler logs under `logs`, and plans,
methods, summaries, and handoff under `reports`. Grouping review precedes
phenotype/LD/function consumers because it defines INV/WT membership. This is a
reasoning fixture only; the protected real TEMR project is not changed.

## Safety and acceptance

Hard boundaries:

- explicit project roots only; broad/protected roots refused;
- max audit depth 5 and inventory hard cap;
- no symlink traversal or protected-path exception;
- no glob routes and no automatic semantic inference;
- no rename, move, delete, copy, archive mutation, watcher, or daemon;
- all writes dry-run first, normal Agent disclosure/confirmation still required;
- `--yes` is an executor switch, not authorization;
- no concurrent writers; `apply` uses a project-local lock;
- no real submission in tests.

Acceptance requires core CLI fixtures, transaction failure injection, shell gate
integration, dashboard PASS/WARN/BLOCK, full Bioflow maintenance, source/plugin/
runtime equality, real Claude plugin validation, and unchanged PaperPlot and
protected/TEMR paths.
