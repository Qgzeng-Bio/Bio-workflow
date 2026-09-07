# Publication claim traceability and release freeze

Use this contract when a layout-v2 project begins manuscript writing, maps accepted claims into text or figures, prepares coauthor review, or freezes a submission/revision release.

The purpose is to make one stable chain mechanically checkable:

```text
result_manifest Claim_ID
  -> Analysis_Key:Version_ID
  -> Analysis_Key:Figure_ID
  -> exact figure-package source-data TSV
  -> one manuscript Markdown anchor
  -> one immutable release manifest and frozen artifact copy
  -> Git commit/tag
```

This layer does not decide biological truth. `config/result_manifest.yaml` and `check_result_contract.py` remain the authority for scientific support. It does not replace `Version_Index.tsv`, `Figure_Index.tsv`, acceptance records, project records, or Git history.

## Minimal paper layout

Create a paper package only after the user selects a Paper ID and scope:

```text
manuscripts/P01-genome/
├── Manuscript.md
├── Claim_Evidence_Map.tsv
├── supplement/
├── references/
└── releases/
    └── R01/
        ├── Release_Manifest.yaml
        └── files/
```

Do not let `init_project.sh` guess `P01`, manuscript scope, title, figure order, or release ID. Ordinary project initialization creates only `manuscripts/README.md`. Creating a paper package remains a separately disclosed project write.

## Existing authorities remain unchanged

Do not change these existing headers merely to add publication links:

```text
# results/<module>/Version_Index.tsv
Version_ID	Parent_Version	Status	Selected	Input_Manifest	Parameter_File	Script_Commit	Result_Path	Acceptance_Path	Notes

# results/<module>/figures/Figure_Index.tsv
Figure_ID	Figure_Title	Figure_Directory	Source_Result	Plot_Script	Status	Manuscript_Target	Notes
```

Cross-layer links live only in `Claim_Evidence_Map.tsv`. Do not add a duplicate Source Table Index or Manuscript Status TSV.

## Claim_Evidence_Map.tsv

Exact header:

```text
Schema_Version	Paper_ID	Claim_ID	Manuscript_Path	Figure_Refs	Source_Table_Paths	Version_Refs	Mapping_Status	Notes
```

Field contract:

- `Schema_Version`: `claim_evidence.v1`;
- `Paper_ID`: stable `P01`, `P02`, ... and must match the containing `P01-*` directory;
- `Claim_ID`: unique in this map and present in `config/result_manifest.yaml`;
- `Manuscript_Path`: project-relative POSIX path inside the current paper directory;
- `Figure_Refs`: semicolon-separated `Analysis_Key:Figure_ID` values, or `NA`;
- `Source_Table_Paths`: semicolon-separated project-relative TSV paths, or `NA`;
- `Version_Refs`: semicolon-separated `Analysis_Key:Version_ID` values, or `NA`;
- `Mapping_Status`: `Draft`, `Reviewed`, or `Frozen`;
- `Notes`: human context only; never a replacement for machine relationships.

Semicolon is the only multi-value separator. Duplicate values, empty list items, commas used as list separators, absolute paths, `..`, symlinks, external paths, and any `tmp` path are invalid.

The map is a relationship table, not a second result manifest. It does not copy claim text, protocol, caveats, evidence status, or numerical results.

## Manuscript anchors

Immediately before the primary paragraph for one mapped claim, add:

```markdown
<!-- bioflow-claim: ASM_QV_COMPARE_001 -->

The selected assembly showed a higher QV than the comparator under the same
k-mer and read-database protocol.
```

Rules:

- one map row has exactly one primary anchor in its declared Markdown file;
- one Claim ID cannot have multiple primary anchors;
- an anchor without a map row is invalid;
- a map row without an anchor is invalid when Reviewed/Frozen;
- Draft may temporarily lack an anchor but must remain WARN/not release-ready;
- secondary mentions use normal prose or cross-references, not duplicate anchors;
- no NLP or fuzzy text matching is used to infer claims;
- if the bounded Markdown scan reaches depth 5 with unchecked content remaining, audit BLOCKs rather than asserting anchor uniqueness from a truncated inventory.

## Claim support

The publication layer reads, but does not reimplement, the result contract:

- Draft mapping may reference `uncertain` evidence only with WARN;
- Reviewed/Frozen mapping requires the manifest claim to be `supported` and the existing claim checker to have no applicable BLOCK/UNCERTAIN;
- a supported manifest claim not used in this paper is allowed and should be reported only as optional context;
- deleting analysis types or claim evidence to obtain PASS is forbidden.

