# Project lifecycle and startup contract

Use this contract to start, resume, manage, validate, interpret, and deliver a
bioinformatics project. It is the single source of truth for project stages;
task-specific playbooks add domain checks but must not redefine these stages.

## Contents

- [Evidence rules](#evidence-rules)
- [Lifecycle](#lifecycle)
- [Startup planning contract](#startup-planning-contract)
- [Project management artifacts](#project-management-artifacts)
- [Status table](#status-table)

## Evidence rules

- Assign one primary stage from current, readable project-local evidence.
- Treat status files as pointers, not proof. Verify their `Evidence_Path`.
- Prefer the newest terminal evidence when logs conflict, but report a strategy
  switch, abandoned route, or unresolved secondary state explicitly.
- Do not advance a stage because a directory exists or a command exited zero.
- Do not infer missing biological design, reference versions, sample identities,
  or acceptance thresholds.
- Keep the default audit read-only and bounded to the active layout. Layout v2 uses
  `config/`, `rawdata/`, `scripts/`, `logs/`, `tmp/`, `results/`, `docs/`, and
  `manuscripts/`; unmarked legacy projects keep `data/` and `reports/`.
- In layout v2, do not accept a formal output, evidence path, figure, claim,
  acceptance, delivery, or manuscript record that depends on `tmp/`.
- When `config/Workspace_Policy.tsv` exists, read
  `references/workspace-steward.md`: a Draft/drifted workspace is planning
  evidence, not permission to generate or submit managed work.

## Lifecycle

The normal path is:

```text
Project_intake -> Input_ready -> Plan_ready -> Script_ready
               -> Queued_or_running -> Complete_unvalidated
               -> Analysis_ready -> Delivered
```

`Failed` is an exception state reachable from setup or execution. After triage,
return to the earliest stage whose evidence remains valid; do not automatically
restart from `Project_intake`.

### Project_intake

**Decision evidence:** A project directory or stated idea exists, but its research
question, scope, comparison, or explicit inputs are missing or ambiguous; no
trustworthy later-stage evidence supersedes it.

**Required inputs:** Research question and purpose; organism/material, comparison
unit, deliverables, constraints; exact inputs or a bounded discovery plan.

**Allowed:** Read project-local metadata, identify missing decisions, draft an
intake, and offer method alternatives with their consequences.

**Forbidden:** Do not invent design, reference identity, groups, replicates, or
claims. Do not install tools, write analysis scripts, or submit work as if scope
were fixed.

**Minimum next action:** Complete the startup contract through the input section.

**Transition gate:** Advance to `Input_ready` only when inputs, sample roles,
reference/version, and relevant format or coordinate assumptions are explicit.

### Input_ready

**Decision evidence:** A manifest identifies intended inputs, sample roles,
reference/version, file types, and compatibility assumptions, but the executable
analysis plan is incomplete.

**Required inputs:** Validated manifest, design, reference/version, input format
notes, research question, and expected deliverables.

**Allowed:** Run lightweight input checks, compare methods, estimate resource
drivers, and draft outputs, acceptance criteria, risks, and checkpoints.

**Forbidden:** Do not treat a file listing as a validated manifest, submit jobs,
or silently choose a method that changes the scientific aim.

**Minimum next action:** Complete and review the startup planning contract.

**Transition gate:** Advance to `Plan_ready` only when methods, parameters,
outputs, resources, acceptance, dependencies, risks, and open decisions are
recorded.

### Plan_ready

**Decision evidence:** A project-local plan covers every required startup field,
cites the input manifest, and has no unresolved blocking design choice; no runnable
script has yet reached execution preparation.

**Required inputs:** Reviewed plan and manifest; tool/environment route, resource
model, output paths, and acceptance gates. In a steward-enabled project, the
module DAG and canonical role routes must validate before script generation.

**Allowed:** Generate scripts/configuration and run syntax, environment, and input
prechecks without changing the agreed scientific design.

**Forbidden:** Do not hide changed biological parameters in scripts or submit
before formal preflight and user confirmation.

**Minimum next action:** Generate the smallest runnable workflow linked to the plan.

**Transition gate:** Advance to `Script_ready` when runnable scripts/configs exist,
inputs and outputs are known, and formal pre-submit review is next. A managed
workspace must be `Reviewed`, match its SHA256, and have had every script/log/tmp/
output location resolved from the declared module routes.

### Script_ready

**Decision evidence:** Runnable `.slurm`, `.sbatch`, or workflow scripts exist and
no newer active, failed, or completed run supersedes them.

**Required inputs:** Reviewed plan, script, manifest/input list, output target,
environment, and justified CPU/memory/partition/concurrency.

**Allowed:** Run `prepare_submission.sh` or fallback `slurm_preflight.sh`; correct
preflight failures without changing agreed analysis parameters. For an enabled
workspace, pass project/module/task and explicit output/tmp context so Workspace
preflight is part of the GO/NO-GO package.

**Forbidden:** Do not run `sbatch` without a passing gate and explicit user
confirmation, silently add short walltime, or overwrite existing results.

**Minimum next action:** Resolve every `FAIL`, explain every `WARN`, then request
submit confirmation.

**Transition gate:** Advance to `Queued_or_running` only with a concrete job ID or
equivalent active workflow evidence.

### Queued_or_running

**Decision evidence:** Queue/accounting reports an active job, or the newest
run/status evidence records a job start without a terminal marker.

**Required inputs:** Job ID, submitted script snapshot, resources, logs, and
expected outputs.

**Allowed:** Monitor `squeue`, `sacct`, and bounded log tails.

**Forbidden:** Do not alter the active reproducibility record, call partial output
complete, or cancel/change concurrency/resubmit without confirmation.

**Minimum next action:** Wait for terminal evidence, then route to `Failed` or
`Complete_unvalidated`.

**Transition gate:** Advance only after terminal scheduler/program state and output
integrity are known.

### Failed

**Decision evidence:** Scheduler, logs, or output integrity show terminal failure,
non-zero exit, truncation, missing required output, or blocking incompatibility.

**Required inputs:** Relevant logs, accounting, submitted script/config, inputs,
and partial-output state.

**Allowed:** Classify the failure, inspect resource evidence, and propose the
smallest fix.

**Forbidden:** Do not increase resources by habit, delete partial output, or
resubmit without reading evidence and obtaining confirmation.

**Minimum next action:** Run `slurm_failure_triage.sh` where applicable and identify
the earliest valid recovery stage.

**Transition gate:** Leave `Failed` only when cause, affected artifacts, fix, rerun
boundary, and required authorization are explicit.

### Complete_unvalidated

**Decision evidence:** Planned jobs/programs ended normally and expected outputs
exist, but run/data/analysis acceptance is incomplete.

**Required inputs:** Completion logs, expected-output list, result files, versions,
and acceptance criteria from the plan.

**Allowed:** Run format, count, completeness, compatibility, and workflow-specific
checks.

**Forbidden:** Do not interpret biology, create publication claims, or treat exit
code zero as acceptance.

**Minimum next action:** Complete the relevant layered acceptance checklist.

**Transition gate:** Advance to `Analysis_ready` only when run, data, analysis, and
reproducibility checks pass or accepted limitations are explicit.

### Analysis_ready

**Decision evidence:** Results passed technical acceptance and the next work is
interpretation, plotting, reporting, or justified downstream analysis.

**Required inputs:** Validated outputs, acceptance report, methods/parameters, and
a result manifest when evidence-to-claim rules apply.

**Allowed:** Interpret and visualize evidence while distinguishing Observation,
Interpretation, Hypothesis, and Limitation.

**Forbidden:** Do not overstate associations, omit caveats, mix coordinate/reference
versions, or use unversioned intermediates for final claims.

**Minimum next action:** Produce claim-linked results and assemble delivery artifacts.

**Transition gate:** Advance to `Delivered` only when outputs, methods, provenance,
limitations, and a reproducible entry point are packaged and checked.

### Delivered

**Decision evidence:** A delivery index resolves to final outputs, validation,
methods, versions, limitations, and the reproducibility entry point. Applicable
publication- or decision-grade claims passed their result contract.

**Required inputs:** Final output index, acceptance report, methods summary,
software/parameter record, known limitations, and rerun entry command/script.

**Allowed:** Archive or hand off the reviewed package and open a separately scoped
follow-up.

**Forbidden:** Do not call an undocumented output directory a delivery or silently
replace a delivered artifact.

**Minimum next action:** Preserve the snapshot; start later work as a new version or
explicit downstream stage.

**Transition gate:** Terminal for the agreed scope. Reopen only when scope, version,
and reason for change are recorded.

## Startup planning contract

Use existing project conventions; otherwise prefer `config/Analysis_Plan.yaml` or
`docs/Analysis_Plan.md` in layout v2 (`reports/Analysis_Plan.md` in legacy).
Keep `Plan_Status: Draft` until the user or project
owner accepts it, then set `Plan_Status: Reviewed`. A plan is `Plan_ready` only
when reviewed and when it records:

1. **Question:** scientific question, purpose, analysis unit, comparison, and claim
   boundary.
2. **Design:** organism/material, groups, replicates, covariates, batch structure,
   exclusions, and expected sample count.
3. **Inputs:** manifest, exact paths/link policy, types, sample naming,
   reference/version, coordinates, and lightweight integrity status.
4. **Methods:** stages, candidate tools, selected route and rationale,
   environment/container, and critical parameters with evidence.
5. **Outputs:** expected intermediate/final artifacts, locations, and downstream
   consumers.
6. **Acceptance:** run, data, analysis, reproducibility, and biological gates plus
   failure/stop conditions; do not invent unsupported thresholds.
7. **Resources:** scale evidence, CPU, memory, partition, concurrency, disk/temp
   growth, pilot need, and runtime uncertainty.
8. **Risks and dependencies:** missing tools/data, overwrite/protected-path risks,
   coordinate/reference incompatibility, decisions, and fallback.
9. **Execution:** ordered stages, checkpoints, dependencies, rerun boundary, and
   actions needing user confirmation.
10. **Open decisions:** owner, required decision, blocking status, and evidence
    needed to resolve it.

Mark unknowns `UNKNOWN`, explain why they matter, and keep the project at the
earliest stage blocked by each unknown. Do not pad unknown fields with guesses.

## Project management artifacts

Read `references/project-layout.md` for the authoritative directory boundaries,
naming rules, identifier/version policy, examples, and compatibility guidance.

Layout v2 uses:

- `config/`: manifests, sample/reference metadata, parameters, environment references,
  result manifest, and machine-readable workspace contracts;
- `rawdata/`: immutable original inputs or read-only links only; no analysis writes;
- `scripts/`: numbered scientific modules and executable workflow sources;
- `logs/`: complete program and scheduler logs with Job IDs;
- `tmp/`: reproducible disposable intermediates only, never formal evidence;
- `results/`: retained scientific outputs, with one stable entry per Analysis_Key,
  internal `versions/VNN`, summary tables, and figure packages;
- `docs/`: plan, status, research/decision logs, acceptance, methods, interpretation,
  handoff, and delivery index; `references/project-records.md` defines the status page,
  dated research logs, Log_Index, Decision_Index, and changelog contract;
- `manuscripts/`: one stable directory per paper, claim mapping, supplement, and
  frozen submission releases.

Legacy projects retain `data/` and `reports/`; they are not automatically moved.

When explicitly enabled, `Workspace_Policy.tsv`, `Workspace_Modules.tsv`, and
`Workspace_Routes.tsv` add static module/dependency/path contracts. They do not
replace runtime status, claims, or delivery records. Use
`scripts/workspace_steward.py inspect` at intake/takeover, `plan/apply` before
managed scripts, and `audit` before acceptance/delivery.

The minimal reproducibility chain is:

```text
Question -> Input manifest -> Plan -> Script/config snapshot -> Task/run record
         -> Output index -> Research/decision record -> Acceptance evidence
         -> Claim/report -> Delivery index
```

Use `docs/status/workflow_status.tsv` for one project-wide lifecycle state and
`docs/status/Task_Status.tsv` for concurrent stages, samples, pilots, jobs, and
validation tasks in v2; use the existing `reports/` paths in legacy projects.
Read `references/task-monitoring.md` for the task schema and
read-only dashboard; do not force a mixed project into one task state. Run
`scripts/project_records_audit.py` before acceptance, PR review, or manuscript
freeze so research/decision records and the human status page remain internally
consistent.

Prefer Markdown, YAML, and tab-separated TSV. Do not add a database or workflow
framework solely to track these artifacts.

## Project status table

Write the active layout's `workflow_status.tsv` only after user confirmation. The
audit helper prints a suggested row but never writes it.

Required tab-separated columns:

```text
Stage\tStatus\tEvidence_Path\tJob_ID\tExit_Code\tInput_Path\tOutput_Path\tNext_Action\tUpdated_Time
```

- `Stage`: `Project_intake`, `Input_ready`, `Plan_ready`, `Script_ready`,
  `Queued_or_running`, `Failed`, `Complete_unvalidated`, `Analysis_ready`, or
  `Delivered`.
- `Status`: for example `Needs_intake`, `Needs_planning`, `Needs_scripting`,
  `Needs_preflight`, `Running`, `Needs_triage`, `Needs_validation`, `Validated`,
  or `Delivered`.
- `Evidence_Path`: strongest readable evidence, not the status row itself when a
  more direct artifact exists.
- `Job_ID`, `Exit_Code`, `Input_Path`, and `Output_Path`: concrete values or `NA`.
- `Next_Action`: concise and tab-free.
- `Updated_Time`: ISO-like local time, for example `2026-07-11T18:30:00+0800`.
