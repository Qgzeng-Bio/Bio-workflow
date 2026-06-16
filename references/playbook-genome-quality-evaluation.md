# Playbook — Systematic genome quality evaluation (QUAST · Merqury QV · BUSCO · LAI · mapping · telomere [+ snail plot])

> **Status: DRAFT for review.** Distilled from the completed, **verified-successful** quinoa evaluation runs
> under `7-Genome-evalution/` (dirs `0-QUAST`, `1-QV`, `2-BUSCO`, `3-LAI`, `4-Mapping_rate`, `5-snailplot`,
> `6-telomere`). The numbers below are the real observed values. Style: flexible.
>
> Runs **after** `playbook-genome-finishing.md` — score the finished assembly before any downstream use.
> Evaluate **all three deliverables in parallel**: `Cqu_final.fa` (primary) + `Cqu_final_rename_hap1.fa` +
> `…_hap2.fa`. (In the real quinoa run, **primary** has the full set; **hap1/hap2** have QV/LAI/mapping but
> BUSCO/telomere were not run on the haplotypes — shown as 〔run〕 in the dashboard, not as results.) Six
> **core** metrics answer complementary questions; the snail plot is a **bonus** visual.

## What each metric actually measures (don't conflate them)

| Axis | Metric | Question it answers | "good" bar |
|---|---|---|---|
| **Contiguity** | **0 QUAST** | how few, how long, how gap-free are the pieces? | contigs ≈ #chromosomes, big N50, ~0 N/100 kb |
| **Base accuracy** | **1 Merqury QV** | how correct is each base? | QV ≥ 40 ok, ≥ 50 great, **≥ 60 ≈ T2T-grade** |
| **Gene space** | **2 BUSCO** | are conserved single-copy genes all present? | Complete ≥ 95 % (≥ 98 % excellent) |
| **Repeat space** | **3 LAI** | is the LTR/intergenic space assembled? | **< 10 draft, 10–20 reference, > 20 gold** |
| **Read concordance** | **4 Mapping rate** | do the reads that built it map back? | long ≥ 99 %, short ≥ 98 % |
| **Chromosome ends** | **6 Telomere (tidk)** | are the chromosome ends capped? | ends-with-telomere / 2·#chr |
| *bonus* | **5 Snail plot** | one figure summarising the above | (visual, no threshold) |

> They are **orthogonal** — a high QV says nothing about contiguity; high BUSCO (genic) can hide poor LAI
> (repeat-space); 100 % mapping can coexist with mis-joins. Report all six.

**Envs (real):** `access` (QUAST, Merqury, tidk), `busco` (BUSCO v6.0.0 + miniprot), `LTR_retriever` + `annotation`
(genometools `gt` 1.6.2) for LAI, `assembly` (minimap2/bwa/samtools) for mapping. The top-level
`auto_genome_eval.sh` is a **generic template** (QUAST/QV/BUSCO/tidk only, default `eudicots_odb10`, k=21) — the
**real runs are the per-dir scripts** (mostly PBS), which use embryophyta lineages, run QV per-haplotype, and add
LAI + mapping. Follow the per-dir scripts, not the template.

---

## 0 — QUAST (contiguity / assembly stats) · core

```bash
conda activate access
quast.py -o quast -t 16 Cqu_final.fa        # de-novo stats; no reference, no GFF
```

Read `quast/report.txt`: `# contigs` (want ≈ #chromosomes), `Total length` (vs expected genome size), `N50`/`auN`
(bigger = more contiguous), `# N's per 100 kbp` (gap density; **0 = gap-free**), GC %.

**Quinoa observed** (`Cqu_final.fa`): **18 contigs** (= 18 chromosomes), total **1,271,319,056 bp** (~1.27 Gb),
**N50 70.1 Mb**, largest 85.8 Mb, L50 9, GC **36.95 %**, **0.00 N's / 100 kb** (gap-free). PBS `ppn=16`.

## 1 — Merqury QV + k-mer completeness (base accuracy) · core

```bash
conda activate access
meryl k=21 count output read.meryl cqu_hifi_70x.fa.gz       # k=21 read DB from the accurate HiFi reads
# run merqury PER deliverable (non-trio) — do NOT merge the haplotypes for QV
merqury.sh read.meryl Cqu_final_rename_hap1.fa result_hap1
merqury.sh read.meryl Cqu_final_rename_hap2.fa result_hap2
merqury.sh read.meryl Cqu_final.fa            result_cqu   # primary, in its own dir
```

QV = −10·log₁₀(per-base error). Q30 ≈ 1/10³, Q40 ≈ 1/10⁴, **Q50 ≈ 1/10⁵ (T2T bar)**, Q60 ≈ 1/10⁶. Also read
`*.completeness.stats` (k-mer completeness %) and the spectra-cn plot (false-duplication / missing).

**Quinoa observed:** hap1 **QV 66.93**, hap2 **65.78**, primary **63.24** (all ≫ Q60); k-mer completeness ~**99.32 %**
for all three. (These per-haplotype QVs are the ones to quote — the merged-`Cqu_final.fa` QV is lower by construction.)
Non-trio mode (no parental data). PBS `ppn=16`.

## 2 — BUSCO (gene-space completeness) · core

```bash
conda activate busco            # BUSCO v6.0.0, predictor miniprot
busco -i Cqu_final.fa -c 16 -f -o busco_odb10 -m genome -l <lineage_db> --offline
#   lineages actually run for comparison: embryophyta_odb10 (n=1614), embryophyta_odb12 (n=2026),
#   eudicots_odb10 (n=2326). Pick embryophyta_odb12 as the headline; eudicots_odb10 is the stricter, more
#   specific set the survey/assembly stage also used.
```

**⚠️ Allotetraploid reading:** quinoa is AABB — a **high Duplicated (D)** fraction is **expected and correct**
(both subgenomes retained), *not* assembly redundancy. Judge on **Complete (C)** high + **Missing (M)** / **Fragmented (F)** low.

**Quinoa observed** (`Cqu_final.fa`): embryophyta_odb12 **C 99.7 %** (S 3.3 / **D 96.4** / F 0.0 / M 0.3);
embryophyta_odb10 **C 99.4 %** (D 96.0); eudicots_odb10 **C 98.4 %** (D 94.2 / M 1.6). Beats the published QQ74
reference (odb12 C 99.5 %). CPUs/threads are per-server tunables (the run reserved PBS `ppn=10` and passed
BUSCO `-c 16`) — size them to your node, there's no fixed value. (Mode: `-m genome`; the `geno` shorthand is
also valid in v6 — verified via `busco --help` "geno or genome".)

