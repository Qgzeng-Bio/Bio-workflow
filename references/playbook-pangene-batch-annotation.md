# Playbook - Pan-gene batch genome annotation

> **Status: DRAFT from real project evidence.** Distilled from the completed
> 10-genome quinoa batch annotation directory:
> `/data9/home/qgzeng/projects/2-C_quinoa/9-Annotation/2-Protein_coding_genes/4-Genes_prediction/8-pangene_anno`.
> Use this when handling multi-accession annotation batches with per-sample
> directories and several evidence routes.

## Table of contents

- Scope and real evidence
- Official tool cross-check
- Batch directory contract
- Stage A - RNA evidence alignment
- Stage B - EviAnn evidence integration
- Stage C - BRAKER3 prediction
- Stage D - AUGUSTUS training and batch prediction
- Stage E - transcript ORFs with TransDecoder
- Stage F - protein-to-genome evidence with SPALN3
- Stage G - aggregation and BUSCO
- Acceptance gates
- Resource notes
- Silent traps

## Scope and real evidence

This playbook covers batches like:

```text
batch_root/
├── LM172/
│   ├── LM172_final.fa.masked
│   ├── RNAseq/bam/
│   ├── eviann/
│   ├── braker3/
│   ├── transdecoder/
│   ├── spaln3/
│   └── augustus/
├── LM176/
...
├── Caryophyllales.pep.fasta
├── braker3.sif -> /data9/home/qgzeng/tools/Braker3/braker3.sif
├── eviann_summary/
├── braker3_summary/
└── braker3_pep_busco/
```

The real run used 10 sample directories:
`LM172`, `LM176`, `LM177`, `LM225`, `LM270`, `LM320`, `LM393`, `LM411`,
`LM42`, and `LM96`.

Do not treat this reference as a command template. Use it as a boundary and QC
model for future batches.

## Official tool cross-check

Checked against official docs/GitHub on 2026-06-18. Reuse this section as the
principle layer, but still record the exact local executable, container, script,
and command log for each run.

- **BRAKER3:** use RNA+protein ETP mode when both evidence classes exist; run on a
  softmasked, high-quality genome with simple sequence names. Protein input must be
  a broad protein-family database, such as the matching OrthoDB clade, with close
  relatives added when useful. If `--busco_lineage` or BUSCO-maximizing modes are
  used during prediction, do not treat later BUSCO on the same lineage as fully
  independent validation.
- **AUGUSTUS:** train from bona fide, non-redundant gene structures in GenBank
  format; split a random held-out test set; run `new_species.pl`, `etraining`, and
  optional `optimize_augustus.pl` only when the runtime is justified. Use a
  project-local `AUGUSTUS_CONFIG_PATH`.
- **TransDecoder:** predicts coding regions in transcript sequences. Use
  `TransDecoder.LongOrfs` then `TransDecoder.Predict` or the wrapper route, record
  whether homology retention and `--single_best_only` were used, and preserve the
  genome-projection route if ORFs are lifted back to genome coordinates.
- **SPALN3:** format genome databases explicitly for DNA or protein query mode
  (`-KD` or `-KP` with `-W`), choose output format deliberately (`-O0` gene GFF3
  versus `-O2` match GFF3), and record the real table/genetic-code choice.
- **HISAT2/StringTie:** `--dta` is required when HISAT2 BAMs feed transcript
  assembly; StringTie inputs must be coordinate-sorted. For mixed short/long read
  mode, StringTie expects the short-read alignment first and long-read alignment
  second.
- **EviAnn:** no stable public official GitHub/doc page was found in this check.
  Treat the local installed `eviann.sh` 2.0.4 help and source as the version-specific
  authority for this server; it requires RNA BAM or related EST evidence, uses `-p`
  for related-species protein FASTA, and falls back to UniProt/Swiss-Prot only when
  close relatives are unavailable.

## Batch directory contract

Prefer an explicit manifest. If discovery is necessary, require all of:

- directory name matches the expected sample pattern, for example `^LM[0-9]+$`
- per-sample masked FASTA exists: `<Sample>/<Sample>_final.fa.masked`
- expected evidence subdirectories exist for the planned route
- expected sample count is stated and checked

Do not define samples as "all directories under batch root". Exclude training,
summary, BUSCO, cache, and tool directories such as `augustus_Cquzz`,
`braker3_summary`, `eviann_summary`, and `braker3_pep_busco`.

Keep a stable sample order for arrays and write it to a manifest or log. Before
interpreting results, compare the final summary sample set to the intended sample
set, not just to the number of rows in a TSV.

## Stage A - RNA evidence alignment

Real pattern:

