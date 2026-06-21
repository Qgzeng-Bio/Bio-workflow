# Unknown program onboarding

Use this protocol when the user asks to run a program that has no card in this
directory. The goal is to turn an unknown tool into a safe, auditable workflow
without installing, downloading, or scanning broadly by default.

Third-version onboarding provides a project-local helper:

```bash
python3 scripts/program_onboard.py choose <program>
python3 scripts/program_onboard.py probe <program>
python3 scripts/program_onboard.py plan-install <program> --package <package> --source conda
python3 scripts/program_onboard.py install --proposal <install_proposal.json> --yes
python3 scripts/program_onboard.py capture <program> --evidence-dir <evidence_dir>
python3 scripts/program_onboard.py draft-card <evidence_dir>
```

Use the helper for local discovery, install proposals, post-install evidence, and
draft card generation. By default, run it from the analysis project root: choice
JSON is written under `config/program-onboarding/`, and evidence bundles are
written under `reports/program-onboarding/<program_key>/<timestamp>/`. Use
`--project-root <dir>` when invoking the helper from another directory. Program
card drafts remain skill-owned and are written to `references/program-cards/drafts/`
unless `--output-card` is supplied. See `evidence-bundle-schema.md` for bundle
contents. Install proposal format and execution gates are defined in
`install-proposal-template.md`.

`install` is the only subcommand that mutates a Conda environment, and it must be
called with `--yes` against a generated proposal. Network access, Conda env
mutation, writes under `~/tools/`, downloads, and SLURM
submission still require explicit user confirmation. Evidence and choice paths
are project-local by default; `--allow-external-paths` is only for non-install
smoke tests, and automatic `install` still accepts only a generated proposal
inside a `reports/program-onboarding/<program_key>/<timestamp>/` evidence bundle.

Use level names when reporting progress, so "tested" is not confused with "only
looked for the executable":

- `L0 choice/intake`: install target, source route, and pilot input choice recorded.
- `L1 probe`: local executable/env/help discovery only.
- `L2 install proposal`: reviewed JSON/Markdown proposal exists; no install yet.
- `L3 installed+captured`: executable, version/help, and env proof captured.
- `L4 pilot script/preflight`: minimal input checked and script/gate prepared.
- `L5 pilot/run validated`: real pilot or production output passed acceptance checks.
- `L6 active card`: reviewed card promoted and registered.

## State machine

### 1. Intent intake

Confirm:

- program name and aliases
- biological or data-analysis goal
- likely mode
- expected input type and output type
- whether this is a one-off run or a reusable workflow

If the user only gives a program name, ask for the goal and mode before writing a
command.

When the missing items are install location, source route, or pilot input mode,
prefer the terminal selector instead of repeated free-text questions:

```bash
python3 scripts/program_onboard.py choose <program>
```

It uses a curses menu in a real terminal and falls back to numbered prompts with
`--plain`. It writes `config/program-onboarding/<program_key>_choice.json`.
If the current directory is not the analysis project root, pass
`--project-root <dir>` so the JSON and suggested project-local test path are
recorded in the right project.
Use `--default-source container` when the official docs provide a Docker,
Singularity, or Apptainer image. Use `--default-source github` for tools whose
official installation is only a GitHub or source checkout. The selector only
records choices; it does not install, download, scan data, submit jobs, or mutate
environments.

### 2. Local discovery

Use cheap, bounded checks only:

- `command -v <program>`
- `<program> --version`, `<program> -h`, or `<program> --help` if present
- explicitly named Conda env, module, container, or binary path
- current project scripts or manifests when they are in the working project

Do not run broad searches under `/data9`, `/data9/home/qgzeng`, or large project
roots. If discovery requires a search, ask for a bounded root, pattern, and
maxdepth.

Default tool command:

```bash
python3 scripts/program_onboard.py probe <program>
```

### 3. Trusted source discovery

If the program is not installed, propose sources in this priority order:

1. existing server environment or explicit user-provided path
2. official Docker/Singularity/Apptainer container image
3. Conda/Bioconda package
4. official release archive
5. GitHub source build

Use only official or maintainer-documented images. Treat third-party, untagged,
or unclear images as untrusted until reviewed. Do not let a complex
`environment.yml`/`env.yml` solve become the first route when an official
container exists; use Conda only when the official container is unavailable,
too large/inaccessible, incompatible with the cluster/runtime, or the user
explicitly chooses Conda for integration reasons. For Conda fallback proposals,
record the solver (`conda`, `mamba`, or `micromamba`), channel priority, expected
failure risks, and the exact validation command that will prove the executable is
usable after activation.

Do not run installation snippets from a README without user confirmation.

### 4. Install proposal

Before any install or environment mutation, state:

- package/program name
- source and version
- install method
- target path
- expected writes
- network need
- risks and rollback limits

Default user-level targets are a named Conda env or a clear directory under
the current user's `~/tools/`, but writing there still requires confirmation.

Default third-version container proposal when an official image exists:

```bash
python3 scripts/program_onboard.py plan-install <program> --package <official_image_uri_or_tag> --source container
```

