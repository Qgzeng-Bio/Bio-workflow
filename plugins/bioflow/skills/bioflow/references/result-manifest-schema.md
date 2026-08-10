# Result manifest v2 — claim-specific contract

`scripts/check_result_contract.py` gates a **declared claim**, not the mere
presence of a metric block. The current schema is:

```yaml
schema_version: result_manifest.v2
```

A `PASS` means every explicit claim selected a concrete subject set, a matching
protocol, complete required provenance, and readable cited evidence. It does not
replace technical or biological review.

## Top-level shape

```yaml
schema_version: result_manifest.v2
analysis_id: quinoa_v2_evaluation
project: quinoa_project
created_at: 2026-08-10T12:00:00Z
created_by: bioflow
analysis_types: [assembly_evaluation]

assemblies:
  - key: asm1
    role: primary
    fasta: results/asm1.fa
    total_length: 1271319056
    contig_N50: 70111769
    scaffold_N50: null
    misjoin_validated: false

busco:                         # multiple lineages per assembly are legal
  - assembly_key: asm1
    lineage: embryophyta_odb12
    mode: genome
    db_version: "2025-07-01"
    busco_version: "6.0.0"
    n_busco: 2026
    C: 99.7
    S: 3.3
    D: 96.4
    F: 0.0
    M: 0.3

merqury:
  - assembly_key: asm1
    k: 21
    read_db_type: hifi
    coverage: 70.0
    independence: false
    QV: 63.2366

lai:
  - assembly_key: asm1
    LAI: 16.09
    total_LTR_RT_pct: 50.0
    intact_LTR_RT_pct: 2.0

mapping:
  - assembly_key: asm1
    read_type: hifi
    rate_pct: 100.0

telomere:
  - assembly_key: asm1
    repeats: 36
    expected: 36

sv:
  callers:
    - name: Sniffles2
      evidence_axis: read
    - name: SyRI
      evidence_axis: assembly

claims: []
```

`analysis_types` currently covered here are `assembly_evaluation`,
`kmeria_association`, `sv_confidence`, `rnaseq_differential_expression`,
`population_variant_calling`, and `gwas`. An unknown or overly broad type returns
`UNCERTAIN`; omitting it cannot turn absent coverage into `PASS`. In particular,
generic `rnaseq` remains uncertain until differential expression, quantification,
or another explicit mode is selected.

## Claim interface

Every v2 claim has these machine-checked fields:

```yaml
claims:
  - claim_id: ASM_QV_COMPARE_001
    claim_type: metric_observation | metric_comparison | assembly_quality_overview | sv_high_confidence | rnaseq_differential_expression | population_variant_calling | gwas
    metric: N50 | BUSCO | QV | LAI | mapping | telomere | SV | assembly_quality
    subjects: [asm1, asm2]
    protocol:
      lineage: embryophyta_odb12  # BUSCO / overview
      mode: genome
      k: 21                       # QV / overview
      read_db_type: hifi
      n50_type: contig_N50        # N50 / overview
      mapping_read_type: hifi     # overview; metric-only mapping uses read_type
    evidence_paths:
      - ../results/QV_Summary.tsv
    status: supported | uncertain | blocked
    caveats: []
```

Relative `evidence_paths` resolve against the **manifest directory**, not the
shell working directory. A `supported` claim whose cited path is absent,
unreadable, or not a regular file is `BLOCK`. Only paths explicitly listed in the
manifest are checked; the checker never scans surrounding directories.

Claim cardinality:

- `metric_observation`: exactly one subject;
- `metric_comparison`: at least two subjects;
- `assembly_quality_overview`: one or more subjects, each with all six axes;
- `sv_high_confidence`: one or more comparison subjects and orthogonal SV axes.

Claim IDs must be unique. `subjects`, `protocol`, `evidence_paths`, `status`, and
`caveats` are never inferred from narrative prose.

## Metric gates

### BUSCO

