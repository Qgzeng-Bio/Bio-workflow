# Bio-Workflow Skill Handoff

Last updated: 2026-06-18 — SKILL.md slimming with functional-equivalence routing

## Current State

- Source directory: `/data9/home/qgzeng/projects/3-Biotools_create/bio-workflow`
- Installed Codex skill: `/data9/home/qgzeng/.codex/skills/bio-workflow`
- GitHub remote: `Qgzeng-Bio/Bio-workflow`
- Branch state observed last: `main` at `92a4cb3 Drop dead fallback to ~/.claude/skills/bioinformatics-analysis-workflow`
- Current working tree intentionally has local edits:
  - `SKILL.md`: slimmed from 707 to 454 lines and converted into a routing hub.
  - `HANDOFF.md`: compacted from long journal into this current-state handoff and updated for slimming.
  - `references/validation-checklists.md`: added shared closure, CENH3/centromere, and synteny checklists.
  - `references/resource-feedback.md`: new resource sizing and pilot feedback details.
  - `references/executor-safety.md`: new SLURM generation/preflight/submit details.
  - `references/operations-reporting.md`: new download, qp, monitoring, and reporting details.

The installed `.codex` runtime copy should be kept in sync with this source
directory after edits. Do not assume source edits are automatically installed.

## Validation Snapshot

Last validation in this session:

```bash
python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py /data9/home/qgzeng/.codex/skills/bio-workflow
bash -n scripts/*.sh
python3 scripts/validate_program_cards.py
python3 scripts/validate_program_cards.py --check-drafts
diff -qr . /data9/home/qgzeng/.codex/skills/bio-workflow
```

Result:

- Source skill: `Skill is valid!`
- Installed skill: `Skill is valid!`
- Shell syntax for bundled shell scripts: PASS
- Program card validation: PASS (5 active cards, 0 draft cards)
- Source vs installed copy: only source-local development directories should differ:
  `.agents`, `.claude`, `.codex`, `.git`

## Current Installation Model

There are two active locations:

- Source of development: this repository directory.
- Runtime installation: `/data9/home/qgzeng/.codex/skills/bio-workflow`.

The old Claude skill copy was removed:

- Removed directory: `~/.claude/skills/bioinformatics-analysis-workflow/`
- Temporary backup at removal time:
  `/tmp/bioinformatics-analysis-workflow.snap.1781448044`
- The old helper fallback to `~/.claude/skills/bioinformatics-analysis-workflow/scripts`
  was removed from:
  - `scripts/prepare_submission.sh`
  - `scripts/gen_sbatch.sh`
  - `scripts/submit_and_log.sh`

Do not reintroduce the old `~/.claude/skills/bioinformatics-analysis-workflow`
fallback. `bio-workflow` should have one real source directory and one Codex
runtime copy.

## Recent Uncommitted Change Summary

### SKILL.md Slimming

`SKILL.md` was reduced from 707 lines to 454 lines without deleting behavior. The
main file now keeps first-load rules and routing:

- frontmatter trigger description
- mission and startup rules
- server safety, admin2/login-node rule, and protected-path rules
- confirmation gates for `sbatch`, `scancel`, installs, downloads, overwrites,
  protected writes, and high-resource work
- resume/takeover route
- program-level route
- task-routing index
- result claim source-of-truth policy and auto-trigger phrases
- workflow skeleton
- skill maintenance and default response shape
- functional-equivalence guardrails for future slimming

Detailed content moved into directly linked references:

- `references/resource-feedback.md`: CPU/memory sizing, partition choice,
  resource audit, pilot interpretation, and array-concurrency rules.
- `references/executor-safety.md`: `gen_sbatch.sh`, `slurm_preflight.sh`,
  `prepare_submission.sh`, `parallelization_audit.sh`,
  `resource_usage_audit.sh`, `submit_and_log.sh`, and array templates.
- `references/operations-reporting.md`: monitoring/triage details, raw-data
  download safety, qp mode, and plotting/reporting rules.

Functionality is preserved by explicit routing from `SKILL.md`:

- `Reference routing map`
- task routing bullets
- workflow steps 4-12
- functional-equivalence guardrails

Completion evidence collected: source and installed quick validation, `bash -n
scripts/*.sh`, program-card validation, draft-card validation, and `diff -qr`
against the installed Codex copy.

### Shared Validation Checklist

`references/validation-checklists.md` now includes:

- `Core bioinformatics closure checklist`
- `Centromere and CENH3 checklist`
- `Synteny checklist`

Intent: make common acceptance gates reusable by `bio-workflow`,
`centromere-predict`, `cenh3-chipseq`, `centromere-hor-scoring`,
`jcvi-synteny`, and figure/reporting workflows.

### Runtime Sync

The current source versions of these files were copied to the installed Codex
runtime copy:

