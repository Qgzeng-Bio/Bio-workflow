# Playbook — Genome finishing: reference scaffolding (RagTag) · gap filling · polishing

> **Status: DRAFT for review.** Distilled from completed, **verified-successful** quinoa runs
> (`4-scaffolding/4-Ragtag`; `5-Gaps_filling/{2-gaps_filling,6-gaps_filling_primary,4-Polish}`),
> reconciled with the literature (sources at bottom). Style: flexible. Gap-filling was **manual /
> semi-automated** — the **judgment-heavy** parts are flagged honestly, not dressed up as a clean recipe.
>
> Downstream of assembly (`playbook-genome-assembly.md`) and Hi-C/Pore-C scaffolding
> (`playbook-chromosome-scaffolding-cphasing.md`). Design here; submit via the executor trio.

## Two finishing paths (know which you're on)

- **Reference individual** (had Pore-C): assembly → **CPhasing scaffold + orient/name** → **F2 gap-fill** →
  **F3 polish** → `Cqu_final.fa` (the finished reference; merged QV ~**63.2**, per-haplotype QV **66.9 / 65.8**).
- **Pangenome accessions** (HiFi-only, no 3C): assembly → **F1 RagTag against `Cqu_final.fa`** →
  dotplot + LAI QC. (RagTag is reference-based scaffolding — the substitute for de-novo Hi-C/Pore-C
  when you only have a reference + contigs.)

So F1 (RagTag) needs a finished reference, which F2+F3 produce. Order on the reference:
C-Phasing `cqu_chrom.fa` → orient/name to `cqu_chrom.oriented.fa` → F2 → F3. Order on accessions: F1 only.

---

## Stage F1 — Reference-based scaffolding (RagTag)

### When & decision

