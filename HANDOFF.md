# Bioflow Skill Handoff

Last updated: 2026-08-10 - reusable Pi interaction package added locally

## Latest Local Update — 2026-08-10: Reusable `pi-ask` Dialogs

Purpose: let users give short requests while any Pi skill can collect only the
consequential missing decisions through reusable TUI dialogs.

What changed locally:

- Created independent project
  `/data9/home/qgzeng/projects/3-Biotools_create/pi-ask` and initialized an empty
  `main` Git repository; no commit or remote exists yet.
- Added global model tools `ask_user` (clarification only) and `confirm_action`
  (fully disclosed gated-action approval), plus exported `ask()`/`confirm()` APIs
  for extension reuse.
- The extension is UI-only: static safety tests reject filesystem/process/network
  APIs and `pi.exec`; non-TUI confirmation fails closed.
- Installed the local package with `pi install`; Pi stored the settings-relative
  package path `../../projects/3-Biotools_create/pi-ask`.
- Added `/ask-demo` for a model-free TUI check. Run Pi `/reload` before using it.
- Bioflow now prefers bounded read-only inference, calls `ask_user` only for
  consequential unknown choices, and reserves `confirm_action` for actions after
  complete purpose/method/path/output/risk disclosure. Text fallback remains.
- Bioflow maintenance now runs the optional `pi-ask` contract suite and verifies
  its local package registration when present.

Validation so far:

- `pi-ask/scripts/test.sh`: PASS (manifest, UI-only static guard, Jiti extension
  load, choice/custom-input/confirmation/non-TUI contracts, whitespace).
- `PI_OFFLINE=1 pi -e <pi-ask> --list-models`: PASS without a model call.
- Installed resource load via `PI_OFFLINE=1 pi --list-models`: PASS.
- Bioflow source regression suite: PASS, including optional `pi-ask` registration
  and contract checks. The Pi interaction contract brings `SKILL.md` to 541 lines
  with source md5 `ead03c65dff5ccdf24f17c3add5a8d7f` before synchronization.
- No network access, SLURM action, analysis-data write, or protected-path write.

Publication state before the authorized follow-up: the previous Bioflow change
was at pushed commit `4d0b2c0`; the HANDOFF refresh and optional-tool integration
were local changes. The user subsequently authorized committing and pushing only
the Bioflow integration. The independent `pi-ask` repository remains local with
no commit, remote, or push and must not be included in the Bioflow commit.

## Latest Update — 2026-08-10: Dashboard, PaperPlot, and Pi Agent Route

Purpose: strengthen the user's frequent running-task/progress workflow without
automatic status mutation, delegate scientific plotting to the installed
`paperplot-skills` instead of duplicating plotting logic, and make Pi a
first-class bioflow agent surface.

What changed:

- Added `reports/Task_Status.tsv` as a task-level companion to the project-wide
  `workflow_status.tsv`; the initializer creates only the missing empty template.
- Added `scripts/project_dashboard.py`, a read-only text/TSV/JSON dashboard that
  reconciles task rows, `run_record.tsv`, project status, and optionally only the
  registered Job IDs from `squeue`/`sacct`.
- Added mixed running/blocked/validated, run-record completion, missing-output,
  malformed-schema, broad-root, and read-only regression fixtures.
- Added `references/task-monitoring.md` and routed progress/queue/mixed-state
  requests through the dashboard while preserving confirmation gates.
- Scientific plotting now uses surface-aware delegation: Codex invokes
  `$paperplot-skills`; Pi loads the discovered `paperplot-skills` (user force-load
  command `/skill:paperplot-skills`). Bioflow retains biological
  readiness/provenance/claim checks and does not substitute another plotting
  skill when PaperPlot is unavailable.
- Added a `PI_CODING_AGENT=true` startup branch using Pi's concatenated context
  files and `PI_CODING_AGENT_DIR` resource root.
- Pi settings now explicitly load bioflow and PaperPlot. Pi's PaperPlot symlink
  points to the same installed copy used by Codex, removing the prior hidden,
  divergent `disable-model-invocation: true` source entry.
- The maintenance suite now checks Pi bioflow drift, PaperPlot name/discoverability,
  PaperPlot skill validity, and Pi settings JSON. `SKILL.md` is 530 lines; the
  documented increase above the former 450-500 target is the explicit Pi startup
  and cross-surface plotting contract, not duplicated domain detail.

No job submission, cancellation, result overwrite, or protected-path write was
part of this update.

Validation completed:

- `scripts/test_skill.sh`: PASS, including dashboard, lifecycle, initialization,
  result-contract, claim-audit, SLURM fixtures, program cards, plugins, and
  whitespace.
- Dashboard regression: mixed states, read-only fingerprint, completed accounting,
  failed array element, missing output, malformed schema, and broad-root refusal
  all PASS.
- Source, Codex runtime, Claude symlink, Pi symlink, and plugin-wrapper `SKILL.md`
  share md5 `d5370ccc3d99cca201365d812e7663f9` after synchronization.
- Pi PaperPlot and Codex PaperPlot share md5
  `6a4bfd0749c3024eb106b598921e0b73`; the active frontmatter has no
  `disable-model-invocation: true`.
- Claude CLI plugin validation was skipped because `claude` was unavailable;
  Codex plugin validation passed.

Commit and publication state:

- The complete dashboard + PaperPlot + Pi adaptation change set was committed as
  `4d0b2c0 feat: add task dashboard and Pi plotting integration` on `main`.
