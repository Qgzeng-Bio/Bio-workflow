# Manuscripts

Create one stable directory per paper only when writing begins and only after the user selects its identity and scope, for example `P01-genome`.

A paper package uses:

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

Templates are available in the Bioflow Skill assets, but ordinary `init_project.sh` intentionally does not create `P01-*` directories or guess Paper/Release IDs.

Keep Markdown/LaTeX/BibTeX source, claim mapping, supplement, and release manifests here. Do not maintain a second changing copy of analysis figures: reproducible figure packages stay under the owning `results/<module>/figures/`; submission snapshots are created only at an explicit reviewed release.

Read `references/publication-traceability.md` before creating a Claim Evidence Map, adding manuscript claim anchors, or freezing a release. These are persistent writes and require the normal disclosure/confirmation flow.
