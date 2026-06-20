# Software resource cards

These cards give qgzeng-server starting points for CPU, memory, partition, array
concurrency, and preflight checks. They are heuristics, not fixed templates. Always
adjust them with input size, tool version, current queue state, and previous `sacct`
records when available.

## Table of contents

- How to use these cards
- minimap2
- samtools sort
- SyRI
- OrthoFinder
- EDTA
- TRF
- RepeatModeler
- RepeatMasker
- HiTE and panHiTE / Nextflow drivers
- TEsorter and repeat post-processing
- STAR
- featureCounts
- PanGenie
- KMERIA
- BLAST, DIAMOND, and HMMER-family searches
- hifiasm
- Juicer and 3D-DNA
- BRAKER and MAKER
- bcftools and GATK
- fastp, FastQC, and MultiQC
- MUMmer and plotsr
- BUSCO
- QUAST
- Resource-report checklist

## How to use these cards

Before proposing a SLURM request:

1. Identify the exact tool mode. Index building, mapping, sorting, clustering, and
   plotting have different resource shapes.
2. Estimate input scale from explicit files only: file size, `.fai`, `.bai`, `.tbi`,
   sample manifest, or small headers. Do not scan large trees.
3. Classify parallelism: single-threaded, moderately parallel, strongly parallel,
   memory-bound, or I/O-bound.
4. Estimate memory as:

```text
memory = base index/database/input memory
       + per-thread memory * useful threads
       + temporary/output headroom
```

5. Choose partition by memory, not habit:
   - `< 200G`: usually `normal`
   - `>= 200G`: consider `fat` or `fat2`
   - uncertain: run a bounded pilot or ask the user
6. Do not add `#SBATCH --time` by default except debug-style tests or explicit user
   request.
7. For arrays, cap concurrency from total memory and disk pressure. Prefer `%2`,
   `%4`, or `%5` over uncapped arrays.
8. If expected memory is `>100G`, runtime is long, or disk growth is large, state the
   risk and wait for confirmation before submission.

## minimap2

**Typical use:** long-read mapping, assembly-to-reference mapping, PAF/SAM generation
for synteny/SV workflows.

**Parallelism:** good but not unlimited. Threads help alignment, but I/O and downstream
sorting often become bottlenecks. Avoid requesting more than 32 CPUs unless a prior
benchmark supports it.

**Memory drivers:**

- target genome index size
- query size and sequence count
- preset, especially asm-vs-read modes
- SAM/BAM output plus downstream sorting

**Starting points:**

- single plant genome or read set: `normal`, 8-16 CPUs, 32-64G
- large assembly-vs-assembly pair: `normal` or `fat`, 16-24 CPUs, 64-128G
- many pairwise alignments: job array with `%2-%4`, not one huge loop on login node

**Preflight checks:**

- get reference size from `.fai` if present
- inspect query file sizes with `ls -lh`
- decide whether output should be PAF, SAM, or compressed BAM
- if BAM sorting follows, budget `samtools sort` separately

**Red flags:**

- all-vs-all genome alignments
- ultra-large SAM output
- piping directly into sort without matching memory to `samtools sort -m`

## samtools sort

**Typical use:** coordinate/name sorting BAM files.

**Parallelism:** moderate. More threads can help, but memory is controlled by
`-m` per thread and disk I/O often limits gains.

**Memory model:**

```text
requested_mem >= threads * sort_m + 20-30% headroom
```

Example: `samtools sort -@ 8 -m 4G` needs at least about 32G plus headroom, so request
40-48G rather than 32G.

**Starting points:**

- ordinary BAM: `normal`, 4-8 CPUs, 16-48G
- very large BAM: `normal`, 8-12 CPUs, 64-96G
- unusually large plant-genome BAM: consider `fat` only if estimated memory exceeds
  normal-node comfort or previous jobs show OOM

**Preflight checks:**

- check BAM size with `ls -lh`
- set `-T project/tmp/...` explicitly
- ensure tmp space can hold temporary chunks, often comparable to input size or larger

**Red flags:**