- Push completed successfully: `2293287..4d0b2c0 main -> main`; local `HEAD` and
  local tracking `origin/main` both resolve to `4d0b2c0`.
- The working tree was clean immediately after push. This HANDOFF-only refresh is
  the first follow-up local edit and is not yet committed or pushed.
- No force push or history rewrite was used.
- User-local Pi discovery state is intentionally outside Git:
  `~/.pi/agent/settings.json` explicitly lists bioflow and PaperPlot, and
  `~/.pi/agent/skills/paperplot-skills` points to the Codex-installed PaperPlot.
  Run Pi `/reload` or start a new session after discovery changes.

## Completion Summary — 2026-07-11

The user reviewed the concise feature summary and confirmed the optimization was
useful. The completed implementation now provides:

- nine evidence-based project lifecycle stages and minimum safe next actions;
- a ten-part new-project planning contract plus input, status, acceptance,
  methods, and delivery templates;
- stable directory, artifact, table, identifier, reference, date, and version
  naming rules with a non-overwriting project initializer;
- layered result acceptance and evidence-to-claim interpretation with explicit
  `UNCERTAIN` handling;
- one maintenance entry covering lifecycle, initialization, result-contract,
  SLURM PASS/WARN/FAIL/negative fixtures, program cards, plugins, and whitespace;
- synchronized bioflow behavior across source, Codex runtime, Claude source
  link, and the repo-local plugin skill copy at final validation time.

Pre-commit Git status at this documentation checkpoint:

- No Git commit or push had been performed at this checkpoint.
- Before the authorized commit, `HEAD` and `origin/main` both remained at
  `8ade19270901bdab04307c6f04340854088362a9`.
- The checkpoint worktree included the existing
  `bio-workflow` -> `bioflow` rename and the optimization changes documented
  below. The user subsequently authorized one local commit of this complete
  change set; consult `git log -1` for its resulting hash. No push was authorized.
- That checkpoint edit changed documentation only and was not independently
  synced; the later pre-push behavior correction is recorded next.

## Pre-push Review Correction — 2026-07-11

An independent review of commit `478b368` found a lifecycle evidence bug before
push: a `workflow_status.tsv` row could promote a project to `Plan_ready`,
`Analysis_ready`, or `Delivered` when its pointer resolved to any existing file,
even if that file did not prove review, acceptance, or delivery. The same path
also allowed a tab-containing status row to become a malformed suggested
`Evidence_Path`.

The audit now treats status rows strictly as pointers. A promotion requires the
resolved project-local artifact itself to contain the applicable marker:
`Plan_Status: Reviewed|Approved`,
`Acceptance_Status: Accepted|Validated|Passed`, or
`Delivery_Status: Delivered`. Delivery additionally requires accepted evidence
and a real result. Status pointers resolving outside the project are ignored.
Four negative pointer fixtures cover input/result-only and external evidence;
they remain `Input_ready` or `Complete_unvalidated`. Two timestamp fixtures prove
that a complete delivery supersedes an older failure, while an unaccepted
delivery marker cannot suppress one. The positive `Analysis_ready` fixture now
points to an accepted report rather than treating a result file as validation
evidence.

## Latest Update — 2026-07-11: Lifecycle and Project-Startup Contract

Purpose: complete the bioflow optimization goal through small, testable batches.
The skill previously had six resume states and no single contract for new-project
intake, reviewed analysis plans, final delivery, or uncertainty-aware result
interpretation. State definitions were duplicated across `SKILL.md`,
`resume-protocol.md`, validation guidance, and the audit helper.

Read-only audit before editing:

- Preserved the existing uncommitted `bio-workflow` → `bioflow` rename; no user
  changes were reverted, staged, committed, or pushed.
- Confirmed strong existing SLURM safety, program onboarding, resource feedback,
  result-contract, validation, and task-playbook layers.
- Confirmed four main goal gaps: incomplete lifecycle/startup planning; naming
  guidance without mechanical lint; project-management/delivery artifacts not yet
  standardized end to end; result-contract coverage remains intentionally partial.
- Chose lifecycle/startup first because every later naming, execution,
  interpretation, and delivery improvement depends on stable project stages.

What changed:

- Added `references/project-lifecycle.md` as the single contract for nine stages:
  `Project_intake`, `Input_ready`, `Plan_ready`, `Script_ready`,
  `Queued_or_running`, `Failed`, `Complete_unvalidated`, `Analysis_ready`, and
  `Delivered`. Every stage defines evidence, required inputs, allowed/forbidden
  actions, minimum next action, and transition gate.
- Added the startup planning contract: question, design, inputs, methods, outputs,
  acceptance, resources, risks/dependencies, execution checkpoints, and open
  decisions. `Plan_Status: Reviewed` is required for `Plan_ready`.
- Added the minimal reproducibility chain and canonical `workflow_status.tsv`
  stage/status contract.
- Slimmed `references/resume-protocol.md` from 252 to 74 lines; it now owns only
  bounded takeover evidence and mixed-evidence precedence instead of duplicating
  lifecycle definitions.
- Updated `SKILL.md`, README, and validation checklist routing. `SKILL.md` remains
  below the skill-creator 500-line target at 482 lines.
- Extended `scripts/project_state_audit.sh` to identify the three new stages,
  exclude plan/acceptance/delivery metadata from biological-result counts, and
  print explicit primary stage/status lines.
- Added `scripts/test_project_lifecycle.sh`, a standard-library-only `/tmp`
  regression test covering all nine stages plus boundary cases: an initialized
  skeleton and a reviewed plan without inputs stay `Project_intake`, while a
  draft plan with inputs stays `Input_ready`.