- build a per-sample HISAT2 index on `<Sample>_final.fa.masked` if missing
- find `*_clean_1.fq.gz` / `*_clean_2.fq.gz` pairs under `RNAseq/`
- run HISAT2 with `--dta`; this is a transcript-assembly mode, not cosmetic logging
- pipe to `samtools sort`, then create BAM indexes
- keep one `.hisat2.log` per RNA sample or tissue

Acceptance:

- every intended RNA pair has a BAM and index
- BAMs passed to StringTie/EviAnn/BRAKER are coordinate-sorted, indexed, and tied to
  the same genome FASTA used to build the HISAT2 index
- HISAT2 logs have high enough overall alignment for the biological context
- failed or missing pairs are explicit warnings, not silent skips
- sorted BAMs are under `RNAseq/bam/` and named consistently
- if STAR is used instead of HISAT2, require transcript-strand tags suitable for
  StringTie/BRAKER, for example STAR `--outSAMstrandField intronMotif`

For the observed LM172 leaf example, HISAT2 reported `99.02% overall alignment
rate`. Treat such values as evidence for that sample/tissue only, not as a batch
claim unless all logs are summarized.

## Stage B - EviAnn evidence integration

Real inputs:

- masked genome FASTA
- per-sample BAM list written as `paired.txt`, one BAM per line with a `bam` label
- shared protein FASTA selected by target-species taxonomy. In the real quinoa run,
  this was `Caryophyllales.pep.fasta`; for other species, replace it with the
  corresponding family/order/clade protein database rather than reusing
  Caryophyllales.

Protein database principle:

- EviAnn `-p` should receive proteins from preferably multiple related species; its
  local 2.0.4 help falls back to UniProt/Swiss-Prot only when close relatives are not
  available.
- BRAKER3 `--prot_seq` follows the same evidence logic: use a sufficiently broad
  protein-family database, such as an appropriate OrthoDB clade, and add close
  relatives when they improve taxonomic relevance.
- Do not use a tiny convenience protein set. Require enough families and enough
  representatives to support homology-based models, then deduplicate and clean
  headers before sharing the library across EviAnn, BRAKER3, and SPALN/miniprot-style
  protein-to-genome stages.
- Record a protein-library manifest with taxon scope, species/database sources,
  download or build date, raw and filtered sequence counts, filtering/dedup rules,
  header-cleaning rule, md5, and the reason this clade matches the target species.

Local EviAnn 2.0.4 script contract:

- require RNA BAM evidence (`-r`) or related transcript/EST evidence (`-e`) before
  expecting EviAnn to build transcript-supported models
- treat `-p` proteins as related-species homology evidence, not final product names
- keep the internal miniprot/protein-to-genome and TransDecoder-retain-hits outputs
  traceable through logs, because EviAnn wraps multiple tools under one command

Real outputs and sentinels observed:

- `<Sample>_final.fa.masked.gff`
- `<Sample>_final.fa.masked.proteins.fasta`
- `<Sample>_final.fa.masked.transcripts.fasta`
- `transcripts_assemble.success`
- `transcripts_merge.success`
- `protein2genome.align.success`
- `protein2genome.deduplicate.success`
- `pseudo_detect.success`
- `loci.success`
- `eviann.stdout.log` and `eviann.stderr.log`

QC rule:

- count `gene`, `mRNA`, `exon`, and `CDS`
- split mRNA evidence categories from `Evidence=` into `complete`,
  `transcript_only`, `protein_only`, and `other`
- any `no_gff`, `ambiguous_gff`, or non-`ok` status blocks biological
  interpretation for that sample

Observed caution: LM411 had multiple EviAnn GFF candidates and was flagged
`ambiguous_gff` even though a final-looking GFF existed. This is the right failure
mode; do not silently pick one candidate unless the rule is explicit.

## Stage C - BRAKER3 prediction

Real pattern:

- run BRAKER3 from Singularity, not from a mutable local install
- require `braker3.sif`, protein FASTA, BAMs, and BAM indexes before running
- use `--softmasking`, `--gff3`, `--prot_seq`, and comma-separated RNA BAMs
- create a unique per-task working directory such as
  `braker3/run_<SLURM_JOB_ID>_<TASK_ID>`
- create a unique species name per sample/run, for example
  `braker3_<Sample>_<RunTag>`
- keep per-sample `braker3.stdout.log`, `braker3.stderr.log`, and symlinks to
  SLURM stdout/stderr

Never run multiple BRAKER3 array tasks into the same working directory or reuse the
same species config without an explicit reason.

Official-doc constraints:

- use a softmasked genome and simple FASTA headers before alignment and prediction
- use RNA-seq read alignments from the target species, not assembled transcriptome
  mappings, when passing RNA BAMs to BRAKER
