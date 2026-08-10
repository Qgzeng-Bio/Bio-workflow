# Bioflow

A personal **bioinformatics workflow skill** for planning, generating, preflighting,
submitting, monitoring, and validating analyses on the `gridview` SLURM cluster — without
wasting shared compute or submitting anything by accident.

It is a Pi / Claude Code / Codex **skill**, not a pipeline:
[`SKILL.md`](SKILL.md) is the entry point an agent loads, and the `scripts/` are
read-only checks and guarded executors it calls.

> **Safety first.** Nothing here installs, cancels, or overwrites on its own, and nothing
> submits a job without an explicit `--yes`. The audit scripts are read-only and only
> advise; the one submitter stops at a confirmation gate.

---

## The server it targets

These are baked in as defaults so an agent doesn't rediscover them every time:

| | |
|---|---|
| Filesystem | `/data9` |
| Scheduler | SLURM (`--account=qgzeng`, `--qos=user_qgzeng`) |
| Partitions | `debug`, `normal` (default), `high`, `fat`/`fat2` (≈384 cores / ~6T each) |
| **QOS limits** | submitted (queued+running) ≤ **200**, running ≤ **100**, running CPU ≤ **600** |
| Packages | `micromamba` (base conda/mamba solver is broken), conda-forge first; reuse existing envs |
| Protected (no writes) | `/data9/home/qgzeng/data`, `/data9/home/qgzeng/tools` |
| Login/admin nodes | no compute on `admin2` / login nodes — route heavy work through SLURM |
| Walltime | no `#SBATCH --time` on `normal`/`fat`/`fat2`/`high` (only `debug`, or with `--allow-time`) |

## Repository layout

```text
bioflow/
├── SKILL.md                 # skill entry point
├── HANDOFF.md               # running change log
├── agents/openai.yaml       # agent metadata
├── assets/slurm-templates/  # per_sample_array.sbatch, per_chunk_array.sbatch
├── references/              # software resource cards, validation checklists, resume protocol
└── scripts/                 # read-only checks + guarded executors (below)
```

## The executor trio — generate → gate → submit

The core loop. Each step reuses the one before it; the human presses the button.

```text
gen_sbatch.sh  ──▶  prepare_submission.sh  ──▶  submit_and_log.sh
generate a              read-only GO/NO-GO         confirmed submit + run record
preflight-clean         "green-light package"      (dry-run by default; --yes to submit)
script (by construction) (never submits)
```

## Start a project

Preview the minimal seven-directory layout and management templates, then create
only missing paths after review:

```bash
scripts/init_project.sh --project /absolute/path/to/project
scripts/init_project.sh --project /absolute/path/to/project --yes
```

The initializer never overwrites existing files. It includes an empty
`reports/Task_Status.tsv` for concurrent work units. Naming, identifier/version,
and legacy compatibility rules are in
[`references/project-layout.md`](references/project-layout.md).

## Monitor running work

Use the read-only dashboard to reconcile task records, submission records, project
status, and registered SLURM Job IDs:

```bash
python3 scripts/project_dashboard.py --project /absolute/path/to/project
python3 scripts/project_dashboard.py --project /absolute/path/to/project --check-queue
python3 scripts/project_dashboard.py --project /absolute/path/to/project --check-queue --format json
```

It never writes status or changes the queue. `reports/workflow_status.tsv` remains
the project-wide lifecycle record; `reports/Task_Status.tsv` records concurrent
stages, samples, pilots, jobs, blockers, and validation tasks. See
[`references/task-monitoring.md`](references/task-monitoring.md).

**1. Generate** — emits a script that already passes preflight (absolute `%j_%x` logs,
strict mode, CPU forwarding, array `%N` cap, no default `--time`); it runs `bash -n` and
`slurm_preflight.sh` on its own output and refuses to emit anything that would FAIL.