- Synchronized the repo-local `plugins/bioflow/skills/bioflow/` distribution copy.

Follow-up batch — layout, naming, and project initialization:

- Added `references/project-layout.md` as the single detailed rule set for the
  seven standard directories, raw/config/script/log/tmp/result/report boundaries,
  two-digit script stages, human-facing artifact names, TSV columns, identifiers,
  references, dates/versions, examples, and safe legacy/tool compatibility.
- Moved the long naming detail out of `SKILL.md`; the entry point now routes to the
  reference and is 475 lines.
- Added minimal templates under `assets/project-templates/`:
  `Input_Manifest.tsv`, `Analysis_Plan.md`, `workflow_status.tsv`, and
  `Delivery_Index.md`.
- Added `scripts/init_project.sh`. It is dry-run by default, creates only missing
  standard directories/templates after explicit `--yes`, never overwrites, and
  refuses broad or protected `~/data`/`~/tools` paths.
- Added `scripts/test_init_project.sh`: dry-run write check, successful creation,
  idempotent no-overwrite rerun, and protected-path refusal all PASS.
- Resynchronized and revalidated the plugin wrapper after this batch; follow-up
  dry-run reports no drift.

Follow-up batch — evidence-to-claim uncertainty:

- Added `references/result-interpretation.md` with the evidence ladder,
  Observation/Interpretation/Hypothesis/Limitation categories, claim-record
  schema, status semantics, and a concise interpretation output contract.
- Extended `result_manifest.yaml` with `analysis_types` and optional structured
  `claims`. Legacy assembly/KMERIA/SV blocks can be inferred; unknown analysis
  types are never inferred as validated.
- Fixed `check_result_contract.py` so absent rule coverage returns `UNCERTAIN`
  instead of a false `PASS`. Overall precedence is now
  `BLOCK > UNCERTAIN > WARN > PASS`; PASS wording is explicitly limited to active
  rules and cited local evidence.
- Updated `log_claim_audit.sh` and `submit_and_log.sh` to preserve `UNCERTAIN` as a
  machine-readable status (exit 3) without treating it as an infrastructure error
  or cancelling an already submitted job.
- Added `test_result_contract.py` for PASS, inferred coverage, unknown and mixed
  coverage, empty scope, BLOCK precedence, and CLI exit/status; added
  `test_claim_audit.sh` to verify an UNCERTAIN row records `COVERAGE` evidence.
- One initial CLI test failed because `/usr/bin/env python3` resolved to an active
  environment without PyYAML. Root-cause evidence confirmed the base Anaconda
  interpreter had PyYAML; the test now reuses `sys.executable`. Full rerun PASSed.

Follow-up batch — project closure and maintenance entry:

- Added `Acceptance_Report.md` and `Methods_Summary.md` project templates and
  included them in the non-overwriting initializer.
- Added `scripts/test_skill.sh` as the single maintenance entry. It uses a Python
  with PyYAML, redirects bytecode to `/tmp`, runs all shell syntax/Python compile
  checks and regression fixtures, validates the skill, program cards, Codex and
  Claude plugin manifests when available, checks plugin drift, and finishes with
  `git diff --check`.
- `scripts/test_skill.sh` completed with `PASS | bioflow maintenance suite` after
  the plugin wrapper was synchronized.
- Added `scripts/test_slurm_preflight.sh` to satisfy the safety-check fixture
  contract: generated clean PASS (`PASS=19 WARN=0 FAIL=0`), explicit walltime WARN
  (`PASS=18 WARN=1 FAIL=0`), uncapped-array FAIL, and a comment-only `rm -rf`
  negative case that remained clean. The fixture is part of `test_skill.sh`.

Final state-audit correction and forward validation:

- Reproduced an initialized skeleton being falsely classified as `Delivered`.
  Root cause was three independent existence-only heuristics: the header-only
  input manifest counted as data, `Methods_Summary.md` counted as a result, and
  draft acceptance/delivery templates counted as closure evidence.
- `project_state_audit.sh` now requires a real row in recognized tabular input
  manifests, excludes management summaries from result evidence, and requires an
  accepted report, `Delivery_Status: Delivered`, and a real result before direct
  delivery inference. The initialized-skeleton regression fixture passes as
  `Project_intake`.
- A fresh `codex exec` session loaded the installed `$bioflow` runtime and audited
  an initialized `/tmp` project. It reported `Primary_stage: Project_intake`,
  distinguished all ten startup-contract known/unknown groups, avoided queue
  checks, and made no project writes. The complete project SHA-256 fingerprint was
  identical before and after the call.

Validation completed:

```bash
bash -n scripts/*.sh
scripts/test_project_lifecycle.sh
scripts/test_init_project.sh
scripts/test_claim_audit.sh
/data9/home/qgzeng/anaconda3/bin/python scripts/test_result_contract.py
/data9/home/qgzeng/anaconda3/bin/python \
  /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
/data9/home/qgzeng/anaconda3/bin/python scripts/validate_program_cards.py
/data9/home/qgzeng/anaconda3/bin/python scripts/validate_program_cards.py --check-drafts
scripts/sync_plugin_wrapper.sh --yes
/data9/home/qgzeng/anaconda3/bin/python \
  /data9/home/qgzeng/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py \
  plugins/bioflow
claude plugin validate plugins/bioflow
scripts/sync_plugin_wrapper.sh
git diff --check
scripts/test_skill.sh
# Fresh Codex runtime forward test against an initialized /tmp project
```

Results:

- Nine canonical lifecycle states and all boundary/negative cases: PASS.
- Source quick validation: PASS.
- Five active and zero draft program cards: PASS.
- Codex and Claude plugin validation: PASS.
- Plugin sync follow-up dry-run: no content drift.
- Literal repository paths referenced from `SKILL.md` and README: all exist.
- Full maintenance suite, including PASS/WARN/FAIL/negative SLURM fixtures: PASS.
- Fresh runtime forward test: `Project_intake`; project fingerprint unchanged.
- Source, plugin, and Claude-symlink `SKILL.md` share md5
  `031a83d71949e5db47fc5cd0a13cbe27`.

Current final state and known limitations:

- The user-authorized `scripts/sync_install.sh --yes` sync completed; source,
  Codex runtime, repo-local plugin skill copy, and Claude source symlink use the
  current bioflow implementation. Re-run `scripts/test_skill.sh` after source
  changes, then sync the plugin wrapper and runtime deliberately.
- Result-contract rule coverage remains deliberately limited to supported
  analysis types. Unsupported or incomplete coverage returns `UNCERTAIN`; it must
  not be presented as a validated biological claim.
- The existing uncommitted `bio-workflow` -> `bioflow` rename remains preserved.
  No commit, push, SLURM action, installation, download, result overwrite, or
  destructive operation was performed for this goal.

## Latest Update — 2026-07-08: Bioflow Rename Installed and Plan-Mode Ask Tested

Purpose: the planned `bio-workflow` → `bioflow` rename had not been applied to
the actual Codex/Claude skill entries, so the old longer name still affected
skill invocation and plugin install commands. The user also asked whether the new
Codex interactive ask/popup flow can be launched by the agent itself.

What changed in the source tree:

- `SKILL.md` frontmatter is now `name: bioflow`; UI metadata now prompts
  `Use $bioflow ...`.
- Codex runtime sync default is now `~/.codex/skills/bioflow`.
- Repo-local plugin wrapper path is now `plugins/bioflow/`, with the plugin skill
  copy under `plugins/bioflow/skills/bioflow/`.
- Codex and Claude plugin manifests are now named/displayed as `bioflow`.
- Repo-local beta marketplace manifests now expose `bioflow` from
  `./plugins/bioflow`.
- README install/plugin commands now use `bioflow`; the GitHub repository and
  local development checkout directory may remain `Bio-workflow` /
  `bio-workflow`.
- Active helper/provenance text in scripts and playbook section headers now says
  `bioflow`; old `HANDOFF.md` history and already-written historical report
  artifacts are intentionally not rewritten.

Runtime migration completed:

- Codex now uses a real copy at `~/.codex/skills/bioflow`.
- Claude now uses a symlink at `~/.claude/skills/bioflow` pointing to this
  source repo.
- Old installed entries were moved aside, not deleted:
  - `~/.codex/skill-backups/bio-workflow-20260708T203500`
  - `~/.claude/skill-backups/bio-workflow-20260708T203500`
- `~/.codex/skills/bio-workflow` and `~/.claude/skills/bio-workflow` are absent,
  so the old skill name should no longer be discovered from local skill dirs.

Commands/tests run:

```bash
/data9/home/qgzeng/anaconda3/bin/python /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
bash -n scripts/*.sh
/data9/home/qgzeng/anaconda3/bin/python /data9/home/qgzeng/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/bioflow
claude plugin validate plugins/bioflow
scripts/sync_plugin_wrapper.sh --yes
scripts/sync_install.sh --yes
/data9/home/qgzeng/anaconda3/bin/python /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py /data9/home/qgzeng/.codex/skills/bioflow
/data9/home/qgzeng/anaconda3/bin/python /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py /data9/home/qgzeng/.claude/skills/bioflow
md5sum SKILL.md plugins/bioflow/skills/bioflow/SKILL.md /data9/home/qgzeng/.codex/skills/bioflow/SKILL.md /data9/home/qgzeng/.claude/skills/bioflow/SKILL.md
rg -n --hidden 'name: bio-workflow|\$bio-workflow|plugins/bio-workflow|skills/bio-workflow|\.codex/skills/bio-workflow|\.claude/skills/bio-workflow|bio-workflow@qgzeng-bio-beta|bio-workflow@personal|agent-skills/bio-workflow|agent-marketplaces/bio-workflow' SKILL.md README.md agents scripts references .agents .claude-plugin plugins/bioflow
git diff --check
```

Current conclusion:

- Source, plugin-copy, Codex-runtime, and Claude-symlink `SKILL.md` files share
  md5 `100e328bf2ecf84a98999cc03d7f0600`.
- Source skill, Codex installed skill, Claude symlink skill, Codex plugin, Claude
  plugin, shell syntax, and program-card validations all PASS.
- `codex plugin list` reported no installed marketplace plugins, so no old
  `bio-workflow` marketplace plugin was removed.
- The working tree remains dirty; `git add -A` is needed before commit so Git
  records `plugins/bio-workflow/` → `plugins/bioflow/` as a rename.

Plan-mode / interactive ask finding:

- In this Default-mode session, calling `request_user_input` returned
  `request_user_input is unavailable in Default mode`.
- Official Codex manual fetched on 2026-07-08 says `/plan` switches to plan mode;
  in the CLI, Shift+Tab can also toggle Plan mode. The agent cannot switch the
  current conversation into Plan mode by itself from a normal reply.
- Practical rule: if the user wants popup-style early clarification, they should
  start the next request with `/plan` (optionally with inline text). Once the
  conversation is actually in Plan mode, use `request_user_input` for 1-3
  concise, non-blocking or blocking clarification questions as appropriate.
