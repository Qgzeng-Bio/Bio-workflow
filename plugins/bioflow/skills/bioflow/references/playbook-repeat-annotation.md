# Playbook - Repeat annotation

> **Status: DRAFT from real project evidence.** Distilled from the quinoa repeat
> annotation directory:
> `/data9/home/qgzeng/projects/2-C_quinoa/9-Annotation/1-Repeat`.
> Use this when extracting, planning, reviewing, or reproducing plant repeat
> annotation workflows. This is a process/QC reference, not a command template.

## Table of contents

- Source directory and safe-inspection rule
- Official source cross-check
- Workflow map
- Input contract
- Stage A - TRF tandem repeats
- Stage B - RepeatModeler de novo library
- Stage C - EDTA structural and whole-genome TE annotation
- Stage D - DeepTE refinement of EDTA LTR/unknown
- Optional library merging and deduplication
- Stage E - RepeatMasker softmasking
- Stage F - solo LTR and TE density profiling
- Stage G - TEsorter classification and RT phylogeny
- Resource notes
- Acceptance gates
- Silent traps

## Source directory and safe-inspection rule

The real directory is organized as:

```text
1-Repeat/
├── 1-TRF
├── 2-Repeatmodeler
├── 3-EDTA
├── 4-Repeatmasker
├── 5-solo_LTR
├── 6-TEsorter
├── Cqu_final_rename.fa -> ../../5-Gaps_filling/5-Rename/Cqu_final_rename.fa
└── atuo_repeat.sh
```

Inspect this kind of directory by script and metadata only. Do not read large
sequence, RepeatMasker, merged, BAM, or genome-scale GFF/OUT files unless the user
explicitly asks and the cost is justified. In the real run, examples of large files
include `5-solo_LTR/merged.txt` (~10.7G), `merged.clean.txt` (~3.6G), EDTA
`TE.fa`, RepeatMasker `.out`, and masked FASTA files.

Safe inventory pattern:

- top-level `ls -lah`
- `find <repeat_root> -maxdepth 2-3` restricted to scripts, README, and metadata
- `ls -lah` of explicit module directories
- `head`, `tail`, or `cat` only on small logs, summaries, and scripts

## Official source cross-check

Checked against official GitHub/docs on 2026-06-18. Keep the source URL, check
date, local tool version or container, and command mode in any Methods/report
manifest. Local quinoa scripts are evidence of what was run; official docs define
the reusable boundary for future species.

- **TRF**: tandem-repeat discovery. Use `.dat`/`.mask` as tandem-repeat evidence or
  a tandem-repeat mask, not as a whole-genome TE annotation.
- **RepeatModeler**: de novo repeat-family modeling from assembled genomes. Use
  `BuildDatabase` plus one `RepeatModeler` run per intended assembly to produce a
  family library for RepeatMasker/Dfam-style workflows. Do not split one genome into
  arbitrary chunks or naively merge independent runs as if they were one clean
  library.
- **EDTA**: automated whole-genome de novo TE annotation and TE library generation.
  Use its TElib, TEanno GFF3, summaries, intact TE calls, RM output, and optional
  masked genome for distinct downstream purposes. Sequence names should be short and
  stable; `--overwrite`, `--force`, and re-annotation after library edits must be
  explicit decisions.
- **DeepTE**: CNN-based TE classification for unknown TE sequences. In this playbook
  it refines EDTA `LTR/unknown` entries for plants, not genome-wide repeat discovery.
- **RepeatMasker**: homology-based screening/masking with a selected repeat library.
  Use `.masked` for downstream softmasked genome input, `.out/.gff` for repeat
  intervals, and `.tbl` for masking summaries. Interpret masked percentage only with
  the exact library and classification scheme.
- **LTR_retriever utilities**: solo/intact LTR summaries and related helper outputs
  support LTR-retrotransposon turnover questions. They are not a substitute for the
  full LTR_retriever discovery workflow unless candidate discovery, filtering, and
  LAI outputs are also generated.