```bash
scripts/gen_sbatch.sh --job-name align --cpus 8 --mem 16G --log-dir /abs/project/logs \
    --array 1-12%4 --manifest config/samples.tsv \
    --cmd 'fastp --thread "$THREADS" -i "$(echo "$TASK_LINE" | cut -f2)" -o out/$SLURM_ARRAY_TASK_ID.fq.gz'
```

**2. Gate** — bundles input / preflight / array+manifest / quota / overwrite checks into one
GO/NO-GO verdict and prints the exact, **unsubmitted** `sbatch` command. Hard-blocks on
preflight FAIL, missing/empty inputs, a manifest header (templates are 1-indexed),
`--output` under a protected tree, or a quota submit-cap overrun.

```bash
scripts/prepare_submission.sh --script align.sbatch --manifest config/samples.tsv \
    --input-list config/inputs.txt --output results/align
```

**3. Submit** — re-runs the gate as a final check; **dry-run by default**, submits only with
`--yes`, then appends a row to `reports/run_record.tsv`. A NO-GO gate, a missing `--yes`, an
unwritable record, or a script changed since the gate (TOCTOU) all block it.

```bash
scripts/submit_and_log.sh --script align.sbatch --manifest config/samples.tsv --yes
```

## Pre-submit & resource audits (read-only)

| Script | Purpose |
|---|---|
| `slurm_preflight.sh` | static safety check of an sbatch script (logs, `%N` cap, strict mode, destructive `rm`, protected-path writes/deletes, proxy, `admin2`, CPU/mem declarations) — `FAIL` blocks, `WARN` explains |
| `parallelization_audit.sh` | detect serial independent-task bottlenecks and un-forwarded CPUs; recommend an array structure, `%N` cap, and template |
| `resource_usage_audit.sh` | after a pilot, parse `/usr/bin/time -v` + `sacct` to right-size `--cpus-per-task` / `--mem` / array concurrency |
| `check_quota.sh` | show QOS occupancy (200/100/600) and dry-run whether a batch would exceed the submit cap |
| `submit_chunked.sh` | dry-run or submit a large array through per-chunk scripts stored in the current project and re-entering `submit_and_log.sh` |
| `check_inputs.sh` | input inventory + integrity (exists / readable / non-empty / gzip magic / format sniff / optional pairing) |

## Resume & failure triage

| Script | Purpose |
|---|---|
| `project_state_audit.sh` | take over an existing project — classify it across the nine-stage lifecycle from `Project_intake` through `Delivered` and suggest the smallest next step |
| `project_dashboard.py` | reconcile concurrent task records and registered SLURM jobs into running/queued/failed/blocked/complete-unvalidated/validated summaries; read-only |
| `slurm_failure_triage.sh` | classify a failed job (OOM, TIMEOUT, missing input, permission, env/tool, segfault, disk full, shell/pipefail, format incompatibility) and propose a minimal fix |

See [`references/project-lifecycle.md`](references/project-lifecycle.md),
[`references/resume-protocol.md`](references/resume-protocol.md), and
[`references/validation-checklists.md`](references/validation-checklists.md) for the layered
acceptance gates (exit code 0 ≠ success).

## Interactive clarification in Pi

Bioflow can use the optional global `pi-ask` package so short
requests such as “帮我跑 BUSCO” are enough. It first performs bounded read-only
inspection, then calls `ask_user` only for consequential choices that cannot be
inferred safely. Options may include explanations, an evidence-based
recommendation, and custom text.

`ask_user` never grants execution permission. After Bioflow discloses the exact
action, method/command, affected paths, expected outputs, and risks, it may call
`confirm_action` for a gated write or job action. Missing/non-TUI tools fall back
to concise text questions and do not weaken safety gates.

Local Pi installation:

```bash
pi install /data9/home/qgzeng/projects/3-Biotools_create/pi-ask
```

Run `/reload`, then `/ask-demo` to test the model-free dialog.

## Scientific plotting

