# Bio-Workflow Skill Handoff

Last updated: 2026-06-20 - conda-activation PATH-guard lint added to the SLURM toolchain

## Latest Update - 2026-06-20: Conda Activation PATH-Guard Lint

Purpose: record a focused safety addition to the SLURM toolchain after a real
failure — a panTE/HiTE pilot crashed in ~25s because `conda activate` left a
polluted PATH (an env-exporting parent + `sbatch --export=ALL`), so `python`
resolved to the wrong env and `import pysam` failed even though the env had it.

What changed (committed as `15b88c0` on `main`):

- `scripts/slurm_preflight.sh`: new `check_conda_activation`. WARNs when a
  `conda activate` lacks a PATH guard (`export PATH="$CONDA_PREFIX/bin:$PATH"`)
  or a python landing/import self-check. Detection is scoped to the region after
  the LAST activation, so an earlier env's guard cannot mask a later unguarded
  one. Pure WARN, not FAIL (avoids flagging CLI-only / absolute-path / `conda
  run` activations); waivable with a `# ALLOW_NO_PATH_GUARD` comment.
- `scripts/gen_sbatch.sh`: new `--conda-env ENV` / `--conda-check M1,M2` to emit
  a compliant hardened activation block (the lint rule's golden reference).
- Docs: `references/executor-safety.md` (new "Conda environment activation"
  section), `references/validation-checklists.md` (one pre-submit item),
  `SKILL.md` (reference routing + step-6 note).
- `scripts/sync_install.sh` and `scripts/sync_plugin_wrapper.sh` are now tracked
  so the documented runtime/plugin sync steps resolve in a clean checkout.

Review and validation:

- codex review (`codex review --commit`) returned 0 P0/P1, 2 P2. P2-1
  (multi-activate false PASS) was fixed by scoping to the last activation and
  re-verified with codex's own counterexample; P2-2 (untracked sync helper) was
  resolved by tracking the two sync scripts in this commit.
- Regression: 8 lint samples + the multi-activate counterexample + generator
  self-consistency all pass; the real pilot script PASSes.
- Synced to all three trees (repo root, `~/.codex/skills/bio-workflow`,
  `plugins/bio-workflow/skills/bio-workflow`) and verified byte-identical.
- A second codex review (on 15b88c0, after a re-login) found two more P2 in the
  lint itself: P2-A (the after-last-activation scoping still missed an earlier
  activation that runs python before a later guarded one) and P2-B (a guard
  written after the first python in the same block). Fixed in `a853e96` by
  replacing the whole-tail existence checks with a per-activation, order-sensitive
  state machine (within each activate block, a PATH-resolved python before the
  guard => BAD; worst block wins). Re-verified with codex's own counterexamples
  plus the prior samples; pilot still PASSes; re-synced byte-identical. The two
  sync-script findings it also raised (P2-C clean-checkout default path, P3
  `--skip-validate` vs PyYAML) are deferred to the beta-marketplace wrap-up.

Still uncommitted after `15b88c0`: `HANDOFF.md`, `README.md`, `.agents/`,
`.claude-plugin/`, `plugins/` (the pre-existing beta-marketplace changes and
generated mirrors below).

## Latest Update - 2026-06-19: Handoff Refreshed After Beta Marketplace Validation

Purpose: record the current handoff state after adding and validating the
repo-local Codex and Claude Code beta marketplaces.

Current state:

- The repo now has plugin wrappers for both Codex and Claude Code under
  `plugins/bio-workflow/`.
- The repo now has internal beta marketplace manifests for both tools:
  `.agents/plugins/marketplace.json` and `.claude-plugin/marketplace.json`.
- Both marketplaces use the same marketplace name: `qgzeng-bio-beta`.
- Temporary HOME install tests confirmed that both tools can install
  `bio-workflow@qgzeng-bio-beta` from this checkout.
- Nothing has been published to a public marketplace.
- No real user Codex or Claude configuration was modified by the install tests;
  temporary test homes under `/tmp` were used.
- The current working tree is still uncommitted. Intended changes include
  `README.md`, `HANDOFF.md`, `.agents/`, `.claude-plugin/`, and `plugins/`.
  (`SKILL.md`, `scripts/sync_install.sh`, and `scripts/sync_plugin_wrapper.sh`
  were committed on 2026-06-20 as part of `15b88c0`; see the latest update above.)

Commands/tests already run in this marketplace pass:

```bash
/data9/home/qgzeng/anaconda3/bin/python -m json.tool .agents/plugins/marketplace.json
/data9/home/qgzeng/anaconda3/bin/python -m json.tool .claude-plugin/marketplace.json
/data9/home/qgzeng/anaconda3/bin/python /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
/data9/home/qgzeng/anaconda3/bin/python /data9/home/qgzeng/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/bio-workflow
claude plugin validate plugins/bio-workflow
claude plugin validate .
env HOME=/tmp/bwf_codex_home codex plugin marketplace add /data9/home/qgzeng/projects/3-Biotools_create/bio-workflow --json
env HOME=/tmp/bwf_codex_home codex plugin add bio-workflow@qgzeng-bio-beta --json
env HOME=/tmp/bwf_claude_home claude plugin marketplace add /data9/home/qgzeng/projects/3-Biotools_create/bio-workflow
env HOME=/tmp/bwf_claude_home claude plugin install bio-workflow@qgzeng-bio-beta --scope user
scripts/sync_plugin_wrapper.sh
git diff --check
```

Next steps:

- Review the uncommitted changes.
- Commit and push to the branch or tag intended for trusted beta testers.
- Give testers the README `Internal beta marketplace` commands.
- Keep beta testing to read-only checks, dry-runs, script review, and explicit
  confirmation before any `sbatch`, install, download, or overwrite action.

## Latest Update - 2026-06-19: Internal Beta Marketplaces Added

Purpose: let trusted testers install the existing `bio-workflow` plugin wrapper
through repo-local Codex and Claude Code marketplaces without publishing to a
public marketplace.

Key changes:

- `.agents/plugins/marketplace.json`: added a Codex repo/team marketplace named
  `qgzeng-bio-beta`. It exposes `bio-workflow` from `./plugins/bio-workflow`
  with `AVAILABLE` installation policy and `ON_INSTALL` authentication policy.
- `.claude-plugin/marketplace.json`: added a Claude Code marketplace named
  `qgzeng-bio-beta`. It exposes the same `bio-workflow` wrapper through a
  relative `./plugins/bio-workflow` source.
- `README.md`: added an `Internal beta marketplace` section with local clone,
  marketplace add, and plugin install commands for Codex and Claude Code.

Commands/tests run:

```bash
codex plugin marketplace add --help
claude plugin marketplace add --help
/data9/home/qgzeng/anaconda3/bin/python -m json.tool .agents/plugins/marketplace.json
/data9/home/qgzeng/anaconda3/bin/python -m json.tool .claude-plugin/marketplace.json
/data9/home/qgzeng/anaconda3/bin/python /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
/data9/home/qgzeng/anaconda3/bin/python /data9/home/qgzeng/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/bio-workflow
claude plugin validate plugins/bio-workflow
claude plugin validate .
git diff --check
env HOME=/tmp/bwf_codex_home codex plugin marketplace add /data9/home/qgzeng/projects/3-Biotools_create/bio-workflow --json
env HOME=/tmp/bwf_claude_home claude plugin marketplace add /data9/home/qgzeng/projects/3-Biotools_create/bio-workflow
env HOME=/tmp/bwf_codex_home codex plugin add bio-workflow@qgzeng-bio-beta --json
env HOME=/tmp/bwf_claude_home claude plugin install bio-workflow@qgzeng-bio-beta --scope user
env HOME=/tmp/bwf_codex_home codex plugin list
env HOME=/tmp/bwf_claude_home claude plugin list
scripts/sync_plugin_wrapper.sh
```

Current conclusion:

- The marketplace entry points are repo-local and do not publish anything.
- The intended tester flow is to clone a reviewed branch/tag, add the checkout as
  a marketplace, then install `bio-workflow@qgzeng-bio-beta`.
- JSON syntax validation passed for both marketplace manifests.
- Source skill validation passed.
- Codex plugin validation passed.
- Claude plugin validation passed.
- Claude marketplace validation passed for the repo root.
- A temporary Codex HOME under `/tmp` successfully added the repo marketplace and
  installed `bio-workflow@qgzeng-bio-beta`.
- A temporary Claude HOME under `/tmp` successfully added the repo marketplace
  and installed `bio-workflow@qgzeng-bio-beta`.
- `scripts/sync_plugin_wrapper.sh` dry-run after the marketplace changes showed
  no plugin-wrapper content drift.

Caveats:

- Testers need repository access if the beta branch/repo is private.
- The plugin remains qgzeng `/data9` SLURM environment specific and should start
  with read-only checks and dry-runs during beta.
- The temporary install tests wrote only under `/tmp/bwf_codex_home` and
  `/tmp/bwf_claude_home`, not the real user config.

Next steps:

- After review, commit and push the marketplace manifests to the branch/tag that
  trusted testers will clone.

## Latest Update - 2026-06-19: Codex and Claude Plugin Wrappers Added

Purpose: add repo-local Codex and Claude Code plugin wrappers for
`bio-workflow` while keeping the raw skill source as the primary, cross-agent
installation path.

Key changes:

- `plugins/bio-workflow/.codex-plugin/plugin.json`: added a validation-ready
  Codex plugin manifest named `bio-workflow`. The metadata explicitly identifies
  the plugin as a qgzeng `/data9` SLURM bioinformatics workflow wrapper, not a
  generic bioinformatics toolkit.
- `plugins/bio-workflow/.claude-plugin/plugin.json`: added a Claude Code plugin
  manifest named `bio-workflow`, using the same plugin root and the same
  `skills/bio-workflow/` skill copy. This keeps the plugin skill namespaced as
  `/bio-workflow:bio-workflow` in Claude Code.
- `plugins/bio-workflow/skills/bio-workflow/`: added a synchronized skill copy
  containing `SKILL.md`, `agents/`, `assets/`, `references/`, and `scripts/`.
  This is generated content for plugin distribution; the root raw skill remains
  the source of truth.
- `scripts/sync_plugin_wrapper.sh`: added a guarded sync helper. It defaults to
  dry-run, writes only with `--yes`, validates the source skill plus Codex and
  Claude plugin manifests, and excludes `.git`, `.claude`, `.codex`, `.agents`,
  `tmp`, `__pycache__`, and `*.pyc`.
- `scripts/sync_plugin_wrapper.sh`: finalized the rsync exclusion rules after
  dry-run review so source-local directories are excluded explicitly before
  include rules are applied, preventing `.git`, `.claude`, `.codex`, `.agents`,
  `tmp`, `__pycache__`, or `*.pyc` from entering the plugin skill copy.
- `README.md`: added a `Plugin wrapper install` section. It keeps raw skill
  symlink installation as the recommended daily-use path, documents the optional
  plugin wrapper, shows Codex and Claude validation commands, documents local
  Claude testing with `claude --plugin-dir plugins/bio-workflow`, and notes that
  marketplace files are not written automatically.

Commands/tests run:

```bash
chmod +x scripts/sync_plugin_wrapper.sh
bash -n scripts/sync_plugin_wrapper.sh
scripts/sync_plugin_wrapper.sh
scripts/sync_plugin_wrapper.sh --yes
bash -n scripts/sync_plugin_wrapper.sh
scripts/sync_plugin_wrapper.sh
scripts/sync_plugin_wrapper.sh --yes
bash -n scripts/*.sh
/data9/home/qgzeng/anaconda3/bin/python /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
/data9/home/qgzeng/anaconda3/bin/python /data9/home/qgzeng/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/bio-workflow
claude plugin validate plugins/bio-workflow
scripts/sync_plugin_wrapper.sh
git diff --check
find plugins/bio-workflow -maxdepth 4 -type f
git status --short
```

Current conclusion:

- Source skill validation passed.
- Codex plugin validation passed for `plugins/bio-workflow`.
- Claude plugin validation passed for `plugins/bio-workflow`.
- `scripts/sync_plugin_wrapper.sh` dry-run after the write showed no remaining
  plugin-wrapper content drift after the final exclusion-rule update.
- Shell syntax checks passed for root `scripts/*.sh`.
- `git diff --check` passed.
- No SLURM jobs were submitted, cancelled, or modified.

Caveats:

- No user-level or repo-level Codex or Claude marketplace file was created or
  modified. The wrapper is validation-ready, but not marketplace-published.
- The plugin wrapper intentionally duplicates the raw skill into
  `plugins/bio-workflow/skills/bio-workflow/`; refresh it with
  `scripts/sync_plugin_wrapper.sh --yes` after source changes.
- Existing uncommitted edits from the prior startup/sync pass remain in the same
  working tree (`SKILL.md`, `README.md`, `HANDOFF.md`, and `scripts/sync_install.sh`).
- The current shell's default `python3` lacks `yaml`; validation used
  `/data9/home/qgzeng/anaconda3/bin/python`.

Next steps:

- Review and commit the intended changes together.
- If marketplace publication is desired later, add a separate, reviewed
  marketplace entry that points at `./plugins/bio-workflow`; do not silently
  write `~/.agents/plugins/marketplace.json`.
- If marketplace publication is desired for Claude Code later, add a separate,
  reviewed marketplace/setup path; current testing is via
  `claude --plugin-dir plugins/bio-workflow`.

## Latest Update - 2026-06-19: Codex/Claude Startup Split and Codex Sync Helper

Purpose: adapt the `bio-workflow` skill so Codex and Claude Code load their
own project-context files, and add a guarded helper for keeping the Codex
runtime skill copy synchronized with this source directory.

Key changes:

- `SKILL.md`: startup now branches by active agent surface. Codex reads
  `/data9/home/qgzeng/.codex/memories/user_output_format_preferences.md`,
  `/data9/home/qgzeng/.codex/memories/slurm_preferences.md`, and the nearest
  `AGENTS.md`; Claude Code reads the nearest `CLAUDE.md`.
- `SKILL.md`: permission/project-rule language now names the active agent's
  rule file explicitly: `AGENTS.md` for Codex and `CLAUDE.md` for Claude Code.
- `scripts/sync_install.sh`: new guarded source-to-Codex-runtime sync helper.
  It defaults to dry-run, validates with `quick_validate.py`, writes only with
  `--yes`, excludes source-local directories, and restricts the target to
  `/data9/home/qgzeng/.codex/skills/*`.
- `README.md`: maintenance commands now include `scripts/sync_install.sh` dry-run
  and `scripts/sync_install.sh --yes`.

Commands/tests run:

```bash
chmod +x scripts/sync_install.sh
bash -n scripts/sync_install.sh
bash -n scripts/*.sh
/data9/home/qgzeng/anaconda3/bin/python /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
scripts/sync_install.sh
scripts/sync_install.sh --yes
/data9/home/qgzeng/anaconda3/bin/python /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py /data9/home/qgzeng/.codex/skills/bio-workflow
/data9/home/qgzeng/anaconda3/bin/python /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py /data9/home/qgzeng/.claude/skills/bio-workflow
diff -qr --exclude=.git --exclude=.claude --exclude=.codex --exclude=.agents --exclude=tmp --exclude=__pycache__ . /data9/home/qgzeng/.codex/skills/bio-workflow
git status --short
```

Current conclusion:

- Source skill validation passed.
- Installed Codex runtime skill validation passed.
- Claude Code skill path validation passed through the existing
  `~/.claude/skills/bio-workflow` symlink.
- `scripts/sync_install.sh --yes` synchronized the source tree to
  `/data9/home/qgzeng/.codex/skills/bio-workflow`; a subsequent dry-run showed
  no remaining content changes to sync at that time. This handoff refresh was
  included in a follow-up runtime sync before closing the turn.
- No SLURM jobs were submitted, cancelled, or modified.

Caveats:

- The current shell's default `python3` lacks `yaml`; validation used
  `/data9/home/qgzeng/anaconda3/bin/python`.
- The working tree still has uncommitted source edits: `README.md`, `SKILL.md`,
  and new `scripts/sync_install.sh`, plus this handoff update.

Next steps:

- Review and commit the intended changes when ready.
- Run `scripts/sync_install.sh` before future final handoff checks; add `--yes`
  when the Codex runtime copy should be updated.
- Keep Claude Code using the symlinked source skill unless a separate packaged
  Claude distribution is intentionally needed.

## Latest Update - 2026-06-19: Commit and Push Completed

Purpose: record the repository state after committing and pushing the current
bio-workflow maintenance pass.

Repository state:

- Branch: `main`
- Remote: `origin` (`git@github.com:Qgzeng-Bio/Bio-workflow.git`)
- Local and remote are synchronized at
  `edc9c00 Harden bio-workflow helpers and playbooks`.
- Working tree was clean immediately after push; this handoff refresh is the
  only follow-up local edit from the current turn.

Pushed commits:

- `01ce86d Slim bio-workflow skill routing`
- `edc9c00 Harden bio-workflow helpers and playbooks`

Validation before `edc9c00`:

- `bash -n` passed for bundled shell scripts and SLURM templates.
- Python `py_compile` passed for changed/helper Python scripts.
- Program-card validation passed for 5 active cards and 0 draft cards.
- Source and installed runtime skill validation passed with the base Conda
  Python that provides `yaml`.
- `git diff --cached --check` passed before commit.

Caveats:

- No SLURM job was submitted, cancelled, or modified.
- No live analysis project was changed.
- No force push was used.
- This handoff edit itself has not been committed or pushed yet.

Next steps:

- If this handoff refresh should also be tracked remotely, commit and push a
  small follow-up documentation-only commit.
- Otherwise, the remote repository is already current at `edc9c00`.

## Previous Update - 2026-06-19: Review Fixes for Project-Root Helpers and Resume Audit

Purpose: fix small but high-impact issues found in the systematic skills review
without changing the overall bio-workflow chain, live projects, SLURM state, or
tool-install policy.

Key changes:

- `scripts/program_onboard.py`: onboarding choice/evidence outputs now default to
  the current project root, with optional `--project-root <dir>`. Program-card
  drafts remain skill-owned under `references/program-cards/drafts/`. `install`
  accepts generated Conda proposals from any project
  `reports/program-onboarding/<program_key>/<timestamp>/` bundle instead of only
  the skill source tree.
- `scripts/submit_chunked.sh`: chunk scripts now default to the current project
  `reports/submitted_scripts/chunked/`, support explicit `--chunk-dir`, reject
  protected `/data9/home/qgzeng/data` and `/data9/home/qgzeng/tools` targets, and
  remain dry-run unless `--yes` is supplied.
- `scripts/project_state_audit.sh`: bounded project scans include symlinked
  input files, and older failure/install-failure log evidence is filtered when
  newer completion or validated status evidence exists.
- `scripts/check_result_contract.py`: `SUGGEST` findings are rendered under a
  visible `SUGGESTIONS` section.
- `SKILL.md` and references: response style now defers to
  `user_output_format_preferences.md`; `kmeria` is listed with the active
  program cards; onboarding/chunked-submit docs describe current-project output
  semantics.

Commands/tests run:

```bash
bash -n scripts/check_inputs.sh scripts/check_quota.sh scripts/gen_sbatch.sh scripts/log_claim_audit.sh scripts/parallelization_audit.sh scripts/prepare_submission.sh scripts/project_state_audit.sh scripts/resource_usage_audit.sh scripts/slurm_failure_triage.sh scripts/slurm_preflight.sh scripts/submit_and_log.sh scripts/submit_chunked.sh assets/slurm-templates/per_chunk_array.sbatch assets/slurm-templates/per_sample_array.sbatch
python3 -m py_compile scripts/menu.py scripts/validate_program_cards.py scripts/fill_gap_from_spanning_alignment.py scripts/check_result_contract.py scripts/program_onboard.py scripts/program_card_lookup.py scripts/build_cqu_blobdir.py
python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
python3 scripts/validate_program_cards.py
python3 scripts/validate_program_cards.py --check-drafts
python3 scripts/program_onboard.py choose foo --defaults --project-root /tmp/bwf_po_test
python3 scripts/program_onboard.py plan-install foo --package foo --source container --project-root /tmp/bwf_review_fix_fixture
/data9/home/qgzeng/projects/3-Biotools_create/bio-workflow/scripts/submit_chunked.sh -s scripts/test.sbatch -N 3 -k 2 -j 1
/data9/home/qgzeng/projects/3-Biotools_create/bio-workflow/scripts/project_state_audit.sh --project /tmp/bwf_review_fix_fixture --max-depth 3 --max-files 1000
python3 -c "import sys; sys.path.insert(0, 'scripts'); import check_result_contract as c; print(c.render('PASS', [('SUGGEST', 'R1', 'try a narrower validation')]))"
git diff --check
```

Current conclusion:

- Source skill validation passed.
- Program-card validation passed for 5 active cards and 0 draft cards.
- `git diff --check` passed.
- Installed skill validation passed.
- Targeted source-vs-installed diffs for all files synced in this pass are clean.
- Behavior fixtures confirmed project-local onboarding output, chunk dry-run
  output rooted at the current project, symlink input detection, stale-failure
  filtering, and visible `SUGGESTIONS`.

Caveats:

- No SLURM job was submitted, cancelled, or modified.
- No live panTE or other analysis project was changed.
- `/tmp` fixture files were used only for behavior validation.
- The source tree already contained unrelated modified scripts/references and
  untracked playbooks before this pass; those were not reverted.

Next steps:

- If another review pass finds a repeated misuse pattern, add a narrow helper
  lint or fixture test rather than changing the overall workflow chain.
- When ready, commit only the intended skill changes and keep unrelated existing
  local edits separate.

## Latest Update — 2026-06-19: panTE Real-Case Safeguards Backfilled

Purpose: backfill general rules learned from the real panTE/HiTE/Nextflow case
without changing the live panTE project, SLURM jobs, or helper script behavior.
The main correction is that unknown or multi-file biological inputs must not be
discovered by default recursive scans; ask for exact paths, a manifest, a file
pattern, or an explicitly bounded search root.

Key changes:

- `SKILL.md`: tightened the top-level safety boundary so unknown files,
  multi-file biological inputs, and data inventories are not discovered through
  recursive `find`/`grep`/`rg` by default. Lightweight targeted checks remain
  allowed for explicit paths and small script/config/log targets.
- `references/program-cards/program-onboarding.md`: expanded official container
  proposal requirements to include registry/tag or digest, `.sif`/cache target,
  expected size, proxy need, retry/stop conditions, fallback route, and Conda
  fallback evidence. Added install status labels:
  `completed_with_warnings`, `abandoned_with_reason`, and `failed_blocking`.
- `references/program-cards/install-proposal-template.md`: aligned proposal
  review text with the new container risk budget and Conda fallback record.
- `references/executor-safety.md`: added Nextflow/Snakemake/WDL review rules:
  driver resources, executor config, process resources, `queueSize`, `workDir`,
  and trace/report files must be reviewed separately. Scripts must not discover
  unknown biological inputs through recursive searches.
- `references/resume-protocol.md`: added narrow takeover defaults and explicit
  strategy-switch semantics so stale failed install routes do not override newer
  completed-with-warning, abandoned, fallback, or active pilot evidence.
- `references/resource-feedback.md`: strengthened pilot-first scaling for repeat,
  annotation, pan-genome, unknown tools, multi-file workflows, and workflow
  engines. Resource estimates now prefer manifests, indexes, metadata, file
  sizes, and historical `sacct` or `/usr/bin/time -v`, not full data scans.

Commands/tests run:

```bash
rg -n 'recursive find|递归|bounded root|completed_with_warnings|abandoned_with_reason|failed_blocking|queueSize|driver resources|driver|set \+u|pilot|proxy requirement|maximum retry|stop conditions|fallback route|full streaming|workflow engines|recursive `find`' SKILL.md references/program-cards/program-onboarding.md references/program-cards/install-proposal-template.md references/executor-safety.md references/resume-protocol.md references/resource-feedback.md
python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
python3 scripts/validate_program_cards.py
python3 scripts/validate_program_cards.py --check-drafts
git diff --check
rsync -a --relative SKILL.md references/program-cards/program-onboarding.md references/program-cards/install-proposal-template.md references/executor-safety.md references/resume-protocol.md references/resource-feedback.md /data9/home/qgzeng/.codex/skills/bio-workflow/
python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py /data9/home/qgzeng/.codex/skills/bio-workflow
diff -q SKILL.md /data9/home/qgzeng/.codex/skills/bio-workflow/SKILL.md
diff -q references/program-cards/program-onboarding.md /data9/home/qgzeng/.codex/skills/bio-workflow/references/program-cards/program-onboarding.md
diff -q references/program-cards/install-proposal-template.md /data9/home/qgzeng/.codex/skills/bio-workflow/references/program-cards/install-proposal-template.md
diff -q references/executor-safety.md /data9/home/qgzeng/.codex/skills/bio-workflow/references/executor-safety.md
diff -q references/resume-protocol.md /data9/home/qgzeng/.codex/skills/bio-workflow/references/resume-protocol.md
diff -q references/resource-feedback.md /data9/home/qgzeng/.codex/skills/bio-workflow/references/resource-feedback.md
```

Current conclusion:

- Source skill validation passed.
- Program-card validation passed for 5 active cards and 0 draft cards.
- `git diff --check` passed.
- Installed skill validation passed.
- Targeted source-vs-installed diffs for all updated runtime documents are clean.

Caveats:

- This is a documentation/skill-rule fix only. No script-level preflight/lint rule
  was added for recursive data discovery.
- The source tree already had unrelated modified scripts and references before
  this pass. Only the target rule documents above were synced to the installed
  runtime copy.
- Container routes remain proposal-only in the helper; pull/build/run still need
  a separate reviewed plan and user confirmation.

Next steps:

- If the same failure mode recurs, add a script-level lint that flags recursive
  data discovery in generated SLURM/workflow scripts unless a bounded search plan
  is declared.
- If container proposals are used frequently, extend `program_onboard.py` to
  record explicit container risk-budget fields instead of relying on review text.

## Previous Update — 2026-06-19: Official-Container-First Onboarding Rule

Purpose: add the user-requested general rule that when a bioinformatics tool has
an official Docker/Singularity/Apptainer image, the skill should prefer a
container/Singularity proposal before attempting to solve a complex Conda
`environment.yml` or `env.yml`.

Key changes:

- `SKILL.md`: program onboarding now explicitly says to use
  `choose --default-source container` when official container docs exist, and to
  create a proposal-only container record before any Conda install attempt.
- `references/program-cards/program-onboarding.md`: trusted source priority now
  places official Docker/Singularity/Apptainer images before Conda/Bioconda
  packages. Conda is still allowed when the official container is unavailable,
  inaccessible, incompatible with the cluster/runtime, or explicitly chosen by
  the user.
- `references/program-cards/install-proposal-template.md`: container proposals
  must record official image URI, tag/digest, expected `.sif` or cache target,
  image size when known, bind paths, runtime command, and why this route is
  preferred over Conda.
- `scripts/program_onboard.py`: the source selector descriptions now state that
  official containers are preferred and Conda is the executable fallback route.

Commands/tests run:

```bash
bash -n scripts/*.sh
python3 -m py_compile scripts/program_onboard.py
python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
python3 scripts/validate_program_cards.py
python3 scripts/validate_program_cards.py --check-drafts
git diff --check
```

Current conclusion:

- This is a generalized skill behavior, not a panTE-specific workaround. Future
  unknown-tool onboarding should avoid being dragged into Conda solver failures
  when a maintained official container image is available.

Caveats:

- The helper still executes only Conda proposals automatically. Container routes
  remain proposal-only and require a separate reviewed plan before pull/build/run.
- The rule applies to official or maintainer-documented images only. Third-party,
  untagged, or unclear images remain untrusted until reviewed.

Next steps:

- If repeated real cases need it, add a dedicated container execution helper that
  creates project-local `.sif` pull plans with size checks, bind-path checks, and
  no default execution.

## Previous Update — 2026-06-19: panTE Installed-State Audit Fix

Purpose: revisit the live panTE project after the HiTE/Nextflow installation was
completed. The project status now records completed HiTE/Nextflow setup and a
submitted LM42 pilot job, but `project_state_audit.sh` still chose an older
Singularity pull failure as the primary state. This exposed a resume-state
priority bug: stale install failures could override a newer status table and an
active/pending job.

Key changes:

- `scripts/project_state_audit.sh`: now parses both the standard
  `workflow_status.tsv` schema and the simpler project-local schema with
  `stage/status/job_id/started/finished/notes`.
- Job IDs recorded in `workflow_status.tsv` are now included in discovered job
  evidence, so a pending/running pilot can be recognized even before a SLURM log
  exists.
- Active or pending status-table evidence is now added before stale install
  failure candidates. Old install failures are filtered when a newer
  `workflow_status.tsv` records that install/configure routes were completed or
  abandoned.
- `Script_ready` is suppressed when the status table already records an active
  job, avoiding the unsafe implication that the script should be preflighted or
  submitted again.

Commands/tests run:

```bash
/data9/home/qgzeng/.codex/skills/bio-workflow/scripts/project_state_audit.sh --project /data9/home/qgzeng/projects/2-C_quinoa/9-Annotation/9-panTE --max-depth 3
squeue -j 848205 -h -o '%i|%T|%M|%R|%C|%m|%P|%j'
sacct -j 848205 --format=JobID,State,ExitCode,MaxRSS,Elapsed,ReqCPUS,ReqMem,Partition -n -P
bash -n /data9/home/qgzeng/projects/2-C_quinoa/9-Annotation/9-panTE/scripts/10_pilot_LM42.slurm
bash -n /data9/home/qgzeng/projects/2-C_quinoa/9-Annotation/9-panTE/scripts/20_run_panHiTE.slurm
/data9/home/qgzeng/.codex/skills/bio-workflow/scripts/slurm_preflight.sh --script /data9/home/qgzeng/projects/2-C_quinoa/9-Annotation/9-panTE/scripts/10_pilot_LM42.slurm --mode normal
/data9/home/qgzeng/.codex/skills/bio-workflow/scripts/slurm_preflight.sh --script /data9/home/qgzeng/projects/2-C_quinoa/9-Annotation/9-panTE/scripts/20_run_panHiTE.slurm --mode normal
bash -n scripts/project_state_audit.sh
bash -n scripts/*.sh
python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
python3 scripts/validate_program_cards.py
```

Observed results:

- panTE status evidence says `00_install_HiTE_env=completed`,
  `01_install_nextflow=completed`, `02_build_inputs=completed`, and
  `10_pilot_LM42=pending` with job `848205`.
- `squeue` reports `848205|PENDING|0:00|(Priority)|16|128G|normal|panTE_pilot_LM42`.
- `sacct` reports job `848205` as `PENDING`, requested `16` CPUs and `128Gn` on
  `normal`.
- HiTE configure evidence shows `main.py --help` for HiTE v3.3.3 succeeded.
  R dependencies failed because no CRAN mirror was set, but that was recorded as
  non-fatal by the install workflow.
- `10_pilot_LM42.slurm`: shell syntax PASS; SLURM preflight PASS=19 WARN=0
  FAIL=0.
- `20_run_panHiTE.slurm`: shell syntax PASS; SLURM preflight PASS=18 WARN=1
  FAIL=0, with the expected Nextflow-driver warning that child process resources
  must be reviewed in `nextflow.local.config`.
- After the source fix, `scripts/project_state_audit.sh --project ... --max-depth
  3` now returns primary state `Queued_or_running | Needs_monitoring` with
  evidence from `reports/workflow_status.tsv` and Job_ID `848205`.
- The optional `--check-queue` audit was interrupted after it did not return
  promptly; direct `squeue` and `sacct` calls already provided the needed queue
  evidence. No jobs were submitted, cancelled, or modified.

Current conclusion:

- The live panTE project is no longer in install failure. It is in the pilot
  monitoring stage: HiTE/Nextflow are installed, inputs are built, and the LM42
  pilot is pending in SLURM.
- The skill now handles this transition correctly: newer status/evidence and
  active jobs take precedence over stale install failure logs.

Caveats:

- The project-local `workflow_status.tsv` uses a simpler schema than the standard
  resume-protocol table; the audit script now supports it, but standard 9-column
  status rows remain preferred for future projects.
- The R dependency warning from HiTE install should be revisited only if later
  plotting/report-generation stages fail; it is not a blocker for the current
  HiTE pilot.
- The pilot has not produced resource history yet because job `848205` is still
  pending. Do not launch full panHiTE until MaxRSS/Elapsed from the pilot are
  available.

Next steps:

- Monitor job `848205` with `squeue`/`sacct` and bounded log tails.
- After the LM42 pilot finishes, validate `confident_TE.cons.fa`,
  `confident_ltr_cut.fa`, `all_TE.fa`, and `/usr/bin/time -v` MaxRSS/Elapsed
  before changing full panHiTE resources.

## Previous Update — 2026-06-18: panTE Real-Case Feedback Fixes

Purpose: incorporate lessons from the live panTE project at
`/data9/home/qgzeng/projects/2-C_quinoa/9-Annotation/9-panTE`, where the skill
had prepared inputs, install scripts, and SLURM scripts but was still in tool
installation. The review found three generalizable gaps: HiTE/panHiTE resource
semantics were not recognized, Nextflow launcher resources could be mistaken for
total workflow resources, and install failures in plain logs could be missed by
resume-state detection.

Key changes:

- `scripts/slurm_preflight.sh`: added HiTE/panHiTE recognition, separated actual
  invocations from echo/file-existence checks, and added a Nextflow-driver warning
  requiring review of process `cpus`, `memory`, `queueSize`, and config before
  submission.
- `scripts/project_state_audit.sh`: added install/onboarding log failure
  detection for Conda/micromamba/Singularity-style failures and a
  `Failed | Needs_install_triage` state. Job ID extraction now ignores date-like
  numbers in filenames such as `codex_install_20260618.log`.
- `SKILL.md`: resource-card routing now includes HiTE/panHiTE and Nextflow
  workflow drivers; multi-genome FASTA inventory now forbids streaming full FASTA
  bodies on login/admin nodes just to count bases.
- `references/software-resource-cards.md`: added a HiTE/panHiTE/Nextflow resource
  card covering launcher-vs-process resources, pilot-first scaling, `queueSize`
  pressure, container/Conda route matching, and `.fai`-first input prechecks.
- `references/program-cards/program-onboarding.md`: install attempts must leave a
  project-local status/evidence note; `workflow_status.tsv` should not remain
  `pending` when logs show failed/running/switched install strategy.

Commands/tests run:

```bash
bash -n scripts/slurm_preflight.sh
bash -n scripts/project_state_audit.sh
bash -n scripts/*.sh
scripts/slurm_preflight.sh --script /data9/home/qgzeng/projects/2-C_quinoa/9-Annotation/9-panTE/scripts/10_pilot_LM42.slurm --mode fat
scripts/slurm_preflight.sh --script /data9/home/qgzeng/projects/2-C_quinoa/9-Annotation/9-panTE/scripts/20_run_panHiTE.slurm --mode normal
scripts/project_state_audit.sh --project /data9/home/qgzeng/projects/2-C_quinoa/9-Annotation/9-panTE --max-depth 3
python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
python3 scripts/validate_program_cards.py
python3 scripts/validate_program_cards.py --check-drafts
git diff --check
```

Observed results:

- `10_pilot_LM42.slurm`: PASS with one useful WARN only, because it requests
  128G on `fat` (`<200G`), so the reviewer should justify `fat` or prefer
  `normal`.
- `20_run_panHiTE.slurm`: PASS with one useful WARN that the Nextflow driver
  request covers only the launcher and the process config must be reviewed.
- panTE project audit: primary candidate is now
  `Failed | Needs_install_triage`, with evidence from
  `logs/codex_install_20260618_183213.log: critical libmamba Could not solve for
  environment specs`. Suggested `Job_ID` is now `NA`, not the date from the log
  filename.
- Source validation, shell syntax, active/draft program-card validation, and
  `git diff --check`: PASS.
- No files were written in the live panTE project, and no SLURM jobs were
  submitted or cancelled.

Current conclusion:

- The skill now captures the concrete failure mode from the real panTE run:
  installation state takes precedence over `Script_ready`, HiTE/panHiTE resource
  checks are no longer treated as generic wrapper scripts, and Nextflow driver
  jobs cannot pass without an explicit child-process resource review warning.

Caveats:

- `project_state_audit.sh` is still conservative: it flags any recent install log
  failure until a later status/evidence row records the corrected route.
- The HiTE/panHiTE card gives starting points, not fixed resource templates;
  pilot `sacct` evidence should still drive final scaling.
- The live panTE case currently appears to be in an install/fallback phase, so
  the next skill improvement should be based on the first successful pilot and
  its MaxRSS/Elapsed evidence.

Next steps:

- After the panTE install route is resolved, update the project status/evidence
  so resume-state audit can distinguish failed Conda solve from active
  Singularity fallback.
- Once the LM42 pilot completes, feed `sacct` MaxRSS/Elapsed back into
  `references/software-resource-cards.md` to replace starting heuristics with
  project-history evidence.

## Previous Update — 2026-06-18: SLURM Gate Bypass Fixes

Purpose: close the follow-up safety gaps found after adding resource sanity
checks. The core issue was that some paths still treated documented rules as
advice rather than executable gates, especially chunked array submission and
resume/onboarding entrypoints.

Key changes:

- `scripts/submit_chunked.sh`: replaced the direct `sbatch --array` pathway with
  a dry-run-first wrapper. With `--yes`, it materializes one per-chunk sbatch
  script under `reports/submitted_scripts/chunked/`, embeds the real
  `#SBATCH --array=start-end%cap`, and delegates every chunk to
  `scripts/submit_and_log.sh`.
- `scripts/prepare_submission.sh`: quota-overrun messages now point to the safe
  chunked wrapper, `[资源判断]` is preserved in the green-light package, and the
  non-empty output check no longer uses a `find | head` pipeline under
  `pipefail`.
- `scripts/project_state_audit.sh`, `references/resume-protocol.md`,
  `references/validation-checklists.md`, and
  `references/program-cards/program-onboarding.md`: `Script_ready` now routes to
  `prepare_submission.sh` first, with `slurm_preflight.sh` only as fallback.
- `scripts/log_claim_audit.sh`: `--audit` must resolve inside the project and
  cannot target protected raw-data/tool paths.
- `scripts/slurm_preflight.sh` and `scripts/gen_sbatch.sh`: non-debug
  `#SBATCH --time` with `ALLOW_TIME_DIRECTIVE` now emits a WARN requiring
  explicit user/cluster-policy justification, rather than a silent PASS.
- `scripts/check_quota.sh` and `scripts/submit_chunked.sh`: queue user detection
  now prefers `$SLURM_USER`/`$USER` before `whoami`, avoiding NIS-related false
  quota failures in this environment.

Commands/tests run:

```bash
bash -n scripts/*.sh
python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
python3 scripts/validate_program_cards.py
python3 scripts/validate_program_cards.py --check-drafts
git diff --check
rg -n 'sbatch --parsable|透传给 sbatch|operator-trust boundary|ALLOW_TIME_DIRECTIVE comment|Run scripts/slurm_preflight\.sh --script <file>' scripts references SKILL.md README.md -S
```

Behavior fixtures:

- `/tmp` dry-run fixture for `submit_chunked.sh`: verified it prints chunk plans,
  refuses arbitrary `--` sbatch passthrough, and creates no chunk-script
  directory in dry-run mode.
- `/tmp` fake-SLURM fixture (`squeue` empty, `sbatch` prints a fake Job_ID):
  verified `submit_chunked.sh --yes` creates two chunk scripts, each with the
  correct embedded array range, and records two rows through `submit_and_log.sh`.
- `log_claim_audit.sh --audit /data9/home/qgzeng/data/...`: exits 4 before
  writing and reports that audit paths must stay inside the project.
- `gen_sbatch.sh --time ... --allow-time` plus `slurm_preflight.sh`: now produces
  a `WARN | #SBATCH --time is present with ALLOW_TIME_DIRECTIVE marker`.
- `prepare_submission.sh --output <nonempty_tmp_dir>`: reports existing output
  content without tripping `pipefail`.

Observed results:

- Source skill validation: PASS.
- Installed skill validation after sync: PASS.
- Shell syntax for all bundled shell scripts: PASS.
- Program-card validation: PASS for active and draft checks.
- `git diff --check`: PASS.
- Static grep shows the only remaining `sbatch --parsable` is inside
  `scripts/submit_and_log.sh`, the intended single submit backend.
- Source vs installed diff after sync shows only source-local development
  directories: `.agents`, `.claude`, `.codex`, `.git`, and `tmp`.
- No real SLURM jobs were submitted; all `--yes` submission-path testing used a
  copied `/tmp` mini-repo with fake `squeue`/`sbatch`.

Current conclusion:

- The original resource-review gap is fixed, and the larger class of bypasses is
  now narrowed: chunked array submission, resume entrypoints, onboarding
  entrypoints, claim-audit writes, and walltime exceptions all route through
  explicit checks instead of relying only on prompt text.

Caveats:

- `submit_chunked.sh --yes` intentionally writes persistent chunk scripts under
  `reports/submitted_scripts/chunked/`; this is required so the exact submitted
  script is gate-checked and auditable.
- `ALLOW_TIME_DIRECTIVE` is still allowed as an operator marker, but it is only a
  WARN. The final answer before submission must carry the explicit user/cluster
  justification.
- `prepare_submission.sh` still fails closed if `squeue`/quota evidence is truly
  unavailable. The new username fallback only removes the local `whoami`/NIS
  failure mode.

Next steps:

- On the next real over-quota array, use `submit_chunked.sh` first in dry-run
  mode, inspect the planned chunk scripts/commands, then submit only with
  explicit user confirmation and `--yes`.
- Tune resource-sanity heuristics only after repeated real false positives or
  false negatives appear.

## Previous Update — 2026-06-18: SLURM Resource Review Fix


Purpose: fix the observed gap where skill-assisted SLURM script review checked
that CPU and memory directives existed, but did not force a basic resource
reasonableness assessment.

Key changes:

- `SKILL.md`: `Script_ready` now prefers `scripts/prepare_submission.sh` when
  inputs/outputs are known, and every SLURM review must report `🧮 资源判断`
  covering CPU, memory, partition, array concurrency, and tool/input justification.
- `references/resource-feedback.md`: added a minimum SLURM script review checklist
  so resource review cannot be reduced to "directives exist".
- `references/executor-safety.md`: documents that preflight includes only a
  lightweight resource sanity pass and does not prove CPU/memory optimality.
- `scripts/slurm_preflight.sh`: added `check_resource_sanity`, with WARNs for
  obvious CPU/memory/partition mismatches, limited-scaling tools such as SyRI,
  memory-heavy workflows with very low memory, and `samtools sort -m * CPUs`
  headroom issues.
- `scripts/prepare_submission.sh`: green-light package now prints `[资源判断]`
  by extracting `Resource sanity` PASS/WARN/FAIL lines from preflight output.

Commands/tests run:

```bash
bash -n scripts/slurm_preflight.sh
bash -n scripts/prepare_submission.sh
python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py /data9/home/qgzeng/.codex/skills/bio-workflow
scripts/gen_sbatch.sh --job-name preflight_ok --cpus 8 --mem 32G --log-dir /tmp/bio-workflow-logs --cmd 'busco --cpu "$THREADS" -i input.fa -m proteins -o out' --out /tmp/bio-workflow-preflight-ok.sbatch --force
scripts/gen_sbatch.sh --job-name preflight_warn --cpus 32 --mem 64G --log-dir /tmp/bio-workflow-logs --cmd 'syri -c in.delta -r ref.fa -q qry.fa' --out /tmp/bio-workflow-preflight-warn.sbatch --force
scripts/slurm_preflight.sh --script /tmp/bio-workflow-preflight-ok.sbatch
scripts/slurm_preflight.sh --script /tmp/bio-workflow-preflight-warn.sbatch
scripts/prepare_submission.sh --script /tmp/bio-workflow-preflight-warn.sbatch
/data9/home/qgzeng/.codex/skills/bio-workflow/scripts/slurm_preflight.sh --script /tmp/bio-workflow-preflight-warn.sbatch
git diff --check
diff -qr /data9/home/qgzeng/projects/3-Biotools_create/bio-workflow /data9/home/qgzeng/.codex/skills/bio-workflow
```

Observed results:

- Source and installed skill validation: PASS.
- Shell syntax for edited scripts: PASS.
- PASS fixture: BUSCO 8 CPU / 32G returned `PASS=19 WARN=0 FAIL=0`.
- WARN fixture: SyRI 32 CPU / 64G returned two resource-sanity WARNs:
  normal partition with 32 CPUs, and SyRI limited CPU scaling.
- FAIL fixture: temporary normal-partition script with `#SBATCH --time` returned
  `FAIL=1` as expected; the temporary fixture was deleted after testing.
- Installed runtime copy was synced for the changed runtime files and validated.
- No SLURM jobs were submitted; all tests were local/read-only except writing
  temporary `/tmp/bio-workflow-preflight-*.sbatch` fixtures and syncing the skill.

Current conclusion:

- Future SLURM reviews should no longer silently pass by checking only that
  `--cpus-per-task` and `--mem` exist. The skill prompt path and executable gate
  now both surface a resource verdict.

Caveats:

- `Resource sanity` is deliberately conservative and heuristic. It catches obvious
  mismatches; it does not replace input-size-aware estimates from
  `references/resource-feedback.md` and `references/software-resource-cards.md`.
- `prepare_submission.sh` may still produce NO-GO when `check_quota.sh` cannot get
  stable `squeue`/quota evidence in this environment. That is an existing
  conservative quota behavior, not a resource-sanity regression.
- `diff -qr` between source and installed copy should only show source-local
  development directories such as `.agents`, `.claude`, `.codex`, `.git`, and
  `tmp`.

Next steps:

- Use the new `[资源判断]` output on real SLURM script reviews and tune heuristics
  only when repeated false positives/false negatives appear.
- For large or unfamiliar tools, still require a bounded pilot with
  `/usr/bin/time -v` and/or `sacct` evidence before scaling.
- Keep source and installed Codex copies synced after future runtime edits.

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
  - `references/playbook-genome-annotation.md`: new annotation route for repeats, gene prediction, functional annotation, release, and QC.
  - `references/playbook-pangene-batch-annotation.md`: new route distilled from the real 10-genome pangene annotation directory.
  - `references/playbook-genome-annotation.md`, `references/playbook-pangene-batch-annotation.md`, and
    `references/validation-checklists.md`: added target-species protein evidence database rules for
    EviAnn/BRAKER3 shared protein libraries.
  - `references/playbook-pangene-batch-annotation.md`,
    `references/playbook-genome-annotation.md`, and
    `references/validation-checklists.md`: cross-checked annotation-stage principles
    against official docs/GitHub for BRAKER3, AUGUSTUS, TransDecoder, SPALN3,
    HISAT2/StringTie, and miniprot; EviAnn is pinned to the local installed 2.0.4
    script because no stable public official page was found.
  - `references/software-resource-cards.md`: added annotation wrapper preflight
    checks for tool-specific modes, protein-library scope, and BUSCO/evidence
    dependency caveats.
  - `references/playbook-repeat-annotation.md`: new repeat annotation route distilled
    from the real quinoa repeat directory, covering TRF, RepeatModeler, EDTA,
    DeepTE, RepeatMasker, solo LTR, TE density, TEsorter, and RT-domain trees.
  - `references/playbook-repeat-annotation.md`,
    `references/validation-checklists.md`, and
    `references/software-resource-cards.md`: cross-checked repeat-annotation tool
    boundaries and parameter principles against official docs/GitHub for TRF,
    RepeatModeler, EDTA, DeepTE, RepeatMasker, LTR_retriever, TEsorter, bedtools,
    samtools faidx, MAFFT, IQ-TREE, and CD-HIT/CD-HIT-EST library deduplication.
  - `SKILL.md`, `references/playbook-genome-annotation.md`,
    `references/software-resource-cards.md`, and
    `references/validation-checklists.md`: added repeat-annotation routing,
    resource cards, and acceptance gates.

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
- annotation protein evidence checks: taxon-appropriate family/order/clade choice,
  sequence-count/diversity expectations, header cleaning, deduplication, manifest,
  checksum, and EviAnn/BRAKER3 shared-library provenance.
- official annotation tool checks: source URL/path, check date, local version or
  container, HISAT2/StringTie mode compatibility, BRAKER3 evidence/BUSCO caveats,
  AUGUSTUS train/test split, TransDecoder transcript boundary, and SPALN/miniprot
  output/index modes.
- `references/software-resource-cards.md` now mirrors the same annotation-wrapper
  preflight checks so script/resource planning does not bypass the playbook.
- repeat annotation checks: TRF/RepeatModeler/EDTA/DeepTE/RepeatMasker/solo-LTR/
  TEsorter deliverables are separated, tied to exact genome/library versions, and
  checked for coordinate consistency, overwrite risk, large-I/O joins, and required
  logs/summaries.

Intent: make common acceptance gates reusable by `bio-workflow`,
`centromere-predict`, `cenh3-chipseq`, `centromere-hor-scoring`,
`jcvi-synteny`, and figure/reporting workflows.

### Runtime Sync

The current source versions of these files were copied to the installed Codex
runtime copy:

- `scripts/prepare_submission.sh`
- `scripts/gen_sbatch.sh`
- `scripts/submit_and_log.sh`
- `SKILL.md`
- `references/playbook-genome-annotation.md`
- `references/playbook-pangene-batch-annotation.md`
- `references/playbook-repeat-annotation.md`
- `references/software-resource-cards.md`
- `references/validation-checklists.md`
- `HANDOFF.md`

If `HANDOFF.md` or other files are edited again, repeat the sync before assuming
Codex will use the changes.

### Annotation Protein Evidence Rule

The annotation playbooks now distinguish fixed local file names from the reusable
principle:

- quinoa used `Caryophyllales.pep.fasta` because quinoa is in Caryophyllales;
- other target organisms should use the matching genus/family/order/clade protein
  database according to data availability;
- EviAnn `-p` prefers proteins from multiple related species and only falls back to
  UniProt/Swiss-Prot when close relatives are unavailable;
- BRAKER3 `--prot_seq` follows the same concept but expects a sufficiently broad
  protein-family database such as an appropriate OrthoDB clade, optionally with close
  relatives added;
- shared protein libraries must be cleaned, deduplicated, checksummed, and described
  in a manifest before being reused by EviAnn, BRAKER3, SPALN, or miniprot-style
  evidence stages.

### Official Annotation Tool Cross-check

The annotation playbooks now include a source-checked principle layer:

- BRAKER3: softmasked genome, simple FASTA names, RNA+protein ETP mode when both
  evidence classes exist, OrthoDB-style protein-family database, unique work/species
  names, and BUSCO/compleasm caveats for independent validation.
- AUGUSTUS: bona fide GenBank training structures, non-redundant random train/test
  split, project-local `AUGUSTUS_CONFIG_PATH`, `etraining`, and optional
  `optimize_augustus.pl` as an explicit runtime/quality decision.
- TransDecoder: transcript ORF prediction boundary, LongOrfs/Predict or wrapper
  mode, homology-retention settings, and genome projection route.
- SPALN3/miniprot: protein-to-genome index/output modes and deliberate GFF3
  match-versus-gene output choice for evidence integration.
- HISAT2/StringTie: HISAT2 `--dta`, coordinate-sorted BAMs, STAR strand-tag
  alternative, StringTie `--merge` GTF/GFF input, and `--mix` short-read/long-read
  ordering.
- EviAnn: public official docs/GitHub were not found; use the local
  `/data9/home/qgzeng/anaconda3/envs/eviann/bin/eviann.sh` 2.0.4 script as the
  server-specific authority.

### Repeat Annotation Playbook

`references/playbook-repeat-annotation.md` was added from the real repeat directory:

- source evidence: `/data9/home/qgzeng/projects/2-C_quinoa/9-Annotation/1-Repeat`
- safe-inspection rule: only low-depth metadata and small scripts/logs were read;
  large files such as `merged.txt`, `merged.clean.txt`, EDTA genome-scale outputs,
  RepeatMasker `.out`, and masked FASTA were not opened
- workflow captured: TRF tandem repeats, RepeatModeler de novo libraries, EDTA
  structural/whole-genome TE annotation, DeepTE refinement of `LTR/unknown`,
  RepeatMasker softmasking, solo/intact LTR ratios, TE density/metagene profiles,
  TEsorter classification, and RT-domain MAFFT/IQ-TREE2 phylogeny
- reusable boundaries: separate discovery, classification, masking, density,
  solo-LTR biology, and phylogeny deliverables; do not treat them as one result
- resource cards now include TRF, RepeatMasker, and TEsorter/repeat post-processing
  in addition to EDTA and RepeatModeler

### Official Repeat Tool Cross-check

The repeat playbook now has a source-checked principle layer:

- TRF: tandem-repeat discovery/masking only; `.mask` is not whole-genome TE
  annotation.
- RepeatModeler: de novo library modeling from one intended assembly/haplotype per
  run; record `-LTRStruct` decisions, keep logs, and avoid naive split-genome
  merging.
- EDTA: whole-genome TE annotation/library generation; short stable FASTA headers,
  explicit `--overwrite`/`--force`/library decisions, and clear separation of
  TElib, TEanno GFF3/sum, intact calls, RM output, and `.MAKER.masked`.
- DeepTE: refines unknown TE classes, especially EDTA `LTR/unknown` here; it is not
  primary genome-wide repeat discovery.
- RepeatMasker: custom-library masking/interval evidence; `#class/subclass` labels,
  `-xsmall`, backend, library checksum, and real `-pa` CPU accounting are required.
- LTR_retriever helpers, bedtools, samtools, MAFFT, IQ-TREE, and TEsorter are framed
  as downstream summarization/classification/extraction/tree utilities with explicit
  coordinate and mode checks.
- CD-HIT use is mode-specific: nucleotide TE libraries should use `cd-hit-est` or a
  locally verified equivalent, protein/domain FASTA should use `cd-hit`, and
  thresholds/coverage/cluster files must be recorded.

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
  segmental duplications, genome annotation, repeat annotation, and pan-gene batch
  annotation.
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