- **TEsorter**: TE/LTR sequence classification and protein-domain extraction. Use
  `rexdb-plant` for plant LTR/TE sequence classification, domain tables, and RT-tree
  inputs. Its unclassified fraction is expected for non-autonomous/no-domain or
  divergent elements.
- **bedtools/samtools/MAFFT/IQ-TREE/CD-HIT**: use these as coordinate, extraction,
  alignment, tree, or deduplication utilities. For CD-HIT, distinguish protein
  clustering (`cd-hit`) from nucleotide library clustering (`cd-hit-est`). These
  utilities do not add biological evidence by themselves; their parameters define
  how evidence is summarized.

Official source anchors checked:

- TRF: `https://tandem.bu.edu/trf/trf.html` and `trf.unix.help.html`
- RepeatModeler: `https://github.com/Dfam-consortium/RepeatModeler`
- EDTA: `https://github.com/oushujun/EDTA`
- DeepTE: `https://github.com/LiLabAtVT/DeepTE`
- RepeatMasker: `https://github.com/Dfam-consortium/RepeatMasker`
- LTR_retriever: `https://github.com/oushujun/LTR_retriever`
- TEsorter: `https://github.com/zhangrengang/TEsorter`
- bedtools: `https://bedtools.readthedocs.io`
- samtools faidx: `https://www.htslib.org/doc/samtools-faidx.html`
- MAFFT: `https://mafft.cbrc.jp/alignment/software/manual/manual.html`
- IQ-TREE: `https://iqtree.github.io/doc/Command-Reference`
- CD-HIT: `https://github.com/weizhongli/cdhit/wiki/3.-User's-Guide`

## Workflow map

The reusable quinoa repeat workflow has two layers:

1. **Genome masking and TE annotation**
   - TRF for tandem repeats.
   - RepeatModeler for de novo repeat libraries.
   - EDTA for structure-based TE discovery, intact LTR/TIR/Helitron calls, TE
     library construction, and whole-genome TE annotation.
   - DeepTE to refine EDTA `LTR/unknown` labels.
   - RepeatMasker to softmask the genome with a chosen repeat library.
2. **Downstream repeat biology**
   - solo LTR and intact LTR ratios from LTR_retriever utilities.
   - TE density in fixed windows.
   - TE/LTR metagene profiles around genes.
   - TEsorter classification and RT-domain phylogeny for LTR subfamilies.

Keep these deliverables separate. A masked genome, an EDTA TE GFF3, a RepeatMasker
`.out`, a solo-LTR ratio table, and an RT tree are not interchangeable evidence.

Result-use principles:

- TRF `.mask`: tandem-repeat mask/evidence only.
- RepeatModeler `*-families.fa`: de novo repeat library input for RepeatMasker or
  later library merging/deduplication.
- EDTA `.TElib.fa`: non-redundant TE library for masking/re-annotation/reuse.
- EDTA `.TEanno.gff3` and `.TEanno.sum`: class-level whole-genome TE annotation and
  summary evidence.
- EDTA `.MAKER.masked`: low-threshold long-TE softmask useful for gene prediction;
  do not use it as the final TE composition table.
- RepeatMasker `.masked`: softmasked genome input for annotation tools; `.out/.gff`
  are interval evidence; `.tbl` is a summary, not coordinate validation.
- DeepTE-refined TElib: classification-improved EDTA library version that needs a
  new checksum and, when used for annotation, an explicit EDTA/RepeatMasker rerun.
- solo/intact ratio: relative LTR turnover signal tied to one TElib/RM.out pair; not
  total repeat burden.
- TE density/metagene profiles: spatial enrichment summaries and hypothesis support;
  not causal evidence by themselves.
- TEsorter domain tables and RT trees: family/domain classification and phylogenetic
  context for domain-containing elements; biased against no-domain/non-autonomous
  elements.

