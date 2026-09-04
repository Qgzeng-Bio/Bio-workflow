# Workspace Steward

Use this contract when Bioflow starts or takes over a project, designs analysis modules, chooses script/log/tmp/result/docs/manuscript paths, prepares execution, or checks workspace drift. `path_manager.py` remains the lower-level concise-name and `Directory_Index.tsv` engine; `project_structure_audit.py` enforces layout-v2 result/version/figure boundaries.

## Operating model

```text
intake/takeover -> inspect
reviewed science -> module DAG + role routes -> plan
before script generation -> route
approved workspace -> apply (dry-run first)
before submission -> project structure audit + Workspace preflight
monitoring -> project dashboard
acceptance/delivery -> structure audit + Workspace audit
legacy cleanup request -> migration-plan only
```

The Agent reads the scientific plan and bounded evidence, then proposes modules, dependencies, roles, and critical artifacts. The deterministic script validates that explicit contract; it never infers biological chronology from names, modification time, or directory order.

The steward manages module hierarchy and key role directories/artifacts. It does not index every FASTQ/BAM/VCF shard, watch filesystem events, intercept `mkdir`, or replace task/lifecycle/claim records.

## Project-layout profiles

### Layout v2

Marked by `config/Project_Layout.tsv` with `bioflow.layout.v2` and fixed roots:

```text
config rawdata scripts logs tmp results docs manuscripts
```

It uses `workspace.v2`, stable `Analysis_Key`, `NN-analysis-key` module paths, one retained results entry per analysis, internal `versions/VNN`, and the figure-package contract in `references/project-layout.md`.

### Legacy layout

A project without the layout marker remains on:

```text
config data scripts logs tmp results reports
```

It uses `workspace.v1`. Existing paths remain valid and are never auto-migrated. v1/v2 policy and module schemas cannot be mixed.

## Metadata contracts

All files are true TSV with exact headers.

### `config/Workspace_Policy.tsv`

```text
Schema_Version	Enforcement_Mode	Plan_Status	Plan_SHA256	Max_Audit_Depth	Updated_Time
```

- v2 requires `Schema_Version=workspace.v2`; legacy requires `workspace.v1`.
- `Enforcement_Mode=Hybrid`.
- `Plan_Status=Draft|Reviewed`.
- Reviewed requires the deterministic lowercase SHA-256 of normalized module/route rows.
- Any normalized module/route change after review causes fingerprint drift and blocks managed execution until review/application is repeated.
- audit depth defaults to 3 and cannot exceed 5.

### Layout-v2 `config/Workspace_Modules.tsv`

```text
Module_ID	Analysis_Key	Parent_Module	Stage	Short_Name	Module_Kind	Depends_On	Purpose	Owner	Compatibility	Notes
```

Legacy v1 omits `Analysis_Key` and keeps this exact header:

```text
Module_ID	Parent_Module	Stage	Short_Name	Module_Kind	Depends_On	Purpose	Owner	Compatibility	Notes
```

v2 rules:

- `Module_ID`: stable `M001`, `M002`, ...;
- `Analysis_Key`: stable lowercase letters/digits/hyphens such as `assembly` or `genome-qc`;
- one `Analysis_Key` occurs only once in the project;
- `Short_Name` equals `Analysis_Key` for a managed v2 module;
- `Stage`: consecutive `01..N` among managed siblings;
- module path: `NN-analysis-key`;
- module names cannot contain version/status words such as `V2`, `final`, `new`, `latest`, `best`, `revised`, or `rerun`;
- `Module_Kind`: `group`, `analysis`, `publication`, `management`, or `legacy`;
- `Parent_Module`: `ROOT` or a declared module;
- `Depends_On`: comma-separated Module IDs;
- `Compatibility`: `Managed` or `Legacy`.

The combined parent/dependency graph must be acyclic. Sibling dependencies point to earlier stages. Parallel modules may share a parent without false dependencies.

### `config/Workspace_Routes.tsv`

