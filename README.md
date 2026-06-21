# Bio-workflow

A personal **bioinformatics workflow skill** for planning, generating, preflighting,
submitting, monitoring, and validating analyses on the `gridview` SLURM cluster — without
wasting shared compute or submitting anything by accident.

It is a Claude Code / codex **skill**, not a pipeline: [`SKILL.md`](SKILL.md) is the entry
point an agent loads, and the `scripts/` are read-only checks and guarded executors it
calls.

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
bio-workflow/
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
| `project_state_audit.sh` | take over an existing project — classify it as `Input_ready` / `Script_ready` / `Queued_or_running` / `Failed` / `Complete_unvalidated` / `Analysis_ready` and suggest the smallest next step |
| `slurm_failure_triage.sh` | classify a failed job (OOM, TIMEOUT, missing input, permission, env/tool, segfault, disk full, shell/pipefail, format incompatibility) and propose a minimal fix |

See [`references/resume-protocol.md`](references/resume-protocol.md) and
[`references/validation-checklists.md`](references/validation-checklists.md) for the layered
acceptance gates (exit code 0 ≠ success).

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

The raw skill install remains the recommended path for daily use because Codex and Claude Code
can share one source checkout:

```bash
mkdir -p ~/agent-skills ~/.codex/skills ~/.claude/skills
git clone https://github.com/Qgzeng-Bio/Bio-workflow.git ~/agent-skills/bio-workflow
ln -sfn ~/agent-skills/bio-workflow ~/.codex/skills/bio-workflow
ln -sfn ~/agent-skills/bio-workflow ~/.claude/skills/bio-workflow
```

The repo also includes an optional plugin wrapper at `plugins/bio-workflow/`.
It contains both Codex and Claude Code manifests:

```text
plugins/bio-workflow/
├── .codex-plugin/plugin.json
├── .claude-plugin/plugin.json
└── skills/bio-workflow/
```

The wrapper packages a synchronized copy of the raw skill under
`plugins/bio-workflow/skills/bio-workflow/` for future marketplace or team distribution.
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
  plugins/bio-workflow
claude plugin validate plugins/bio-workflow
```

This repository does not write `~/.agents/plugins/marketplace.json` automatically.
To expose the wrapper through a personal Codex marketplace, point a marketplace entry named
`bio-workflow` at `./plugins/bio-workflow` and then install it from that marketplace, for example
`codex plugin add bio-workflow@personal` after the entry exists.

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
git clone https://github.com/Qgzeng-Bio/Bio-workflow.git ~/agent-marketplaces/bio-workflow

codex plugin marketplace add ~/agent-marketplaces/bio-workflow
codex plugin add bio-workflow@qgzeng-bio-beta

claude plugin marketplace add ~/agent-marketplaces/bio-workflow
claude plugin install bio-workflow@qgzeng-bio-beta
```

This is intended for private beta testing only. Share a branch, tag, or private repository access
with testers instead of submitting to public Codex or Claude marketplaces. Testers should start with
read-only checks, dry-runs, and script review before any real `sbatch`, install, download, or
overwrite action.

For Claude Code local testing without publishing a marketplace, launch Claude from the repo root
with:

```bash
claude --plugin-dir plugins/bio-workflow
```

The plugin skill is namespaced as `/bio-workflow:bio-workflow`. Run `/reload-plugins` after
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
  `$HOME/.codex/skills/bio-workflow`; `sync_install.sh` / `sync_plugin_wrapper.sh` look for the
  skill-creator/plugin-creator validators under `$HOME/.codex`. If those validators are absent
  (a non-Codex install), validation is **skipped with a warning** instead of failing.
- **Project rules per user.** The skill's own safety rules live in `SKILL.md` and apply wherever it
  is loaded. On Codex, `SKILL.md` startup reads the active user's own `~/.codex/memories`, so each
  user gets their own output/SLURM preferences. The nearest project-rule file (`CLAUDE.md` for Claude
  Code, `AGENTS.md` for Codex) is path-scoped — qgzeng's live under `/data9/home/qgzeng/projects` — so
  each user should drop an equivalent `CLAUDE.md`/`AGENTS.md` in their own project tree, or rely on the
  rules already embedded in `SKILL.md`.
- **Tool/conda-env paths in the playbooks are qgzeng examples.** Absolute paths in
  `references/playbook-*.md` (e.g. `braker3.sif`, `SURVIVOR`, `ModDotPlot/venv`, `seqkit`,
  `DeepTE.py`, EviAnn) point at the owner's installed tools as tested evidence. Other users must
  install those tools themselves and substitute their own paths.

## Maintenance

`SKILL.md` is the source of truth; validate after changes:

```bash
bash -n scripts/*.sh                             # shell syntax
python3 .../skill-creator/scripts/quick_validate.py .   # needs a python with PyYAML
scripts/sync_install.sh                          # dry-run Codex runtime sync
scripts/sync_install.sh --yes                    # write Codex runtime sync
scripts/sync_plugin_wrapper.sh                   # dry-run Codex plugin-wrapper sync
scripts/sync_plugin_wrapper.sh --yes             # write and validate plugin wrapper
```

For `slurm_preflight.sh` changes, test at least one passing and one failing script before
trusting the new rules.