- In Default mode, fall back to plain-text questions such as "先问我关键问题再动手".

After this rename, start a new Codex/Claude session or reload plugins so the
loader sees `bioflow`.

## Latest Update — 2026-07-06: Output File/Directory Naming Convention

Purpose: agents (especially Codex) were creating overly long, all-lowercase,
suffix-laden output names like `figa_contig_nx_curves_lm_litstyle` when
`FigA_Nx_Curves` would do. Added a naming-convention rule to `SKILL.md` and
refined it via a Codex read-only review before commit.

What changed (committed as `8ade192` on `main`, pushed to `origin/main`):

- `SKILL.md` Project layout section: new naming rule for human-facing
  analysis artifacts (result dirs, figure/report files, final TSVs).
  Initial-capital underscore segments with atomic identifiers preserved
  verbatim (`FigA`, `LM134`, `Nx`, `BUSCO`); no redundant status/style
  suffixes (`_Run`, `_Final`, `_Litstyle`); `YYYYMMDD` dates or `V2`/`v1.1`
  for snapshots; ASCII; ~4-5 segments / 60 chars. Standard project dirs
  (`config/`, `data/`, `scripts/`, `logs/`, `results/`, `reports/`, `tmp/`),
  scripts (step-prefix), and tool-mandated names are exempt.
- Codex review (`codex exec --sandbox read-only`, gpt-5.5, xhigh reasoning)
  found 5 must-fix issues; all applied plus high-value nice-to-haves:
  1. Scope conflict with lowercase standard project dirs → rule scoped to
     human-facing artifacts; standard dirs / tool-mandated names / extensions
     explicitly exempt.
  2. Script exemption now covers new AND existing scripts.
  3. Atomic identifiers (`FigA`/`LM134`/`Nx`/`BUSCO`) preserved verbatim,
     not normalized by the initial-capital rule.
  4. Suffix ban narrowed from "purpose/source/version" to redundant
     context/status/style tokens (`_Run`, `_Result`, `_Report`, `_Litstyle`,
     `_New`, `_Final`).
  5. Version/date guidance: `V2`/`v1.1` for a real version series,
     `YYYYMMDD` for snapshots or colliding reruns, never `_Final`.
  Nice-to-haves applied: soft length limit (4-5 segments / ~60 chars),
  ASCII-only basenames, word-order (artifact → metric → discriminator),
  lowercase-acceptable clarification.

Commands/tests run:

```bash
codex exec --sandbox read-only -   # focused review of the naming rule (read via heredoc)
/data9/home/qgzeng/anaconda3/bin/python /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
bash -n scripts/*.sh
scripts/sync_install.sh --yes
md5sum SKILL.md /data9/home/qgzeng/.codex/skills/bio-workflow/SKILL.md /data9/home/qgzeng/.claude/skills/bio-workflow/SKILL.md
git add SKILL.md && git commit -F -   # 8ade192
git push origin main
```

Current conclusion:

- Source skill validation: PASS.
- Shell syntax: PASS.
- Codex runtime copy synced via `sync_install.sh --yes`; three `SKILL.md`
  share md5 `0f872b660294188d313cbbab8863846c` (source + Codex copy + Claude
  symlink target).
- Claude entry remains a symlink → source, automatically live.
- Committed `8ade192`, pushed `e1bd56f..8ade192 main -> main`.

Caveats:

- Running Codex/Claude sessions cache the old `SKILL.md`; start a new
  session to load the new rule.
- The naming rule is guidance, not a hard gate — no script-level lint
  enforces it yet.
- Codex review output is large (~95 KB transcript); the final markdown
  review is at the tail of the persisted output file.

Deferred (not done this session):

- The `bio-workflow` → `bioflow` rename was discussed and planned in full
  (frontmatter `name`, plugin wrapper + manifests, installed dirs, sync
  targets, prose references, README, HANDOFF). It was deferred at the
  user's request to first land the naming rule. Source repo dir and GitHub
  repo name were to be kept by default. Resume on user request.

Next steps:

- If the naming rule is mis-applied in real use, add a script-level lint
  that flags over-long / all-lowercase / suffix-laden artifact names in
  generated SLURM/workflow scripts.
- Decide whether to proceed with the `bioflow` rename.

## Latest Update — 2026-06-27: Output-Style Neutralization

Purpose: the skill was forcing a fixed `📌/🔎/⚠️/🧮/🛠️/✅/▶️` emoji layout (and an
implied voice) onto the agent's replies. `CLAUDE.md` had already revoked this for
Claude Code, but **Codex does not read `CLAUDE.md`** — it loads `SKILL.md`
directly, where the resume route still said "fixed response shape" and the tail
carried a "Default response shape" emoji template, so Codex kept reproducing it.

Decision: the skill now constrains **what content an answer must cover**, never
**how it must look or sound**. Tone, voice, section layout, language, and whether
to use emoji follow the active agent's own style and the user's loaded output
preferences (`user_output_format_preferences.md`, nearest `CLAUDE.md`/`AGENTS.md`,
latest user instruction).

What changed (source + Codex runtime + plugin wrapper):

- `SKILL.md` startup: added an explicit style-neutrality paragraph (step 6) — no
  imposed tone/voice/layout/emoji/template; later "shapes" are content checklists,
  and a project rule / user instruction always wins over a layout suggestion here.
- `SKILL.md` resume route: "Use this fixed response shape" + the 4-line emoji block
  → a plain content checklist (stage / evidence / blockers / smallest next action).