- `-@ 32 -m 4G` silently implies 128G before headroom
- sorting on `admin2`
- tmp path under a small or shared system directory

## SyRI

**Typical use:** structural rearrangement calling from whole-genome alignments.

**Parallelism:** limited. SyRI itself is not a tool where very high CPU requests usually
pay off. Spend effort on clean alignments and memory headroom.

**Memory drivers:**

- whole-genome alignment size
- number and density of alignment blocks
- repetitive plant genomes and fragmented assemblies
- chromosome naming and filtering quality

**Starting points:**

- clean chromosome-level pair: `normal`, 4-8 CPUs, 32-96G
- large/repetitive pair or dense alignments: `normal` or `fat`, 4-8 CPUs, 96-200G
- many pairwise comparisons: array with `%1-%3`, because each task can be memory-heavy

**Preflight checks:**

- verify chromosome names match between FASTA, `.fai`, and alignment
- inspect alignment summary, not full alignment contents
- confirm required sorted/indexed formats for the selected SyRI input mode

**Red flags:**

- throwing 32 CPUs at SyRI without evidence
- running a full pair on login/admin node
- using unfiltered noisy alignments that inflate memory and false rearrangements

## OrthoFinder

**Typical use:** orthogroup inference, gene-family analysis, pan-genome supporting
analysis.

**Parallelism:** good in search and tree steps, but memory and disk grow quickly with
number of proteomes and total protein count.

**Memory drivers:**

- number of species/genomes
- total protein count
- DIAMOND/BLAST mode
- MSA/tree inference choices
- output directory size

**Starting points:**

- small test with a few proteomes: `normal`, 8-16 CPUs, 32-64G
- 10-30 plant genomes: `normal` or `fat`, 16-32 CPUs, 96-256G
- large pangenome-scale runs: require explicit sizing or a pilot, often `fat/fat2`

**Preflight checks:**

- count proteome files and approximate protein counts from headers or manifests
- check whether DIAMOND or BLAST is used
- confirm output directory is empty or intentionally resumable

**Red flags:**

- mixing isoforms without longest-transcript filtering
- requesting 64 CPUs when the node and workflow cannot use them efficiently
- insufficient disk for intermediate search results

## EDTA

**Typical use:** transposable element annotation and TE library construction.

**Parallelism:** can use multiple threads, but memory and runtime remain high for large
plant genomes. Treat it as a heavy job.

**Memory drivers:**

- genome size and repeat content
- LTR/Helitron/TIR discovery modes
- nested repeat complexity
- temporary directory growth

**Starting points:**

- small genome or test: `normal`, 8-16 CPUs, 64-100G
- quinoa/large plant genome: usually confirmation needed, 16-32 CPUs, 128-250G,
  `fat/fat2` if estimate is `>=200G`
- multiple genomes: array with low concurrency, often `%1-%2`

**Preflight checks:**

- use `.fai` or explicit genome file size
- ensure genome headers are clean, short/simple, and stable before launch
- set a project-local temp/output directory
- decide explicitly whether `--overwrite 0` resume, `--overwrite 1` rerun,
  `--force`, `--curatedlib`, or `--rmlib` is appropriate for this run
- label `.MAKER.masked` as gene-prediction mask evidence, not final TE composition
  evidence
- preserve full logs because EDTA failures often need stage-specific diagnosis

**Red flags:**

- running multiple EDTA jobs concurrently without memory accounting
- writing temporary files into protected raw-data directories
- treating a partial EDTA output as a completed annotation
- using `--overwrite 1` or replacing a DeepTE-refined TElib without an explicit
  backup/version policy

## TRF

**Typical use:** tandem-repeat discovery and simple tandem-repeat masking evidence.

**Parallelism:** limited to moderate depending on wrapper/environment. Treat output
size as the main risk on large plant genomes.

**Memory drivers:**

- genome size
- repeat density
- output `.dat`, `.mask`, and optional HTML report volume

**Starting points:**

- plant genome run: `normal`, 4-10 CPUs, 32-64G unless prior evidence supports more
- many genomes: array with a low concurrency cap from output I/O