## Version references

A reference such as `assembly:V01` resolves to:

```text
results/NN-assembly/Version_Index.tsv -> Version_ID=V01
```

Rules:

- the Analysis Key must identify exactly one result module;
- the Version ID must exist and `Result_Path` must resolve exactly to that module's `versions/<Version_ID>` directory, with no symlink component; a different existing directory is not version evidence;
- Reviewed mappings require `Validated` or `Frozen` versions;
- Frozen mappings require `Selected=Yes`; a merely `Validated` version may be a release WARN until intentionally frozen;
- multiple modules may each have `V01`, so bare `V01` is forbidden.

## Figure and source-table references

A reference such as `assembly:F001` resolves to:

```text
results/NN-assembly/figures/Figure_Index.tsv
  -> Figure_ID=F001
  -> figures/F001_Name/
```

`Figure_Directory` must be a single valid `FNNN_Name` basename whose F-ID matches the referenced Figure ID. It must resolve under that analysis module's `figures/`, with no symlink component. Absolute paths, another module's package, and F-ID aliases are not accepted even at Reviewed stage.

Every referenced figure must have at least one explicit, valid mapped source table of its own; one table for F001 does not cover F002 on the same row.

A mapped source table must:

- be a readable non-symlink `.tsv` regular file;
- be located below the referenced figure package's `source-data/` directory;
- contain true tab-separated columns, a header, and at least one data row; every data row must match the header width, within the 10 MiB / 100,000 data-row limits;
- be explicitly listed in `Source_Table_Paths`;
- not resolve outside the project or under any `tmp` segment.

Draft figure mapping may be incomplete with WARN. Reviewed mapping requires a `Manuscript_ready` or `Frozen` figure and a non-NA `Manuscript_Target`. Frozen release requires figure status `Frozen`.

## Release_Manifest.yaml

One release has one authority file:

```text
manuscripts/P01-genome/releases/R01/Release_Manifest.yaml
```

Schema is `bioflow.release.v1`. Required top-level keys are:

```yaml
schema_version: bioflow.release.v1
paper_id: P01
release_id: P01-R01
status: Draft
release_date: null

git:
  source_commit_sha: null
  release_tag: null

authorities:
  result_manifest: config/result_manifest.yaml
  claim_evidence_map: manuscripts/P01-genome/Claim_Evidence_Map.tsv
  manuscript_source: manuscripts/P01-genome/Manuscript.md
  acceptance_path: docs/validation/Acceptance_Report.md
  rerun_entrypoint: scripts/01-assembly/run_workflow.sh

selected:
  claims: []
  versions: []
  figures: []

artifacts: []
checklist: {}
known_limitations: []
```

Release status is `Draft` or `Frozen`. Draft may retain null/false placeholders and is never publication-ready. Frozen requires:

- Paper/Release IDs and date;
- full 40-character lowercase source commit SHA and non-empty release tag;
- readable project-local authorities and rerun entrypoint;
- selected Claim/Version/Figure sets equal to the traceable publication closure;
- every manuscript, figure, source table, required supplement, and delivery artifact listed once;
- every artifact entry has a stable `A001` ID, role, canonical path, release path, and lowercase SHA-256;
- release paths stay below the current `releases/RNN/files/` directory;
- release-file checksum matches; later canonical-file evolution does not invalidate the frozen copy;
- frozen and canonical artifacts exceeding the 100 MiB bound are blocked before content hashing; unreadable or invalid canonical artifacts are not hashed;
- supplement root and internal symlinks are rejected, never silently omitted from release closure;
- supplement and frozen `files/` inventories include hidden entries, reject non-regular entries, and BLOCK rather than silently truncating beyond depth 5 or 500 total entries (files and directories);
- actual files below the current release's `files/` directory equal the registered release-file set; unregistered, hidden, missing, or symlink files cannot be ignored;
- all checklist values true;
- `known_limitations` exists and contains no `UNKNOWN`/placeholder.

The release manifest does not hash itself, avoiding a self-referential checksum.

### Artifact entry

```yaml
- artifact_id: A001
  role: Manuscript
  canonical_path: manuscripts/P01-genome/Manuscript.md
  release_path: manuscripts/P01-genome/releases/R01/files/Manuscript.md
  sha256: 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
```