```text
Route_ID	Module_ID	Path_Type	Path_Role	Relative_Path	Producer_Tasks	Consumer_Tasks	Retention	Required	Compatibility	Purpose	Notes
```

- `Route_ID`: stable `R001`, `R002`, ...;
- `Path_Type`: `Directory` or exact key `Artifact`;
- task IDs refer to the active layout's `Task_Status.tsv` and must exist;
- `Retention`: `Disposable`, `Working`, `Retained`, or `Delivery`;
- `Required`: `Yes|No`;
- `Compatibility`: `Managed`, `Tool_managed`, or `Legacy`;
- globs are forbidden;
- an Artifact is one exact critical path below a managed directory owned by that module.

## Layout-v2 role roots

| Role | Required root |
|---|---|
| `Config`, `Manifest` | `config/` |
| `Input_Link` | `rawdata/` |
| `Script` | `scripts/` |
| `Log` | `logs/` |
| `Temporary` | `tmp/` |
| `Result`, `QC`, `Plot_Data`, `Source_Table`, `Figure` | `results/` |
| `Report`, `Acceptance`, `Delivery` | `docs/` |
| `Manuscript` | `manuscripts/` |

Legacy mapping stays unchanged: `Input_Link -> data/`, and Figure/Report/Acceptance/Delivery -> `reports/`.

Managed routes normally mirror the module path:

```text
scripts/01-assembly
logs/01-assembly
tmp/01-assembly
results/01-assembly
```

An analysis module requires Script, Log, Temporary, and exactly one root Result directory at `results/<module-path>`. A publication module requires Script, Plot_Data, Figure, and exactly one Manuscript route. Its retained data root is `results/<module-path>`, while its manuscript may independently use `manuscripts/P01-short-name`; manuscript numbering never renames analysis results.

A v2 retained version may appear only at:

```text
results/<module-path>/versions/VNN
```

A managed Figure route names one package only:

```text
results/<module-path>/figures/FNNN_Name
```

The package is allowed to be incomplete while its producer is planned/running. Once its producer is complete/validated or the project is delivered, audit requires PDF, PNG, `README.md`, a TSV under `source-data/`, Markdown and JSON under `checks/`, plus the parent `Figure_Index.tsv`.

`tmp/` can use only the Temporary role. Formal outputs, evidence, acceptance, delivery, figures, and manuscripts cannot be routed there.

## Authorities remain separate

Workspace contracts do not replace:

- `config/Directory_Index.tsv`: directories created/adopted;
- `docs/status/Task_Status.tsv` (v2) or `reports/Task_Status.tsv` (legacy): runtime tasks;
- `workflow_status.tsv`: project lifecycle;
- `config/result_manifest.yaml`: evidence-to-claim contract;
- `Version_Index.tsv`: retained run versions;
- `Figure_Index.tsv`: retained figures;
- Delivery Index: final package.

## CLI workflow

Resolve the skill root when called from another project:

```bash
BIOFLOW=/data9/home/qgzeng/projects/3-Biotools_create/bio-workflow
STEWARD="$BIOFLOW/scripts/workspace_steward.py"
```

### Initialize or bootstrap

New/empty v2 project preview:

```bash
bash "$BIOFLOW/scripts/init_project.sh" --project /abs/project --workspace-steward
```

Existing reviewed Git root opting into v2:

```bash
bash "$BIOFLOW/scripts/init_project.sh" --project /abs/project --layout-v2 --workspace-steward
```

After normal disclosure/confirmation, add `--yes`. Existing legacy projects can bootstrap v1 contracts without changing layout:

```bash
python3 "$STEWARD" bootstrap --project /abs/legacy-project
```

Bootstrap does not create analysis modules or overwrite contracts.

### Inspect

```bash
python3 "$STEWARD" inspect --project /abs/project --max-depth 3 --format tsv
```

Inspection is bounded/read-only, never follows symlinks, skips hidden/cache entries, and does not recurse into raw input, logs, or tmp. Observed roles are hints only.