## Input contract

Before running or reviewing repeat annotation, record:

- exact genome FASTA path, checksum or version, `.fai`, and chromosome naming policy
- target mode: primary assembly, hap1/hap2, all accessions, or subgenome subsets
- coding sequence FASTA for EDTA `--cds`; EDTA expects CDS DNA sequences only, not
  introns, UTRs, or TE sequences
- repeat library source for RepeatMasker: RepeatModeler library, EDTA TElib,
  DeepTE-refined EDTA TElib, curated library, or a merged/deduplicated library
- environment/container paths and versions: EDTA image, RepeatModeler, RepeatMasker,
  rmblast, LTR_retriever, TEsorter, bedtools, seqkit/seqtk, mafft, iqtree2
- output root and overwrite/resume policy

For haplotype-aware runs, do not mix primary and haplotype file names. The real
project used examples such as `Cqu_final.fa`, `Cqu_final_rename.fa`,
`Cqu_final_rename_hap1.fa`, and `Cqu_final_rename_hap2.fa`.

## Stage A - TRF tandem repeats

Real command pattern:

```bash
trf <genome.fa> 2 7 7 80 10 50 500 -m -f -d
```

The seven numeric arguments are match, mismatch, indel delta, match probability,
indel probability, minimum alignment score, and maximum period size. The
`2 7 7 80 10 50 500 -f -d -m` pattern is the official example-style setting for a
general TRF run. Observed local examples used the `annotation` conda environment and
requested 10-30 CPUs with 64G in old PBS/SLURM scripts. Treat TRF as a
tandem-repeat stage; do not call its `.mask` output a full TE annotation.

Expected outputs:

- `<genome>.2.7.7.80.10.50.500.dat`
- `<genome>.2.7.7.80.10.50.500.mask`
- optional `html/` report
- scheduler stdout/stderr log

Acceptance:

- input genome path matches the intended assembly
- `.dat` and `.mask` are non-empty
- parameters are reported exactly, because TRF output filenames encode them

## Stage B - RepeatModeler de novo library

Real primary-assembly pattern:

```bash
BuildDatabase -name cqu_final Cqu_final.fa
RepeatModeler -threads 24 -database cqu_final
```

Real haplotype pattern:

```bash
BuildDatabase -name cqu_hap1 Cqu_final_rename_hap1.fa
RepeatModeler -threads 24 -database cqu_hap1
BuildDatabase -name cqu_hap2 Cqu_final_rename_hap2.fa
RepeatModeler -threads 24 -database cqu_hap2
```

Key outputs:

- `<prefix>-families.fa`
- `<prefix>-families.stk`
- `<prefix>-rmod.log`
- BLAST database side files such as `.nhr`, `.nin`, `.nsq`
- `RM_*` working directories

Acceptance:

- database prefix is deliberate and matches downstream library names
- `<prefix>-families.fa` is non-empty
- RepeatModeler log is kept and tied to the genome version
- `-LTRStruct` decision is recorded; use it when structural LTR discovery should be
  included in the de novo library, but do not silently add it when comparing against
  an older run
- the run is on the intended full assembly/haplotype, not arbitrary split chunks
- requested CPU/memory matches the real `-threads` value; in the observed scripts,
  `--cpus-per-task=32` but `RepeatModeler -threads 24`

Official-use notes:

- RepeatModeler is designed for assemblies, not raw reads.
- It is expected to run on a single machine per assembly; high-throughput batches
  should be separate assemblies with controlled array concurrency, not parallel
  chunks of the same genome.
- Prefer local/project scratch over shared network-heavy paths when possible, because
  the workflow performs many filesystem operations.
- Use `-recoverDir` only when resuming a documented failed working directory.

## Stage C - EDTA structural and whole-genome TE annotation

Real command pattern:

