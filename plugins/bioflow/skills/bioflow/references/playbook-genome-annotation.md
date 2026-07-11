# Playbook - Genome annotation

> **Status: DRAFT for review.** Use this playbook when turning a finished and evaluated
> plant genome into repeat annotations, protein-coding gene models, functional
> annotations, and release-ready files. It routes detail to software resource cards;
> it is not a fixed command template.

## Table of contents

- Decision order
- Module A - input readiness
- Module B - repeat annotation and masking
- Module C - evidence preparation
- Module D - gene model prediction
- Module E - functional annotation
- Module F - QC, release, and handoff
- Multi-accession route
- Resource and SLURM routing
- Evaluation contract
- Silent traps

## Decision order

Do not start by writing a BRAKER, MAKER, or EDTA command. First decide:

1. **Annotation target:** one reference genome, haplotypes, or many accessions.
2. **Deliverable:** repeat-only, gene-structure-only, functional annotation, or full
   release.
3. **Evidence model:** RNA-seq only, protein only, RNA+protein, ab initio rescue, or
   existing annotation liftover.
4. **Masking model:** EDTA TE annotation, RepeatModeler+RepeatMasker softmasking, or
   both with separate purposes.
5. **Release policy:** ID prefix, chromosome naming, isoform policy, functional name
   confidence rules, and final file set.

If these choices are missing, list them as blockers instead of inventing defaults.

## Module A - input readiness

Required inputs before full annotation:

- evaluated genome FASTA and `.fai`
- assembly QC evidence: BUSCO genome mode, LAI or repeat-space proxy, contig/scaffold
  count, and chromosome naming policy
- explicit output root under the project, not protected raw-data or tool paths
- organism name, ploidy/subgenome context, and desired gene ID prefix
- RNA-seq FASTQ/BAM and/or related-species protein evidence, with sample provenance
- known organellar, contaminant, unplaced, and haplotig handling policy

Preflight checks:

- FASTA headers are short, stable, unique, and free of whitespace.
- Chromosome/scaffold names match RNA BAMs, GFF/GTF, BED, and downstream references.
- Existing outputs are either empty, explicitly resumable, or protected from overwrite.
- Work is staged under `results/`, `logs/`, `config/`, `reports/`, and project-local
  `tmp/`.

## Module B - repeat annotation and masking

Treat repeat discovery, repeat classification, and masking as separate deliverables.
For repeat-focused work, read `references/playbook-repeat-annotation.md` before
writing or reviewing scripts.

Recommended split:

- **TRF:** use for tandem-repeat discovery/masking evidence only; do not treat TRF
  `.mask` files as full TE annotation.
- **EDTA:** use for TE annotation and class-level TE GFF3 when the goal includes TE
  composition, LTR/TIR/Helitron calls, or repeat-aware figures.
- **RepeatModeler + RepeatMasker:** use for de novo repeat library construction and
  soft-masked FASTA for downstream gene prediction when this route is already used by
  the project or required by the predictor.
- **RepeatMasker softmasking:** prefer softmask (`-xsmall`) for gene predictors unless
  a tool explicitly needs hard-masked sequence.
- **DeepTE refinement:** use only as a versioned refinement of EDTA `LTR/unknown`
  libraries, with backups and a re-annotation step recorded.
- **solo LTR / TEsorter / RT trees:** treat as downstream repeat biology and
  classification, not as the source of the released masked genome.

Acceptance:

- final repeat GFF3 and/or masked FASTA are non-empty and tied to the exact genome
  FASTA version
- repeat class summaries exist and totals are plausible for the genome size
- EDTA TE GFF3 and RepeatMasker masked FASTA are not treated as the same evidence
- repeat-library provenance is explicit: RepeatModeler, EDTA, DeepTE-refined EDTA,
  curated library, or merged/deduplicated library
- logs show normal completion; partial stage directories are not called final

## Module C - evidence preparation

RNA evidence:

- Confirm strandedness, paired-end naming, sample tissue/stage, and reference version.
- Reuse a compatible STAR/HISAT2 index only when the genome and annotation inputs
  match; otherwise plan a rebuild.
- Keep coordinate-sorted BAMs, indexes, mapping summaries, and MultiQC or equivalent
  QC before passing evidence to predictors.
- Use RNA evidence as support for expressed models, not as proof that missing genes do
  not exist.

Protein evidence:

- Choose the protein evidence database by the target species, not by a fixed filename.
  Use the closest practical taxonomic scope with enough coverage: same species or
  genus when curated and not circular, otherwise the relevant family/order/clade.
  Example: quinoa can use Caryophyllales; another crop should switch to its matching
  family/order rather than reuse Caryophyllales.
- For EviAnn `-p`, prefer protein FASTA from multiple related species; its local
  `eviann.sh` help states UniProt/Swiss-Prot is a fallback when close relatives are
  unavailable. For BRAKER3 `--prot_seq`, follow the same evidence principle: use a
  broad protein-family database such as OrthoDB clades and add close relatives when
  useful.
- Avoid tiny hand-picked protein sets. A useful homology database should cover many
  protein families with multiple representatives, while avoiding uncontrolled
  isoform/duplicate inflation.
- Record taxon choice, source database, species list, version/date, sequence count,
  filtering policy, header-cleaning rule, deduplication rule, and checksum.
- Clean headers before predictors when needed; whitespace and `|` can trigger BRAKER
  warnings and downstream parsing problems.
- Remove obvious duplicates or isoform inflation when using protein sets as training
  or homology evidence.

Existing annotation evidence:

- If lifting over old annotations, record source assembly, liftover method, failed
  models, and whether lifted models are evidence or final calls.

## Module D - gene model prediction