A selected record requires `lineage`, `mode`, `db_version`, `busco_version`,
`n_busco`, `C`, `D`, `F`, and `M`. The same manifest may store several lineages.
Only a `metric_comparison` is blocked when every subject cannot supply exactly one
record for the claim-selected `protocol.lineage + protocol.mode`.

### Merqury QV

A selected record requires `k`, `read_db_type`, `coverage`, `independence`, and
`QV`. A comparison must match both `protocol.k` and
`protocol.read_db_type`; otherwise ranking is blocked. HiFi-on-HiFi or another
non-independent truth set remains `WARN`, and the claim must carry an explicit
non-independence caveat.

### N50

An assembly may legally store both `contig_N50` and `scaffold_N50`. Every N50
claim must choose one through `protocol.n50_type`, and all subjects must have that
same field. Scaffold N50 without `misjoin_validated: true` is `WARN`.

### Assembly quality overview

For **each** subject, the claim must resolve six orthogonal evidence axes:
contiguity (selected N50 type), BUSCO (selected lineage/mode), QV (selected k/read
database), LAI, mapping (selected read type), and telomere. Missing an axis blocks
the overview. A single-metric observation is independently valid and is not
forced to populate the other five axes.

### High-confidence SV

`sv.callers` entries are mappings with `name` and `evidence_axis`. A
`sv_high_confidence` claim requires at least one `read` and one `assembly` axis.
Two assembly callers do not satisfy orthogonality.

### RNA-seq differential expression

Use an `rnaseq_de` block and `claim_type: rnaseq_differential_expression`.
Required gates include readable sample metadata/raw-count/QC paths, biological
replicate counts, explicit design/contrast/strandedness, raw integer count input,
no complete batch-condition confounding, and FDR/effect/shrinkage provenance.
Contrasted-group replicate count `<2` is BLOCK, exactly 2 is WARN, and >=3 is the
recommended starting point.

### Population variant calling

Use `population_variants` and `claim_type: population_variant_calling`. Record
reference path/version/checksum, ploidy, caller/version/mode, sample match,
multiallelic policy, normalization tool/version, filter provenance, and readable
sample-manifest/VCF/index paths.

### GWAS

Use `gwas` and `claim_type: gwas`. Record phenotype/genotype sample match, QC
thresholds, PCA/kinship/covariates, multiple testing, QQ evidence, and effect
allele. Route D must be a validated homeolog-resolved biallelic disomic
PLINK2+GEMMA model. Route P must name and validate a dosage/polyploid-aware engine;
unselected or incompatible engines block a claim.

See `playbook-rnaseq-differential-expression.md` and
`playbook-population-variants-gwas.md` for the full planning and acceptance
contracts.

## Status and overall result

Precedence remains `BLOCK > UNCERTAIN > WARN > PASS`, with stable checker exit
codes `2/3/1/0` respectively.

- **PASS** — all declared v2 claims are `supported`, complete, protocol-matched,
  evidence-backed, and have no warning or block.
- **WARN** — a supported analysis has no explicit claim, publication provenance
  or caveat is incomplete, QV is non-independent, or a supported status conflicts
  with a warning. It is not a formal claim PASS.
- **BLOCK** — invalid comparison, missing evidence for a supported claim,
  read+assembly SV orthogonality failure, explicit `status: blocked`, or
  `status: supported` conflicts with a block.
- **UNCERTAIN** — rule coverage is absent, evidence scope cannot be determined, or
  a claim explicitly has `status: uncertain`.

## Legacy compatibility

`result_manifest.v1` and unversioned manifests remain parseable. They are not
automatically or destructively migrated. Even when their known analysis blocks
are complete, absence of an explicit v2 claim limits the result to `WARN`; an
unsupported analysis type remains `UNCERTAIN`. The checker prints the fields
needed for a manual v2 upgrade.

New projects receive `config/result_manifest.yaml` from
`assets/project-templates/result_manifest.yaml`. `scripts/init_project.sh`
creates it only when absent and never overwrites an existing manifest.