**Preflight checks:**

- record the full seven numeric TRF parameters because they are encoded in output
  filenames
- confirm input genome FASTA version and whether `.mask` is only tandem-repeat
  evidence
- record that TRF is tandem-repeat discovery/masking, not whole-genome TE
  classification
- keep `.dat`, `.mask`, and logs together

**Red flags:**

- treating TRF `.mask` as a whole-genome TE annotation
- scanning or rendering TRF HTML/output folders recursively when only script
  extraction is needed

## RepeatModeler

**Typical use:** de novo repeat library construction.

**Parallelism:** moderate. `-pa` helps but memory and runtime are dominated by genome
size, repeat content, and database steps.

**Memory drivers:**

- genome size
- repeat content
- database construction
- number of parallel search workers

**Starting points:**

- bounded test or small genome: `normal`, 8-16 CPUs, 64-100G
- large plant genome: 16-32 CPUs, 128-250G; use `fat/fat2` if `>=200G`
- many genomes: array with `%1-%2`, because each job is long and heavy

**Preflight checks:**

- confirm BuildDatabase input and output naming
- put database and temp outputs under project results/tmp
- record RepeatModeler and RepeatMasker versions
- decide whether `-LTRStruct` is required for structural LTR recovery before
  comparing or scaling runs
- run one intended assembly/haplotype per database; do not split one genome into
  arbitrary chunks for naive later merging
- use `-recoverDir` only for a documented failed working directory

**Red flags:**

- high concurrency on shared `fat` nodes
- restarting into an unclear half-built database without documenting state
- assuming `-pa 32` always gives a proportional speedup
- running from slow shared paths when project-local scratch is available

## RepeatMasker

**Typical use:** homology-based repeat masking with a custom or curated repeat
library, often producing the soft-masked FASTA used by gene prediction.

**Parallelism:** moderate. `-pa` helps, but library size, genome size, rmblast, and
output writing are major drivers.

**Memory drivers:**

- genome size
- repeat-library size and classification quality
- `-pa` worker count
- `.out`, `.gff`, `.cat.gz`, and `.masked` output volume

**Starting points:**

- small/medium genome: `normal`, 8-16 CPUs, 64-120G
- quinoa-scale repeat masking: `fat`, 16-32 CPUs, 128-250G after confirmation
- many genomes: array with `%1-%2` if each task writes large `.out/.cat.gz` files

**Preflight checks:**

- confirm the repeat library source: RepeatModeler, EDTA, DeepTE-refined EDTA,
  curated library, or a merged/deduplicated library
- if the library was merged/deduplicated, verify `cd-hit-est` versus `cd-hit`, `-c`,
  `-n`, coverage thresholds, counts before/after, and `.clstr` provenance
- preserve useful `#class/subclass` labels in custom library FASTA headers when
  RepeatMasker class summaries are needed
- use `-xsmall` for gene-prediction softmasking unless a tool requires hard masking
- record `RepeatMasker`, rmblast, library checksum, `-pa`, backend, and `-rmblast_dir`
- account for backend-specific core multiplication from `-pa` before choosing SLURM
  CPUs
- run `bash -n` on wrapper scripts; malformed command continuations can make options
  such as `-pa` execute as separate shell commands

**Red flags:**

- using an unclassified or wrong-species library without labeling the limitation
- comparing masked percentages from different libraries as if they were the same
  method
- treating `.tbl` summary success as proof that GFF3 coordinates and library labels
  are publication-ready

## HiTE and panHiTE / Nextflow drivers

**Typical use:** single-genome TE discovery with HiTE, or multi-genome pan-TE
workflows through panHiTE/Nextflow.

**Parallelism:** HiTE uses a thread parameter for compute-heavy discovery stages.
The Nextflow SLURM job is usually only a launcher; real CPU, memory, partition, and
concurrency live in the Nextflow `process` config.

**Memory and disk drivers:**