```bash
singularity exec ~/tools/edta/EDTA.sif EDTA.pl \
  --genome Cqu_final.fa \
  --species others \
  --step all \
  --force 1 \
  --overwrite 1 \
  --sensitive 1 \
  --anno 1 \
  --threads 32 \
  --cds Cquinoa_QQ74_v2_CDS.fasta
```

Observed version from logs: EDTA v2.2.0.

Parameter meaning that must be preserved:

- `--species others`: use when the target is not one of EDTA's built-in species
  presets.
- `--step all`: run full discovery, filtering/finalization, and annotation.
- `--sensitive 1`: use RepeatModeler to recover additional TEs; useful but heavy.
- `--anno 1`: perform whole-genome TE annotation after library construction.
- `--evaluate 1`: evaluate classification consistency when annotation is produced.
- `--force 1`: allow fallback behavior when no confident TE candidates are found;
  do not make this a hidden default for new species.
- `--overwrite 1`: destructive/resume-sensitive; require explicit user confirmation
  when rerunning in a non-empty EDTA directory.
- `--overwrite 0`: preferred resume behavior when restarting an interrupted run and
  preserving existing intermediate state.
- `--cds`: use coding DNA from this genome or a close relative, excluding introns,
  UTRs, and TEs.
- `--curatedlib`: curated TE library input when a trusted species/clade library is
  available.
- `--rmlib`: RepeatMasker library input for annotation mode when a custom library is
  deliberately selected.

Key outputs:

- `<genome>.mod.EDTA.TElib.fa`
- `<genome>.mod.EDTA.TEanno.gff3`
- `<genome>.mod.EDTA.TEanno.sum`
- `<genome>.mod.EDTA.intact.gff3`
- `<genome>.mod.EDTA.intact.fa`
- `<genome>.mod.EDTA.RM.out`
- `<genome>.mod.EDTA.RM.gff3`
- `<genome>.mod.MAKER.masked`
- `<genome>.mod.EDTA.TE.fa.stat`
- `*.TE.fa.stat.all.sum`, `*.nested.sum`, `*.redun.sum`

Acceptance:

- genome FASTA headers are short/simple and stable before EDTA is launched
- EDTA log reaches final annotation and evaluation completion markers
- output prefixes match the genome basename actually passed to EDTA
- final TElib, TEanno GFF3, TEanno sum, RM out/GFF, and intact LTR files are
  non-empty
- warnings about missing TE_SO terms, zero-byte raw components, or fallback behavior
  are reported rather than hidden
- `.MAKER.masked` is labeled as gene-prediction mask evidence, not final TE
  composition evidence

## Stage D - DeepTE refinement of EDTA LTR/unknown

Purpose: refine EDTA `LTR/unknown` sequences into `LTR/Copia`, `LTR/Gypsy`, or
remaining `LTR/unknown`, then rebuild EDTA annotation from the updated TElib.

Required inputs:

- EDTA prefix such as `Cqu_final.fa.mod.EDTA`
- `${PREFIX}.TEanno.sum`
- `${PREFIX}.TEanno.gff3`
- `${PREFIX}.final/${PREFIX}.TElib.fa` or top-level `${PREFIX}.TElib.fa`
- DeepTE script, for example `/data9/home/qgzeng/tools/DeepTE/DeepTE.py`
- DeepTE `Plants_model`
- `seqtk`

Real extraction and classification pattern:

