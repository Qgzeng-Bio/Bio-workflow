# Project records: status, research logs, and decisions

Use this contract for layout-v2 projects when updating the human status page, recording an analysis or interpretation change, registering a scientific decision, preparing a Pull Request, or auditing whether project records explain what changed and why.

This layer does not replace:

- `docs/status/workflow_status.tsv` — project lifecycle authority;
- `docs/status/Task_Status.tsv` — concurrent task authority;
- `logs/` — scheduler/program output;
- `config/result_manifest.yaml` — claim-support gate;
- Workspace Steward — module/route authority.

## Record roots

```text
PROJECT_STATUS.md
CHANGELOG.md
docs/research-log/
├── README.md
├── TEMPLATE.md
├── Log_Index.tsv
└── YYYYMMDD_Short_Name.md
docs/decisions/
├── Decision_Log.md
└── Decision_Index.tsv
```

## PROJECT_STATUS.md

`PROJECT_STATUS.md` is a concise human landing page, not a second task database.

Required sections:

```text
## Current objective
## Priorities
## Blockers
## Machine-readable status
```

Required values:

- `Current analysis stage`: one lifecycle stage from `Project_intake` through `Delivered`;
- `Current result maturity`: `Exploratory`, `Provisional`, `Verified`, or `Frozen`;
- `Current manuscript stage`: `Not_started`, `Outline`, `Drafting`, `Evidence_review`,
  `Coauthor_review`, `Pre_submission`, `Submitted`, `Revision`, or `Published`;
- `Last_Reviewed`: `UNKNOWN` or `YYYY-MM-DD`;
- links to the two machine-authority TSV files.

A `Verified`/`Frozen` maturity with an `UNKNOWN` baseline is a review warning.

## Research logs

One Markdown file records one important analysis or interpretation change:

```text
docs/research-log/YYYYMMDD_Short_Name.md
```

Stable metadata fields:

```text
Research_Log_ID: R001
Date: YYYY-MM-DD
Analysis_Key: assembly
Module_ID: M001 or NA
Task_ID: T001 or NA
Result_Maturity: Exploratory|Provisional|Verified|Frozen
```

Required sections:

```text
## Scientific question
## Inputs and versions
## Exact commands and parameters
## Outputs
## Checks
## Observations
## Interpretation
## Limitations
## Impact
## Next action
```

Rules:

- IDs are stable and unique (`R001`, `R002`, ...); never reuse or renumber.
- Filename date and `Date` must match.
- Markdown records must be direct children of `docs/research-log/`; subdirectories are blocked so no dated record can escape indexing.
- Commands are pasted exactly or bound to an exact submitted-script snapshot; do not reconstruct from memory.
- Scheduler-generated diagnostics stay in `logs/`; this record explains scientific intent and evidence.
- `Outputs` must not cite disposable `tmp/` paths.
- `Verified`/`Frozen` records cannot contain `UNKNOWN` placeholders and must name at least one formal output path.
- `Impact` should identify affected claims and/or figures/tables whenever known.
- Draft alternatives and preliminary explorations remain clearly `Exploratory`.

### Log_Index.tsv

Exact header:

```text
Research_Log_ID	Date	Filename	Analysis_Key	Module_ID	Task_ID	Result_Maturity	Record_Status	Title	Notes
```

- `Record_Status`: `Draft`, `Complete`, or `Superseded`;
- every Markdown research log must have exactly one index row;
- an indexed log must exist;
- indexed date, filename, analysis key, module, task, and maturity must match the Markdown metadata;
- filenames are unique.

## Decision records

`docs/decisions/Decision_Index.tsv` is the authority for decisions that change scientific design, inputs, parameters, result selection, interpretation, figures, or manuscript scope.

Exact header:

```text
Decision_ID	Date	Decision	Evidence_Path	Affected_Modules	Affected_Claims	Status	Decided_By	Notes
```

Rules:

- `Decision_ID`: stable `D001`, `D002`, ...;
- `Date`: `YYYY-MM-DD`;
- `Decision`: one clear, human-readable decision;
- `Evidence_Path`: readable project-local file or directory for accepted decisions; `NA` is allowed only while a decision remains `Proposed`, and `Superseded`/`Reversed` rows must cite the evidence that changed them;
- `Affected_Modules` / `Affected_Claims`: comma-separated stable IDs or `NA`;
- `Status`: `Proposed`, `Accepted`, `Superseded`, or `Reversed`;
- `Decided_By`: responsible user/team;
- never reuse a decision ID; supersede with a new ID and reference the old one in Notes;
- accepted evidence cannot resolve to disposable `tmp/` or outside the project.

`Decision_Log.md` may provide longer narrative background, but must not maintain a conflicting second decision table.

## CHANGELOG.md

Record compact, human-readable milestones: important scientific changes, selected result versions, manuscript freezes, and release boundaries. Git commits remain the detailed change history. Do not turn CHANGELOG into a scheduler log or a duplicate task database.

## Read-only audit

Run:

```bash
python3 scripts/project_records_audit.py --project /abs/project
python3 scripts/project_records_audit.py --project /abs/project --format json
```

Exit codes follow the Bioflow convention:

- `0`: PASS;
- `1`: WARN requires review/explanation;
- `2`: BLOCK or usage/error.

The audit is bounded and read-only. It never edits records, creates indexes, submits jobs, or runs Git commands.

Stable findings include:

| Rule | Meaning |
|---|---|
| `REC_STATUS_*` | status-page schema, values, baseline, or authority-link issues |
| `REC_LOG_NAME` | invalid research-log filename |
| `REC_LOG_META` / `REC_LOG_DATE` | missing/invalid metadata or date mismatch |
| `REC_LOG_SECTION` | missing required narrative section |
| `REC_LOG_MATURITY` | invalid maturity value |
| `REC_LOG_FORMAL` | Verified/Frozen record remains incomplete |
| `REC_LOG_TMP` | Outputs section cites `tmp/` |
| `REC_LOG_INDEX` | missing/duplicate/mismatched Log_Index row |
| `REC_DECISION_INDEX` | malformed decision index |
| `REC_DECISION_ROW` | invalid decision row |
| `REC_DECISION_EVIDENCE` | accepted decision lacks readable non-tmp evidence |
| `REC_CHANGELOG` | missing or unreadable changelog |

Legacy projects are not forcibly enrolled; the audit reports `REC_LEGACY` and leaves their established records unchanged.

## Update workflow

After completing an important analysis or interpretation change:

1. Create or update one research-log Markdown record from `TEMPLATE.md`.
2. Update `Log_Index.tsv`.
3. Record any design/input/parameter/result-selection choice in `Decision_Index.tsv`.
4. Refresh `PROJECT_STATUS.md` and, when appropriate, `CHANGELOG.md`.
5. Run `scripts/project_records_audit.py --project <project>`.
6. Resolve every BLOCK and explain every WARN before acceptance, PR review, or manuscript freeze.

These updates are persistent project writes. The Agent must disclose affected paths and obtain normal confirmation before writing them.