- `SKILL.md` tail: "Default response shape" emoji template → "Response content
  checklist"; explicitly says do not reintroduce the mandatory emoji layout.
- `🧮 资源判断` literal directives reworded to "cover a resource assessment …" in
  `SKILL.md` (resume + SLURM-review), `references/resume-protocol.md`,
  `references/validation-checklists.md`, and
  `references/program-cards/program-onboarding.md`.
- Decorative emoji inside `references/playbook-*.md` (e.g. `✅ confirmed`,
  `⚠️ headers`) are documentation markers, not reply-format directives, and were
  left as-is.

Validation: `quick_validate.py .` → valid; `validate_program_cards.py`
(active + drafts) → PASS. Synced to `~/.codex/skills/bio-workflow` and the
`plugins/bio-workflow/skills/bio-workflow` wrapper.

Live verification: ran two `codex exec --sandbox read-only` cases against the
synced runtime copy — (1) a project-takeover/resume prompt (the route that
previously forced the emoji shape) and (2) an unprompted hifiasm SLURM
resource-review prompt with no style hint. Both returned natural Chinese prose
with the full skill substance preserved (agent-surface detection, preference
reads, six-state classification, broad-scan refusal, minimal next step;
CPU/memory/partition `<200G`-vs-`>=200G` judgement, CPU-forwarding check,
no-default-`--time`) and **no** `📌/🔎/⚠️/🧮/🛠️` template — confirming the
content constraints survive while the forced layout is gone.

Committed as `a58b326` on `main` (9 files: source + plugin wrapper copies);
not pushed yet. Test transcripts left under `tmp/codex-style-test/` (untracked).

Follow-up (same day): pushed `9b6e224..6444028` to `main`, removed the test
transcripts, and verified both agents serve the update — `~/.claude/skills/bio-workflow`
is a symlink to this repo (live, no sync needed) and `~/.codex/skills/bio-workflow`
is the synced copy; all three `SKILL.md` share md5 `f2272fd5…`. See the updated
`Current Installation Model` section for the per-agent sync rule.

## Latest Update — 2026-06-20: Multi-user Portability Pass

Purpose: let trusted same-cluster colleagues install and run the skill without
tripping over hardcoded `/data9/home/qgzeng` paths, while keeping the original
owner's behavior byte-for-byte unchanged.

What changed (committed as `7da5271` on `main`; source + synced plugin copy + Codex runtime copy):

- **User-relative paths.** All bash helpers now use `$HOME`; `program_onboard.py`
  uses `Path.home()`. For `$HOME=/data9/home/qgzeng` every code path is identical
  to before.
- **Write-protection semantics unified.** A path is protected iff it is the
  current user's `~/data`/`~/tools` (or under them), OR matches
  `/data9/home/<user>/(data|tools)[/...]` (bash regex
  `^/data9/home/[^/]+/(data|tools)(/.*)?$`; Python `parts` check). This now
  protects every account's raw-data/tools, and does NOT match project-internal
  `.../projects/<x>/data`. Touched: `gen_sbatch.sh`, `submit_and_log.sh`,
  `submit_chunked.sh`, `log_claim_audit.sh`, `slurm_preflight.sh` (new
  `value_is_protected` helper + the two inline checks + `check_protected_paths`
  loop), `prepare_submission.sh`, and `program_onboard.py`
  (`is_protected_write_path`, `PROTECTED_WRITE_ROOTS`, `BROAD_PROJECT_ROOTS`).
- **Sync/runtime targets follow `$HOME`.** `sync_install.sh` defaults to
  `$HOME/.codex/skills/bio-workflow` and validates the target is under
  `$HOME/.codex/skills`; both sync scripts resolve validators under `$HOME/.codex`
  and now **warn-skip** (instead of ERROR-exit) when the validator is absent, and
  only require a PyYAML Python when a validation will actually run. Python
  candidate lists use `$HOME/anaconda3/bin/python` first, then `python3`/`python`.
- **broad-root audit** (`project_state_audit.sh`) still refuses `/`, `/data9`,
  `/data9/home`, and now also the running user's own home and `~/projects`.
- **Docs.** Rule-level protected-path text in `SKILL.md`, `executor-safety.md`,
  `validation-checklists.md`, `program-onboarding.md`, `install-proposal-template.md`,
  and `program-cards/README.md` now reads `~/data`/`~/tools` (+ cross-user note).
  Playbook tool/conda-env absolute paths are intentionally left as qgzeng tested
  evidence. README gained a `Multi-user / portability` section.

Validation: `bash -n` (all shell + sbatch templates), `py_compile` (all Python),
`quick_validate.py .`, program-card validation (active + drafts), and
`git diff --check` all PASS. Behavior regression confirmed: (A)
`/data9/home/qgzeng/data/x` protected when `$HOME=/data9/home/qgzeng`; (B)
`/data9/home/alice/data/x` protected (new cross-user); (C)
`/data9/home/qgzeng/projects/foo/data/x` NOT protected. Plugin wrapper copy
re-synced and verified byte-identical to source.

Codex-review hardening: 10 rounds of `codex review --uncommitted`, 0 P0; 8 P2 +
2 P1, each fixed and independently regression-tested (~40 fixture cases). Almost
every finding was in `slurm_preflight.sh`'s `check_protected_paths` line-level
body scan:

- cross-user `/data9/home/*/data|tools` coverage in the body scan (not just the
  current user); unexpanded home forms `$HOME` / `${HOME...}` (incl. `${HOME%/}`),
  split-quoted `"$HOME"/data`, and named-tilde `~user/data`.