- genome size and repeat content
- HybridLTR, NeuralTE, RepeatMasker, or other enabled submodules
- number of genomes in the manifest
- Nextflow `queueSize`, per-process `cpus`, per-process `memory`, and `workDir`
- container/Conda route and temporary directory growth

**Starting points:**

- single quinoa-scale HiTE pilot: `normal` or `fat`, 16-32 CPUs, 96-160G
- if requested memory is `<200G`, justify `fat/fat2` use or prefer `normal`
- panHiTE/Nextflow launcher: usually `normal`, 1-2 CPUs, 4-8G
- panHiTE child processes: often 16-32 CPUs and 60-160G per active process; cap
  `queueSize` from total memory and disk pressure before full scale

**Preflight checks:**

- review both the driver SLURM script and the `-c` Nextflow config
- confirm the run mode matches the installed route: Conda profile vs Singularity
  image, bind paths, and project-local `SINGULARITY_TMPDIR`
- keep `workDir`, output, trace, timeline, and report under the project
- run a single-genome pilot before a 20-genome or larger production run
- compare pilot `sacct` MaxRSS/Elapsed with requested resources before scaling

**Red flags:**

- treating the Nextflow launcher request as the total workflow resource request
- `queueSize * process memory` exceeding available node/account capacity
- switching from Conda to Singularity without updating run scripts and config
- full multi-genome launch without pilot completion evidence
- full FASTA body scans in input-prep scripts when `.fai` or existing metadata can
  provide genome sizes

## TEsorter and repeat post-processing

**Typical use:** classify intact LTRs or TE libraries against RexDB-style databases,
extract domains, build RT-domain alignments/trees, and support solo/intact LTR or TE
density analyses.

**Parallelism:** mode-dependent. TEsorter and MAFFT/IQ-TREE use threads, while large
joins, density windows, and bedtools intersections are often I/O-bound.

**Memory and disk drivers:**

- intact LTR count and extracted FASTA size
- `.domtbl`, `.dom.tsv`, `.dom.faa`, and class-library output size
- MAFFT alignment length and sequence count
- large join/merge tables for solo LTR superfamily annotation

**Starting points:**

- TEsorter on intact LTRs: `normal`, 8-20 CPUs, 32-100G
- quinoa-scale classification/tree work: 20-30 threads can be reasonable after
  checking sequence count
- large solo-LTR joins or density summaries: SLURM or approved compute context; do
  not run multi-GB joins casually on admin/login nodes

**Preflight checks:**

- confirm EDTA intact GFF3 and genome FASTA are from the same assembly
- verify command name in the environment (`TEsorter` vs `tesorter`)
- record database, usually `rexdb-plant`, coverage, e-value, prefix, target
  superfamily, and target domain
- distinguish element mode from genome mode; this route expects extracted TE/LTR
  sequences and `*.cls.*`/domain outputs
- state that unclassified elements can reflect database limits, divergence,
  no-domain/non-autonomous TEs, or false positives
- validate non-zero family/domain counts before MAFFT/IQ-TREE
- verify local IQ-TREE2 bootstrap option spelling (`-bb` vs local-help-confirmed
  `-B`) before reusing older scripts
- for density/metagene profiles, verify BED 0-based coordinates and chromosome names

**Red flags:**

- assuming EDTA `LTR/unknown` refinement, TEsorter classification, and RepeatMasker
  softmasking are interchangeable deliverables
- joining multi-GB solo-LTR tables without sorted-key checks and disk estimates
- using old `iqtree` PBS commands when the environment provides `iqtree2`

## STAR

**Typical use:** RNA-seq genome index generation and read alignment.

**Parallelism:** good for alignment and index generation, but memory depends strongly
on genome index and read workload.

**Memory drivers:**

- genome size and annotation
- genome index generation vs alignment mode
- number of concurrent sample jobs
- shared filesystem pressure from reading the same index

**Starting points:**

- genome index generation for plant genome: `normal` or `fat`, 12-24 CPUs, 80-200G
- per-sample alignment: `normal`, 8-16 CPUs, 32-80G
- many samples: array with `%2-%5`, lower if index I/O or memory pressure is high