```bash
grep "LTR/unknown" "${TELIB}" | grep "^>" | sed 's/^>//' | cut -d' ' -f1 > ids_LTR_unknown.txt
grep "^>" "${TELIB}" | grep -v "LTR/unknown" | sed 's/^>//' | cut -d' ' -f1 > ids_LTR_known.txt
seqtk subseq "${TELIB}" ids_LTR_unknown.txt > LTR_unknown.fa
seqtk subseq "${TELIB}" ids_LTR_known.txt > LTR_known.fa

python "${DEEPTE_PY}" -d . -o . -i LTR_unknown.fa -sp P -m_dir "${MODEL_DIR}" -fam LTR \
  1>DeepTE.log 2>&1

sed -e 's,LTR/unknown__ClassI_LTR_Copia,LTR/Copia,g' \
    -e 's,LTR/unknown__ClassI_LTR_Gypsy,LTR/Gypsy,g' \
    -e 's,LTR/unknown__ClassI_LTR,LTR/unknown,g' \
    opt_DeepTE.fasta > LTR_unknown_DeepTE.fa
cat LTR_unknown_DeepTE.fa LTR_known.fa > "${TELIB}.tmp"
mv "${TELIB}.tmp" "${TELIB}"
```

Optional re-annotation after updating TElib:

```bash
singularity exec ~/tools/edta/EDTA.sif EDTA.pl \
  --genome Cqu_final.fa \
  --step anno \
  --overwrite 1 \
  --anno 1 \
  --threads 16
```

Acceptance:

- original `${PREFIX}.TEanno.sum`, `${PREFIX}.TEanno.gff3`, and TElib are backed up
  before any overwrite
- `ids_LTR_unknown.txt`, `ids_LTR_known.txt`, `LTR_unknown.fa`, `LTR_known.fa`,
  `opt_DeepTE.fasta`, and `LTR_unknown_DeepTE.fa` are non-empty
- DeepTE log is saved and checked for normal completion
- updated TElib path and checksum are recorded
- EDTA `--step anno` rerun is treated as a new annotation version, not a silent edit
- DeepTE species mode is selected deliberately (`-sp P` for plants here), model
  directory/version is recorded, and the default or selected probability threshold is
  stated

Do not auto-download `Plants_model` during skill-driven execution without user
confirmation, because it is an external download and changes reproducibility.

## Optional library merging and deduplication

Use this only when intentionally merging RepeatModeler, EDTA, DeepTE-refined, or
curated libraries into a reusable masking library. Treat it as a new library version,
not an in-place cleanup.

For nucleotide TE libraries, prefer `cd-hit-est` or the local equivalent confirmed
by `command -v` and local help:

```bash
cd-hit-est \
  -i merged.TElib.fa \
  -o merged.TElib.nr.fa \
  -c 0.90 \
  -n 8 \
  -aS 0.90 \
  -d 0 \
  -T 8 \
  -M 0
```

Principles:

- Use `cd-hit` for protein FASTA and `cd-hit-est` for nucleotide DNA/RNA FASTA.
- `-c` is the identity threshold; `-aS` requires alignment coverage of the shorter
  sequence; `-d 0` keeps FASTA descriptions up to the first whitespace in cluster
  output.
- Choose `-n` consistently with the identity threshold and local CD-HIT help; for
  nucleotide `-c 0.90`, `-n 8` is the documented range.
- Keep both representative FASTA and `.clstr` cluster file, plus raw input checksum,
  output checksum, sequence counts before/after, and the exact command.
- Do not compare RepeatMasker masked percentages across raw and deduplicated
  libraries without labeling the library version.

## Stage E - RepeatMasker softmasking

Real command pattern:

```bash
RepeatMasker \
  -lib cqu_final-families.fa \
  -pa 32 \
  -xsmall \
  -gff \
  -norna \
  -no_is \
  -e rmblast \
  -rmblast_dir ~/anaconda3/envs/repeat/bin \
  ./Cqu_final.fa
```

Parameter meaning:

- `-lib`: custom repeat library, often RepeatModeler, EDTA, or a curated/merged
  library. FASTA IDs should preserve repeat class/subclass labels such as
  `#LTR/Gypsy` when library classification matters.
- `-pa`: parallel workers; account for backend-specific core multiplication rather
  than assuming requested cores equal `-pa`.