Bioflow delegates scientific figure diagnosis, redesign, rendering, export, and
image-level QA to the separately installed skill named `paperplot-skills`.
Bioflow retains responsibility for biological readiness, reference/coordinate
consistency, data provenance, statistics, and claim limits; it does not duplicate
or silently replace PaperPlot's workflow.

- Codex invokes `$paperplot-skills`.
- Pi loads the discovered `paperplot-skills`; users can force it with
  `/skill:paperplot-skills`.
- If PaperPlot is unavailable, bioflow reports the blocker instead of substituting
  another plotting skill or claiming PaperPlot QA.

Run `/reload` in Pi or start a new Pi/Codex session after changing skill discovery.

## Safety model

- **Read-only by default.** All audit scripts only read and print recommendations; they
  never rewrite project scripts, lower memory, or touch the queue.
- **Confirmation gates.** `sbatch` / `scancel` / installs / writes to protected paths /
  overwriting results / large downloads require explicit confirmation; `submit_and_log.sh`
  enforces this with `--yes`.
- **Heuristic, not a sandbox.** `slurm_preflight.sh` catches *common mistakes* (accidental
  `rm -rf`, writing to protected dirs, missing `%N` cap). It cannot catch dynamic evasions
  (`$RM`, `eval`, `bash -c "…"`); the real protection is filesystem permissions plus the
  confirmation gate.

## Plugin wrapper install

The raw skill install remains the recommended path for daily use because Pi,
Codex, and Claude Code can share one source checkout:

```bash
mkdir -p ~/agent-skills ~/.pi/agent/skills ~/.codex/skills ~/.claude/skills
git clone https://github.com/Qgzeng-Bio/Bio-workflow.git ~/agent-skills/bioflow
ln -sfn ~/agent-skills/bioflow ~/.pi/agent/skills/bioflow
ln -sfn ~/agent-skills/bioflow ~/.codex/skills/bioflow
ln -sfn ~/agent-skills/bioflow ~/.claude/skills/bioflow
```

For Pi plotting delegation, make the same reviewed PaperPlot installation visible
to Pi and include it in the Pi `skills` setting when explicit resource paths are
used:

```bash
ln -sfn ~/.codex/skills/paperplot-skills ~/.pi/agent/skills/paperplot-skills
```

When `~/.pi/agent/settings.json` uses explicit skill paths, include both entries:

```json
{
  "skills": [
    "~/.pi/agent/skills/bioflow",
    "~/.pi/agent/skills/paperplot-skills"
  ]
}
```

Pi discovers it on the next `/reload` or new session. The PaperPlot frontmatter
must not set `disable-model-invocation: true` when automatic delegation is wanted.

The repo also includes an optional plugin wrapper at `plugins/bioflow/`.
It contains both Codex and Claude Code manifests:

```text
plugins/bioflow/
├── .codex-plugin/plugin.json
├── .claude-plugin/plugin.json
└── skills/bioflow/
```

The wrapper packages a synchronized copy of the raw skill under
`plugins/bioflow/skills/bioflow/` for future marketplace or team distribution.
It is a distribution layer only; do not edit the copied skill by hand.

Refresh the plugin wrapper from the raw skill source with:

```bash
scripts/sync_plugin_wrapper.sh          # dry-run
scripts/sync_plugin_wrapper.sh --yes    # write wrapper copy and validate plugin
```

Validate the wrapper directly with:

```bash
/data9/home/qgzeng/anaconda3/bin/python \
  /data9/home/qgzeng/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py \
  plugins/bioflow
claude plugin validate plugins/bioflow
```

This repository does not write `~/.agents/plugins/marketplace.json` automatically.
To expose the wrapper through a personal Codex marketplace, point a marketplace entry named
`bioflow` at `./plugins/bioflow` and then install it from that marketplace, for example
`codex plugin add bioflow@personal` after the entry exists.

## Internal beta marketplace

For trusted testers, this repo includes marketplace manifests without publishing to a public
registry:

```text
.agents/plugins/marketplace.json      # Codex marketplace
.claude-plugin/marketplace.json       # Claude Code marketplace
```

The marketplace name is `qgzeng-bio-beta`. After cloning a reviewed branch or tag, testers can add
the local checkout as a marketplace and install the plugin:

```bash
git clone https://github.com/Qgzeng-Bio/Bio-workflow.git ~/agent-marketplaces/bioflow

codex plugin marketplace add ~/agent-marketplaces/bioflow
codex plugin add bioflow@qgzeng-bio-beta

claude plugin marketplace add ~/agent-marketplaces/bioflow
claude plugin install bioflow@qgzeng-bio-beta
```

This is intended for private beta testing only. Share a branch, tag, or private repository access
with testers instead of submitting to public Codex or Claude marketplaces. Testers should start with
read-only checks, dry-runs, and script review before any real `sbatch`, install, download, or
overwrite action.

For Claude Code local testing without publishing a marketplace, launch Claude from the repo root
with:

```bash
claude --plugin-dir plugins/bioflow
```

The plugin skill is namespaced as `/bioflow:bioflow`. Run `/reload-plugins` after
editing plugin metadata or non-skill plugin components.

This skill targets the qgzeng `/data9` SLURM cluster. It assumes the local SLURM partitions and
QOS, the cluster's `admin2`/login-node policy, and the C quinoa workflow conventions. External
users on a different cluster should adapt the partition/resource rules before relying on it.

## Multi-user / portability

The helper scripts no longer hardcode `/data9/home/qgzeng`. They follow whoever runs them:

- **User-relative paths.** Bash scripts use `$HOME`; `program_onboard.py` uses `Path.home()`. For
  the original owner (`$HOME=/data9/home/qgzeng`) behavior is unchanged; for any other account the
  same rules apply to that account's own home.
- **Write protection.** A path is protected when it is the current user's own `~/data` or `~/tools`
  (or anything under them), **or** any `/data9/home/*/data` or `/data9/home/*/tools` on this
  cluster. So a shared install protects every account's raw-data/tools, not just one — while a
  project-internal `…/projects/<x>/data` directory stays writable.
- **Runtime/plugin sync targets follow `$HOME`.** `sync_install.sh` writes to
  `$HOME/.codex/skills/bioflow`; `sync_install.sh` / `sync_plugin_wrapper.sh` look for the
  skill-creator/plugin-creator validators under `$HOME/.codex`. If those validators are absent
  (a non-Codex install), validation is **skipped with a warning** instead of failing.
- **Project rules per user.** The skill's own safety rules live in `SKILL.md` and apply wherever it
  is loaded. Codex reads the active user's `~/.codex/memories`; Pi uses its
  concatenated global/parent/current `AGENTS.md` or `CLAUDE.md` context and any
  memory files those rules require; Claude Code reads its nearest `CLAUDE.md`.
  These files are path-scoped, so each user should keep equivalent rules in their
  own project tree or rely on the safety rules embedded in `SKILL.md`.
- **Tool/conda-env paths in the playbooks are qgzeng examples.** Absolute paths in
  `references/playbook-*.md` (e.g. `braker3.sif`, `SURVIVOR`, `ModDotPlot/venv`, `seqkit`,
  `DeepTE.py`, EviAnn) point at the owner's installed tools as tested evidence. Other users must
  install those tools themselves and substitute their own paths.

## Maintenance

`SKILL.md` is the source of truth; validate after changes:

```bash
scripts/test_skill.sh                            # core suite, including optional Pi integration checks
scripts/sync_install.sh                          # dry-run Codex runtime sync
scripts/sync_install.sh --yes                    # write Codex runtime sync
scripts/sync_plugin_wrapper.sh                   # dry-run Codex plugin-wrapper sync
scripts/sync_plugin_wrapper.sh --yes             # write and validate plugin wrapper
```

For `slurm_preflight.sh` changes, test at least one passing and one failing script before
trusting the new rules.