Use a repeat-masked genome and explicit evidence paths. Pick the workflow by evidence:

- **BRAKER/BRAKER3:** good for RNA/protein-supported ab initio gene prediction when
  GeneMark/AUGUSTUS configuration is ready.
- **MAKER:** useful when combining repeats, protein evidence, transcripts, and ab
  initio predictors into iterative evidence-weighted models.
- **EVM/PASA/StringTie/TransDecoder-style routes:** use only when the project already
  follows that pattern or the user requests a custom consensus workflow.

Operational rules:

- Never run multiple chromosome/scaffold tasks into the same predictor work directory.
- For arrays, give every task a unique work/output directory and cap concurrency from
  memory, disk I/O, and database contention.
- Check official docs/GitHub or local installed wrapper source for the exact mode
  before turning a remembered command into a script. Record the source URL or local
  path, check date, tool version/container, and the reason the mode fits the evidence.
- Distinguish training or prediction evidence from independent validation. If a
  predictor used BUSCO/compleasm, target proteins, or a specific annotation as an
  optimization input, do not reuse the same evidence as an unqualified independent QC.
- Preserve full logs because wrapper failures are often hidden in nested logs.
- Define isoform policy before release: all isoforms, primary transcript, or
  longest-transcript set for downstream OrthoFinder/BUSCO.
- Define gene IDs once, for example `CquG000001`, and do not rename after downstream
  functional annotation unless a mapping table is released.

Structural QC:

- GFF3 parses and has valid `ID`/`Parent` relationships.
- CDS phases are valid; translated proteins have expected starts/stops and limited
  internal stops.
- Gene, mRNA, exon, CDS, UTR, intron, and isoform counts are summarized.
- BUSCO protein mode is run on the released protein FASTA.
- Gene density and model lengths are checked for obvious repeat-driven inflation.

## Module E - functional annotation

Use functional annotation to label proteins, not to repair weak gene models silently.

Core evidence classes:

- similarity: DIAMOND/BLASTP against Swiss-Prot, NR, or curated plant proteins
- domains: InterProScan, Pfam, HMMER-family searches
- orthology: eggNOG-mapper, OrthoFinder, or project-specific orthogroups
- pathways/terms: GO, KEGG/KOfam, MapMan, or project-selected databases

Rules for naming:

- Record database names, versions, dates, thresholds, and output fields.
- Avoid strong product names from one weak hit; use "putative" or domain-level names
  when evidence is partial.
- Keep raw hits, filtered hits, and final merged annotation as separate files.
- Do not mix different database versions in a comparison without labeling them.

Suggested outputs:

- `functional_raw/` for raw DIAMOND, InterProScan, eggNOG, HMMER outputs
- `functional.filtered.tsv` for filtered evidence
- `gene_function.tsv` with one row per released gene or transcript
- `annotation_methods.md` with database versions, thresholds, and merge priority

## Module F - QC, release, and handoff

Release file set:

- genome FASTA used for annotation
- repeat library, repeat GFF3, and masked FASTA
- gene models: `genes.gff3`, `transcripts.gff3` if separate, `cds.fa`,
  `protein.fa`, `transcript.fa`
- primary/longest transcript set when downstream comparative genomics needs it
- functional annotation table and raw evidence directory
- summary report with counts, BUSCO protein mode, repeat summary, and known caveats
- ID mapping table if any IDs were renamed

Before handoff, run the "Genome annotation checklist" in
`references/validation-checklists.md`.

## Multi-accession route

For pan-gene or multi-accession annotation batches, read
`references/playbook-pangene-batch-annotation.md` before generating scripts,
interpreting summaries, or comparing gene-model quality across samples.

## Resource and SLURM routing

Read these cards before writing scripts:

- `TRF`
- `EDTA`
- `RepeatModeler`
- `RepeatMasker`
- `TEsorter and repeat post-processing`
- `BRAKER and MAKER`
- `STAR` and `featureCounts` when preparing RNA evidence
- `BLAST, DIAMOND, and HMMER-family searches` for functional annotation
- `BUSCO` for genome/protein completeness checks

Use `references/executor-safety.md` for SLURM generation and preflight. Do not add
`#SBATCH --time` by default. Heavy annotation jobs need user confirmation before
submission, high-memory resource requests, or large database downloads.

## Evaluation contract

An annotation run is not complete until these are documented:

- exact genome FASTA checksum or path/version
- repeat annotation source and masked FASTA source
- predictor workflow, environment, tool versions, and evidence paths
- official documentation/GitHub or local wrapper source checked for each
  tool-specific mode, including check date and source
- final gene/transcript/protein/CDS counts
- BUSCO protein-mode lineage, version, and summary
- functional database names, versions, and filtering thresholds
- known excluded contigs, organellar sequences, contaminants, or failed regions
- final output paths and overwrite/resume policy

## Silent traps

- Unmasked repeats can inflate gene counts and create false multi-exon models.
- Hard-masked sequence can break evidence alignment or predictors when softmasking was
  expected.
- EDTA TE GFF3, RepeatMasker GFF, and soft-masked FASTA answer different questions.
- RNA-seq from limited tissues supports expressed genes but does not prove absence.
- BUSCO genome mode and protein mode answer different questions; do not compare them
  as the same metric.
- GFF3 files can look non-empty but still be unusable because `ID`, `Parent`, phase, or
  coordinate conventions are invalid.
- Wrapper arrays sharing one output directory can corrupt each other.
- Wrapper pipelines can hide tool-specific assumptions; verify BRAKER evidence mode,
  AUGUSTUS training split, TransDecoder transcript boundary, SPALN output mode, and
  HISAT2/StringTie alignment requirements explicitly.
- Functional names without database versions are not reproducible.