## 3 — LAI (LTR Assembly Index — repeat-space contiguity) · core

Three-step chain (envs `LTR_retriever` + `annotation`; tools are local installs):

```bash
# 1) LTR_FINDER_parallel  -> *.finder.combine.scn
LTR_FINDER_parallel -seq Cqu_final.fa -threads 20 -harvest_out -size 1000000
# 2) genometools ltrharvest  -> *.harvest.scn   (suffixerator index first)
gt suffixerator -db Cqu_final.fa -indexname Cqu_final -tis -suf -lcp -des -ssp -sds -dna
gt ltrharvest -index Cqu_final -minlenltr 100 -maxlenltr 7000 -mintsd 4 -maxtsd 6 -motif TGCA \
   -motifmis 1 -similar 85 -vic 10 -seed 20 -seqids yes > Cqu_final.harvest.scn
# 3) LTR_retriever  -> Cqu_final.fa.out.LAI
LTR_retriever -genome Cqu_final.fa -inharvest Cqu_final.harvest.scn -infinder Cqu_final.finder.combine.scn \
   -threads 16 -u 4.79e-9            # -u = quinoa neutral mutation rate (omit -> default)
```

Read the `whole_genome` row of `*.out.LAI` (LAI column). Bar: **< 10 draft, 10–20 reference, > 20 gold**. LAI is
the metric BUSCO/QUAST miss — it scores the LTR-RT / intergenic space, where most assemblies fail.

**Quinoa observed:** primary **LAI 16.09** (best), hap1 **10.28**, hap2 **9.99** (≈reference, hap2 borderline);
the published refs sit 12.8–13.8 — so primary ≥ refs, haplotypes at the reference floor. PBS/SLURM (`fat`, 32 CPU, 128–200 G).

## 4 — Mapping rate (read concordance) · core

```bash
conda activate assembly
minimap2 -ax map-hifi -t 32 Cqu_final.fa cqu_hifi_70x.fa.gz | samtools sort -O BAM -o hifi.bam -
samtools flagstat hifi.bam                                  # read "mapped (%)" / "primary mapped (%)"
minimap2 -ax map-ont  -t 32 Cqu_final.fa Cqu_ONT.fastq.gz   | samtools sort -O BAM -o ont.bam -   # map-ont for ONT
bwa mem ref R1 R2 | samtools flagstat -                     # Illumina: also read "properly paired %"
```

Map the **same reads that built the assembly** back to it; near-total mapping is expected, a drop flags missing/mis-assembled
sequence. Bar: long ≥ 99 %, short ≥ 98 %.

**Quinoa observed:** HiFi **100.00 %**, ONT **99.74 %** (primary mapped 99.64 %), Illumina **99.98 %** (properly
paired 98.46 %) — against `Cqu_final.fa` and both haplotypes. SLURM `fat`, 32 CPU, 300 G.

## 6 — Telomere (chromosome ends, tidk) · core

```bash
conda activate access
tidk search -s CCCTAAA -o telo -d ./cqu_final_telo Cqu_final.fa   # plant telomere motif (CCCTAAA / rc TTTAGGG)
tidk plot -t ./cqu_final_telo/telo_telomeric_repeat_windows.tsv -o telo
```

Count how many of the **2·#chromosomes** ends carry a telomeric-repeat array (terminal-window copy threshold ≈ 100).
36/36 (= both ends of all 18 chromosomes) ⇒ every chromosome is capped (T2T-level ends).

**Quinoa observed:** 18 chromosomes → **36/36 ends detected, 0 missing, all 18 both-ended** (terminal copies 151–976).
Runs alongside the QUAST PBS job (`ppn=16`).

