# Bio-workflow

A personal **bioinformatics workflow skill** for planning, generating, preflighting,
submitting, monitoring, and validating analyses on the `gridview` SLURM cluster — without
wasting shared compute or submitting anything by accident.

It is a Claude Code / codex **skill**, not a pipeline: [`SKILL.md`](SKILL.md) is the entry
point an agent loads, and the `scripts/` are read-only checks and guarded executors it
calls. `skills.md` is a byte-for-byte mirror of `SKILL.md` kept for habit.

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
├── SKILL.md / skills.md     # skill entry point (+ mirror)
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
| `submit_chunked.sh` | submit a large array in chunks that stay under the submit cap |
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

## Maintenance

`SKILL.md` is the source of truth; keep `skills.md` identical and validate after changes:

```bash
cmp -s SKILL.md skills.md                       # must match byte-for-byte
bash -n scripts/*.sh                             # shell syntax
python3 .../skill-creator/scripts/quick_validate.py .   # needs a python with PyYAML
```

For `slurm_preflight.sh` changes, test at least one passing and one failing script before
trusting the new rules.