- `-xsmall`: softmask repeats with lowercase sequence for gene predictors.
- `-gff`: produce GFF output.
- `-norna`: leave small-RNA genes unmasked while still masking SINEs.
- `-no_is`: skip bacterial insertion sequence handling.
- `-e rmblast -rmblast_dir`: use rmblast backend from the recorded environment.

Expected outputs:

- `<genome>.masked`
- `<genome>.out`
- `<genome>.out.gff`
- `<genome>.tbl`
- `<genome>.cat.gz`

Observed quinoa sanity anchor from `Cqu_final.fa.tbl`:

- genome length: 1,271,319,056 bp
- bases masked: 883,133,327 bp, 69.47%
- retroelements: 36.94%
- LTR elements: 35.32%
- unclassified repeats: 26.64%

Use these values only as a same-project sanity anchor, not as a threshold for other
species.

Script caution from observed failed logs: do not split a RepeatMasker command with
comments or malformed line continuations in a way that turns `-pa` into a separate
shell command. Require `bash -n`, full stderr, and a command echo before submission.

## Stage F - solo LTR and TE density profiling

### solo/intact LTR ratio

The real workflow uses LTR_retriever helper scripts:

```bash
perl ~/tools/LTR_retriever/bin/find_LTR.pl -lib Cqu_final.fa.mod.EDTA.TElib.fa > TElib.fa.info
perl ~/tools/LTR_retriever/bin/solo_finder.pl \
  -i Cqu_final.fa.mod.EDTA.RM.out \
  -info TElib.fa.info > Cqu_RepeatMasker.solo.list
perl ~/tools/LTR_retriever/bin/intact_finder_coarse.pl \
  Cqu_final.fa.mod.EDTA.RM.out > Cqu_final.intact.list
perl ~/tools/LTR_retriever/bin/solo_intact_ratio.pl \
  Cqu_RepeatMasker.solo.list \
  Cqu_final.intact.list > Cqu_final.Cqu_final.solo_intact.ratio
```

Inputs:

- EDTA or curated `TElib.fa`
- EDTA `*.RM.out` or compatible RepeatMasker `.out`

Outputs:

- `TElib.fa.info`
- `*.solo.list`
- `*.intact.list`
- `*.solo_intact.ratio`

Boundary:

- This helper route is downstream summarization from a chosen TElib and compatible
  RepeatMasker/EDTA `.out`.
- A full LTR_retriever discovery/LAI workflow starts from LTR candidate files from
  tools such as LTRharvest/LTR_FINDER-like callers plus the genome, then produces
  filtered intact LTR lists, an LTR library, whole-genome LTR annotation, and LAI.
- Keep solo/intact ratios tied to the exact library and `.out`; changing either
  changes the biological denominator.

### Superfamily join

Observed join pattern:

```bash
sort -k1,1 Cqu_final.intact.list | uniq > intact.sorted
tail -n +2 TEnum_superfamily.out | awk 'BEGIN{OFS="\t"}{print $6, $0}' | sort -k1,1 > super.sorted
join -t $'\t' -1 1 -2 1 intact.sorted super.sorted > merged.tmp
awk 'BEGIN{OFS="\t"}{ $7=""; print }' merged.tmp | sed 's/\t\t/\t/g' > merged.clean.txt
```

This join can create multi-GB files. Treat it as a heavy I/O step: use SLURM, a
project-local output directory, and explicit expected disk growth.

### TE density

Observed density script:

```bash
samtools faidx <genome.fa>
cut -f1-2 <genome.fa>.fai > <prefix>.sizes
bedtools makewindows -g <prefix>.sizes -w 200000 > <prefix>_200000bp.windows
awk -v t="$type" 'NR==6 || $3==t' <EDTA.TEanno.gff3> > <type>.gff3
awk '{print $1"\t"$4"\t"$5"\t"$3}' <type>.gff3 > <type>.pos
bedtools intersect -a <windows> -b <type>.pos -c > <type>.density
```