Version 1 supports exactly four roles with explicit closure authorities: `Manuscript`, `Figure`, `Source_Table`, and `Supplement`. Independent `Methods`, `Table`, and `Other` roles are not supported in v1. Extra deliverable files may be intentionally placed under the paper's `supplement/` and registered as `Supplement`; they must pass the same inventory, path, and checksum rules. Additional independent roles require a separately designed registration contract, not an exception allowing arbitrary extra artifacts.

## Checklist semantics

The v1 checklist keys are fixed:

```yaml
result_contract_required: true
structure_audit_required: true
records_audit_required: true
trace_audit_required: true
limitations_reviewed: true
sensitive_data_reviewed: true
licenses_reviewed: true
coauthor_approval_recorded: true
```

A boolean states that the named review was completed and its evidence remains resolvable; it does not prove scientific correctness by itself.

## Git and freeze safety

The trace auditor may run local read-only Git queries to verify that `source_commit_sha` exists and that `release_tag` resolves through the exact `refs/tags/<name>` namespace to a commit containing this exact Release Manifest path/content. A branch or HEAD is not a tag. Subsequent lookups are pinned to the resolved commit; each blob's type and size are checked before bounded content reads. Oversized or invalid local release files are excluded from Git content checks, even when earlier findings already BLOCK the release. The release tag does not need to equal the source commit: the source commit identifies the analysis/manuscript baseline, while the later tagged release commit can add the manifest and frozen copies. This avoids requiring a manifest to contain the hash of the commit that contains itself. The auditor must not fetch, checkout, create/delete tags, modify the index, commit, push, or access the network.

Freezing artifacts, creating a source baseline commit, writing/copying release files, committing the release package, creating a Git tag, and pushing are separate actions. Before each action, disclose exact paths/commands, expected files, overwrite/storage risks, repository/branch/remote, and obtain explicit approval.

## Read-only trace and release auditor

Use:

```bash
python3 scripts/publication_trace_audit.py --project /abs/project
python3 scripts/publication_trace_audit.py --project /abs/project --paper P01-genome --format json
python3 scripts/publication_trace_audit.py --project /abs/project --paper P01-genome --release R01 --check-git
```

The implementation joins result-manifest claims, retained versions, figures, source tables, manuscript anchors, and optional release manifests without writing files. Layout markers, result manifests, and referenced indexes have their full project-relative path components checked before content reads; a parent-directory symlink is not made safe by a regular final file. Exit codes are 0 PASS, 1 WARN, and 2 BLOCK/error. Draft and legacy behavior is conservative; absence of a manuscript directory is `TRACE_NOT_APPLICABLE`, not an error.

Within one paper audit, repeated module-index parses and source-table format checks reuse local results (including error text). Path safety and current figure ownership are still checked for every reference, and each claim generates its own findings at its current Mapping_Status severity. Nothing is cached across audit calls or written as a cache file; this is not a concurrent filesystem snapshot guarantee.

A missing or header-only Claim Evidence Map is a WARN only when no selected or existing Frozen release requires it. If a release is explicitly selected, or an existing release is Frozen, either missing or empty mapping is BLOCK even without `--check-git`. An early missing-map return must not silently downgrade release requirements.

YAML metadata (including result/release manifests) and acceptance text are limited to 2 MiB. Manuscript text retains its 2 MiB bound; artifacts and historical Git artifact blobs retain the 100 MiB bound. Files that exceed a limit are rejected rather than loaded or hashed in full. Before invoking prerequisite audits, also check the layout's canonical acceptance path, even when the release declares a different authority. Known unsafe or oversized acceptance metadata blocks that release before prerequisite content checks, rather than allowing a downstream re-read.

A Frozen release additionally enforces exact selected Claim/Version/Figure closure, prerequisite structure/records audits without WARN/BLOCK, accepted evidence, rerun entrypoint, complete checklist/limitations, frozen artifact copies and SHA-256. `--check-git` performs local read-only source-commit, release-tag, tagged-manifest, and tagged-artifact verification; it never fetches or mutates Git.

## Legacy compatibility

- legacy projects without `config/Project_Layout.tsv` are not automatically enrolled;
- a layout-v2 project without a `manuscripts/P*-*` paper directory is not applicable, not failed;
- existing Figure/Version indexes keep their current schemas;
- no paper directory, map, anchor, release, copy, checksum, tag, commit, or push is created automatically;
- result-manifest v1 or unknown claim coverage cannot produce a Frozen release.