- use a protein-family database with enough representatives per family; a small
  convenience FASTA is not equivalent to OrthoDB-style evidence
- record whether `--busco_lineage` or BUSCO-driven TSEBRA/compleasm modes were used;
  if yes, separate prediction optimization from independent BUSCO validation

Output selection:

- prefer canonical `braker.gff3`
- prefer canonical `braker.aa` for protein BUSCO
- if several GFF/protein candidates exist, select by an explicit priority rule or
  mark the sample ambiguous

## Stage D - AUGUSTUS training and batch prediction

Real training pattern:

- train from a trusted fixed GFF3 and matching FASTA, not from every draft output
- convert GFF3 to GenBank with `gff2gbSmallDNA.pl`
- run generic `etraining` first to discover bad training genes
- filter bad genes, then run `randomSplit.pl`
- copy container AUGUSTUS config into a project-local `augustus_config`
- set `AUGUSTUS_CONFIG_PATH` explicitly
- record raw and filtered locus counts
- optionally skip `optimize_augustus.pl` unless the extra runtime is justified

Official AUGUSTUS training constraints:

- do not train from a tiny or noisy set; AUGUSTUS documentation gives about 200 good
  gene structures as a minimum and about 1000 as a point where quality matters more
  than additional quantity
- keep training/test genes non-redundant and randomly split; the held-out test set
  should be large enough to make accuracy estimates meaningful
- the GenBank training records should contain bona fide gene structures, preferably
  non-overlapping with one transcript per gene
- `optimize_augustus.pl` can run for hours or days; skipping it is acceptable only
  when logged as a deliberate runtime/quality tradeoff

Batch prediction pattern:

- require the trained species config before the array starts
- set `AUGUSTUS_CONFIG_PATH` through the container environment
- write one per-sample GFF3 under `<Sample>/augustus/`

Acceptance:

- `genes.raw.gb` and filtered `genes.gb` locus counts are logged
- filtered locus count is high enough for `randomSplit.pl`
- training summary records species name, input GFF3/FASTA, image, and config path
- each sample has a non-empty `<Sample>.augustus.gff3`

## Stage E - transcript ORFs with TransDecoder

Real pattern:

- merge per-sample RNA BAMs when more than one exists
- run StringTie on the merged BAM
- convert GTF to transcript FASTA and alignment GFF3
- run `TransDecoder.LongOrfs` and `TransDecoder.Predict`
- project ORFs back to genome with `cdna_alignment_orf_to_genome_orf.pl`

Official TransDecoder boundary:

- TransDecoder is an ORF caller on transcript sequences, not a whole-genome gene
  predictor by itself
- record whether the pipeline used transcript-only mode, genome+GTF wrapper mode, or
  a manual transcript-to-genome projection utility
- report the expected `.transdecoder.pep`, `.transdecoder.cds`, `.transdecoder.gff3`,
  and genome-projected GFF3 outputs separately

Preflight details worth preserving:

- check all TransDecoder utility scripts are executable
- record TransDecoder home and exact utility paths
- check BAM indexes before merging
- use a deterministic samtools route; a local samtools binary can be primary with a
  Conda fallback if both are logged
- account for Perl module issues such as missing `URI::Escape` through documented
  `PERL5LIB`, not hidden interactive fixes

Rerun caution:

- this route often deletes stale TransDecoder outputs before rerun. In future skill
  usage, explain the delete set and ask before removing existing results.

## Stage F - protein-to-genome evidence with SPALN3

Real pattern:

- use a real SPALN table ID; do not write a generic value such as `genome`
- record `spaln -V` or version fallback, executable path, and `gnm2tab` path
- format a per-sample genome database under `<Sample>/spaln3/db`
- run protein-to-genome alignment to GFF3 match output
- sort match-format GFF3 into EVM-compatible protein evidence
- keep optional binary-output plus `sortgrcd` as a separate branch

Official SPALN3 boundary:

- for protein-to-genome evidence, format the genome for protein queries, for example
  `spaln -W -KP <genome>`; `.bkp` is the expected protein-query block index
- choose output format by downstream consumer: `-O0` is gene-style GFF3, while `-O2`
  is match-style GFF3 suitable for evidence integration routes such as EVM
- if the genome FASTA is only a subset, set the max-gene/search assumptions
  deliberately instead of relying on whole-genome defaults

Observed table ID: `chenquin`. For other projects, inspect `share/spaln/table/gnm2tab`
and choose deliberately.

Acceptance:

- SPALN DB files exist: `.idx`, `.grp`, `.ent`, `.seq`, `.bkp`
- match GFF3 exists and is non-empty
- EVM protein GFF3 is sorted by sequence and coordinates
- if optional `sortgrcd` is requested, require `.qrd`, `.grd`, and `.erd` or mark
  the locus-level output skipped