`bedtools intersect -c` reports the count of overlaps for each window. For very
large window/feature files, presort both sides and use the sorted algorithm when the
coordinate sort order is valid.

Default observed types:

- `Gypsy_LTR_retrotransposon`
- `Copia_LTR_retrotransposon`
- `CACTA_TIR_transposon`
- `helitron`

Do not rely blindly on `NR==6` as the header rule for new EDTA versions. Validate
the GFF3 header and feature type names first.

### Flanking-gene and metagene profiles

Input preparation:

- convert gene GFF3/GTF to BED6: `chrom start0 end gene_id . strand`
- convert TE/LTR intervals to midpoint 1-bp BED for frequency profiles
- use compatible chromosome names across genes, TE BED, and genome sizes

Observed plotting defaults:

- flank: 2 kb up/down
- flank bin: 100 bp
- gene body bins: 100
- smoothing window: 5
- output: TSV, PDF, PNG
- tool core: `bedtools intersect -c` over generated metagene bins

## Stage G - TEsorter classification and RT phylogeny

### TEsorter from EDTA intact LTRs

Reusable script route:

```bash
bash step1_run_TEsorter_from_EDTA.sh \
  -g <genome.fa.mod.EDTA.intact.gff3> \
  -f <genome.fa> \
  -p 30 \
  -d rexdb-plant \
  -c 10 \
  -e 1e-2 \
  -o TE_analysis
```

Internal logic:

- select GFF3 records where column 3 contains `LTR_retrotransposon` and attributes
  contain `method=structural`, case-insensitive
- convert to BED6 with 0-based starts
- replace strand `?` with `+` before sequence extraction
- extract stranded sequences with `bedtools getfasta -name -s`
- simplify `bedtools` headers from `ID::coords` to `ID`
- run `TEsorter` with `rexdb-plant`, coverage, e-value, and prefix settings

Expected outputs:

- `TE_analysis.intact_LTR.bed`
- `TE_analysis.intact_LTR.fa`
- `TE_analysis.cls.tsv`
- `TE_analysis.dom.gff3`
- `TE_analysis.dom.tsv`
- `TE_analysis.dom.faa`
- `TE_analysis.cls.lib`
- `TE_analysis.cls.pep`

Official-use notes:

- In element mode, TEsorter input is TE/LTR sequences, not the whole genome; the
  script extracts intact LTR sequences from EDTA before running TEsorter.
- `rexdb-plant` is the default plant choice; record any change to `rexdb` or `gydb`.
- Lower coverage/higher e-value settings such as `-cov 10 -eval 1e-2` increase
  sensitivity; stricter coverage/e-value settings increase specificity.
- Genome mode has different output behavior and does not produce all `*.cls.*`
  outputs expected by this route.
- TEsorter reports the best domain hit per domain; unclassified elements may reflect
  incomplete databases, divergent/mutated elements, no-domain/non-autonomous TEs, or
  false positives.

### RT-domain alignment and tree

Reusable script route:

```bash
bash step2_run_RT_tree.sh \
  -a TE_analysis.dom.faa \
  -b TE_analysis.dom.tsv \
  -s Ty1_copia \
  -m RT \
  -t Cqu \
  -o Cqu_Copia \
  -p AUTO
```

Internal logic:

- filter `.dom.tsv` by superfamily and exact domain match using a pattern like
  `-${DOMAIN}\t`
- extract domain sequences with `seqtk subseq`
- simplify FASTA IDs and add a species/sample tag
- align with `mafft --auto`
- optionally format insertion-time metadata
- build tree with model selection and ultrafast bootstrap, for example
  `iqtree2 -s <alignment> -m MFP -bb 1000 -T <threads>` or the local-help-confirmed
  `-B 1000` form

Expected outputs:

- `<prefix>.RT.id.list`
- `<prefix>.RT.raw.fa`
- `<prefix>.RT.clean.fa`
- `<prefix>.RT.aln`
- `<prefix>.RT.tree.treefile`
- `<prefix>.RT.tree.iqtree`