**Preflight checks:**

- confirm genome FASTA, GTF/GFF, and chromosome naming match
- check whether the STAR index already exists
- avoid rebuilding index unless inputs or parameters changed

**Red flags:**

- many STAR jobs starting simultaneously against the same index
- underestimating memory for index generation
- placing STAR index in a temporary directory that may be deleted

## featureCounts

**Typical use:** gene-level counting from BAM files.

**Parallelism:** modest. It is usually efficient with low to moderate CPU requests.

**Memory drivers:**

- number and size of BAM files
- annotation size
- paired-end and multi-mapping options
- whether all BAMs are processed together

**Starting points:**

- few BAMs: `normal`, 2-4 CPUs, 8-24G
- many large BAMs: `normal`, 4-8 CPUs, 24-64G
- sample-wise arrays are usually not necessary unless the workflow needs per-sample
  isolation

**Preflight checks:**

- verify BAM indexes if later QC needs them
- check annotation format and feature type
- confirm strandedness and paired-end settings

**Red flags:**

- requesting 16-32 CPUs without evidence
- wrong strandedness, which wastes compute and gives unusable counts
- chromosome name mismatch between BAM and annotation

## PanGenie

**Typical use:** graph/pangenome-based genotyping.

**Parallelism:** moderate and mode-dependent. Memory can be high because graph, k-mer,
and sample-specific operations may dominate.

**Memory drivers:**

- graph/reference panel size
- k-mer database size
- sample read depth
- number of concurrent samples
- whether indexing/building or genotyping is being run

**Starting points:**

- per-sample genotyping with known stable setup: `normal` or `debug` only for tiny
  tests, 4-16 CPUs, 64-160G
- large panel or memory-heavy stage: `fat/fat2`, 8-24 CPUs, 160-300G after confirmation
- many samples: array with `%2-%5`, lower if `fat/fat2` queue is crowded

**Preflight checks:**

- inspect existing successful job records with `sacct` when rerunning similar batches
- confirm graph/index files are complete and stable
- check output naming so array tasks do not overwrite each other
- plan validation around expected genotype files, logs, and sample count

**Red flags:**

- using `debug` for full production batches
- uncapped arrays on memory-heavy stages
- resubmitting failed samples without reading `.err` and MaxRSS

## KMERIA

**Typical use:** k-mer based GWAS or genotype/phenotype association workflows built
from renamed FASTQ inputs, k-mer counting, matrix construction, filtering, format
conversion, and association testing.

**Parallelism:** stage-dependent. `kmeria count` can use threads per sample, but
the useful thread count must be measured because FASTQ I/O and k-mer table writes
can dominate. Matrix construction and association stages may have different CPU,
memory, and disk behavior; do not extrapolate from the count stage alone.

**Memory and disk drivers:**

- sample count and read depth
- k-mer size and min/max abundance filters
- whether count output is binary/text, KMERIA native, or KMC-compatible
- matrix-construction format and compression
- temporary count tables and filtered/BIMBAM outputs
- phenotype/sample order consistency

**Starting points:**

- install/CLI smoke test: login-safe only for `command -v`, `--version`, and tiny
  metadata checks; no FASTQ streaming on a login/admin node
- one-sample count benchmark: SLURM debug or normal, 4/8/16-thread comparison, full
  stderr/time log retained
- end-to-end pilot: small sample subset only after confirming count output can be
  consumed by matrix construction; request disk headroom and record per-stage sizes
- full sample set: split count by sample/batch with a conservative array cap; size
  matrix, filtering, and association stages from pilot evidence before submission

**Preflight checks:**

- verify renamed FASTQ symlinks with explicit manifests; do not write into raw-data
  directories
- preserve sample order from count through matrix, phenotype, and association files
- use long flags for Perl wrapper options when short flags have known collisions
- run generation-only or inspect wrapper output before executing generated stages
- treat wrapper text such as `IMPORTANT NOTE`, `kctm step currently expects KMC`,
  or `count output to KMC format` as a blocker until the format path is resolved
