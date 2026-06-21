---
name: bio-workflow
description: "规划、接管、实现、提交前检查、监控和验收 qgzeng 个人分析服务器上的生物信息学工作流。Use when working under /data9/home/qgzeng/projects on quinoa genomics, assembly, annotation, repeat, pan-genome, RNA-seq, GWAS, SNP/INDEL/SV, synteny, centromere, segmental duplication, genome structure, program-level tool execution, plotting, SLURM scripts, Singularity/Conda environments, raw-data downloads, CPU/memory estimation, job arrays, failure diagnosis, project resume/takeover, result validation, or reproducible reports. This skill emphasizes server-specific safety: no broad filesystem scans, no compute on admin2/login nodes, no wasteful CPU or memory requests, no external proxy for raw-data downloads, and no default SLURM --time except debug-style jobs when needed."
---

# Bio-workflow

## Mission

Plan and execute reproducible bioinformatics work on qgzeng's server without wasting shared resources. Start from the research question, explicit input paths, expected outputs, resource model, and validation criteria. Do not start by writing a command.

## Non-negotiable startup

Before substantive work:

1. Identify the active agent surface from the system/developer context, available CLI identity, or explicit user wording.
2. If using Codex, read:
   - `~/.codex/memories/user_output_format_preferences.md` (the active user's own Codex memories)
   - `~/.codex/memories/slurm_preferences.md`
   - the nearest `AGENTS.md` in the current directory or parent directories
3. If using Claude Code, read the nearest `CLAUDE.md` in the current directory or parent directories.
4. If the active agent is unclear, state that briefly and continue without loading agent-specific memory files by default.
5. If any required file for the active agent is missing or unreadable, state the missing item briefly and continue with available context.
6. Reply according to loaded output preferences; if they have no stronger preference, Chinese is the default for this user.

## Server safety boundaries

Use only explicit paths from the user or the current project. Keep probes narrow and cheap.

Use these lightweight probes freely when they answer the task:

- `pwd`, `hostname`, `df -h .`
- `sinfo`, `squeue -u "$USER"`, `sacct -j <jobid> --format=JobID,State,ExitCode,MaxRSS,Elapsed`, `scontrol show job <jobid>`
- `command -v <tool>`, `<tool> --version`, `<tool> -h`, or `<tool> --help`
- `rg`, `rg --files`, `find . -maxdepth N` scoped to the project
- `ls -lh`, `wc -l`, `head`, `tail`, `file` on explicit files
- `du -sh <explicit_project_or_output_path>` only for user-specified paths

Do not run broad scans such as `find /data9`, `find /data9/home/qgzeng`, unbounded `find` on large roots, `du -sh /data9/*`, `ls -R` on large directories, or full-file decompression/streaming over large FASTQ/BAM/VCF files unless the task requires it and the cost is explained. When the target is an unknown file, multi-file biological input, or data inventory, do not use recursive `find`/`grep`/`rg` to discover it by default. Ask for an exact path, manifest, filename pattern, or user-approved bounded root plus max depth. Targeted `rg`, `grep`, or `find -maxdepth` remain acceptable for explicit paths, small code/config/log directories, and known script or report targets.

Treat `admin2` as a login/admin node. On `admin2`, run only planning, script edits, syntax checks, light metadata checks, and SLURM control commands. Do not run aligners, assemblers, sorters, repeat annotation, pangenome tools, compression/decompression over large files, or full-data QC directly on `admin2`. If a command may use more than one CPU, run for more than about 3 minutes, stream large genomic files, or produce large output, route it through SLURM or ask before an interactive compute allocation.

## Permission and confirmation rules

Always apply the active agent's nearest project rule file first: `AGENTS.md` for Codex and `CLAUDE.md` for Claude Code. If it requires write disclosure or confirmation, follow it even for low-risk project files. If no applicable agent-specific project rule file adds stricter limits, use these defaults.

Low-risk actions inside the working project:

- read files and inspect small explicit inputs
- create or edit scripts, configs, manifests, reports, and small check files
- run syntax checks such as `bash -n`, R parse checks, or Python import/compile checks
- inspect queue state and existing logs

Require user confirmation before:

- `sbatch`, `scancel`, resubmission, or changing job concurrency
- starting high CPU, high memory, long-running, or large-I/O work
- installing, upgrading, removing, or changing Conda, modules, tools, or containers
- writing into the current user's `~/data/` or `~/tools/` (on this cluster, any `/data9/home/*/data|tools` is also protected)
- overwriting, moving, deleting, or replacing existing results
- changing formal analysis parameters after a plan has been agreed
- downloading large raw data

Before any write or job action, state purpose, logic, exact command or edit method, affected paths and approximate size, expected outputs, and risks including overwrite, disk, runtime, and queue impact.

## Project layout

Prefer this structure unless the project already has a stronger convention:

```text
project/
├── config/
├── data/       # symlinks or manifests only; raw data remains protected
├── scripts/
├── logs/
├── results/
├── reports/
└── tmp/
```

Use tab-separated tables for intermediate and final tabular outputs. Use English column names with initial capitals and underscores, for example `Gene_ID`, `Sample_Name`, and `Read_Count`.

## Reference routing map

Keep `SKILL.md` as the routing hub. Load detailed references only when their task is active:

- `references/resume-protocol.md`: use when taking over, checking, recovering, or validating an existing project. It defines project states, forbidden actions, and the `workflow_status.tsv` contract.
- `references/software-resource-cards.md`: use when estimating resources or writing commands for known tools. It gives per-tool modes, memory drivers, parallelism, red flags, and acceptance notes.
- `references/resource-feedback.md`: use for CPU/memory sizing, pilot or benchmark interpretation, partition choice, array concurrency, resource down-tuning, and serial-to-array audits. It supports `scripts/resource_usage_audit.sh` and `scripts/parallelization_audit.sh`.
- `references/executor-safety.md`: use for SLURM generation, conda activation PATH guards, preflight, submit gates, chunked array submission, array templates, and run recording. It supports `scripts/gen_sbatch.sh`, `scripts/slurm_preflight.sh`, `scripts/prepare_submission.sh`, `scripts/submit_and_log.sh`, and `scripts/submit_chunked.sh`.
- `references/validation-checklists.md`: use before interpreting completed results, before figures, before SLURM submission, after failures, and when a task has domain-specific acceptance gates.
- `references/operations-reporting.md`: use for failure monitoring details, raw-data downloads, qp mode, and plotting/reporting handoff details.
- `references/result-manifest-schema.md`, `references/interpretation-rules.tsv`, and `references/project-anchors.yaml`: use with `scripts/check_result_contract.py` when a result claim may affect a paper, downstream biology, or decision.
- `references/playbook-genome-annotation.md`: use for repeat annotation, evidence preparation, gene model prediction, functional annotation, release packaging, and annotation QC.
- `references/playbook-repeat-annotation.md`: use for TRF, RepeatModeler, EDTA, DeepTE refinement, RepeatMasker, solo LTR, TE density, TEsorter, and RT-domain repeat phylogeny workflows.
- `references/playbook-pangene-batch-annotation.md`: use for multi-accession or pan-gene genome annotation batches with per-sample directories, EviAnn, BRAKER3, AUGUSTUS, TransDecoder, SPALN3, and BUSCO/GFF3 aggregation.
- `references/program-cards/README.md` and specific cards: use when the request starts from a program/tool name.
- `references/program-cards/program-onboarding.md`: use only when no active card exists or the program needs discovery/proposal/capture.

Every new reference must be linked from this map or a task route below; do not create orphan references.

## Resume an existing project

When the user asks to continue, check, recover, validate, explain, or take over an existing project, do not plan from scratch. First decide the current project state, then take the smallest safe next step.

Use this read-only entry before task routing when project artifacts already exist or the request is ambiguous:

```bash
scripts/project_state_audit.sh --project <project_dir> --max-depth 3
```

Default to the current directory. Do not walk upward to parent roots or scan account/project roots unless the user confirms a deliberately broader audit. Add `--check-queue` only when audit evidence or user-provided context contains job IDs or SLURM log clues. This may call `squeue`/`sacct`, but it must not submit, cancel, resubmit, repair, or write status files.

Read `references/resume-protocol.md` when resuming a project. Classify one primary state:

- `Input_ready`: inputs or manifests exist, but no runnable workflow is ready.
- `Script_ready`: scripts exist and need preflight before submission.
- `Queued_or_running`: SLURM evidence shows work is pending, running, or incomplete.
- `Failed`: logs or accounting show a failed job or failed workflow step.
- `Complete_unvalidated`: outputs and completion logs exist, but result acceptance is missing.
- `Analysis_ready`: results have been validated and are ready for interpretation, plotting, or reporting.

Use this fixed response shape for resume work:

```text
📌 当前阶段
🔎 证据
⚠️ 阻塞
🛠️ 下一步最小动作
```

Minimum next actions:

- `Input_ready`: define missing manifests, methods, and success criteria.
- `Script_ready`: run `scripts/prepare_submission.sh --script <file>` when inputs/outputs are known, or `scripts/slurm_preflight.sh --script <file>` as the fallback. Always report a `🧮 资源判断` covering CPU, memory, partition, array concurrency, and whether the requested resources are justified by input size/tool behavior before asking about `sbatch`.
- `Queued_or_running`: monitor with `squeue`/`sacct`; do not edit scripts or resubmit while active.
- `Failed`: run `scripts/slurm_failure_triage.sh --jobid <id>` or `--err <file>`, then propose the smallest fix.
- `Complete_unvalidated`: run result acceptance from `references/validation-checklists.md` before biological interpretation.
- `Analysis_ready`: proceed with concrete validated evidence.

Do not write `reports/workflow_status.tsv` automatically. The audit script only prints a suggested TSV row; write it only after user confirmation.

## Program-level requests

Use this route before task routing when the user mainly names a program or tool instead of a complete biological task, for example "我要跑 BUSCO", "run SyRI", or "帮我用 minimap2 比对".

1. Normalize the program name and check `references/program-cards/`. Prefer:

   ```bash
   python3 scripts/program_card_lookup.py <program_name>
   ```

2. If a matching card exists, read `references/program-cards/README.md` and the card. Confirm mode, input type, output target, and result goal before writing commands.
3. If no card exists, read `references/program-cards/program-onboarding.md` and collect missing choices when install location, source, or pilot inputs are not fixed. If official Docker/Singularity/Apptainer images exist, prefer the container route before attempting a Conda `environment.yml` solve:

   ```bash
   python3 scripts/program_onboard.py choose <program_name>
   # When official container docs exist:
   python3 scripts/program_onboard.py choose <program_name> --default-source container
   ```

   In this chat UI, do not assume native pop-up controls. For local terminal use, run `choose` with curses/arrow keys, or `--plain`; it writes `config/program-onboarding/<program_key>_choice.json` under the current project by default. Use `--project-root <dir>` when invoking it from another directory.

4. Start third-version onboarding with:

   ```bash
   python3 scripts/program_onboard.py probe <program_name>
   ```

   If installation is needed, generate a proposal first, stop for user confirmation, then install only from the generated proposal. For official container routes, create a proposal-only record first and do not pull/build/run the image until a separate reviewed plan is confirmed:

   ```bash
   python3 scripts/program_onboard.py plan-install <program_name> --package <official_image_uri_or_tag> --source container
   python3 scripts/program_onboard.py plan-install <program_name> --package <package> --source conda
   python3 scripts/program_onboard.py install --proposal <install_proposal.json> --yes
   python3 scripts/program_onboard.py capture <program_name> --evidence-dir <evidence_dir>
   python3 scripts/program_onboard.py draft-card <evidence_dir>
   ```

   Do not install, download, write under `~/tools/`, submit SLURM, scan broadly, write onboarding evidence outside the project, or overwrite draft cards without explicit confirmation.

5. For any program-level run, follow: environment discovery -> input dialogue -> parameter confirmation -> script generation -> safety preflight -> user-confirmed submit/run -> acceptance checks. Report the level honestly: `L0=choice/intake`, `L1=probe`, `L2=install proposal`, `L3=installed+captured`, `L4=pilot script/preflight`, `L5=pilot/run validated`, `L6=active card`. Do not describe `probe` or `plan-install` as testing that the program can run.
6. Use `references/software-resource-cards.md` for resource estimates and `references/validation-checklists.md` for shared acceptance gates. Do not copy shared checks into cards unless a tool has extra acceptance rules.
7. Use the SLURM safety layer for generated jobs: `scripts/gen_sbatch.sh`, `scripts/slurm_preflight.sh`, `scripts/prepare_submission.sh`, and after user confirmation `scripts/submit_and_log.sh`. For arrays that exceed the submit cap, use `scripts/submit_chunked.sh` only as the safe chunked wrapper; it must re-enter the same submit gate. Read `references/executor-safety.md` for executor details.
8. If the user gives a full analysis objective rather than only a program name, use the relevant playbook below first, then load program cards for tool details.
9. After capture, keep generated cards in `references/program-cards/drafts/` until human review and a successful local pilot/run justify promotion. Only then move to the active card path, register it in `registry.tsv`, and use `local_run` or `project_history` evidence.

Known first cards:

- `references/program-cards/busco.md`
- `references/program-cards/minimap2-samtools.md`
- `references/program-cards/syri.md`
- `references/program-cards/biser.md`
- `references/program-cards/kmeria.md`

After editing program cards or the registry, run:

```bash
python3 scripts/validate_program_cards.py
python3 scripts/validate_program_cards.py --check-drafts
```

## Task routing

Pick the narrowest route before reading detailed references or writing scripts.

**De-novo genome pipeline:** ① survey → ② assembly → ③ scaffolding → ④ gap-fill & polish → ⑤ evaluation → ⑥ SV calling.

- **① Genome survey:** read `references/playbook-genome-survey.md`; route read QC and k-mer survey work here.
- **② Primary assembly + assembly QC:** read `references/playbook-genome-assembly.md`; for hifiasm/BUSCO/QUAST details also read `references/software-resource-cards.md` and `references/validation-checklists.md`.
- **③ Chromosome scaffolding:** read `references/playbook-chromosome-scaffolding-cphasing.md`; use C-Phasing for 3C data and RagTag for accessions without 3C data.
- **④ Gap-fill & polish:** read `references/playbook-genome-finishing.md`; reference individual only, with optional polishing.
- **⑤ Genome quality evaluation:** read `references/playbook-genome-quality-evaluation.md`; validate QUAST, Merqury QV, BUSCO, LAI, read mapping, telomeres, and optional BlobToolKit snail plot.
- **⑥a SV/synteny:** read `references/playbook-variant-synteny-syri.md`; for adding orthogonal evidence use the high-confidence playbook.
- **⑥b High-confidence SV:** read `references/playbook-high-confidence-sv-multicaller.md`; use SyRI + SVIM-asm + Sniffles2 evidence and uniform normalization.

**Genome structure umbrella:** analyses run on a finished, evaluated genome.

- **Centromere localization:** read `references/playbook-centromere-chipseq.md`; integrate CENH3 IP/Input, deepTools log2(IP/Input), TRASH 40-bp monomers, and HOR.
- **Segmental duplications:** read `references/playbook-segmental-duplications.md`; BISER route on a soft-masked reference.

Other routes:

- **Repeat annotation and masking:** read `references/playbook-repeat-annotation.md`; then use `EDTA`, `RepeatModeler`, `RepeatMasker`, `TRF`, `TEsorter`, `BUSCO`, and figure/checklist references as needed.
- **Annotation:** read `references/playbook-genome-annotation.md`; for multi-accession/pan-gene batches also read `references/playbook-pangene-batch-annotation.md`; then use the relevant software cards.
- **RNA-seq:** read `fastp, FastQC, and MultiQC`, `STAR`, and `featureCounts`; confirm strandedness, paired-end naming, and index reuse.
- **Read-based / population SNP-INDEL-SV:** read `bcftools and GATK`; confirm reference compatibility and chromosome names.
- **Pangenome/orthology:** read `OrthoFinder`, `PanGenie`, and search-tool cards; estimate database/output growth and array concurrency.
- **K-mer GWAS / KMERIA:** read the `KMERIA` card; run a format-compatibility pilot before scaling and treat wrapper warnings about `count`/`kctm` formats as blockers.
- **Downloads, qp mode, plotting, reporting:** read `references/operations-reporting.md` plus figure checks in `references/validation-checklists.md`.

## Result claims: source-of-truth policy

Before publication-grade or decision-changing claims, treat the skill's interpretation layer as constraints, not as biological conclusions. Authority order:

1. Local manifest / observed tool output for this run.
2. Project anchors in `references/project-anchors.yaml`, only within declared `scope`.
3. Method papers / official tool docs for metric applicability and provenance fields.
4. Model common knowledge, last and never overriding 1-3 silently.

Rule strengths in `references/interpretation-rules.tsv`:

- `BLOCK`: do not make the constrained claim unless higher-grade local evidence invalidates the rule. State the rule_id and what would lift it.
- `WARN`: claim is allowed only with the explicit caveat carried into the narrative.
- `SUGGEST`: next-step hint; not evidence by itself.
- `NOTE`: provenance reminder; report the field.

When a result manifest exists, run the checker before any publication-grade or downstream-biology claim:

```bash
python3 scripts/check_result_contract.py --manifest <result_manifest.yaml>
```

Treat `BLOCKED CLAIMS` as veto and `WARNINGS` as required caveats. Never silently downgrade or override a rule. The contract details per stage live in each playbook's `### Evaluation contract` block.

### Auto-trigger phrases for the claim checker

The checker is cheap and guards against silent claim drift. Run it against the relevant `result_manifest.yaml` before finalizing an answer when the user's request or your draft response contains any of these patterns. Rerun if the manifest path changed.

- Publication / decision-grade language: "publication-grade", "for the manuscript", "report Methods", "Table 1", 发表, 论文 Methods, 投稿, 正式报告.
- Cross-comparator language with concrete metrics, assemblies, lineages, haplotypes, or biological comparison: "compare across", "better than", "best assembly", "vs hap1/hap2", "vs previous version", "improved over", 比之前好, 比 hap1 高, 跨 lineage, 跨 haplotype.
- Headline metric claims: "QV improvement", "BUSCO went up", "LAI grade", "completeness reaches", "reference-quality assembly", "T2T-level", QV 提升, BUSCO 提升, LAI 等级, 完整性达到, 参考级, T2T 级.
- Cross-scope mixing: a non-quinoa species name appears with numbers from `references/project-anchors.yaml` `quinoa_project` scope, or vice versa.

Do not trigger for pure tool-usage questions, SLURM failure debugging, file listing, manifest schema discussion, or repeating an already checked result in the same answer with the same manifest path.

After running the checker, also append an audit row:

```bash
bash scripts/log_claim_audit.sh --manifest <path> --job-id <id_or_NA>
```

## Workflow

### 1. Define the task

Record:

- research question and biological purpose
- organism, reference version, samples, groups, and replicate design
- exact input paths and file types
- expected outputs and final deliverables
- method preferences or constraints
- success criteria and failure conditions

If key biological or experimental information is missing, list missing items instead of inventing assumptions. Do not convert missing design context into hidden defaults.

### 2. Build a narrow input inventory

Inspect only explicit inputs. Prefer metadata and indexes over reading full files:

- FASTQ: use file sizes and file names first; avoid full decompression unless needed.
- FASTA: use `.fai` if present; creating a new index writes a file, so state impact first. For multi-genome input builders, do not stream full FASTA bodies on login/admin nodes just to count bases; use existing indexes/metadata, or route the indexing/counting cost through a confirmed SLURM precheck.
- BAM/CRAM: use `.bai/.crai` and `samtools idxstats` only when indexes exist and the tool is available.
- VCF/BCF: use header, tabix index, and small targeted regions when possible.
- GFF/GTF/BED/TSV: use `head`, `wc -l`, and format-specific sanity checks on explicit files.

For unknown or multi-file inputs, build the inventory from a user-provided manifest,
explicit paths, or a user-approved bounded search plan. Do not recursively scan
project roots, parent directories, or `$HOME` to infer biological inputs.

Stop and warn if files are missing, empty, inconsistent, damaged, or biologically ambiguous.

### 3. Discover tools without installing

Check tools in this order:

1. current `PATH`
2. active Conda environment
3. known Conda environments only when explicitly named or cheap to inspect
4. cluster module system if available
5. project or user tool paths when explicitly provided
6. Singularity images when explicitly provided or already used by the project
7. installation only after user confirmation

Record tool versions and exact commands used for reproducibility. If a tool is missing, use program onboarding; do not infer install commands from memory.

### 4. Estimate resources

Do not request CPU or memory by habit. Start from input size, algorithm memory model, thread scalability, temporary expansion, per-thread memory, array concurrency, current queue state, and previous job history.

Read `references/resource-feedback.md` for:

- CPU/memory reasoning pattern
- pilot and `/usr/bin/time -v` interpretation
- resource down-tuning from `Percent of CPU` and `MaxRSS`
- partition choice
- array concurrency
- serial-to-array audits

Read `references/software-resource-cards.md` when the task involves minimap2, samtools sort, SyRI, OrthoFinder, EDTA, HiTE/panHiTE, Nextflow workflow drivers, RepeatModeler, STAR, featureCounts, PanGenie, BLAST, DIAMOND, HMMER-family searches, hifiasm, Juicer/3D-DNA, BRAKER/MAKER, bcftools/GATK, fastp/FastQC/MultiQC, MUMmer/plotsr, BUSCO, QUAST, KMERIA, or BISER. Use cards as starting points, then adjust with explicit input size, queue state, and `sacct`.

When uncertain, propose a small pilot or benchmark before the full run. Do not keep high CPU requests because a template used them.

### 5. Choose SLURM resources

Use queue and memory evidence, not a fixed template.

- `< 200G` memory: prefer `normal`, usually up to about 16 CPUs.
- `>= 200G` memory: consider `fat` or `fat2`, often 16-32 CPUs, after checking queue state.
- `debug`: use only tiny tests, dry runs, and fast validation. A short `--time` is acceptable here when helpful or required.
- `high`: use only when user/project policy or queue state justifies it.
- unknown memory: ask or run a bounded pilot; do not guess with maximum resources.

Do not add `#SBATCH --time` by default for `normal`, `fat`, `fat2`, or `high`. If an existing script has a short walltime, warn that it may cause `TIMEOUT`. Add or keep `--time` only when the user explicitly asks, cluster policy requires it, or the job is a debug-style test.

Use job arrays for independent samples, but always set a concurrency cap such as `%2`, `%4`, or `%5`. Choose the cap from combined memory, disk I/O, database contention, and current queue pressure.

### 6. Write robust scripts

Read `references/executor-safety.md` when generating or reviewing SLURM scripts. Prefer:

```bash
scripts/gen_sbatch.sh --job-name NAME --cpus N --mem SIZE --log-dir ABS_DIR [--partition P] [--array RANGE] [--manifest FILE] [--cmd 'COMMAND'] [--conda-env ENV [--conda-check pysam]] [--out FILE]
```

Preserve:

- strict mode: `set -euo pipefail`
- absolute `%j_%x` logs
- CPU forwarding through `THREADS=${SLURM_CPUS_PER_TASK}`
- protected-path guards
- conda activation PATH guard + python self-check when a conda env is used (or `gen_sbatch.sh --conda-env`)
- full stderr and `/usr/bin/time -v` logs
- clear rerun behavior
- no default `#SBATCH --time`

Avoid unguarded display-only pipelines such as `ls ... | head`, `find ... | head`, or `tool ... | head` under `pipefail`. If a preview is only diagnostic, guard it with `|| true` or write a bounded loop.

### 7. Preflight before submitting

Read `references/executor-safety.md` for the full gate. Run:

```bash
scripts/prepare_submission.sh --script <slurm_script> [--manifest <manifest.tsv>] [--input-list <filelist.txt>] [--output <output_dir>] [--mode <partition>] [--conc <N>]
```

Hard blockers include preflight `FAIL`, missing/empty inputs, bundled-template manifest headers, protected `--output`, and quota submit-cap overrun. Warnings include preflight `WARN`, non-empty output directories, and unknown quota/header status.

Every SLURM script review must include a simple resource assessment, even when the user only asks for "review". Do not stop at "CPU/memory directives exist". In the answer, include `🧮 资源判断` with:

- whether `--cpus-per-task`, `--mem`, and `--partition` match the tool class and input size
- whether the tool can use the requested CPUs
- whether memory is unknown, too low, too high, or requires a pilot
- whether array concurrency fits per-task memory and disk/database pressure
- whether `normal` vs `fat/fat2` follows the `<200G` / `>=200G` rule

If unavailable, run:

```bash
scripts/slurm_preflight.sh --script <slurm_script>
```

Treat any `FAIL` as a blocker and `WARN` as an item to explain before submission. Lightweight resource-sanity WARNs are not proof of failure, but they must be answered with evidence, a smaller pilot, or a corrected request. If preflight warns about serial independent tasks or high CPUs not being passed to the tool, run:

```bash
scripts/parallelization_audit.sh --script <slurm_script> --manifest <manifest.tsv> --mode auto
```

Submit only after user confirmation. For confirmed submission and run records, use:

```bash
scripts/submit_and_log.sh --script <slurm_script> [gate options] [--record FILE] [--yes]
```

For arrays that exceed the submit cap, do not call `sbatch --array` directly.
Use the dry-run-first chunked wrapper:

```bash
scripts/submit_chunked.sh -s <slurm_script> -N <tasks> -k <chunk_size> -j <cap> [gate options] [--yes]
```

It must materialize per-chunk scripts under the current project by default and
delegate to `submit_and_log.sh`.

### 8. Monitor and diagnose

Read `references/operations-reporting.md` for monitoring and failure-diagnosis details. Record job ID, scripts, configs, resources, submit time, logs, accounting, failure type, and the smallest justified fix. Ask before resubmitting.

### 9. Validate results in layers

Read `references/validation-checklists.md` for the relevant acceptance gate. Do not treat exit code 0 as success. Validate run layer, data layer, analysis layer, reproducibility layer, and biological layer. For quinoa work, connect interpretation to plausible biology only as hypotheses unless experimentally validated.

### 10. Download raw data safely

Read `references/operations-reporting.md` before large downloads. Do not use external proxies for raw data unless explicitly confirmed. Confirm destination, expected size, staging location, checksums, and protected-path implications first.

### 11. Use qp mode when appropriate

Read `references/operations-reporting.md` for the qp pattern under `/data9/home/qgzeng/projects/2-C_quinoa/12-jobs/`. Do not change `MAX_PARALLEL` for large-memory jobs without confirmation.

### 12. Plot and report

Read `references/operations-reporting.md` and `references/validation-checklists.md`. Save plotting data, code, parameters, and figure legends. Report what the figure proves and what it does not prove.

## Skill maintenance

`SKILL.md` is the single official entry point; the skill loader reads only this file before references are requested. Keep `SKILL.md` as the routing hub and move long detail into directly linked references.

## Functional-equivalence guardrails

When slimming or reorganizing this skill, preserve behavior before reducing line count. A change is not acceptable if it weakens any of these:

- trigger coverage in the frontmatter `description`
- agent-specific startup memory and project-rule checks
- narrow-scan policy and login/admin node limits
- protected path rules for the current user's `~/data/` and `~/tools/` (and any `/data9/home/*/data|tools`)
- user confirmation before `sbatch`, `scancel`, resubmission, install, large download, high-resource work, overwrite, or protected write
- resume route through `project_state_audit.sh` and `references/resume-protocol.md`
- program-level route through program cards and onboarding
- task routing to playbooks and software cards
- result-claim gate through `check_result_contract.py`, auto-trigger phrases, and `log_claim_audit.sh`
- SLURM safety layer through `gen_sbatch.sh`, `slurm_preflight.sh`, `prepare_submission.sh`, `submit_and_log.sh`, and `submit_chunked.sh`
- validation gate through `references/validation-checklists.md`

If content is moved out of `SKILL.md`, ensure the destination reference is linked from `Reference routing map`, from a task route, or from the relevant workflow step. Do not create orphan references.

Before declaring a slimming pass complete, verify:

- `SKILL.md` line count is near 450-500 unless there is a documented reason.
- every moved behavior has an explicit route to a reference.
- all scripts named in `SKILL.md` still exist.
- source and installed `.codex` copies have been synchronized when runtime behavior should change.

Run after structural changes:

```bash
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
```

Run `bash -n` for bundled shell script changes. For `scripts/slurm_preflight.sh`, test at least one passing script and one failing script before trusting rule changes. After editing program cards or registry, run `python3 scripts/validate_program_cards.py` and `python3 scripts/validate_program_cards.py --check-drafts`.

After source edits that should affect Codex runtime behavior, sync the installed copy at `~/.codex/skills/bio-workflow` with:

```bash
scripts/sync_install.sh --yes
```

The script validates source and installed skill and reports the remaining source-vs-installed differences.

## Default response shape

Use this compact Chinese structure only when the user's memory or the current
request asks for a compact workflow/status response. Do not enforce it when
`user_output_format_preferences.md` or the user's latest instruction prefers a
different style.

```text
📌 结论
🔎 已确认
⚠️ 风险
🧮 资源判断
🛠️ 将执行/已执行
✅ 验收
▶️ 下一步
```

Keep tables short. Prefer clear bullets with concrete paths, commands, job IDs, and validation criteria.
