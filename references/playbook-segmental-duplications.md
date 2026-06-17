# Playbook — Segmental duplications (SDs) with BISER — polyploid

> **Status: DRAFT for review.** Distilled from the completed, working **LM134** run under `8-Structure/5-SDs`
> (BISER on the soft-masked `Cqu_final.fa`). Style: flexible. Lines marked **〔verify〕** still need sign-off.
>
> **Part of the Genome-structure umbrella** — runs on an already-finished assembly (output of
> `playbook-genome-finishing.md`) after **soft-masking**. Sibling: `playbook-centromere-chipseq.md`. **Scope
> here = a single reference individual** (LM134 → `Cqu_final.fa`); the 19-accession batch (`scripts/run_biser_array.sh`,
> `step1-filter.sh`/`step2-classify.sh`, which deliberately *exclude* LM134) is the generalization, out of scope.

## When to use

Catalog **segmental duplications** (paralogous genomic blocks **≥ 1 kb at ~≥ 90 % identity**) on a finished
assembly, then split them **intra- vs inter-chromosomal** and by **subgenome** (A2A / A2B / B2B), and quantify
the non-redundant SD content of the genome.

**Caller: BISER v1.4** (fast SD detection on a masked genome — not SEDEF, not a hand-rolled minimap2/nucmer
self-alignment). BISER takes a **soft-masked** FASTA and hard-masks the lowercase internally.

**Biological output (one line):** LM134 SD catalog — **14,464 filtered SD pairs** (≥ 1 kb, ~≥ 90 % id, 18 main
chromosomes) = **11,833 inter- + 2,631 intra-chromosomal** → **~60.6 Mb non-redundant ≈ 4.7 % of the 1.29 Gb
genome** (intra 23.5 Mb / inter 44.3 Mb; subgenome A2A 24.1 / A2B 14.7 / B2B 30.4 Mb — B-subgenome SD-richest).

---

## Stage A — soft-masked reference (RepeatModeler + RepeatMasker `-xsmall`)

BISER needs a **soft-masked** (lowercase-repeat) FASTA. Built once under `9-Annotation/1-Repeat/` (env `repeat`,
RepeatMasker 4.2.1 / RMBLAST 2.14.1+; SLURM `fat`, 32 CPU, 200 G) and consumed here via symlink.

```bash
conda activate repeat
# 1) de-novo TE library
~/tools/RepeatModeler/BuildDatabase -name cqu_final /path/to/Cqu_final.fa
~/tools/RepeatModeler/RepeatModeler -threads 24 -database cqu_final          # -> cqu_final-families.fa
# 2) soft-mask with the custom library (-xsmall = lowercase, NOT N)
~/tools/RepeatMasker/RepeatMasker -lib cqu_final-families.fa -pa 32 -xsmall -gff \
    -norna -no_is -e rmblast -rmblast_dir ~/anaconda3/envs/repeat/bin ./Cqu_final.fa   # -> Cqu_final.fa.masked
# in the SD dir: ln -s ../../9-Annotation/1-Repeat/4-Repeatmasker/Cqu_final.fa.masked
```

## Stage B — run BISER (the SD caller)

```bash
source ~/.bashrc && conda activate biser_py310          # BISER v1.4
biser -t 20 -o SDs_output ./Cqu_final.fa.masked --gc-heap 2G
```

- Only non-default flags: `-t 20` (threads), `--gc-heap 2G`. **No identity/length flags** — all filtering is
  downstream (Stage C). BISER internally: hard-mask → per-chr putative SD detection → alignment → decomposition
  → `translate`. ~63 min on a 1.3 Gb genome.
- **Memory-heavy** — the batch siblings use `fat`, **16 CPU, 100 G** (`biser -t 16 … --gc-heap 2G`); size LM134 similarly.
- **Output `SDs_output`** = **156,919 raw SD pairs**, tab-separated. Raw columns observed in LM134:
  `chr1 s1 e1  chr2 s2 e2  ref  score  strand1 strand2  len1 len2  CIGAR  "X=..;ID=.."`.
  Coordinates use the project/BISER interval convention where length is `end - start`; the canonical ≥1 kb
  filter therefore uses `e1-s1` and `e2-s2`, **not `+1`**. `score` is a BISER divergence/error-like score
  used for the project threshold (`score <= 10`, approximately ≥90% similar); the trailing `ID=` tag is kept
  as provenance but is not the filter key.

## Stage C — filter to the canonical SD definition

Keep a pair only if **both chromosomes ∈ the 18 main chromosomes**, **len1 ≥ 1000**, **len2 ≥ 1000**, and
**`score` ≤ 10** (≈ ≥ 90 % identity):

