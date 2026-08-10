# Playbook — RNA-seq differential expression

> **Status:** active planning and acceptance contract. This is not a claim that one
> fixed end-to-end pipeline has already been validated for every library on this
> server. Before execution, verify local tool versions and flags with bounded
> `--help`/official-document checks. Do not install software or submit work without
> the normal Bioflow confirmation gates.

Default route:

```text
FASTQ QC -> evidence-based optional trimming -> STAR -> featureCounts
-> sample/count QC -> DESeq2 -> PaperPlot
```

## 1. Intake and hard design gates

Create a tab-separated sample manifest:

```text
Sample_ID	Condition	Biological_Replicate	Batch	Tissue	Read1	Read2
```

Required decisions before commands:

- biological question and exact contrast (`Factor`, numerator, denominator);
- authoritative `Sample_ID`, condition, biological replicate, tissue, and batch;
- technical-replicate relationship (same biological specimen/library or not);
- reference FASTA/GTF release, checksums, chromosome naming, and gene-ID namespace;
- paired/single-end, read length, library strandedness, and expected insert size;
- whether a STAR index already matches the FASTA/GTF/read-length contract;
- expected final outputs and claim scope.

Hard gates:

- fewer than **2 biological replicates in any contrasted group: BLOCK** for
  population-level DE inference;
- exactly 2 in any group: `WARN`; **>=3 is the recommended starting point**;
- condition and batch/tissue/other required covariate fully confounded: `BLOCK`;
- sample IDs, mate pairing, reference IDs, or gene annotation incompatible:
  `BLOCK`;
- technical replicates are not counted as independent biological replicates.

If no biological replication exists, report sample-level expression/QC only. Do
not manufacture degrees of freedom or label the result differential expression.

## 2. Reference and STAR index contract

Record in `config/`:

- FASTA and GTF absolute paths, versions, SHA256, sequence IDs, and gene ID field;
- STAR version and index-generation command;
- read length used to choose `sjdbOverhang` (verify the local STAR option);
- index directory checksum or a deterministic file inventory/checksum record;
- whether annotation and FASTA chromosome names match exactly.

Reuse one validated STAR index. Do not let every array task rebuild it. On shared
storage, stagger/cap array concurrency if all tasks load the same index; index I/O
and node memory, not sample count alone, determine safe concurrency.

## 3. FASTQ QC and trimming decision

For every sample:

1. verify R1/R2 identity, compression readability, and non-empty input;
2. run FastQC and aggregate with MultiQC (use local versions/flags);
3. inspect adapter content, per-base quality, duplication, GC, overrepresented
   sequence, read length, and mate balance;
4. run trimming only when QC provides a reason.

Trimming is **not unconditional**. If needed, record tool/version, adapter source,
minimum retained length, quality rule, and pre/post read counts. Never overwrite
raw FASTQ. A failed or unexpectedly large read-loss sample stops before mapping.

## 4. Alignment

Use STAR per sample with a verified index and explicit paired/single-end input.
Build commands only after checking the installed STAR help. At minimum record:

- STAR version/index identity;
- input files and decompression method;
- threads from `${SLURM_CPUS_PER_TASK}`;
- sorted BAM/log destinations and overwrite policy;
- multimapping, splice-junction, and unmapped-read policy;
- complete `Log.final.out` and command line.

Do not infer success from BAM existence. Check uniquely mapped %, multimapped %,
unmapped reasons, splice counts, mismatch rate, BAM indexability, chromosome
coverage, and consistency across replicates. Extreme mapping or assignment
outliers pause the route.

### Quinoa homeolog policy

Quinoa is allotetraploid (A/B subgenomes). Homeologous sequence creates ambiguous
mapping. The primary DE analysis should preserve A- and B-homeolog gene IDs and
prefer reads that can be assigned under a documented unique-attribution policy.
Do not merge homeolog counts before DE. A multimapping-inclusive/allocated route
is a clearly labeled **sensitivity branch**, not a silent change to the primary
analysis.

## 5. featureCounts

Before counting, verify against local `featureCounts -h`:

- annotation feature type (commonly `exon`);
- grouping attribute (commonly `gene_id`);
- paired-end and properly paired policy;
- strandedness code validated from library metadata or a documented inference;
- multimapping/multi-overlap policy;
- chromosome aliases and gene-ID uniqueness.

Record assigned/unassigned categories per sample. The output for DESeq2 is a gene
× sample matrix of **raw integer counts**. TPM, FPKM, CPM, transformed values, or
plot-normalized values are not DESeq2 count input.

Technical replicates from the same biological library/specimen may be merged only
with documented provenance after confirming compatibility; use count summation at
the defined biological-sample boundary. Never merge distinct biological
replicates.

## 6. Sample and count QC

