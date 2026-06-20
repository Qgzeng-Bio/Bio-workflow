# Playbook — Centromere localization by CENH3 ChIP-seq (+ TRASH/HOR structural) — polyploid

> **Status: DRAFT for review.** Distilled from the completed, working **LM134** run under
> `8-Structure/1-Centromere/4-Chipseq` (CENH3 IP vs input ChIP-seq, mapped to `Cqu_final.fa`). Style: flexible.
> Lines marked **〔verify〕** still need sign-off.
>
> **Part of the Genome-structure umbrella** — analyses run on an already-finished, evaluated assembly
> (output of `playbook-genome-finishing.md` / `playbook-genome-quality-evaluation.md`), not part of the
> linear de-novo pipeline. Sibling: `playbook-segmental-duplications.md`. **Scope here = a single reference
> individual** (LM134 → `Cqu_final.fa`); the 19-accession `samples/` generalization is out of scope.

## When to use

Locate the **functional centromere of each chromosome** on a finished assembly using **CENH3 ChIP-seq**
(immunoprecipitation vs input), then cross-validate with the **TRASH satellite-monomer + HOR** structure.

Two **independent evidence axes** — keep them separate by design:
- **Functional / epigenetic** — where CENH3 nucleosomes sit = log2(IP/Input) enrichment domains.
- **Structural / DNA** — the centromeric satellite array (quinoa's **40-bp** monomer) and its higher-order
  repeat (HOR) organization, from TRASH + modDotPlot.

**Final boundaries = the TRASH+modDotPlot structural call, *confirmed or selectively adjusted* by CENH3.**
In the LM134 run only **Cq7B** was changed (expanded to the full local CENH3 domain); weak right-tail CENH3
signal on Cq2B/Cq8B/Cq9B was deliberately **not** used to extend boundaries.

**Biological output (one line):** per-chromosome centromere coordinates for all 18 chromosomes (Cq1A…Cq9B)
against `Cqu_final.fa` → `09_hor/LM134_final_centromere_prediction.CENH3_TRASH_HOR.final.bed` (e.g. Cq1A
28,896,000–36,608,999).

---

## Setup — reference, env, inputs

- **Reference:** `Cqu_final.fa` (the finished AABB chromosome assembly), symlinked into `00_ref/`. **Effective
  genome size = 1,271,319,056 bp** (sum of `.fai` lengths; the preflight asserts it — reuse this constant in
  MACS2 `-g` and deepTools `--effectiveGenomeSize`).
- **Conda env `cenh3_chipseq`** — `bwa, samtools, macs2, deeptools (bamCoverage/bamCompare), bedtools, python+pyBigWig`.
- **Separate venv** for HOR + modDotPlot: `/data9/home/qgzeng/tools/ModDotPlot/venv/bin/python` (matplotlib/cairosvg/pyBigWig).
  **TRASH itself is run upstream** (env `trash`) — its monomer/region tables are inputs here, not a step in this dir.
- **Inputs (paired-end FASTQ):** IP = `IP_LM_134_CENH3_R1/2.fq.gz`, Input = `IN_LM_134_R1/2.fq.gz` (+ `md5.txt`).
- **No read trimming step** — raw FASTQ goes straight to `bwa mem`; QC is post-alignment only.
- **SLURM:** `-p normal`, `--cpus-per-task=24`, `--mem=120G` (bwa `-t 24`, sort/deeptools `-@ 8`). No `--time`.

---

## Stage A — align (repeat-aware) + filter branches + dedup

```bash
conda activate cenh3_chipseq
bwa index 00_ref/Cqu_final.fa && samtools faidx 00_ref/Cqu_final.fa
mkdir -p 01_bam 03_peaks 04_bigwig 05_domains 06_overlap 07_report 09_hor

# align + filter + index BOTH samples (IP = CENH3 immunoprecipitate, IN = input control)
for S in IP IN; do
  # bwa -a emits secondary alignments; the -F 2308 filter below drops them again, so each branch is PRIMARY-only
  bwa mem -a -t 24 00_ref/Cqu_final.fa ${S}_R1.fq.gz ${S}_R2.fq.gz | samtools sort -@ 8 -o 01_bam/${S}.all.sorted.bam -
  # MAIN branch: proper-paired PRIMARY, NO MAPQ filter (retains reads that multi-map in repeats)
  samtools view -@ 8 -b -f 2 -F 2308    -o 01_bam/${S}.repeatAware.primary.bam 01_bam/${S}.all.sorted.bam
  # control branch: same + MAPQ≥30
  samtools view -@ 8 -b -f 2 -F 2308 -q 30 -o 01_bam/${S}.unique.q30.bam       01_bam/${S}.all.sorted.bam
  samtools index -@ 8 01_bam/${S}.repeatAware.primary.bam
  samtools index -@ 8 01_bam/${S}.unique.q30.bam
done

# dedup (markdup -r) — sensitivity control; shown for the MAIN branch (repeat for unique.q30 → *.unique.q30.dedup.bam)
for S in IP IN; do
  samtools sort -n -@ 8 01_bam/${S}.repeatAware.primary.bam | samtools fixmate -m - - \
    | samtools sort -@ 8 - | samtools markdup -r -@ 8 - 01_bam/${S}.repeatAware.dedup.bam
  samtools index -@ 8 01_bam/${S}.repeatAware.dedup.bam
done
```

- `-f 2` proper pair; `-F 2308` drops unmapped(4)+**secondary(256)**+supplementary(2048) → so despite `bwa -a`,
  each branch is **primary-only** (one record per read; the MAIN branch simply omits the MAPQ filter).
- **`repeatAware.primary` (no-MAPQ-filter, non-dedup) is the MAIN analysis branch** — it keeps low-MAPQ reads
  (the ones that map ambiguously inside repeats) so CENH3 signal in repeat-rich centromeres is not under-counted.
  `unique.q30` + the `dedup` branches are **sensitivity controls only**. Post-align QC = `samtools flagstat`/`stats`
  + a MAPQ histogram per BAM.

## Stage B — coverage / log2(IP/Input) tracks (deepTools)

```bash
# per-sample CPM track (IP, IN), 50-bp bins, extend read pairs
for S in IP IN; do
  bamCoverage -b 01_bam/${S}.repeatAware.primary.bam --normalizeUsing CPM --binSize 50 \
      --effectiveGenomeSize 1271319056 --numberOfProcessors 8 --extendReads \
      -o 04_bigwig/${S}.repeatAware.CPM.bw
done
# log2(IP/Input) — the MAIN track (run for all 4 branches; repeatAware.primary shown)
bamCompare -b1 01_bam/IP.repeatAware.primary.bam -b2 01_bam/IN.repeatAware.primary.bam \
    --operation log2 --normalizeUsing CPM --scaleFactorsMethod None --binSize 50 --pseudocount 1 \
    --effectiveGenomeSize 1271319056 --numberOfProcessors 8 --extendReads \
    -o 04_bigwig/LM134_CENH3.repeatAware.log2IPInput.bw
```

Key params: **binSize 50**, CPM, `--scaleFactorsMethod None`, `--pseudocount 1`, `--extendReads`. The main
track is `LM134_CENH3.repeatAware.log2IPInput.bw`.

## Stage C — CENH3 domain calling (the core functional definition)

```bash
# bigWig → bedGraph (bigWigToBedGraph, or the pyBigWig fallback in the master script) → sort
sort -k1,1 -k2,2n track.bedGraph > sorted.bedGraph
# threshold log2(IP/Input) ≥ 1  (≥2× enrichment)
awk '($4!="nan" && $4>=1){print $1"\t"$2"\t"$3"\t"$4}' sorted.bedGraph | sort -k1,1 -k2,2n > log2ge1.sorted.bed
# merge bins within 5 kb (keep mean signal), then keep domains ≥ 5 kb
bedtools merge -i log2ge1.sorted.bed -d 5000 -c 4 -o mean > merged.raw.bed
awk '(($3-$2)>=5000)' merged.raw.bed > 05_domains/LM134_CENH3.repeatAware.CENH3_domains.bed
bedtools map -a 05_domains/LM134_CENH3.repeatAware.CENH3_domains.bed -b sorted.bedGraph -c 4 -o mean,max \
    > 05_domains/LM134_CENH3.repeatAware.CENH3_domains.signal.tsv
```

Domain params: **`LOG2_THRESHOLD=1`, `MERGE_GAP=5000`, `MIN_DOMAIN_LEN=5000`**. `repeatAware.CENH3_domains.bed`
is the main domain set (the run aborts if it is empty).

## Stage D — MACS2 peaks (auxiliary evidence only)

```bash
macs2 callpeak -t 01_bam/IP.repeatAware.primary.bam -c 01_bam/IN.repeatAware.primary.bam \
    -f BAMPE -g 1271319056 -n LM134_CENH3_repeatAware_noDedup --outdir 03_peaks -q 0.01 --keep-dup all
# also: unique.q30 (narrow), and a broad call: --broad --broad-cutoff 0.05
```

`-f BAMPE` (paired-end, no `--extsize`), `-q 0.01`, `--keep-dup all`. MACS2 is **supporting evidence**, not the
domain caller — the log2 domains (Stage C) define CENH3 occupancy.

## Stage E — integrate with structure (TRASH/modDotPlot), validate, call boundaries

```bash
# reference BEDs (chrom-name normalized, sorted): TRASH satellite regions + a refined-boundary v2 (LM134 rows)
DOM=05_domains/LM134_CENH3.repeatAware.CENH3_domains.bed
bedtools coverage  -a "$DOM" -b TRASH_regions.Cqu_final.bed                > 06_overlap/domain_TRASH_repeat_coverage.tsv
bedtools coverage  -a "$DOM" -b centromere_refined_boundaries.v2.LM134.bed > 06_overlap/domain_refined_coverage.tsv
bedtools intersect -c -a "$DOM" -b 03_peaks/LM134_CENH3_repeatAware_noDedup_peaks.narrowPeak > 06_overlap/domain_macs2_peak_counts.tsv

# functional-core validation vs the structural (TRASH+modDotPlot) prediction
python scripts/build_lm134_cenh3_final_review.py \
    --structural-bed 06_overlap/LM134_final_centromere_prediction.TRASH_modotplot.as_supplied.bed \
    --flank 2000000 --bin-size 10000 --cluster-gap 50000
```

For each of the 18 structural intervals this pulls log2 mean/max + MACS2 counts + domain overlap, merges CENH3
domain fragments within **50 kb** into core clusters, and picks the **dominant (largest) cluster** per
chromosome with an `auto_support_level` (strong_compact_core / strong / moderate / weak) and
`manual_status=pending_IGV_review`.

## Stage F — TRASH monomers + HOR scoring (structural axis)

TRASH ran upstream (env `trash`); its monomer table feeds the HOR analysis:

```bash
/data9/home/qgzeng/tools/ModDotPlot/venv/bin/python scripts/analyze_lm134_hor.py \
    --monomers TRASH_all_repeats_selected_monomers_LM134.tsv \
    --structural-bed 06_overlap/LM134_final_centromere_prediction.TRASH_modotplot.as_supplied.bed \
    --cenh3-core-bed 07_report/LM134_CENH3_functional_core.dominant_cluster.preliminary.bed \
    --outdir 09_hor
# defaults: 40-bp primary monomer; 79-bp dimer → two overlapping 40-bp units; 171-bp = secondary family (excluded);
#           subtype greedy-cluster Hamming ≤ 6/40; HOR scan period 2–25, ≥3 repeats, match-fraction ≥ 0.70.
```

Yields a 0–100 `HOR_structure_score` (monomer density 20 + HOR coverage 25 + periodicity 25 + copy number 15 +
continuity 15) and an HOR class. Optional structural cross-check (Cq7B): `moddotplot static -k 21 -m 1000 -w 5000`.

## Stage G — final integrated call + plots

Final coordinates: `09_hor/LM134_final_centromere_prediction.CENH3_TRASH_HOR.final.bed` / `.tsv` are
**0-based, half-open** intervals (`length_bp = end - start`; verified from the LM134 final TSV). The `.tsv`
records `final_status` / `decision_basis` / `comment` per chromosome. Plots: genome-wide overview (100-kb bins),
per-chromosome zoom (±2 Mb, 10-kb bins), HOR "h-like" figures, Fig1C ideogram.

---

## inputs → outputs → params

| Stage | Tool | Input | Output | Key params |
|---|---|---|---|---|
| A align | `bwa mem` → `samtools sort` | IP/IN FASTQ + ref | `*.all.sorted.bam` | `bwa mem -a -t24`; **no trimming** |
| A filter | `samtools view` | all.sorted.bam | `repeatAware.primary` (main), `unique.q30` | `-f 2 -F 2308` (+ `-q 30`) |
| A dedup | `samtools fixmate -m` + `markdup -r` | branch BAMs | `*.dedup.bam` | controls only |
| B tracks | `bamCoverage`, `bamCompare` | branch BAMs | `*.CPM.bw`, `*.log2IPInput.bw` | CPM, binSize 50, `--scaleFactorsMethod None --pseudocount 1 --extendReads` |
| C domains | `awk` + `bedtools merge/map` | log2 bigWig | `*.CENH3_domains.bed` | **log2 ≥ 1, merge 5 kb, ≥ 5 kb** |
| D peaks | `macs2 callpeak` | IP+IN BAM | `*_peaks.{narrow,broad}Peak` | `-f BAMPE -g 1271319056 -q 0.01 --keep-dup all` |
| E validate | `bedtools`, `build_lm134_cenh3_final_review.py` | domains, structural bed, peaks, bigWigs | functional-core preliminary BEDs | flank 2 Mb, bin 10 kb, cluster-gap 50 kb |
| F HOR | `analyze_lm134_hor.py` (ModDotPlot venv) | TRASH monomers, structural bed, core bed | HOR tables + 0–100 score | 40 bp monomer; Hamming ≤ 6/40; period 2–25, match ≥ 0.70 |
| G final | final BED + plot scripts | all above | `…CENH3_TRASH_HOR.final.bed/.tsv` + figures | genome 100 kb / zoom 10 kb |

## How this maps onto the bio-workflow safety layer

1. **Design** here → IP/Input ChIP, the four BAM branches, log2 domains, structure cross-check.
2. **Generate** with `gen_sbatch.sh` (`--partition normal --cpus 24 --mem 120G`; forward `${SLURM_CPUS_PER_TASK}` to `bwa -t`).
3. **Gate** with `prepare_submission.sh` (inputs incl. the IP/IN pairs + `md5.txt`; one ChIP job is well under 200/100/600).
4. **Submit + record** with `submit_and_log.sh --yes`; the master `run_lm134_cenh3_chipseq.sh` is idempotent (steps skip on valid output).
5. **Validate** — flagstat/MAPQ QC, a non-empty main domain set, and IGV review of the dominant clusters before finalizing boundaries.

## Pitfalls

- **No read trimming** — confirm read quality is acceptable before trusting the signal.
- **Keep multimappers in the main branch** (`bwa mem -a`, no MAPQ filter) — centromeres are repeat-rich; a
  MAPQ≥30-only analysis under-counts CENH3. The q30/dedup branches are sensitivity checks, not the answer.
- **Two evidence axes stay separate** — CENH3 (functional) vs TRASH/HOR (structural DNA). The HOR score is an
  in-house monomer-order metric, not a universal HOR definition.
- **Final boundaries are semi-manual** — structural (TRASH+modDotPlot) call confirmed/adjusted by CENH3; only
  change a boundary with explicit evidence (LM134: only Cq7B). Weak tails were intentionally not used to extend.
- **Two Python environments** — alignment/peaks/tracks in conda `cenh3_chipseq`; HOR + modDotPlot in the ModDotPlot venv.
- **Coordinate convention** — final BED/TSV are **0-based half-open** (`length_bp=end-start`). TRASH monomer
  inputs may arrive in mixed inclusive/width conventions; `analyze_lm134_hor.py` normalizes monomer units with
  `to_half_open()` before overlap/HOR scoring. Convert to 1-based inclusive only at FASTA slicing/reporting boundaries.
- **Reuse the genome-size constant** `1271319056` for MACS2 `-g` and deepTools `--effectiveGenomeSize`.

## Sources

- BWA — Li & Durbin 2009; samtools — Danecek et al. 2021. MACS2 — Zhang et al., *Genome Biol* 2008.
- deepTools (`bamCoverage`/`bamCompare`) — Ramírez et al., *NAR* 2016.
- bedtools — Quinlan & Hall, *Bioinformatics* 2010.
- TRASH — Wlodzimierz et al., *Nat Commun* 2023 (tandem-repeat / satellite monomer + HOR). ModDotPlot — Sweeten et al. 2024.
- CENH3 marks functional centromeres — e.g. quinoa/plant CENH3 ChIP-seq literature; the 40-bp satellite is quinoa's centromeric monomer.