## Stage G - aggregation and BUSCO

For every predictor or evidence route, write both:

- per-sample stats under the sample route directory
- one combined TSV under a route-level summary directory

Minimum GFF3 stats:

- `sample`
- `gff_file`
- `gene_count`
- `mrna_count`
- `exon_count`
- `cds_count`
- `status`

For EviAnn, also count:

- `complete_mrna`
- `transcript_only_mrna`
- `protein_only_mrna`
- `other_evidence_mrna`

Protein BUSCO route:

- run protein mode on the released or candidate protein FASTA
- record BUSCO binary, lineage path, mode, threads, output directory, stdout/stderr
- parse the compact `C:[S,D],F,M,n` line; if missing, fall back to count lines
- keep `status` values such as `ok`, `missing_pep`, `busco_failed`,
  `no_short_summary`, and `parse_failed`

Important typo guard: verify the lineage path exactly. In the real scripts,
`embryophyta_odb12` was the intended lineage; a typo such as `embryophyta_od12`
should fail preflight.

## Acceptance gates

Do not compare or publish batch annotation quality until all gates pass:

- intended sample set equals observed sample set
- all top-level stage scripts were run or deliberately skipped
- every sample has the expected masked FASTA
- RNA BAMs and indexes exist for RNA-supported routes
- EviAnn and BRAKER3 combined summary `status` is `ok` for every intended sample
- no non-sample directory appears in sample-level summary rows
- BUSCO protein summary contains only intended samples and all intended rows are
  `ok`
- BUSCO lineage, mode, marker count, and database version/path are reported
- official docs/GitHub or local installed source were checked for each tool-specific
  mode used in the batch, and the check date/source is recorded in Methods or a
  manifest
- high BUSCO duplicated percentage is interpreted in the allotetraploid/subgenome
  context, not automatically as over-duplication
- any ambiguous GFF/protein candidate is resolved by a documented priority rule
  before downstream orthology, pangenome, or functional interpretation

Observed real summary anchors:

- EviAnn gene counts were about 51.5k-53.5k per sample, with mRNA counts about
  90k-97k. One sample was blocked as `ambiguous_gff`.
- BRAKER3 gene counts were about 47.3k-49.4k per sample, with mRNA counts about
  54.5k-56.6k; all observed BRAKER3 status rows were `ok`.
- BRAKER3 protein BUSCO Complete was about 99.3%-99.5% with high duplicated BUSCOs
  around 90%-92%, consistent with the quinoa allotetraploid context.

Use these anchors as sanity ranges for this project lineage only, not universal
thresholds for other species.

## Resource notes

Real starting points observed:

- HISAT2 per-sample array: `fat`, 32 CPUs, 100G, array `0-9%5`
- EviAnn: `fat`, 32 CPUs, 150G, array over 10 samples
- BRAKER3: `fat`, 32 CPUs, 150G, array over 10 samples
- GFF3 stats: 2 CPUs, 8G
- protein BUSCO: `normal`, 20 CPUs, 40-100G depending on route
- AUGUSTUS training: `normal`, 16 CPUs, 100G
- AUGUSTUS batch prediction: `normal`, 12 CPUs, 100G
- TransDecoder route: `normal`, 16 CPUs, 100G
- SPALN3: `normal`, 16 CPUs, 150G

For new runs, add array concurrency caps from memory, database loading, and disk I/O.
Do not copy uncapped `--array=0-9` by habit. Keep the user's rule: no default
`#SBATCH --time` unless explicitly requested.

## Silent traps

- A directory named like a stage or summary can be mistaken for a sample.
- A final-looking GFF can coexist with multiple candidate GFFs; mark ambiguous until
  a priority rule is applied.
- BUSCO summary scripts can report extra `no_short_summary` rows for non-sample
  directories if sample discovery is too broad.
- Protein BUSCO success does not validate GFF3 structure, transcript evidence, or
  functional names.
- High duplicated BUSCOs in quinoa are expected; do not call them redundancy without
  subgenome/ploidy context.
- `set -u` can break when sourcing cluster shell config; disable nounset around
  `source ~/.bashrc` when needed, then re-enable it.
- SPALN3 species/table IDs are not intuitive; wrong IDs can silently make evidence
  biologically weak even if files are produced.
- Deleting stale intermediate outputs in rerun scripts must be explicit and confirmed.
- Do not let a wrapper command hide tool-specific assumptions: HISAT2 `--dta`,
  StringTie `--mix` ordering, BRAKER protein-family scope, AUGUSTUS train/test split,
  TransDecoder transcript boundary, and SPALN GFF3 output mode all need explicit logs.