- keep full `kmeria count` stderr/time logs; failures may not include the literal
  word `error`
- avoid `rm -rf` cleanup of pilot/results directories; use a job-ID run directory or
  explicit user-confirmed cleanup

**Red flags:**

- `kmeria count` outputs are fed directly to `kctm` after a wrapper warning that the
  formats are incompatible
- a pilot rerun deletes the previous failed evidence directory
- `.err` is empty because stage stderr was redirected to a filtered/overwritten time
  file
- helper scripts contain `ls ... | head` under `set -euo pipefail`, causing a
  diagnostic preview to fail the job
- only count-stage disk/runtime is measured, then the full matrix/association run is
  scaled without validating downstream stages

## BLAST, DIAMOND, and HMMER-family searches

**Typical use:** sequence similarity, orthology support, annotation, domain search,
`hmmsearch`, `hmmscan`, `cmscan`, and related scans.

**Parallelism:** varies. DIAMOND is generally more scalable than classic BLAST. HMMER
tools may benefit from threads, but database size and output volume often dominate.

**Memory drivers:**

- database size
- query count
- output format and hit threshold
- per-task database loading when arrays run concurrently

**Starting points:**

- small annotation search: `normal`, 4-8 CPUs, 16-32G
- large protein/genome search: `normal`, 8-16 CPUs, 32-100G
- many independent query chunks: array with `%2-%5`, tuned to database loading pressure

**Preflight checks:**

- confirm database path and version
- estimate query count with a lightweight header count only on explicit files
- set output format to the minimum useful fields
- avoid wrapping long searches with `timeout`; use normal program exit and output checks

**Red flags:**

- verbose alignment output for huge searches
- many array jobs loading the same large database at once
- treating an interrupted output as complete

## hifiasm

**Typical use:** HiFi genome assembly, trio/hic-aware assembly, primary/alternate
contig generation.

**Parallelism:** strong but memory-heavy. Threads help graph construction and
correction, but memory, input read depth, and heterozygosity often dominate.

**Memory drivers:**

- HiFi read depth and total bases
- genome size, heterozygosity, and repeats
- assembly mode, especially Hi-C/trio/phasing inputs
- temporary graph and bin files

**Starting points:**

- tiny pilot or subset: `normal`, 8-16 CPUs, 64-128G
- quinoa-scale HiFi assembly: usually confirmation needed, 24-32 CPUs, 200-500G,
  `fat/fat2` when the estimate is `>=200G`
- multiple accessions: array only with very low concurrency, often `%1`

**Preflight checks:**

- estimate read bases from explicit FASTQ file sizes or prior seqkit summaries
- confirm HiFi read set, optional Hi-C/trio files, and output prefix
- ensure output and temp paths are project-local and large enough
- preserve logs and hifiasm `.bin` files if resumability matters

**Red flags:**

- starting full assembly on `normal` without memory evidence
- uncapped arrays of assemblies
- writing assembly outputs into raw-data directories

## Juicer and 3D-DNA

**Typical use:** Hi-C read alignment, contact-map generation, chromosome scaffolding,
misjoin correction, and review-ready assembly candidates.

**Parallelism:** pipeline-dependent. Alignment and split stages can parallelize, but
single stages and Java memory settings can bottleneck.

**Memory drivers:**

- genome size and number of restriction fragments or MboI/DpnII sites
- Hi-C read depth and lane count
- duplicate marking and sorting stages
- Java heap settings and temporary files

**Starting points:**

- small test: `normal`, 8-16 CPUs, 32-80G
- plant genome Hi-C run: `normal` or `fat`, 16-32 CPUs, 96-250G
- 3D-DNA polishing/scaffolding: `normal`, 8-16 CPUs, 64-160G unless prior OOM

**Preflight checks:**

- confirm restriction enzyme, genome `.fai`, and chromosome naming
- check whether Juicer expects a specific directory layout
- set Java memory explicitly when the wrapper supports it
- plan review outputs: `.hic`, assembly, lifted AGP, and logs

**Red flags:**