- `scripts/prepare_submission.sh`
- `scripts/gen_sbatch.sh`
- `scripts/submit_and_log.sh`
- `references/validation-checklists.md`
- `HANDOFF.md`

If `HANDOFF.md` or other files are edited again, repeat the sync before assuming
Codex will use the changes.

## Active Design Decisions

- `SKILL.md` is the only official skill entry point.
- `README.md` is repo documentation; agents should not rely on it as the skill
  execution contract.
- `HANDOFF.md` is a compact current-state handoff, not a full development journal.
  Use git history for detailed old entries.
- Installation, large downloads, `sbatch`, `scancel`, resubmission, and protected
  path writes still require explicit confirmation.
- No heavy compute on `admin2` or login nodes.
- Raw data under `/data9/home/qgzeng/data/` and tools under
  `/data9/home/qgzeng/tools/` remain protected from write-like actions unless the
  user explicitly confirms.
- `#SBATCH --time` remains absent by default for normal/fat/fat2/high unless
  explicitly justified.

## Architecture Milestones

This section replaces the previous 2000-line chronological journal.

- Initial server-adapted skill: qgzeng SLURM defaults, QOS limits, protected paths,
  micromamba policy, input checks, quota checks, and chunked array submission.
- Resume layer: `project_state_audit.sh`, `slurm_failure_triage.sh`, six project
  states, and conservative takeover behavior.
- Execution safety layer: `slurm_preflight.sh`, `prepare_submission.sh`,
  `gen_sbatch.sh`, and `submit_and_log.sh`.
- Resource feedback layer: `resource_usage_audit.sh`, `parallelization_audit.sh`,
  array templates, CPU-forwarding checks, and pilot-based right-sizing.
- Program-card layer: registry, lookup, validator, unknown-program onboarding,
  proposal-only install flow, evidence bundles, and draft cards.
- Domain playbooks: genome survey, assembly, chromosome scaffolding, finishing,
  quality evaluation, SyRI SV/synteny, high-confidence SV, CENH3 centromeres,
  and segmental duplications.
- Evidence-to-Claim layer: `interpretation-rules.tsv`, `project-anchors.yaml`,
  `result-manifest-schema.md`, and `check_result_contract.py`.
- Feedback loop: `log_claim_audit.sh`, `Checker_Status_AtSubmit`, and
  `reports/claim_audit.tsv` for later false-positive/false-negative review.
- Skill cleanup: removed dead Claude global copy, standardized runtime location
  under `.codex/skills`, and synchronized source/runtime validation checklists.

For full historical detail, inspect git commits instead of expanding this file:

```bash
git log --oneline --decorate
git show <commit>:HANDOFF.md
```

## Known Open Design Work

Keep these as design options, not automatic next tasks:

- Shorten `SKILL.md` from 707 lines toward 450-500 lines.
  Suggested split:
  - keep startup, safety, resume route, program route, task-routing index,
    claim policy, workflow skeleton, and response shape in `SKILL.md`;
  - move long SLURM executor details to `references/executor-safety.md`;
  - move resource feedback details to `references/resource-feedback.md`;
  - move download/reporting and qp details to targeted references.
- Add `scripts/test_skill.sh` as the single maintenance entry:
  quick validate, shell syntax, program-card validation, and representative
  dry-run fixtures.
- Add `scripts/sync_install.sh` to copy source files into
  `/data9/home/qgzeng/.codex/skills/bio-workflow` and validate both sides.
- Add `UNCERTAIN` to claim checking when an analysis type has no matching rule
  coverage.
- Add rule dependencies to `interpretation-rules.tsv` only after rule count and
  output noise justify a DAG.
- Unify evidence terminology between program cards and interpretation rules when
  program cards are next revised.

## Important Caveats

- `slurm_preflight.sh` is a static heuristic, not a sandbox. Dynamic shell tricks
  such as variable-wrapped `rm`, `eval`, or nested `bash -c` cannot be fully
  proven safe by static checks.
- `project_state_audit.sh` is a bounded heuristic. Old logs and mixed outputs can
  produce multiple plausible states; the agent must choose the primary state from
  concrete evidence.
- `check_result_contract.py` currently covers the first claim-control rules,
  mostly around quinoa genome evaluation and known silent traps. It should not be
  treated as universal biological interpretation.
- KMERIA-related guidance came from a real failed pilot and is intentionally
  conservative around count-to-matrix format compatibility.

## Minimal Maintenance Commands

Run after editing skill structure:

```bash
python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
python3 scripts/validate_program_cards.py
python3 scripts/validate_program_cards.py --check-drafts
```

Run after editing shell helpers:

```bash
bash -n scripts/*.sh
```

Run after changing the installed copy:

```bash
python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py /data9/home/qgzeng/.codex/skills/bio-workflow
diff -qr . /data9/home/qgzeng/.codex/skills/bio-workflow
```

Expected `diff -qr` noise is limited to source-local development directories:
`.agents`, `.claude`, `.codex`, `.git`.