---

## 5 — Snail plot (BlobToolKit) · BONUS (nice-to-have)

A single figure that overlays the contiguity + completeness story (N50, total length, GC, BUSCO, contig distribution).

```bash
# standard BlobTools2 three-step (env not pinned in the project)
blobtools create --fasta Cqu_final.fa --taxdump taxdump <BlobDir>
blobtools add    --busco full_table.tsv <BlobDir>            # BUSCO run_*/full_table.tsv as the BUSCO field
blobtools view   --view snail --local <BlobDir>              # snail plot (needs a headless browser)
```

> **Honest state:** in the real project this was **staged but not run** — `Cqu_final.fa`, the BUSCO odb12
> `full_table.tsv`, and `taxdump/` are in place, but no BlobDir was generated. Treat the commands above as the
> intended recipe, not a verified run. It adds no number beyond §0/§2 — purely a presentation extra.

---

## QC dashboard — the quinoa benchmark (fill this per assembly)

| Metric | Bar | primary `Cqu_final` | hap1 | hap2 |
|---|---|---|---|---|
| QUAST contigs / N50 / gaps | ≈#chr / big / ~0 | 18 / 70.1 Mb / 0 N | — | — |
| Merqury QV | ≥50 great | 63.24 | **66.93** | **65.78** |
| BUSCO C% (embryophyta_odb12) | ≥98 % | **99.7 %** (D 96.4) | 〔run〕 | 〔run〕 |
| LAI (whole_genome) | 10–20 ref | **16.09** | 10.28 | 9.99 |
| Mapping rate (HiFi / ONT / Illumina) | ≥99 / ≥98 % | 100 / 99.74 / 99.98 % | HiFi 100 % (ONT 99.74) | HiFi 100 % (ONT 99.80) |
| Telomere ends | →2·#chr | 36/36 | 〔run〕 | 〔run〕 |
| Snail plot | visual | (bonus, staged) | — | — |

## How this maps onto the bio-workflow safety layer

1. **Design** here → run the six core metrics on `primary + hap1 + hap2`; snail plot only if a figure is wanted.
2. **Generate** with `gen_sbatch.sh`: most steps are light (QUAST/tidk/QV ~16 CPU); mapping is the heaviest
   (`fat`, 32 CPU, ~300 G); LAI is multi-step (forward `${SLURM_CPUS_PER_TASK}` to each tool's `-threads`).
3. **Gate** with `prepare_submission.sh`; metrics are independent → a SLURM **array** (one task per metric ×
   assembly) parallelises well under the 200/100/600 quota.
4. **Submit + record** with `submit_and_log.sh --yes`.
5. **Validate** — collect each metric into one dashboard (table above); `resource_usage_audit.sh` to right-size
   (QUAST/tidk over-request CPU; mapping is the real memory driver).

## Pitfalls

- **Six orthogonal axes — don't substitute one for another.** High BUSCO ≠ contiguous; 100 % mapping ≠ correctly
  joined; high QV ≠ complete repeat space. A genome is "good" only when all six pass.
- **Allotetraploid → BUSCO Duplicated is high BY DESIGN** (~96 %). Don't "fix" it by deduplicating — that would
  collapse the two subgenomes.
- **QV: quote the per-haplotype values, not the merged `Cqu_final.fa`** (merging two near-identical haplotypes
  inflates the apparent error rate; merged 63.2 vs per-hap 66.9/65.8). k=21, non-trio.
- **LAI `-u` is species-specific** (quinoa 4.79e-9); a wrong neutral-mutation-rate shifts the LAI. Compare to
  published refs of the same species, not across species.
- **Mapping uses the assembly's own reads** → near-100 % is expected and only weakly diagnostic; a *low* rate is
  the alarm, a high rate is not proof of correctness.
- **`auto_genome_eval.sh` is a template, not the run** — it omits LAI/mapping, defaults to `eudicots_odb10`/k=21,
  and is single-assembly. The per-dir scripts (embryophyta lineages, per-haplotype QV, PBS) are what actually ran.
- **Snail plot was staged, not executed** — its commands are unverified here.

## Sources

- QUAST — Gurevich et al., *Bioinformatics* 2013; https://github.com/ablab/quast
- Merqury — Rhie et al., *Genome Biology* 2020 (reference-free QV + k-mer completeness); https://github.com/marbl/merqury
- BUSCO — Manni et al., *MBE* 2021 (v5+; miniprot in v6); https://busco.ezlab.org
- LAI — Ou, Chen & Jiang, *NAR* 2018, 46:e126; LTR_retriever + LTR_FINDER_parallel + genometools `ltrharvest`.
- minimap2 — Li, *Bioinformatics* 2018; bwa — Li & Durbin 2009; samtools `flagstat` — Danecek et al. 2021.
- tidk — Brown et al. (telomere identification toolkit); https://github.com/tolkit/telomeric-identifier
- BlobToolKit — Challis et al., *G3* 2020 (snail plot); https://github.com/blobtoolkit/blobtoolkit