```bash
awk -F'\t' '
  BEGIN{OFS="\t"; split("Cq1A Cq1B Cq2A Cq2B Cq3A Cq3B Cq4A Cq4B Cq5A Cq5B Cq6A Cq6B Cq7A Cq7B Cq8A Cq8B Cq9A Cq9B",a," ");
        for(i in a) keep[a[i]]=1}
  NF>=14{ c1=$1; c2=$4; sub(/_.*$/,"",c1); sub(/_.*$/,"",c2);     # strip any _SAMPLE suffix
         len1=$3-$2; len2=$6-$5;
         if((c1 in keep) && (c2 in keep) && len1>=1000 && len2>=1000 && $8<=10)
             print $1,$2,$3,len1,$4,$5,$6,len2,$8,$9,$10,$11,$12,$13,$14 }
' SDs_output > SD_out_filter                                     # LM134: 14,464 pairs
```

Canonical `SD_out_filter` schema (verified from the LM134 file) is:
`chr1 s1 e1 len1 chr2 s2 e2 len2 score strand1 strand2 raw_len1 raw_len2 CIGAR tags`; therefore `chr2` is `$5`
after filtering, while raw `SDs_output` has `chr2` in `$4`.

## Stage D — split intra- vs inter-chromosomal

```bash
awk '$1 != $5' SD_out_filter > SD_out_inter    # different chromosome → 11,833
awk '$1 == $5' SD_out_filter > SD_out_intra    # same chromosome      →  2,631
```

> **Column caveat:** raw `SDs_output` uses chr2 = `$4`; canonical filtered `SD_out_filter` inserts `len1`
> before chr2, so split/classify uses chr2 = `$5`.

## Stage E — subgenome classification (A2A / A2B / B2B)

Subgenome = the **last character** of the cleaned chromosome name (`Cq3A` → A). Split the filtered pairs into
A2A / A2B / B2B 6-column pair BEDs (`3-sorted_SD/{1-A2A,2-A2B,3-B2B}/*_sd.bed`). `A2B` = inter-subgenome
homoeologous SD.

## Stage F — collapse to non-redundant regions + measure bp

```bash
# per category / inter / intra: merge overlapping intervals, then sum lengths
python 01-merge_sd_region.py -i SD_out_inter -o sd_inter_merged.bed   # 6,917 regions, 44,280,983 bp
python 01-merge_sd_region.py -i SD_out_intra -o sd_intra_merged.bed   # 2,767 regions, 23,518,295 bp
awk '{sum+=$3-$2} END{print sum}' sd_inter_merged.bed                 # -> bp
```

LM134 NR total **60,642,758 bp ≈ 4.7 %** of the 1.29 Gb genome. Subgenome bp: **A2A 24.1 / A2B 14.7 / B2B 30.4 Mb**.

> **Two merge conventions coexist — pick one and be consistent 〔verify〕:** `01-merge_sd_region.py` (1-based
> inclusive merge, emits 0-based BED; the original Dec-2025 results) vs `standardize_lm134_nr_sd.sh`
> (`bedtools merge`, half-open, **no** `start-1`; the Apr-2026 set aligned with the 19-accession pangenome).

## Stage G — SD content composition (gene/exon + TE peeling)

Mutually-exclusive peeling **Gene > LTR > TIR > LINE > SINE > Unannotated**, using the **EDTA** TE GFF3
(`9-Annotation/1-Repeat/3-EDTA/3-primary/Cqu_final.fa.mod.EDTA.TEanno.gff3`) — a different product from the
RepeatMasker library used for masking — and the gene GFF3:

```bash
sort -k1,1 -k2,2n SD.bed | bedtools merge -i - > SD.merged.bed
awk 'BEGIN{OFS="\t"} $3=="exon"{print $1,$4-1,$5}' genes.gff3 | sort -k1,1 -k2,2n | bedtools merge -i - > gene.exon.bed
awk 'BEGIN{OFS="\t"} $0!~/^#/{print $1,$4-1,$5,$3}' EDTA.TEanno.gff3 > TE.type.bed
# then peel classes from SD by priority Gene>LTR>TIR>LINE>SINE with successive `bedtools subtract`
# (remove already-assigned bp) + `bedtools intersect` (measure each class), summing bp — see sd_composition.sh for the exact chain.
```

## Stage H — plotting (karyoploteR + Circos)

No `.R`/Circos `.conf` is stored in-repo — only the prepared link files (the figures were made interactively):
`4-karyoploteR/{SD_links.txt (6-col pair + RGB color), sd_samechr.txt (intra), sd_link_5kb.txt (≥5 kb)}` →
`karyoploteR::kpPlotLinks`; `5-circos/inter_large_5kb*.txt` → a Circos link track. Showcase uses the **≥ 5 kb** links.