- many Hi-C samples reading/writing the same directories at once
- unclear enzyme choice or mixed libraries
- treating automated 3D-DNA output as final without manual/contact-map review

## BRAKER and MAKER

**Typical use:** protein-coding gene prediction and annotation using RNA-seq,
protein evidence, repeats, and ab initio predictors.

**Parallelism:** moderate and fragile. Wrappers launch many tools, and scaling depends
on species partitioning, evidence size, and database access.

**Memory drivers:**

- genome size and number of scaffolds
- RNA-seq BAM/protein evidence size
- repeat-masked genome quality
- Augustus/GeneMark/Exonerate stages and temporary files

**Starting points:**

- small scaffold subset: `normal`, 4-8 CPUs, 24-64G
- quinoa-scale annotation: `normal` or `fat`, 12-24 CPUs, 96-250G after confirmation
- chromosome-wise/scaffold-wise arrays: cap `%1-%3` and avoid shared output clashes

**Preflight checks:**

- confirm repeat-masked FASTA, evidence files, species model, and licenses
- check chromosome/scaffold naming across FASTA, BAM, GFF/GTF, and proteins
- ensure each array task has a unique working directory
- record tool versions because annotation wrappers are version-sensitive
- verify tool-specific modes against official docs or local wrapper source before
  scripting: BRAKER3 evidence mode, AUGUSTUS train/test split, HISAT2/StringTie
  transcript-assembly mode, TransDecoder transcript boundary, and SPALN/miniprot
  protein-to-genome output format
- when protein evidence is used, confirm the database is taxon-appropriate and broad
  enough for protein-family support; do not substitute a tiny convenience FASTA for an
  OrthoDB-style clade or multi-species related-protein library

**Red flags:**

- running wrappers in a shared output directory from multiple tasks
- missing GeneMark/Augustus configuration or licenses
- using unmasked repeats and then over-interpreting inflated gene counts
- evaluating a prediction with the same BUSCO lineage or evidence class that was used
  to optimize/train it without labeling that dependency

## bcftools and GATK

**Typical use:** SNP/INDEL calling, filtering, normalization, joint genotyping,
variant statistics, and VCF transformations.

**Parallelism:** mode-dependent. Many operations are single-threaded or modestly
parallel; interval/sample arrays often work better than very high CPUs per task.

**Memory drivers:**

- BAM/CRAM count and depth
- reference and interval size
- joint genotyping cohort size
- VCF compression/indexing and temporary files

**Starting points:**

- VCF filtering/stats: `normal`, 1-4 CPUs, 8-24G
- per-sample or per-chromosome calling: `normal`, 4-8 CPUs, 24-80G
- large cohort joint genotyping: `normal` or `fat`, 8-16 CPUs, 80-250G with pilot

**Preflight checks:**

- confirm FASTA index, sequence dictionary, BAM indexes, and chromosome names
- check interval/chromosome split strategy and array concurrency
- decide normalization and multiallelic handling before filtering
- preserve exact filter expressions and versions

**Red flags:**

- requesting 32 CPUs for mostly single-threaded filtering
- mixing references or chromosome naming schemes
- unbounded arrays over all samples/chromosomes against shared storage

## fastp, FastQC, and MultiQC

**Typical use:** raw-read QC, adapter/quality trimming, per-sample reports, and
multi-sample QC summaries.

**Parallelism:** fastp is moderately parallel and I/O-bound. FastQC is usually
per-file; MultiQC is light and should summarize existing reports.

**Memory drivers:**

- compressed FASTQ size and read length
- number of concurrent samples
- output compression and filesystem bandwidth
- FastQC temporary extraction/report generation

**Starting points:**

- per-sample fastp: `normal`, 4-8 CPUs, 8-24G
- FastQC arrays: `normal`, 1-4 CPUs, 4-12G per task, cap `%4-%10` by I/O pressure
- MultiQC summary: `normal` or login/admin only for small report directories,
  1-2 CPUs, 4-8G

**Preflight checks:**