Acceptance:

- if using official TEsorter helper extraction, record the `concatenate_domains.py`
  command and domain naming scheme; if using the local `seqtk` route, verify domain
  names in `.dom.tsv` first
- `.dom.tsv` family/domain spelling is verified before filtering
- target family/domain count is non-zero
- MAFFT alignment is non-empty
- IQ-TREE2 is optional but its skip or completion is logged
- tree IDs can be linked back to intact LTR coordinates or insertion-time records

## Resource notes

Observed starting points from local scripts:

- TRF: old scripts used 10-30 CPUs and 64G
- RepeatModeler: `fat`, 32 CPUs, 200G requested, with `RepeatModeler -threads 24`
- EDTA: `fat`, 32 CPUs, 300G requested
- DeepTE refinement: `fat`, 16 CPUs, 80G requested
- RepeatMasker: `fat`, 32 CPUs, 200G requested
- TEsorter: 20-30 threads in script examples
- RT tree: MAFFT/IQ-TREE2 can use many threads, but tree building should be sized
  from sequence count and alignment length

For new runs, use these only as starting points. Estimate from genome size, repeat
content, library size, intermediate file growth, and prior `sacct` where available.
Use low array concurrency for multi-genome EDTA/RepeatModeler/RepeatMasker runs.
Do not add `#SBATCH --time` by default.

## Acceptance gates

Do not call repeat annotation complete until all relevant gates pass:

- genome FASTA and `.fai` match the intended assembly and chromosome naming
- all tool versions, containers, environments, database/library paths, and parameters
  are recorded
- EDTA final TElib, TEanno GFF3, TEanno sum, RM out/GFF, and intact LTR files exist
  and are non-empty
- RepeatModeler family libraries and logs exist for the intended primary or haplotype
  genomes
- RepeatMasker `.masked`, `.out`, `.out.gff`, `.tbl`, and `.cat.gz` exist when
  softmasking is requested
- RepeatMasker `.tbl` masked percentage is plausible for the target species and not
  interpreted without considering library choice
- DeepTE-refined libraries have backups, logs, non-empty input/output ID lists, and a
  new checksum or version label
- solo/intact LTR ratios are tied to the exact TElib and `RM.out` used
- density and metagene profiles use consistent 0-based BED coordinates and chromosome
  names
- TEsorter outputs include non-empty class/domain tables before downstream phylogeny
- any large merge/join output is run under SLURM or an approved compute context, not
  casually on an admin/login node

## Silent traps

- `atuo_repeat.sh` has CRLF line endings in the observed file; normalize before
  reuse.
- Quoted paths containing `~`, such as `"~/tools/RepeatModeler/BuildDatabase"`, do
  not expand in Bash. Use `$HOME/...` or an absolute path.
- Old PBS scripts are historical evidence, not current qgzeng SLURM templates.
- `source ~/.bashrc` under `set -u` can fail if shell startup files reference
  undefined variables; guard it when needed.
- EDTA `--overwrite 1`, DeepTE `mv` over TElib, and RepeatMasker output reuse can
  replace evidence; require explicit overwrite policy.
- External DeepTE model download changes reproducibility and requires confirmation.
- RepeatMasker command continuations must not place comments or extra text where the
  next option becomes a separate shell command.
- `samtools faidx` creates a `.fai`; state this write before running it.
- `join` requires both inputs sorted on the join key; unsorted inputs can silently
  corrupt merged superfamily tables.
- Metagene profiles require BED 0-based half-open coordinates; do not feed raw GFF3
  coordinates directly.
- TEsorter command name can differ by environment (`TEsorter` versus `tesorter`);
  check `command -v` in the activated environment.
- `iqtree` and `iqtree2` option names differ; verify the binary before reusing old
  PBS tree scripts.
