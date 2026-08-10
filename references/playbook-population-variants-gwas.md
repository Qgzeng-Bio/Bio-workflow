# Playbook — population SNP/INDEL calling and GWAS

> **Status:** active planning and acceptance contract. This playbook provides
> decision-complete routes, not a claim that one fixed command set has been
> validated for every cohort/server version. Verify local GATK/bcftools/PLINK2,
> GEMMA, and any polyploid engine before generating formal commands. KMERIA remains
> a separate k-mer association route and is not part of this SNP-GWAS workflow.

Two entry routes:

```text
Route A: validated indexed VCF -> sample/genotype QC -> GWAS
Route B: FASTQ/BAM -> joint SNP/INDEL calling -> normalized indexed VCF -> Route A
```

Two genetic-model branches:

```text
D route: homeolog-resolved + biallelic + disomic approximation valid
         -> PLINK2 QC/format -> GEMMA LMM
P route: dosage/non-disomic/polyploid model required
         -> selected and locally validated dosage/polyploid-aware engine
```

Do not issue a formal association command until D versus P is resolved.

## 1. Intake manifests and identity gate

Minimum sample manifest:

```text
Sample_ID	BAM_or_VCF_ID	Population	Family	Batch	Ploidy_Model	Input_Path
```

Minimum phenotype manifest:

```text
Sample_ID	Trait	Value	Environment	Trial	Block	Batch
```

Record:

- biological question, trait, cohort, exclusions, and expected sample count;
- reference FASTA version/checksum/index and chromosome convention;
- FASTQ/BAM/VCF paths, indexes, callers, versions, and prior filters;
- canonical sample-ID mapping across input, phenotype, covariates, and kinship;
- expected chromosome/subgenome, ploidy, allele dosage, and genotype encoding;
- environmental/trial design, units, missing phenotype policy, and transformations;
- intended variant calling route and GWAS D/P route.

Any duplicate/unmatched/ambiguous sample ID is a `BLOCK` until reconciled in a TSV
mapping. Never rely on coincidental row order.

## 2. Route A — accept an existing VCF

Before genotype QC, verify:

- VCF/BCF and tabix/CSI index are readable and coordinate-compatible;
- reference contig header, reference build, and normalization provenance;
- sample count/list exactly match the reviewed manifest;
- variant type, biallelic/multiallelic representation, genotype fields, phasing,
  ploidy, and missing-value semantics;
- caller/version, joint/single-sample history, filtering status, and excluded
  regions;
- allele/reference orientation and duplicate loci.

An existing VCF with unknown reference, ploidy, normalization, or filters is not a
validated shortcut. Stop or rebuild from Route B.

## 3. Route B — joint SNP/INDEL calling

Choose GATK or bcftools only after verifying local versions/help and the intended
ploidy model. The execution plan must state:

- read-group/sample identity and reference checksum for every BAM;
- BAM sort/index/duplicate handling and per-sample coverage QC;
- per-sample intermediate versus direct multisample calling;
- explicit ploidy assumption by chromosome/region when it varies;
- joint genotyping/merge strategy;
- SNP/INDEL selection, left alignment, reference checks, multiallelic splitting or
  retention policy;
- hard-filter/VQSR or caller-specific quality model with exact thresholds and
  training resources;
- final bgzip VCF/BCF and index.

Do not silently use a diploid default for allotetraploid dosage. If the reference
is homeolog-resolved and evidence supports disomic calling per locus, record that
assumption and its exceptions. Otherwise choose an appropriate dosage/polyploid
calling and association branch.

## 4. Population genotype and sample QC

Thresholds are cohort/data dependent and must be predeclared after inspecting
quality distributions. Record both pre/post counts and reasons. Review:

- sample call rate and variant missingness;
- per-sample/per-site depth and genotype quality;
- allele count/frequency (MAC/MAF) appropriate to the model;
- transition/transversion and allele-balance behavior;
- heterozygosity/outlier burden under the stated ploidy model;
- duplicate/identity-by-state, family, and relatedness;
- batch/platform/reference effects;
- chromosome/subgenome balance and homeologous mapping bias;
- repeat, centromere, segmental-duplication, and low-mappability masks.

### HWE boundary in quinoa

Diploid Hardy-Weinberg tests are not an unconditional hard filter in polyploid
quinoa. Apply HWE only where the encoded genotype, population assumptions,
disomic inheritance, unrelated subset, and subpopulation scope justify it.
Population structure, selection, inbreeding, dosage uncertainty, and homeolog
mapping can all create deviations. Record HWE as a conditional diagnostic or an
explicit model-compatible filter, never a hidden default.

## 5. Phenotype and covariate QC

For each trait/environment:

- verify units, range, missingness, replicate/trial aggregation, and outliers;
- visualize distribution and decide any transformation before association;
- record environment, trial, block, batch, sex/age or other relevant covariates;
- avoid leakage by deriving transformations/covariates under the declared design;
- define whether multi-environment data use adjusted means/BLUPs or a joint model;
- reconcile final phenotype/genotype sample sets explicitly.

Dropping samples to make distributions look normal is not acceptable. Preserve a
sample-exclusion TSV with reason and evidence.

## 6. Genetic-model decision

### D route — disomic approximation

Use only when all are supported:

- A/B homeologs are resolved sufficiently for unique locus assignment;
- variants are biallelic under diploid/disomic encoding;
- allele dosage beyond 0/1/2 is not required;
- missingness/heterozygosity and chromosome behavior support the approximation;
- local PLINK2 and GEMMA versions/format compatibility are validated with a small
  pilot.

PLINK2 performs reviewed QC/format conversion; GEMMA performs kinship-aware LMM
association. Record effect allele and allele coding through every conversion.