### Plan and route

```bash
python3 "$STEWARD" plan --project /abs/project
python3 "$STEWARD" route --project /abs/project --module M001 --role Log --path-type Directory
```

`plan` checks exact schema/profile matching, IDs, stable Analysis_Key, module tree, consecutive stages, combined DAG, role roots, unique results entry, version/figure/manuscript placement, parent coverage, task links, and collisions. `route` requires exactly one match and never chooses silently.

### Apply

```bash
python3 "$STEWARD" apply --project /abs/project
```

After disclosure/confirmation, add `--yes`. Under a project-local non-following lock, it revalidates, creates only missing Managed Directory routes in depth order, updates `Directory_Index.tsv`, and writes Reviewed policy/fingerprint atomically. On failure it restores prior index/policy bytes and modes and removes only newly created empty directories. It never creates Artifact routes. Existing unindexed Managed paths are refused; missing Legacy/Tool_managed paths are not created.

### Audit and structure audit

```bash
python3 "$BIOFLOW/scripts/project_structure_audit.py" --project /abs/project
python3 "$STEWARD" audit --project /abs/project --format json
```

Structure audit checks v2 fixed roots, one-analysis-one-entry, module names, version indexes/placement, formal tmp references, figure packages, and manuscript names. Workspace audit joins policy, modules/routes, Directory Index, bounded filesystem, tasks, and lifecycle.

Workspace findings remain:

- `WS001`: schema/profile;
- `WS002`: module/Analysis_Key/DAG/order;
- `WS003`: role/root/path;
- `WS004`: review/fingerprint;
- `WS005`: required directory;
- `WS006`: unplanned path;
- `WS007`: legacy;
- `WS008`: tool-managed;
- `WS009`: strong placement evidence;
- `WS010`: required key artifact timing;
- `WS011`: Directory Index;
- `WS012`: task/module/producer/consumer/routing;
- `WS013`: symlink/boundary;
- `WS014`: root clutter;
- `WS015`: completed figure-package completeness.

Exit codes are 0 PASS, 1 WARN, 2 BLOCK/error.

### Execution preflight

```bash
python3 "$STEWARD" preflight \
  --project /abs/project --module M001 --task-id T001 \
  --script-path /abs/project/scripts/01-assembly/job.slurm \
  --log-path '/abs/project/logs/01-assembly/%j_%x.out' \
  --log-path '/abs/project/logs/01-assembly/%j_%x.err' \
  --output-path /abs/project/results/01-assembly \
  --tmp-path /abs/project/tmp/01-assembly
```

Policy must be Reviewed and unchanged. Preflight imports every audit BLOCK, binds the exact registered script/task/module, and validates each explicit path against allowed roles and producers. `prepare_submission.sh` runs the v2 structure gate as well. An output under rawdata/tmp is blocked.

### Migration plan

```bash
python3 "$STEWARD" migration-plan --project /abs/project --max-depth 3 --format tsv
```

It gives only bounded `PLAN_ONLY` suggestions for high-confidence mechanical cases. It does not rename, move, delete, copy, archive, rewrite references, or convert legacy projects.

## Hybrid enforcement and safety

- Steward absent: legacy Bioflow behavior; v2 structure audit still enforces its explicit marker.
- Draft: planning/audit allowed, managed execution blocked.
- Reviewed/fingerprint match: Managed paths strict.
- Legacy: WARN and no automatic migration.
- Tool_managed: layout/name exempt, boundary checks remain.
- Unplanned/unregistered path in Reviewed workspace: BLOCK.

Hard boundaries: explicit narrow roots only; audit depth at most 5 and inventory capped; no symlink traversal for controlled/managed paths; no protected-path exception; no glob routes; no semantic auto-inference; no rename/move/delete/copy/archive/watch/daemon surface; all writes dry-run first and separately confirmed; `--yes` is an executor switch, not authorization; no concurrent writers; no real submission in tests.