---

## inputs → outputs → params

| Stage | Tool (env) | Input | Output | Key params |
|---|---|---|---|---|
| A mask | RepeatModeler + RepeatMasker (`repeat`; fat/32/200G) | `Cqu_final.fa` | `Cqu_final.fa.masked` (soft) | `-lib … -pa 32 -xsmall -gff -norna -no_is -e rmblast` |
| B BISER | **BISER v1.4** (`biser_py310`; fat/16–20 CPU/100 G) | `Cqu_final.fa.masked` | `SDs_output` (156,919 raw pairs) | `-t 20 -o SDs_output --gc-heap 2G` |
| C filter | awk | `SDs_output` | `SD_out_filter` (14,464) | 18 chr; len1&len2 ≥ 1000; `score ≤ 10` (≈ ≥ 90 % id) |
| D split | awk | `SD_out_filter` | `SD_out_inter` (11,833) / `SD_out_intra` (2,631) | `$1==$5` vs `$1!=$5` |
| E classify | awk | filtered pairs | A2A / A2B / B2B beds | subgenome = last char of chr |
| F merge | `01-merge_sd_region.py` / `bedtools merge`; awk | category/inter/intra beds | `*_merged.bed` + bp | NR merge → Σ(end−start) |
| G compose | `bedtools intersect/subtract` | SD.merged + EDTA TEanno.gff3 + gene gff3 | composition tsv | peel Gene>LTR>TIR>LINE>SINE>Unannot |
| H plot | karyoploteR / Circos (interactive) | inter/intra link txt | figures | ≥ 5 kb link filter |

## How this maps onto the bio-workflow safety layer

1. **Design** here → soft-mask, BISER, the ≥1 kb / score≤10 / 18-chr filter, intra/inter + subgenome split, NR bp.
2. **Generate** with `gen_sbatch.sh`: masking `--partition fat --cpus 32 --mem 200G`; BISER `--partition fat
   --cpus 16 --mem 100G` (forward `${SLURM_CPUS_PER_TASK}` to `biser -t`, keep `--gc-heap 2G`).
3. **Gate** with `prepare_submission.sh` (input = the soft-masked FASTA; BISER is memory-heavy — mind 200/100/600).
4. **Submit + record** with `submit_and_log.sh --yes`; run BISER from a **writable** cwd (its internal `./results`; see Pitfalls).
5. **Validate** — non-empty `SDs_output`, filtered-pair count, intra+inter = total, NR bp / % genome sane vs the ~4.7 % benchmark.

## Pitfalls

- **BISER needs SOFT-masked input** (`-xsmall`, lowercase) — never feed an unmasked FASTA; BISER hard-masks the lowercase itself.
- **`-o SDs_output` is the output FILE** (the SD-pairs table). Separately, BISER needs a **writable working
  directory**: the first LM134 attempt died at the final `translate` step because its internal `./results` dir
  wasn't writable (`SD.o1017610`, exit −6) — run from a writable cwd.
- **`score` is the project filter key, not a direct identity percentage** — `score ≤ 10` is the working proxy
  for ~≥90% similarity; the trailing `ID=` tag is retained for audit but not used for filtering.
- **Memory-heavy** — `fat`, ~100 G, 16 CPU for a 1.3 Gb genome; `--gc-heap 2G` set. conda libmamba / GLIBCXX warnings are harmless.
- **Two NR merge conventions** (`01-merge_sd_region.py` vs `standardize_lm134_nr_sd.sh`) — pick one; they differ by the `start-1` offset.
- **TE composition uses EDTA**, a *different* annotation from the RepeatMasker library used for masking — don't conflate them.
- **LM134 has its own per-step scripts** (`LM134/`); the shared `step1-filter.sh`/`step2-classify.sh` loops deliberately skip LM134.
- **Plotting scripts are not in the repo** — only the prepared link files; figures were generated interactively.

## Sources

- BISER — Numanagić et al. / Mirabueno et al. (fast SD & inverted-repeat detection on masked genomes); https://github.com/0xTCG/biser
- RepeatModeler / RepeatMasker — Smit & Hubley; RMBLAST. EDTA — Ou et al., *Genome Biol* 2019 (TE annotation).
- bedtools — Quinlan & Hall, *Bioinformatics* 2010. karyoploteR — Gel & Serra, *Bioinformatics* 2017. Circos — Krzywinski et al., *Genome Res* 2009.
- SD definition (≥ 1 kb, ≥ 90 % identity) — Bailey et al., *Genome Res* 2001 (the standard human-SD criteria adopted here).