- exact-dir boundary so siblings like `data-backup` / `tools-v2` / `datax` are
  NOT flagged (kept consistent with `value_is_protected`).
- **read-only-input vs write-target distinction**: a protected path used only as
  a read-only input (e.g. `tool --input ~/data/ref --output results/x`) is now a
  WARN; FAIL is reserved for protected paths that are the write/delete TARGET.
- full write-command set: rm/rmdir/shred/unlink/mv/mkdir/touch/tee/wget/curl/
  pigz/gzip/bgzip/bzip2/xz, plus cp/rsync/install/ln targets including
  `-t`/`--target-directory`, trailing options, and inline `# comment` tails
  (inline comments are stripped before matching).
- two cross-cutting fixes outside that function: `SKILL.md` startup now reads the
  active user's `~/.codex/memories` (README aligned); `project_state_audit.sh`
  refuses ANY `/data9/home/<user>[/projects]` broad root, not just the current
  user's.

The line-level scan stays an explicit heuristic (not a sandbox): indirect forms
(a variable holding HOME, `eval`, `$(...)`) cannot be statically enumerated, and
the authoritative protected-OUTPUT blocks remain the structured hard-FAIL gates
on `#SBATCH --output/--error/--chdir` (`value_is_protected`), `--output`
(`prepare_submission.sh`), and `--record` (`submit_and_log.sh`).

Committed as `7da5271` and pushed (`fa28aa0..7da5271`, 36 files). The Codex
runtime copy at `~/.codex/skills/bio-workflow` was re-synced with
`scripts/sync_install.sh --yes` and verified identical to source. The separate
beta-marketplace + Codex/Claude plugin-wrapper publish landed earlier as
`fa28aa0`.

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

## Historical State Snapshot (pre-2026-07-11; non-authoritative)

The following section records the earlier slimming/annotation pass and contains
historical paths and commit states. Use the 2026-07-11 update and Current
Installation Model for current truth.

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

## Historical Validation Snapshot

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

There are four active development/runtime entries with two sync semantics, plus
the generated plugin distribution:

- **Source of development**: this repository directory.
- **Codex runtime**: `~/.codex/skills/bioflow` is a **real copy**, so source
  edits are NOT live until `scripts/sync_install.sh --yes` runs.
- **Claude Code**: `~/.claude/skills/bioflow` is a **symlink → this repo**, so
  it reflects source edits live.
- **Pi Agent**: `~/.pi/agent/skills/bioflow` is a **symlink → this repo**, so it
  also reflects source edits live. Pi loads global/parent/current context files
  and detects its surface with `PI_CODING_AGENT=true`.

Verified 2026-08-10: Codex uses the synchronized copy; Claude and Pi use source
symlinks; the plugin wrapper is generated from source. Net rule: **after a source
edit, only Codex needs `sync_install.sh`; Claude and Pi are current automatically.**
Running sessions cache skill discovery/content, so use Pi `/reload` or start a new
Pi/Codex/Claude session after discovery or routing changes. Pi's
`paperplot-skills` entry points to the same installed copy used by Codex and is
explicitly listed in Pi settings for surface-aware plotting delegation.

The old standalone Claude skill copy was removed earlier:

- Removed directory: `~/.claude/skills/bioinformatics-analysis-workflow/`
- Temporary backup at removal time:
  `/tmp/bioinformatics-analysis-workflow.snap.1781448044`
- The old helper fallback to `~/.claude/skills/bioinformatics-analysis-workflow/scripts`
  was removed from:
  - `scripts/prepare_submission.sh`
  - `scripts/gen_sbatch.sh`
  - `scripts/submit_and_log.sh`

Do not reintroduce the old `~/.claude/skills/bioinformatics-analysis-workflow`
fallback. `bioflow` has one real source directory, one Codex runtime copy, and
Claude/Pi symlinks back to the source.

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
- Resume/lifecycle layer: `project_state_audit.sh`, `slurm_failure_triage.sh`, nine
  project stages, startup planning, delivery closure, and conservative takeover.
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
  `result-manifest-schema.md`, `result-interpretation.md`, and
  `check_result_contract.py`, including explicit `UNCERTAIN` coverage.
- Feedback loop: `log_claim_audit.sh`, `Checker_Status_AtSubmit`, and
  `reports/claim_audit.tsv` for later false-positive/false-negative review.
- Skill cleanup: removed dead Claude global copy, standardized runtime location
  under `.codex/skills`, and synchronized source/runtime validation checklists.

For full historical detail, inspect git commits instead of expanding this file:

```bash
git log --oneline --decorate
git show <commit>:HANDOFF.md
```

## Claim-specific hardening and new workflow routes

The latest maintenance pass added five bounded improvements without changing
PaperPlot itself, installing software, running biology, or touching protected data:

1. `fill_gap_from_spanning_alignment.py` now validates complete maximal internal
   N-runs and safe output paths before BAM fetch, refuses overwrite by default,
   and transactionally stages FASTA/report outputs. A real indexed pysam fixture
   covers forward/reverse donors, indels, flags, identities, overwrite, and index
   failures. `filled` is explicitly sequence replacement, not join acceptance.
2. `result_manifest.v2` is claim-specific. Claims select subjects/protocols and
   readable evidence paths. Multi-lineage BUSCO storage and dual N50 fields are
   legal; only invalid selected comparisons block. QV checks k and truth-set type;
   high-confidence SV requires read+assembly axes. v1 remains readable but cannot
   false-PASS without v2 claims.
