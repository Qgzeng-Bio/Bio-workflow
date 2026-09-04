# Git/GitHub collaboration for Bioflow projects

Use this contract when initializing a Git-backed project, reviewing changes, connecting analysis to a manuscript, freezing results, preparing a Pull Request, or planning a GitHub release. Read `references/project-layout.md` first.

## Purpose

Git records the reviewable project spine:

```text
question -> input identity -> plan -> scripts/config -> accepted results
         -> figure/source table -> claim -> manuscript -> commit/tag
```

GitHub adds access-controlled collaboration, Issues, Pull Requests, diff review, and milestones. Neither Git nor GitHub replaces HPC storage, institutional backup, data governance, or ethics review.

## Track versus exclude

Normally track:

- `README.md`, `PROJECT_STATUS.md`, `CHANGELOG.md`, `.gitignore`, `.github/`;
- small non-sensitive text under `config/`;
- scripts, workflows, plotting code, and environment/container descriptions;
- plans, research logs, decisions, methods, validation, and delivery records under `docs/`;
- Markdown/LaTeX/BibTeX manuscript sources and release manifests;
- compact TSV source tables and reviewed figures when size/licence/policy allow.

Normally exclude:

- `rawdata/` contents except its explanatory README;
- `logs/`, `tmp/`, `.snakemake/`, `.nextflow/`, `work/`, caches, and environment directories;
- FASTQ, BAM, CRAM, large VCF/FASTA/indexes/databases and large reproducible intermediates;
- credentials, `.env`, tokens, keys, controlled human data, and unapproved collaborator data.

A private repository is access control, not proof of ethical, legal, contractual, or institutional compliance. `.gitignore` is not a security boundary and does not erase an already committed secret.

## Read-only Git safety gate

Before staging or requesting a commit review, run:

```bash
python3 scripts/git_project_audit.py --project /abs/project
```

Use `--staged-only` when reviewing exactly the current staged set. The audit does
not run `git add`, commit, push, fetch, clone, tag, reset, checkout, clean, or any
network command. It reads only Git metadata and bounded worktree file metadata.

Its stable outcomes are:

- `PASS`: reviewable code/config/Markdown/TSV candidate;
- `WARN`: binary/bioinformatics delivery file or >=50 MiB file needs human review;
- `BLOCK`: rawdata, runtime/cache path, raw/alignment file, credential/private-key
  heuristic, unsafe symlink, or >=100 MiB candidate;
- exit 0/1/2 means PASS/WARN/BLOCK respectively.

Treat it as a preflight heuristic, not an ethics review or full secret scanner.
A `BLOCK` requires removing the file from the Git index and retaining a manifest,
checksum, external storage pointer, or another approved route. A `WARN` must be
explained before intentionally staging the file.

## Daily change cycle

1. Start from a reviewed main baseline; inspect `git status` before changing files.
2. Use one branch for one bounded scientific, figure, validation, or writing intent.
3. Run/validate work through the normal Bioflow gates.
4. Update the research or decision record and affected Claim/Figure/Version indexes.
5. Inspect `git diff` and `git diff --cached`; stage explicit paths rather than habitual `git add .`.
6. Commit one coherent intent with a useful prefix such as `analysis:`, `data:`, `figure:`, `methods:`, `writing:`, `fix:`, or `docs:`.
7. Use a Pull Request for evidence review before merging important scientific changes.

Do not automatically run `git init`, `git add`, commit, push, merge, tag, history rewrite, LFS setup, repository creation, or PR creation. These are separately disclosed actions; network publication and history-changing operations require exact target/impact review and approval.

## Human records and machine authorities

- `PROJECT_STATUS.md` is a concise human landing page. The machine authorities remain `docs/status/workflow_status.tsv` and `Task_Status.tsv` in layout v2.
- `docs/research-log/` records why an analysis/interpretation changed. `logs/` records what programs/schedulers emitted.
- `config/result_manifest.yaml` decides whether a scientific claim is supportable under active checks.
- A manuscript `Claim_Evidence_Map.tsv` maps that stable Claim ID to manuscript text, figures, source tables, scripts, review, and release state. It must not silently redefine scientific support.
- `Version_Index.tsv` and `Figure_Index.tsv` record selected versions and figure state. Git history does not replace these identities for server-side results.

## Claim and manuscript traceability

Use stable IDs across layers:

```text
Analysis_Key -> Module_ID -> Task_ID -> retained output
             -> Claim_ID -> Figure_ID/Table -> manuscript section -> commit/tag
```

Abstract-level and strong comparative/mechanistic claims require explicit Claim IDs and accepted evidence. Association, overlap, enrichment, and prediction are not causation. Unsupported statements are downgraded, blocked, or labeled hypotheses.

Markdown/LaTeX/BibTeX are preferred editable sources because Git can show meaningful diffs. Word/PDF/Excel are delivery exports; keep their text/tabular sources and bind frozen exports to a release manifest.

## Pull Request review

An important analysis or paper PR should state:

- question and rationale;
- Analysis_Key, Module_ID, Task_ID, Claim_ID, and affected figures/tables/sections;
- exact input/reference versions and changed scripts/parameters;
- retained outputs and acceptance evidence;
- what the change supports and cannot support;
- overwrite, privacy, licensing, large-file, and reproducibility risks.

Review the staged diff, actual rendered figures, source-table consistency, Methods, and claim wording. Exit code 0 alone is insufficient.

## Freeze and release

Use annotated tags for meaningful scientific/manuscript milestones rather than `final_v2` filenames. A frozen submission release records:

- tag and commit SHA;
- scope/version/date;
- selected Version IDs and Figure IDs;
- manuscript, figures, tables, supplement, checksums, and storage locations;
- acceptance and claim-check status;
- known limitations and rerun entry point.

Do not silently replace a frozen artifact. Corrections or revisions become a new commit/tag and retain the reason for change.

## Safe first setup

For a new/empty directory, preview the v2 skeleton:

```bash
scripts/init_project.sh --project /abs/project --workspace-steward
```

For an existing reviewed Git root, opt into v2 explicitly with `--layout-v2`. After normal write disclosure/confirmation, add `--yes`. This writes only missing local templates; it does not initialize Git or contact GitHub.

Before a first publication, inspect staged files and repository policy manually. Do not upload until raw/sensitive data, credentials, large files, licences, repository visibility, and collaborator access have been reviewed.