### P route — dosage/polyploid-aware

Use when dosage, non-disomic inheritance, multiallelic genotypes, or a true
polyploid model is required. Select an engine/model appropriate to the available
genotype representation (for example, a validated applicable GWASpoly or GAPIT
model), verify local version and input semantics, and run a small compatibility
pilot. Until an engine is **selected and validated**, stop before formal
association commands. Do not relabel diploid PLINK/GEMMA output as polyploid GWAS.

## 7. Structure, kinship, and association

Required pre-association decisions:

- LD pruning policy for PCA/kinship, with chromosome/subgenome awareness;
- PCA axes and population labels used as covariates;
- kinship estimator compatible with genotype encoding;
- fixed covariates (environment/trial/batch and justified PCs);
- LMM/GLMM or polyploid model and trait distribution;
- whether proximal contamination is material;
- optional leave-one-chromosome-out (LOCO), validated for the selected engine;
- one primary model plus predeclared sensitivity models.

Inspect PCA/kinship/family concordance before GWAS. A high genomic inflation factor
is not fixed by adding arbitrary PCs until the QQ plot looks flat; review model,
relatedness, batch, trait, allele-frequency, and mapping artifacts.

## 8. Multiple testing and lead loci

Predeclare and report the correction method (for example Bonferroni, effective
number of tests, or FDR) and exact threshold. Produce QQ data/plot, genomic
inflation summary, and Manhattan data. Every association row must retain:

- chromosome/position/reference build;
- reference and effect allele;
- effect estimate, SE, test statistic, p-value, sample count, MAF/MAC;
- model, trait, covariates, and correction threshold.

Define lead-locus clumping/window/LD rules before candidate-gene lookup. Report
candidate intervals with reference coordinates and gene annotation version.
Significant loci overlapping repeats, centromeres, segmental duplications, or
low-mappability/homeologous regions require explicit caveats and independent
support.

Association is not causation. Prioritize independent cohort/environment
replication, targeted genotyping, expression/functional evidence, and experimental
validation.

## 9. Outputs

Minimum TSV contracts:

```text
# results/Variant_QC_Summary.tsv
Stage	Sample_Count	Variant_Count	SNP_Count	INDEL_Count	Missing_Rate	Filter_ID	Reference_Version	Ploidy_Assumption

# results/Sample_QC.tsv
Sample_ID	Call_Rate	Mean_Depth	Heterozygosity	Relatedness_Status	Population	QC_Status	Exclusion_Reason

# results/GWAS_Associations.tsv
Trait	Chr	Position_bp	Ref_Allele	Effect_Allele	Effect	SE	P_Value	Adjusted_P_Value	MAF	MAC	N	Model

# results/Lead_Loci.tsv
Trait	Lead_Variant	Chr	Start_bp	End_bp	Effect_Allele	Effect	P_Value	Threshold	Candidate_Genes	Region_Caveat
```

Retain normalized indexed VCF/BCF, sample order, filter expressions, pre/post
counts, PCA, kinship, covariates, phenotype table, QQ/Manhattan plotting TSVs,
software versions, commands, logs, reference checksum, and exclusion decisions.
Use tabs and English initial-capital underscore columns.

## 10. SLURM/resource principles

- Route B per-sample calling may use capped arrays; joint genotyping/normalization
  and GWAS are separate dependency-aware stages.
- Size memory/CPU from cohort size, depth, chromosome sharding, genotype matrix,
  caller behavior, a pilot, and prior `sacct`. Do not copy a fixed template.
- Cap arrays for shared reference/index and filesystem pressure; avoid many
  concurrent writers to one VCF/database.
- Forward `${SLURM_CPUS_PER_TASK}` only to tools that use it; preserve absolute
  project logs and strict mode.
- Do not add default `#SBATCH --time`. Run `prepare_submission.sh`; submit only
  after separate confirmation.

## 11. PaperPlot handoff

Bioflow prepares accepted TSVs with explicit sample order, trait units, reference,
model, effect allele, thresholds, and region caveats. Delegate PCA, phenotype QC,
QQ, Manhattan, and effect/lead-locus panels to `paperplot-skills` for design,
PDF/PNG export, metadata, and rendered-image QA. Manhattan points must match the
accepted association TSV/reference coordinates; QQ denominators and exclusion
rules must be stated.

## 12. Result-manifest v2 contract

### Population variant calling

Use `analysis_types: [population_variant_calling]`, a `population_variants` block,
and `claim_type: population_variant_calling`. The checker requires reference
path/version/checksum, ploidy and caller provenance, sample match, explicit
normalization/multiallelic policy/filter provenance, and readable sample manifest,
VCF, and index.

### GWAS

Use `analysis_types: [gwas]`, a `gwas` block, and `claim_type: gwas`. The checker
requires phenotype/genotype sample match, route/model compatibility, explicit QC
thresholds, PCA/kinship/covariates, multiple-testing method/threshold, QQ evidence,
and effect-allele reporting. D route requires validated homeolog-resolved,
biallelic, disomic PLINK2+GEMMA. P route requires a selected validated dosage and
polyploid-aware engine.

## 13. Acceptance

Accept a callset/GWAS claim only when:

- reference, ploidy, samples, coordinates, normalization, filters, VCF, and index
  are reproducible;
- sample/variant QC thresholds and pre/post counts are explicit;
- phenotype and genotype samples match and population structure is addressed;
- D/P engine assumptions are demonstrated rather than inferred;
- multiple testing, QQ behavior, effect allele, and candidate-region caveats are
  reported;
- manifest claims cite readable evidence and pass their active gates;
- independent validation needs and the non-causal nature of association are
  stated.