Container routes are proposal-only in this helper. The proposal must record the
image URI, tag or digest when available, expected `.sif` or cache target,
estimated download size if known, bind paths, runtime command, proxy requirement
or "none", maximum retry count, stop conditions, fallback route, and why this
route is preferred over Conda. Pull/build/run only after a separate reviewed plan
and user confirmation.

Default third-version Conda proposal when no official container route is suitable:

```bash
python3 scripts/program_onboard.py plan-install <program> --package <package> --source conda
```

The default target env is `bio_<program_key>`. If the env already exists,
proposal generation blocks unless `--reuse-existing` is supplied. Container,
GitHub source, manual source, and binary routes are proposal-only; do not execute
them through this helper. Package names, channels, target env names, and the
structured command argv are validated again by `install`.

### 5. User confirmation

Stop before:

- installing, updating, or removing tools
- writing to `~/tools/`
- downloading databases or large reference files
- submitting SLURM jobs
- overwriting existing results

For Conda installs, review `install_proposal.md` and run only after confirmation:

```bash
python3 scripts/program_onboard.py install --proposal <install_proposal.json> --yes
```

Without `--yes`, `install` must exit without executing.

### 6. Environment proof

After installation or discovery, record:

- `which <program>` or absolute binary path
- version output
- help output source
- minimal startup check
- environment activation command or container invocation

Use `local_help` evidence after help/version is captured. Use `local_run` only
after a pilot or real run succeeds.

Failed help/version attempts are recorded, but they do not count as `local_help`.

After every install attempt, including failed solver runs or abandoned fallback
routes, record a project-local status note or evidence bundle with the command,
log path, exit/status, install route, and next state. Do not leave install progress
only in chat or loose logs, and do not leave `workflow_status.tsv` as `pending`
when install logs already show `FAILED`, `RUNNING`, or a switched strategy.
Use explicit install status labels when a simple success/failure would hide the
real state:

- `completed_with_warnings`: executable is usable, but non-critical dependency,
  optional feature, or cleanup warnings remain.
- `abandoned_with_reason`: a route such as container pull, Conda solve, or source
  build was intentionally stopped and replaced by another strategy.
- `failed_blocking`: no usable executable exists and the next workflow step cannot
  proceed without a fix or user decision.

Default capture command:

```bash
python3 scripts/program_onboard.py capture <program> --evidence-dir <evidence_dir>
```

### 7. Input dialogue

Accept only:

- explicit input paths
- a manifest
- a user-approved bounded search root plus filename pattern and maxdepth

Do not infer inputs by scanning large directories.

### 8. Input preflight

Check by input type:

- FASTA: exists, non-empty, header style, `.fai` if needed
- FASTQ: exists, non-empty, pair naming, compression suffix
- BAM/CRAM: exists, non-empty, index if needed, reference compatibility
- VCF/BCF: exists, non-empty, header, index if needed, coordinate naming
- GFF/GTF/BED/TSV: exists, non-empty, column count, coordinate convention
- manifest: no unintended header for bundled SLURM templates unless the script
  explicitly handles one

Use metadata and small headers first. Avoid heavy decompression or full-file scans
unless the user accepts the cost.

### 9. Parameter negotiation

Ask only for parameters that affect:

- biological interpretation
- input compatibility
- output schema
- resource use
- rerun/overwrite behavior

Record defaults that matter for reproducibility.

### 10. Script generation

Generate a script instead of blindly running a long command. Include:

- strict shell mode
- environment proof
- input checks
- explicit output paths
- project-local temp paths
- version logging
- full stdout/stderr/time logs
- overwrite guards

When activating Conda under `set -u`, avoid shell activation failures from
unbound variables. Set required defaults first, temporarily relax nounset around
the activation block, then restore strict mode:

```bash
set +u
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate <env>
set -u
```

### 11. Safety gate

Before submission:

- run `bash -n <script>`
- run `scripts/prepare_submission.sh --script <script>` with manifest/input/output
  arguments when available
- use `scripts/slurm_preflight.sh --script <script>` only as a fallback when
  manifest/input/output context is not available yet
- include a `🧮 资源判断` for CPU, memory, partition, array concurrency, and
  whether the request fits the tool/input scale

Treat `FAIL` as a blocker. Explain `WARN` items before asking for submission.

### 12. Run, monitor, validate

Ask before `sbatch`. After completion:

- record job ID and logs
- inspect `sacct` when available
- validate expected outputs, non-empty files, schemas, counts, and summaries
- compare resource usage to the request before scaling

If the install strategy changes, for example from Conda to Singularity or source
build, update the generated run script and config before preflight so the actual
environment route matches what will run.

### 13. Persist

After a successful run, propose a new program card using `template.md`. Upgrade
evidence labels from `inferred` or `github_readme` to `local_help`, `local_run`, or
`project_history` only when the proof exists.

Before a successful run, generate only a draft:

```bash
python3 scripts/program_onboard.py draft-card <evidence_dir>
```

Drafts go to `references/program-cards/drafts/<program_key>.md` and are copied
back into the evidence bundle as `card_draft.md`. Do not register a draft in
`registry.tsv`. Move it to the active card directory and register it only after a
human review and at least one confirmed local pilot/run when `local_run` evidence
is claimed. Existing drafts are not overwritten unless `draft-card --force` is
used deliberately.