3. Historical quinoa Merqury values are now correctly labeled HiFi-built and
   non-independent, separate from recommended independent PCR-free Illumina
   evaluation. `Cqu_final` is primary A+B, not a hap1+hap2 concatenation;
   `embryophyta_odb12` is headline BUSCO; QV/telomeres alone do not establish T2T.
4. `prepare_paperplot_handoff.py` enforces true TSV, explicit units/directions,
   audited bp/kb/Mb/Gb conversion, within-metric fractional rank, coverage-aware
   ordering, deterministic key samples, and readiness JSON before PaperPlot
   delegation. PaperPlot source/runtime fingerprints are intentionally untouched.
5. Active RNA-seq DE and population SNP/INDEL+GWAS playbooks now define intake,
   route/model choices, replication/confounding/ploidy gates, SLURM resource
   principles, TSV outputs, result-contract fixtures, and PaperPlot handoff.

The maintenance suite includes the four dedicated Python regressions plus the
expanded result-contract matrix. Source is mirrored into the repo-local plugin;
Codex runtime sync is performed only through guarded `sync_install.sh --yes`.
Remote push remains a separate online action.

## Concise directory naming and management

The deferred folder-naming request is now implemented as a bounded Bioflow
capability:

- `scripts/path_manager.py suggest` emits one validated short name from 1–3
  explicit semantic tokens (`03_RNA_DE`), with a 24-character budget and optional
  sibling collision check.
- `audit` is read-only, deterministic, max-depth bounded (hard cap 5), skips
  data/log/tmp interiors, never follows symlinks, and reports true TSV rule rows.
- `create` and `register` are dry-run by default. After write disclosure and
  confirmation, `--yes` creates one directory or registers one existing path and
  atomically updates `config/Directory_Index.tsv`.
- Index replacement failure restores the previous index and rolls back a newly
  created empty directory. Duplicate IDs/paths, case collisions, broad/protected
  roots, symlink escapes, missing parents, and overwrite attempts are blocked.
- `tool_managed` names are exempt and `legacy` names remain advisory; no
  rename/move/delete/cleanup/archive-mutation surface exists.
- `init_project.sh` creates the index header only when absent. Dedicated fixtures
  cover naming budgets, audit exits/ordering, safe writes, and rollback.

Detailed rules live in `references/path-management.md`; `SKILL.md` only routes
matching requests. The implementation uses the Python standard library and was
informed by local Agent Skills/skill-creator/audit patterns because the session
was offline; no external organizer was installed or copied.

A later read-only tuning exercise against the protected quinoa TEMR results
clarified directory-stage semantics. New sibling directories are now planned by
bounded evidence and real dependency/scientific reading order, then numbered
consecutively (`01`, `02`, `03`, ...), without default ten-step gaps. Alphabetic,
mtime, listing, and accidental legacy order are forbidden as sequencing evidence.
The documented TEMR example places preparation/QC/core tables before inversion
group review and its consumers, then plot data before figures and final docs.
This changes guidance only: no TEMR path was modified, stable legacy directories
are not renumbered, and script files retain their separate 10-step prefix policy.

## Remaining Design Options

Keep these as design options, not automatic next tasks:

- Add a read-only `rename-plan` only when real audit output demonstrates a need.
  Actual `mv` remains a separate high-risk, separately confirmed workflow.
- Add rule dependencies to `interpretation-rules.tsv` only after rule count and
  output noise justify a DAG.
- Unify evidence terminology between program cards and interpretation rules when
  program cards are next revised.
- Extend `check_result_contract.py` / `interpretation-rules.tsv` to more analysis
  types' biological silent-traps (alignment rate, assembly N50/BUSCO sane ranges,
  annotation completeness, etc.) — but ONLY by distilling a real "exit 0 yet the
  result is wrong" case when it actually occurs. Do NOT invent threshold rules up
  front; that just adds false positives. Pairs with the `UNCERTAIN` item above.
- Add a lightweight tool/env availability + version precheck at playbook entry
  (confirm the key tools / conda envs exist and versions match before a run) so a
  job does not fail halfway on a missing tool/env. Low cost; do it when a real
  "tool not found / wrong version mid-run" case motivates it. The other "not
  guaranteed" limits (static scan is not a sandbox; exit 0 ≠ biological success;
  pilot-driven resource sizing; on-demand card/playbook growth) are accepted
  boundaries, not optimization targets.

## Important Caveats

- `slurm_preflight.sh` is a static heuristic, not a sandbox. Dynamic shell tricks
  such as variable-wrapped `rm`, `eval`, or nested `bash -c` cannot be fully
  proven safe by static checks.
- `project_state_audit.sh` is a bounded heuristic. Old logs and mixed outputs can
  produce multiple plausible states; the agent must choose the primary state from
  concrete evidence.
- `check_result_contract.py` covers explicit active gates for assembly evaluation,
  SV confidence, RNA differential expression, population variant calling, and
  GWAS. It is still not universal biological interpretation; unsupported or
  generic analysis types must remain `UNCERTAIN`.
- KMERIA-related guidance came from a real failed pilot and is intentionally
  conservative around count-to-matrix format compatibility.

## Minimal Maintenance Commands

Run after editing skill structure:

```bash
scripts/test_skill.sh
```

Run after changing the installed copy:

```bash
python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py /data9/home/qgzeng/.codex/skills/bioflow
diff -qr . /data9/home/qgzeng/.codex/skills/bioflow
```

Expected `diff -qr` noise is limited to source-local development directories:
`.agents`, `.claude`, `.codex`, `.git`.