Required pre-DE evidence:

- library size and detected genes;
- STAR mapping and featureCounts assignment rates;
- count distribution and low-count burden;
- variance-stabilized/rlog PCA for visualization (not DE input);
- sample correlation/distance;
- condition, batch, tissue, and replicate overlays;
- sample swaps, contamination, and outlier review.

Do not delete an outlier only because it weakens significance. Record the
technical/biological evidence, run a predeclared sensitivity analysis when
appropriate, and retain an exclusion table. If exclusion drops a contrasted group
below the replicate gate, formal DE is blocked.

## 7. DESeq2 model and inference

Before running R:

- write the design formula explicitly (for example `~ Batch + Condition`);
- verify the model matrix is full rank and the requested contrast is estimable;
- state the exact contrast direction;
- keep raw integer counts and sample metadata in matching canonical order;
- predeclare independent-filtering/low-count policy;
- report log2 fold change and uncertainty, not p-value alone;
- apply BH false-discovery-rate correction (or document another justified FDR
  method);
- record alpha, effect-size threshold, and log2FC shrinkage method/version.

A recommended result filter is expressed as both adjusted p-value and biologically
meaningful effect size; it is not hard-coded here because the question and assay
determine the effect threshold. Report all tested genes, not only significant
ones.

## 8. Outputs

Use project TSV conventions. Minimum outputs:

```text
# results/DE_Results.tsv
Gene_ID	Base_Mean	Log2FC	LFC_SE	Statistic	P_Value	Adjusted_P_Value	Contrast	Status

# results/Sample_QC.tsv
Sample_ID	Condition	Biological_Replicate	Batch	Read_Pairs	Unique_Mapping_pct	Assigned_Reads_pct	Library_Size	QC_Status

# reports/DE_Contrast_Summary.tsv
Contrast	Genes_Tested	Genes_FDR_Pass	Genes_Effect_Pass	FDR_Method	Alpha	Effect_Threshold	Design_Formula
```

Also retain raw count matrix, normalized values for visualization, size factors,
PCA coordinates, sample-distance data, session information, package versions,
commands, logs, exclusions, and reference/index checksums. Tables are TSV with
English initial-capital underscore columns.

## 9. SLURM/resource principles

- FASTQ QC/alignment/counting are per-sample candidates for arrays with an explicit
  concurrency cap; DESeq2 contrasts usually run after the complete count matrix.
- Size STAR index memory from the actual index/reference and a pilot or prior
  `sacct`, not a fixed template. Confirm that requested CPUs reach STAR/counting.
- Account for shared-index and FASTQ/BAM I/O before increasing concurrency.
- Use absolute project `logs/%j_%x.out|err`, strict shell mode, and explicit output
  guards.
- Do not add default `#SBATCH --time`. Run `prepare_submission.sh` before a
  separately confirmed submission.

## 10. PaperPlot handoff

After DE acceptance, delegate figure design/export/QA to `paperplot-skills`:

- PCA: sample coordinates + condition/batch/replicate;
- MA: base mean, shrunken log2FC, adjusted significance;
- volcano: effect and adjusted significance with a bounded label policy;
- heatmap: predeclared genes and transformed expression, preserving sample order.

Bioflow supplies TSV data, units/transforms, sample order, contrast, and evidence.
PaperPlot supplies the design brief, visual pattern, PDF/PNG, metadata, strict
rendered-image QA, and legend. Never use raw p-value stars as the only message.

## 11. Result-manifest v2 contract

Use `analysis_types: [rnaseq_differential_expression]`, an `rnaseq_de` block, and
a claim with `claim_type: rnaseq_differential_expression`. Minimum gates checked
by `check_result_contract.py`:

- readable sample metadata, raw count, and QC evidence paths;
- biological replicate counts (`<2 BLOCK`, `2 WARN`);
- design, contrast, and strandedness;
- `count_input.type: raw_integer_counts`;
- `batch_condition_confounding: false`;
- FDR method/alpha, effect-size field, shrinkage, and QC evidence.

The broad `analysis_type: rnaseq` remains `UNCERTAIN`; first choose differential
expression, quantification, or another explicit RNA mode.

## 12. Acceptance

Accept DE only when:

- sample manifest/reference/index/count identities are reproducible;
- all intended biological samples pass or have justified documented exclusions;
- mapping/assignment/count QC is coherent and no unresolved sample swap remains;
- model is full rank, contrast is estimable, and replication gate is met;
- raw counts, FDR, effect size, shrinkage, and software provenance are complete;
- quinoa homeolog/multimapping policy is explicit;
- result manifest claim and cited evidence pass or carry declared WARN caveats.

A DE association is not proof of regulation mechanism or causation; such
interpretation requires independent experimental validation.