- confirm paired-end naming and sample manifest
- avoid full decompression during inventory; use file sizes and names first
- set output report paths explicitly per sample
- run MultiQC only after expected per-sample reports exist

**Red flags:**

- launching many FASTQ decompression jobs at once
- writing trimmed reads into raw-data directories
- treating MultiQC success as proof every sample was processed

## MUMmer and plotsr

**Typical use:** assembly-to-assembly alignment, nucmer/delta filtering, synteny
visualization, and structural comparison plots.

**Parallelism:** nucmer is moderately parallel; filtering and plotting are often
limited by alignment size, memory, and graphics layout.

**Memory drivers:**

- assembly sizes and repeat content
- number and density of alignments
- delta/filter thresholds
- number of genomes and tracks in plotsr

**Starting points:**

- pairwise chromosome-level alignment: `normal`, 8-16 CPUs, 32-96G
- repetitive or many-contig assemblies: `normal` or `fat`, 12-24 CPUs, 96-200G
- plotsr visualization: `normal`, 1-4 CPUs, 8-32G unless input alignments are huge

**Preflight checks:**

- use `.fai` to confirm chromosome names and sizes
- decide nucmer presets and delta-filter thresholds before running full jobs
- keep alignment, filtered delta, and plotsr config paths explicit
- validate that plotted chromosomes are in the intended order

**Red flags:**

- unfiltered all-vs-all alignments fed directly into plotting
- chromosome name mismatches hidden by plotting defaults
- running many pairwise alignments without array concurrency caps

## BUSCO

**Typical use:** genome, transcriptome, or protein completeness assessment with
lineage datasets.

**Parallelism:** moderate. BUSCO can use CPUs, but lineage database, predictor mode,
and Augustus/MetaEuk/Miniprot stages affect scaling.

**Memory drivers:**

- input genome/proteome size
- selected lineage database
- mode (`genome`, `protein`, or `transcriptome`)
- predictor backend and temporary files

**Starting points:**

- protein-mode BUSCO: `normal`, 4-8 CPUs, 8-24G
- genome-mode BUSCO on plant assemblies: `normal`, 8-16 CPUs, 24-80G
- many genomes: array with `%2-%5`, lower if lineage database I/O is heavy

**Preflight checks:**

- confirm lineage dataset and offline/online behavior
- record BUSCO mode and version
- use a unique output directory per sample
- check that the output summary matches the expected sample count

**Red flags:**

- comparing BUSCO scores across different lineage datasets
- overwriting existing BUSCO output directories
- interpreting fragmented/duplicated BUSCOs without considering polyploidy

## QUAST

**Typical use:** assembly contiguity and reference-based quality metrics.

**Parallelism:** modest. Some stages use threads, but memory and runtime depend on
assembly size, reference alignment, and gene/feature annotation options.

**Memory drivers:**

- assembly and reference genome size
- number of assemblies compared
- reference-based alignment stage
- optional gene/feature annotations

**Starting points:**

- single assembly, no reference: `normal`, 2-4 CPUs, 8-24G
- reference-based plant assembly evaluation: `normal`, 4-8 CPUs, 24-80G
- multiple large assemblies: `normal`, 8-12 CPUs, 48-120G or split comparisons

**Preflight checks:**

- confirm assembly FASTA, optional reference, and gene annotation paths
- decide whether scaffolds/contigs below a threshold should be filtered
- create a fresh output directory or document intended overwrite/resume behavior
- pair QUAST with BUSCO or k-mer/read support when making quality claims

**Red flags:**

- comparing assemblies with different filtering thresholds
- over-weighting N50 without correctness/completeness checks
- running reference-based QUAST with mismatched chromosome naming

## Resource-report checklist

When reporting a proposed job, include:

- tool and mode
- input scale evidence, such as file sizes, `.fai`, sample count, or previous `sacct`
- CPU request and why more CPUs would or would not help
- memory estimate and main memory driver
- partition choice
- array range and concurrency cap if applicable
- temp/output disk estimate
- whether `#SBATCH --time` is absent, and why
- validation checks after completion
- risks that require user confirmation