Use when you have **contigs + a chromosome-scale reference** of the same/near species, and **no 3C
data** for this accession. Reference-guided ordering/orientation into chromosomes. (If you *do*
have Pore-C/Hi-C, prefer de-novo CPhasing — RagTag inherits the reference's structural assumptions.)

### Command (verbatim)

```bash
conda activate assembly          # ragtag v2.1.0, minimap2 v2.30
ragtag.py scaffold <reference.fa> <accession_primary.fa> -t 24 -C -r -u
# internally: minimap2 -x asm5
```

Flag meanings (authoritative — note these, they shape the AGP):

- `-C` — concatenate unplaced contigs into a single `chr0`.
- `-r` — **infer** gap sizes from the alignment (default would be fixed 100 bp gaps); bounded by
  `-g`/`-m` (min/max).
- `-u` — add a suffix to unplaced-sequence headers.

Outputs: `ragtag_output/ragtag.scaffold.fasta` (+ `.agp`, `.confidence.txt`). Then rename
`Cq{N}{A/B}_RagTag` → `Cq{N}{A/B}` (`rename.sh` + `seqkit replace --kv-file rename.txt`).

### QC

```bash
# 1) Dot plot vs reference (visual collinearity)
minimap2 -cx asm5 -t 24 <reference.fa> <ragtag.chrom.fa> > acc.paf
awk 'BEGIN{OFS="\t"} {sub(/_RagTag.*/,"",$1); print}' acc.paf > acc_rename.paf  # strip _RagTag suffix, KEEP the Cq..A/B name
Rscript ~/tools/dotPlotly/pafCoordsDotPlotly.R -i acc_rename.paf -o acc -s -l -x
# 2) LAI — LTR Assembly Index (repeat-space contiguity), via LTR_FINDER_parallel + LTR_retriever
```

- **Dot plot**: want a clean diagonal per chromosome (query vs reference); off-diagonal / broken
  diagonals = mis-orders, inversions, or real structural variation — inspect, don't auto-trust.
- **LAI** (Ou et al. 2018): **< 10 draft, 10–20 reference, > 20 gold**. Reports assembly of the
  repeat/intergenic space, complementary to BUSCO (genic) and QUAST (contiguity).

### Resources & state

`fat`, 24 CPU, 100 G. **Run state: 10/10 scaffolded + dot-plotted; LAI completed 8/10** (lm270,
lm411 LAI logs absent — re-run those two). Non-fatal conda `GLIBCXX` warning as usual.

---

## Stage F2 — Gap filling — per-gap, two paths

> **Two ways to fill a gap, both per-gap.** **Path A — TGS-GapCloser** on a ~200 kb window
> (`--racon` vs `--ne` is a *parameter of the same tool*, not a separate method). **Path B — splice in a
> single read/contig that spans the gap** (done by hand in IGV before; now scripted — see Path B below).
> Shared: find gaps (Step 1), then re-splice + validate, telomeres, and combine. Path A's extract/re-splice
> are hand-run `samtools faidx`/`cat`; Path B is `scripts/fill_gap_from_spanning_alignment.py`.

### Step 1 — find gaps

`get_gaps.py` scans a FASTA for `N+` runs → GFF3 (`seqid . gap start end . . . Name=gap<i>;size=<len>`).
Use the already oriented/renamed chromosome FASTA from the C-Phasing playbook:

```bash
python get_gaps.py cqu_chrom.oriented.fa >> gaps.gff3      # these gaps were 100 bp placeholder N-runs from scaffolding
```

### Path A — TGS-GapCloser on a ~200 kb window

**Step 2 — split the chromosome at the gap** (the key technique):

`samtools faidx` the chromosome into the left flank, the right flank, and a small **gap ± ~100 kb
window** (~200 kb total; widen to ±200 kb / 400 kb by hand for a stubborn gap, as `Chr05g2` needed) —
the window is the *only* thing the filler sees:

```bash
samtools faidx chrom.fa Chr05:1-73700000        > Chr05g1_left.fa                  # chromosome BEFORE the window
samtools faidx chrom.fa Chr05:73700001-73900000 > Chr05g1_gaps_flanking_200kb.fa   # the ~200 kb gap window (gap ±100 kb)
samtools faidx chrom.fa Chr05:73900001-87193029 > Chr05g1_right.fa                 # chromosome AFTER the window
# left / window / right are CONTIGUOUS and NON-OVERLAPPING — so re-splicing them duplicates nothing
```

**Step 3 — fill the window** with TGS-GapCloser (ONT):

```bash
conda activate gapcloser          # TGS-GapCloser v1.2.1 + racon
tgsgapcloser --scaff Chr05g1_gaps_flanking_200kb.fa --reads Cqu_ONT.fasta.gz --output Chr05g1_ont_racon \
    --racon $(which racon) --thread 24 > pipe.log 2> pipe.err
# internals: minimap2 -x ava-ont, MIN_IDY 0.3, MIN_MATCH 300; racon ~3 polish iterations
# → filled window: to_filled_chr05g1.fa  (203 kb N-gap window → ~215 kb real sequence)
```

`--racon` (default, error-corrected) vs **`--ne`** (raw ONT, no racon) is a **flag of the same tool**, not
a separate method — switch to `--ne` when racon's fill is poor/empty (used for `Chr05g2`). The choice is a
manual call on fill quality.

### Step 4 — re-splice + validate

Stitch `left + filled-window + right` (contiguous, non-overlapping — the filled window **replaces** the
original window region). The chromosome therefore grows only by the gap size, **not** by +200 kb
(Chr05g1: 100 bp N → ~12 kb real sequence, net ≈ +12 kb). Then check the joins:

```bash
cat Chr05g1_left.fa <filled-window-seq> Chr05g1_right.fa > Chr05g1_gapfree.fa   # concept only: join the SEQUENCE BODIES into ONE chromosome record (not 3 FASTA records); hand-run
# validate: map long reads across each join; confirm continuous depth (no drop at the seam)
minimap2 -ax map-hifi -t 24 <gap_2end_flanking>.fa cqu_hifi_70x.fa.gz | samtools sort -o 2end.bam -   # map-hifi for HiFi reads (asm5 is for assembly-vs-ref, not reads)
pandepth -i 2end.bam -w 1000 -o 2end.depth
```

A gap that can't be filled cleanly is **left open** (Chr04 here — only an end-check, the N-gap stays).

### Path B — splice in a single spanning read/contig (`scripts/fill_gap_from_spanning_alignment.py`)

Instead of an ONT fill, take **one read or contig that already bridges the gap** and splice its sequence
in. This was done by **eyeballing IGV** for a bridging alignment; the script does it deterministically from
a BAM (verified on synthetic spanners, forward + reverse):

```bash
conda activate assembly            # any env with pysam (anaconda3 base works) + minimap2 + samtools
# 1) align the donor to the GAPPED chromosome — contigs FIRST (fast); reads only as fallback (heavy)
minimap2 -ax asm5 -t 24 chrom.fa donor_contigs.fa | samtools sort -o donor.bam - && samtools index donor.bam
# 2) find the spanning donor and splice it in
python scripts/fill_gap_from_spanning_alignment.py \
    --bam donor.bam --ref chrom.fa --gaps gaps.gff3 --donor-type contig \
    --out chrom.gapfilled.fa --report gapfill_report.tsv
# no spanner found? re-run on a reads BAM:  minimap2 -ax map-hifi … reads.fa  +  --donor-type read
```

Rules it encodes (so it matches the manual judgement): a valid spanner is **one single linear PRIMARY
alignment** — a read split across the gap into supplementary (SA) alignments does **not** count as
bridging; it must anchor **≥ MIN_ANCHOR on both flanks** (contig 50 kb / read 1 kb — reads kept permissive
so short ones aren't missed) at **MAPQ ≥ 30** (prefer ≥ 50). Among candidates it takes the **highest flank
identity** (over the anchored flanks only, **excluding the N gap**), ties broken **deterministically**
(longest anchor → leftmost coord) for reproducibility. The fill is the donor bases between the two flank
anchors; a **reverse-strand donor needs no manual reverse-complement** — the BAM stores SEQ in reference
orientation and pysam returns it ref-oriented (confirmed by test). The splice replaces only the N run,
keeping the flanks; then validate the joins exactly as in Path A (re-map long reads, continuous depth).

### Step 5 — telomere ends (missing telomeres ≠ internal gaps) — extend by overlap with donor reads/contigs

Some chromosome **ends** lack a telomere (the scaffold was truncated before reaching `CCCTAAA`). The
fix is **overlap-extension**: find a telomere-bearing **read or contig** that overlaps the chromosome
end and reaches outward into the telomere, then splice its tail on. **The reads/contigs do the
extending** — NextDenovo is *not* the mechanism, it is just one *source* of donor contigs (the other
source is HiFi telomere reads). Not TGS-GapCloser.

```bash
samtools faidx chrom.fa Chr14:<last 500kb> > c14_down500kb.fa                 # 1) cut the chromosome end
# 2) donor reads/contigs that reach into the telomere, from two sources:
#      - HiFi telomere reads  (cqu_hifi_telos.fa — HiFi reads carrying CCCTAAA)
#      - contigs from a separate NextDenovo ONT assembly (ctg002540 → Chr14, ctg170 → Chr08)
minimap2 -ax asm5 -t 24 ctg002540.fa c14_down500kb.fa | samtools sort -o c14_ctg2540.bam -   # 3) align end vs donor (either orientation works for overlap inspection)
# 4) pick the read/contig that overlaps the end AND extends outward with the telomere; splice its tail on
#    → Chr14_filled_telo.fa  (hand-run)
```

So the telomere is recovered by **overlap-extension with donor reads/contigs**; NextDenovo merely
supplied some of those donor contigs (its independent ONT assembly reached ends that hifiasm +
CPhasing missed). HiFi telomere reads are an equally valid donor source.

### Step 6 — combine, preserve final chromosome IDs, then hand to polish

Merge all `*_gapfree.fa` + telomere-extended chromosomes → `Cqu_gapsfilled.fa`, preserving the
`Cq*A/B` IDs and orientations from `cqu_chrom.oriented.fa`, then sort/validate and hand that FASTA to F3.
Do **not** apply the legacy `combined/name.txt` `Chr01-18 -> Cq*A/B` rename after F2 if the input already
came from `cqu_chrom.oriented.fa`: doing so either misses every key (final IDs no longer match `Chr01-18`)
or discards the reverse-complement fixes made during scaffolding. If you only have old `Chr01-18` gap-fill
artifacts, run the scaffolding orient/name step once first, then use those final IDs consistently through F2/F3.

### Resources & state

`fat`, 24 CPU, ~300 G; Path A ~1–2 h/gap (racon), ~20–30 min (`--ne`). **State: most gaps filled**
(`pipe.log` → `ALL DONE !!!`); **Chr04 left open**; Chr05g2 used `--ne`; Chr08/Chr14 telomere ends
recovered by overlap-extension with donor reads/contigs (HiFi telomere reads + NextDenovo donor contigs).
Path B was done ad hoc through IGV in the real run; it is now `scripts/fill_gap_from_spanning_alignment.py`
(a half-finished auto-pipeline under `5-Gaps_filling/7-Auto_gapsfilling/` is unrelated and not used).
Path A's `--racon`↔`--ne` choice remains a manual call on fill quality.

---

## Stage F3 — Polishing (NextPolish2 + HiFi) — optional

### When (your rule)

Polish is **optional**:

- **Whole-genome polish** when **ONT** was used in assembly (ONT is noisier than HiFi).
- After **manual gap-filling**, at least polish **around the filled gaps** (the ONT-racon fill is
  lower-accuracy than the HiFi backbone).

The reference run did a **whole-genome** NextPolish2 polish with HiFi (after gap-filling).

### Command

```bash
conda activate polish            # winnowmap 2.03, yak, meryl, nextPolish2, merqury, samtools
# 1) mask repetitive k-mers, map HiFi with repeat awareness
meryl count k=15 output merylDB Cqu_gapsfilled.fa
meryl print greater-than distinct=0.9998 merylDB > repetitive_k15.txt
winnowmap -t 32 -W repetitive_k15.txt -ax map-pb Cqu_gapsfilled.fa cqu_hifi_70x.fa.gz \
  | samtools sort -o hifi.map.sort.bam -
# 2) short-read k-mer truth (Illumina) for NextPolish2.
#    yak -b37 builds a TWO-PASS Bloom filter (drops singleton/error k-mers to save memory), so it must
#    read the reads TWICE. The two positional slots `<in> [in]` are "two IDENTICAL streams", NOT "R1, R2"
#    — pass 1 fills the Bloom filter, pass 2 counts. So put BOTH mates inside EACH stream, identical:
yak count -o k21.yak -k 21 -b 37 -t 32 <(zcat sr_1.fq.gz sr_2.fq.gz) <(zcat sr_1.fq.gz sr_2.fq.gz)
yak count -o k31.yak -k 31 -b 37 -t 32 <(zcat sr_1.fq.gz sr_2.fq.gz) <(zcat sr_1.fq.gz sr_2.fq.gz)
# Official idiom (yak + NextPolish2 READMEs): `yak count -b37 -o sr.yak <(zcat sr*.fq.gz) <(zcat sr*.fq.gz)`
#   — one glob `sr*.fq.gz` already pulls in R1+R2; the SAME stream is given twice for the 2-pass filter.
# BUG that was here: `<(zcat R1) <(zcat R2)` feeds R1 to the Bloom pass and R2 to the count pass (broken);
#   passing R1 twice drops R2 entirely. Both wrong → the archived k21/k31.yak truth set was incomplete,
#   so a re-polish with the corrected command may shift the QV below (66.9 / 65.8). Verified: yak v0.1-r69.
# 3) polish: HiFi alignment + short-read k-mer hash tables
nextPolish2 -t 32 hifi.map.sort.bam Cqu_gapsfilled.fa k21.yak k31.yak > cqu_np2.fa
```

NextPolish2 corrects with the **HiFi** alignment while using the **short-read** k21/k31 hashes to
choose the right base — HiFi accuracy + short-read truth. (A legacy `run.cfg`/`sgs.fofn` for
**NextPolish v1** Illumina polishing is present but was **not** the path used.) ONT was not used to polish.

### QV / acceptance (merqury)

```bash
meryl count k=21 output read.meryl <short reads>             # k-mer DB from the (accurate) short reads
merqury.sh read.meryl Cqu_final_rename_hap1.fa result_hap1   # run PER haplotype assembly, not the merged Cqu_final.fa
merqury.sh read.meryl Cqu_final_rename_hap2.fa result_hap2
```

- **QV** = log-scaled per-base error: Q30 ≈ 1 err/1 kb, Q40 ≈ 1/10 kb, **Q50 ≈ 1/100 kb (T2T bar)**,
  Q60 ≈ 1/Mb. The quinoa **hap1 / hap2** renamed assemblies scored **QV 66.9 / 65.8** — gold/near-perfect
  (~1 err per ~5 Mb); per-chromosome QV 56–87 (repeat-heavy chromosomes pull the low end). These QVs
  are on the *haplotype-split, renamed* assemblies and were computed by a separate merqury step
  (`…/7-Genome-evalution/1-QV/`, on the `5-Rename/` outputs) — not on the merged `Cqu_final.fa` in the polish dir.
- Also read merqury **k-mer completeness** and the spectra-cn plot (false-duplication / missing).

### Resources & state

`fat`, 32 CPU, 300 G. **Winnowmap dominates (~26 h)**; nextPolish2 only ~21 min; ~28 h total.
**Run state: SUCCESSFUL** → `Cqu_final.fa` (18 chr). QV: merged `Cqu_final.fa` ≈ **63.2**; per-haplotype
(`5-Rename/` hap1 / hap2) **66.9 / 65.8**.

---

## QC / acceptance — the quinoa benchmark

| Stage | Metric | Bar | Quinoa observed |
|---|---|---|---|
| F1 RagTag | dot-plot collinearity | clean per-chr diagonal | ✓ (10 samples) |
| F1 RagTag | **LAI** | >10 reference, >20 gold | 〔record per-sample LAI from `*.finder.combine.scn`〕 |
| F2 gaps | gaps remaining | ≈0 (note intentional skips) | most filled; **Chr04 left open** |
| F3 polish | **merqury QV** | Q40 ok, **Q50+ T2T-grade** | **66.9 / 65.8** (gold) |
| F3 polish | k-mer completeness | high; low false-dup | 〔record from merqury〕 |

### Evaluation contract
- Required report fields: F1 dot-plot status, per-sample LAI with `total_LTR_RT_pct/intact_LTR_RT_pct`, gap count + intentional-skip list, F3 Merqury QV with `k+read_db_type` (this stage's NextPolish2 Merqury uses Illumina short-read truth set, distinct from the evaluation playbook's HiFi-built read.meryl).
- Comparator: `references/project-anchors.yaml` quinoa V2 (hap1 QV 66.9, hap2 QV 65.8 — but those are from the HiFi-truth evaluation Merqury, not the finishing-stage Illumina-truth one; do not cross-reference numerically).
- Invalid comparisons: finishing-stage QV vs evaluation-stage QV (`ASM_QV_002` BLOCK — different `read_db_type`); LAI grade as cross-organism quality grade (`ASM_LAI_002` WARN).
- Silent traps: Merqury inputs MUST be Illumina (NextPolish2 contract); the legacy `yak count -b37` two-positional-arg gotcha (R1 fed twice ≠ R1+R2) is a recurring fail mode — both files must be the merged stream `<(zcat R1 R2)`. F2 gap "filled" status without `get_gaps.py` re-verification can be optimistic.
- Claim allowed only if: dot-plot collinearity is clean AND gap count is verified by `get_gaps.py` re-run AND polish QV cites both `k` and `read_db_type=illumina` AND any LAI grade carries the LTR-content provenance.

## How this maps onto the bio-workflow safety layer

1. **Design** here → pick F1 (accession, has reference) vs F2→F3 (reference individual); pick polish scope.
2. **Generate** with `gen_sbatch.sh` (RagTag `--mem 100G`; gap-fill per-gap `--mem ~64–300G` 〔right-size, see below〕; polish `--mem 300G`, forward `${SLURM_CPUS_PER_TASK}` to `-t`).
3. **Gate** with `prepare_submission.sh`; for many per-gap jobs use a SLURM **array** + `%N` cap, mind the 200/100/600 quota.
4. **Submit + record** with `submit_and_log.sh --yes`.
5. **Validate** with the table above + `resource_usage_audit.sh` — gap-fill/RagTag mem was almost certainly **over-requested** (the CPhasing 300G→25G lesson likely repeats here; measure and right-size).

## Pitfalls

- RagTag: it **propagates the reference's structure** — real SV in the accession can be flattened;
  always read the dot plot. LAI lm270/lm411 were not finished — re-run.
- Gap-filling is **manual and partial** — budget time, expect some gaps to stay open (Chr04), keep
  the `--racon`→`--ne` fallback in mind, and don't assume the extraction/rename is fully scripted.
- Polish: **NextPolish2 (HiFi) ≠ NextPolish v1 (Illumina config)** — don't run the legacy `run.cfg`
  thinking it's what produced `Cqu_final.fa`. Winnowmap mapping is the time sink (~26 h), not the polish.
- **`yak count -b37` is a TWO-PASS Bloom filter, not "R1, R2"** — the two positional inputs are *two
  identical streams* of the SAME reads (pass 1 builds the filter, pass 2 counts). Put both mates in each:
  `<(zcat sr_1.fq.gz sr_2.fq.gz) <(zcat sr_1.fq.gz sr_2.fq.gz)`. Splitting `<(R1) <(R2)` counts only R2
  against an R1-only filter; passing R1 twice drops R2. Either bug yields an incomplete k-mer truth set.
- QV is computed from **short reads** (the accurate truth set) via merqury — keep a clean Illumina library for this.

## Sources

- RagTag — Alonge et al., *Genome Biol* 2022; https://github.com/malonge/RagTag/wiki/scaffold
  (`-C` concat→chr0, `-r` infer gap sizes, `-u` suffix unplaced).
- LAI — Ou, Chen & Jiang, *NAR* 2018, 46:e126 (draft <10 / reference 10–20 / gold >20);
  large-scale plant assessment, *AoB Plants* 2023.
- TGS-GapCloser — Xu et al., *GigaScience* 2020; https://github.com/BGI-Qingdao/TGS-GapCloser
- NextDenovo — Hu et al., *Genome Biol* 2024 (ONT de-novo assembler; here only a *source of donor
  contigs* for overlap-extending telomere ends — not the extension mechanism);
  https://github.com/Nextomics/NextDenovo
- NextPolish2 — Hu et al. 2024; https://github.com/Nextomics/NextPolish2 ; yak (Li);
  Winnowmap (Jain et al.).
- Merqury QV — Rhie et al., *Genome Biol* 2020 (reference-free QV + k-mer completeness).
