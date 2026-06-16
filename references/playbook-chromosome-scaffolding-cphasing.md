# Playbook — Chromosome scaffolding of a (poly)ploid assembly with C-Phasing + Pore-C

> **Status: DRAFT for review.** Distilled from a completed, **verified-successful** quinoa run
> (`4-scaffolding/2-Cphasing/3-primary-ctg`): the HiFi+ONT primary (`cqu_primary.fa`) scaffolded
> into 18 chromosomes with Pore-C, then reconciled with the literature (sources at the bottom).
> Style: flexible.
>
> **Stage 3 (scaffolding)**, downstream of the assembly playbook
> (`playbook-genome-assembly.md`): its **input is the `*_primary.fa`** that playbook
> produces. Design here; submit via the executor trio (`gen_sbatch` → `prepare_submission` →
> `submit_and_log`).

## When to use & what it does

You have primary **contigs** at chromosome-scale N50 but not yet ordered/oriented into
chromosomes, and you have a 3C dataset (**Pore-C** here; Hi-C / HiFi-C also supported). C-Phasing
anchors the contigs into chromosomes. It is **built for polyploids** — long-read Pore-C/HiFi-C
avoids the ambiguous short-read mapping that makes Hi-C scaffolding of polyploids switch/chimera-
prone.

## The key decision — `-n` (and allo- vs auto-polyploidy)

`-n` controls partitioning. Two forms:

- **Single number, e.g. `-n 18`** (basal mode) → that many **collapsed** chromosome groups in one
  round, **no haplotype phasing**.
- **`-n basic:ploidy`, e.g. `-n 9:4`** → haplotype-resolved: `basic` monoploid chromosomes ×
  `ploidy` copies (a 4× with x=9 → 36 phased chromosomes). `-n 0:0` auto-partitions both rounds.

**Choose by polyploid type:**

| Genome | Subgenomes | Recommended | Why |
|---|---|---|---|
| **Allopolyploid** (e.g. quinoa **AABB**) | diverged (A ≠ B) | scaffold the **collapsed primary** with **`-n <total chr>`** (quinoa = **18** = 9A+9B), basal mode | diverged subgenomes separate naturally into distinct chromosomes; no per-homolog phasing needed |
| **Autopolyploid** | near-identical homologs | **`-n <basic>:<ploidy>`** on a **phased/dual** assembly | homologs are not distinguishable as separate chromosomes; needs the phasing round |

For quinoa the run used **`-n 18`** on the collapsed **primary** → 18 chromosomes holding **~96.9% of
the assembly** (`cqu_chrom.fa` ≈ 1.271 Gb of the 1.312 Gb primary; ~303 small contigs ≈ 41 Mb stay
**unplaced** after Juicebox curation — not in the chromosome FASTA).

> **Haplotype ≠ subgenome — two orthogonal axes.** *Subgenomes* (A, B) come from allopolyploidy:
> two **diverged** ancestral genomes, 9 chromosomes each. *Haplotypes* (hifiasm `hap1`/`hap2`) are
> the two **parental copies**, and **each haplotype contains both subgenomes** (≈ 9A + 9B ≈ 18 chr
> ≈ 1.3 Gb; `hap1`+`hap2` ≈ 2.6 Gb ≈ the full 2n = 4x). So "two haps" is **not** "the two
> subgenomes":
> - **`-n 18` on the collapsed primary** resolves the **subgenomes** (A+B → 18 chr) while *merging*
>   the two haplotypes. ← what was done; clean and complete for a chromosome-scale reference.
> - **`-n 9:4` (or `0:0`) on the two-haplotype assembly** (`cqu_allhaps.fa` = `hap1`+`hap2`) resolves
>   **both axes** → ~36 fully haplotype- *and* subgenome-resolved chromosomes. More ambitious; use
>   only if you need allele-resolved chromosomes. (hifiasm treats the allotetraploid as a
>   pseudo-diploid, so its `hap1`/`hap2` are phased sets, not ancestral subgenomes.)

## Inputs

- **Contigs**: the assembly playbook's primary, e.g. `cqu_primary.fa` (1.31 Gb, 326 contigs).
- **Pore-C reads**: `Cqu_pore-c.fastq.gz`. **Enzyme matters** — confirmed **HindIII (`AAGCTT`)** here
  (one of the three standard RE-Pore-C enzymes; NlaIII `CATG` and DpnII `GATC` are the others —
  NlaIII gives the highest contact density, HindIII fewer contacts but longer fragments). The enzyme
  drives the `prepare` / `counts_<enzyme>` step, so it must match your library.

## Command

One-shot pipeline (what was run):

```bash
conda activate cphasing
cphasing pipeline -f ./cqu_primary.fa -pcd ./Cqu_pore-c.fastq.gz -t 32 -n 18
```

- `-f` contigs · `-pcd` **Pore-C** data (use `-hic1/-hic2` for Hi-C, `-prs` for a 4DN pairs file) ·
  `-t` threads · `-n` partition (see decision above).

The pipeline auto-runs these stages. The subcommands below are **simplified** (key flags only) — the
real generated `*.cmd.sh` carry more auto-tuned flags (e.g. hyperpartition's
`-r1/-ir1/-r2/-ir2/-as/-mao/-mw/-mcw/-ms`, scaffolding's `-at None -sc …split.contacts`); read each
stage's `*.cmd.sh` for the exact line before a partial re-run:

```bash
# 1. mapping  → contigs + Pore-C alignment (PAF → porec → pairs)
# 2. prepare
cphasing prepare ../cqu_primary.fa ../Cqu_pore-c.pairs.pqs -p None -q 0 -t 32 --skip-pairs2contacts
# 3. hyperpartition  (polyploid-aware; note --porec, --mode basal, -n 18)
cphasing hyperpartition ../Cqu_pore-c.porec.gz ../cqu_primary.contigsizes output.clusters.txt \
    --porec --mode basal -e 5m -q1 1 -q2 2 -mc 25 -ml 10000 -t 32 -n 18
# 4. scaffolding  (order+orient within groups; -m precision)
cphasing scaffolding ../3.hyperpartition/output.clusters.txt ../2.prepare/Cqu_pore-c.counts_AAGCTT.txt \
    ../2.prepare/Cqu_pore-c.clm.gz -f ../cqu_primary.fa -t 32 -o groups.agp -m precision
# 5. plot  (whole-genome contact heatmap)
cphasing plot -a ../4.scaffolding/groups.agp -m Cqu_pore-c.q1.10k.cool -o groups.q1.500k.wg.png -bs 500k -oc
```

Outputs: `4.scaffolding/groups.agp` (the scaffold map), `cqu_scaffolds_primary_w60.fasta` (all
scaffolds, ~321 seqs) and `cqu_chrom.fa` (the **18 chromosomes only**), `groups.hic` (Juicebox
contact map), `5.plot/…wg.png` (the heatmap).

## Manual curation (standard QC step — do it)

After auto-scaffolding, **review and correct in Juicebox**, then convert back. This is expected,
not optional — it catches mis-joins/inversions the algorithm missed:

```bash
cphasing-rs pairs2mnd -q 1 ../Cqu_pore-c.pairs.pqs -o Cqu_pore-c.pqs.mnd.txt
cphasing utils agp2assembly groups.agp -o groups.assembly
bash ~/tools/3d-dna/visualize/run-assembly-visualizer.sh -p true groups.assembly Cqu_pore-c.pqs.mnd.txt
# → curate groups.assembly in Juicebox → save groups.review.assembly, then:
cphasing utils assembly2agp groups.review.assembly -o groups.review -n 18
cphasing utils agp2fasta groups.review.agp -o groups.review.fasta
```

Result of curation here: `groups.review.corrected.agp` (the final, curated chromosome map).

## Orient & name to a reference (synteny dot plot) — do this before anything downstream

C-Phasing's chromosome **IDs (Chr01…Chr18) and per-chromosome orientation are arbitrary** — assigned by the
algorithm, *not* tied to any reference. Before any comparative/SV work, align the curated chromosomes to a
chromosome-scale reference, read a **dot plot**, and **rename + reverse-complement** to match the reference's
names and orientation. (This is the C-Phasing analogue of the RagTag dot-plot QC in `playbook-genome-finishing.md`.)

```bash
# 1) align curated chromosomes to the reference, then a whole-genome dot plot
conda activate <mummer-env>                       # 〔MUMmer 4; or use the minimap2 alternative below〕
nucmer --maxmatch -t 16 -p cqu_vs_ref reference.fa cqu_chrom.fa
delta-filter -1 cqu_vs_ref.delta > cqu_vs_ref.1.delta              # optional: 1-to-1 filter → cleaner dot plot
mummerplot --png --large --layout -p cqu_vs_ref cqu_vs_ref.1.delta
#   project alternative (what the RagTag stage actually used): minimap2 -cx asm5 ref.fa cqu_chrom.fa > x.paf
#   then Rscript ~/tools/dotPlotly/pafCoordsDotPlotly.R -i x.paf -o cqu_vs_ref -s -l -x
```

Read the dot plot — each query chromosome maps to one reference chromosome:
- **Name** = which reference chromosome the diagonal falls on → that query's true ID.
- **Orientation** = the diagonal's slope: **↗ (forward) = same orientation; ↘ (anti-diagonal) = REVERSED** →
  that chromosome must be reverse-complemented.

```bash
# 2) build maps from the dot plot, then apply with seqkit (real project pattern)
#    flip.ids: the ORIGINAL Chr0x IDs on the anti-diagonal (one/line) — flip BEFORE renaming so they still match
#    rename.txt: <oldID>\t<refID> per line — must cover all 18 (an unmatched key blanks the ID; seqkit replace -U keeps it)
seqkit grep   -n -f flip.ids cqu_chrom.fa | seqkit seq -r -p > flipped.fa       # -r -p = reverse-complement
seqkit grep -v -n -f flip.ids cqu_chrom.fa > kept.fa
cat kept.fa flipped.fa | seqkit replace -p '^(\S+)' -r '{kv}' -k rename.txt \
    | seqkit sort -N > cqu_chrom.oriented.fa     # sort -N = natural ID order; if reference order differs, sort by a reference_order.ids list
```

**Why this is not optional:** a chromosome left in the wrong orientation does **not** error — it silently
surfaces downstream as a **fake two-segment translocation / INVTR** in SyRI (exactly the Cq3B reverse-complement
saga in `playbook-variant-synteny-syri.md`, where QQ74/Javi had to be rc-corrected *after* the fact). Fixing
name + orientation here, against the reference, **prevents this class of artifact for this assembly** — it does
not replace the **per-comparison** SyRI orientation check downstream. 〔Exact MUMmer flags + the rename/flip-map building
are the standard recipe — ground them against your real run before relying on specific values.〕

## Resources & right-sizing  ⚠️

The run used `--partition=fat --cpus-per-task=32 --mem=300G`, but **peak memory was only 24.91 GB**
(~10.5 h elapsed). So:

- **Memory was ~12× over-requested.** A ~1.3 Gb Pore-C scaffolding needs **~32–64 GB** (with
  headroom), not 300 GB → this fits **`normal`**, not `fat`. Don't default to `fat`/300G here.
- 32 CPU / ~10–11 h is reasonable. No `--time`. Re-check with `resource_usage_audit.sh` after a run.

## QC / acceptance — read these

| Check | Pass | Quinoa observed |
|---|---|---|
| **Chromosome count** | = expected (`-n`) | **18** (Chr01–Chr18) ✓ |
| **Anchoring rate** | high (~≥90%) | **~96.9%** — 18 chromosomes = 1.271 Gb of 1.312 Gb (`cqu_chrom.fa`); ~303 small contigs (~41 Mb) unplaced after curation |
| **Contact-map heatmap** (`…wg.png`) | strong **on-diagonal** blocks, weak off-diagonal; no obvious mis-joins or cross-chromosome bleed | clean 18-block diagonal |
| Curated AGP exists | `groups.review.corrected.agp` after Juicebox | present ✓ |

**Interpretation hooks:**

- For an **allotetraploid**, CPhasing yields **18 gametic chromosome groups** (clean diagonal blocks);
  the chromosome **names + orientation come from the synteny dot-plot step above** (CPhasing's Chr01–18
  IDs/orientation are arbitrary), and the 9A/9B subgenome IDs are finalized at finishing via `name.txt`. Off-diagonal signal between a Chr-A and its homeolog Chr-B is expected to be *low*
  (diverged subgenomes); strong A↔B bleed would flag mis-assignment.
- Anchored length ≈ the input primary length (here exactly equal) → no contigs lost; an anchoring
  rate well below ~90% means many contigs stayed unplaced (check contig sizes / Pore-C coverage).
- Cross-check continuity: scaffolded chromosome N50 should jump to chromosome scale (~tens of Mb →
  ~chromosome length); compare against the published quinoa karyotype (2n=4x=36, 18 gametic chr).

## Gotchas (from this run)

- **`-n` is the make-or-break parameter** — `-n 18` (collapsed, allo) vs `-n x:ploidy` (phased,
  auto). Pick by polyploid type *before* running (see the decision table).
- **Pore-C enzyme** must match the library (`AAGCTT` = HindIII here) — it drives the `prepare` /
  `counts_<enzyme>` step.
- The conda startup line `Error while loading conda entry point: conda-libmamba-solver
  (GLIBCXX_3.4.29 not found)` is **non-fatal noise** (the broken base conda) — the `cphasing` env
  still activates and the pipeline runs. Don't treat it as a failure.
- **Juicebox curation is a real step** — budget time for it; the auto AGP is a draft.

## How this maps onto the bio-workflow safety layer

1. **Design** with this playbook → pick `-n` by polyploid type; pick Pore-C vs Hi-C flag; set enzyme.
2. **Generate** the sbatch with `gen_sbatch.sh` — `--partition normal --cpus 32 --mem 64G`
   (right-sized from the 25 GB peak, not the old 300 GB), forwarding `${SLURM_CPUS_PER_TASK}` to `-t`.
3. **Gate** with `prepare_submission.sh` (input `*_primary.fa` exists; preflight; quota).
4. **Submit + record** with `submit_and_log.sh --yes`.
5. **Validate** with the QC table above + the heatmap; curate in Juicebox; right-size repeats with
   `resource_usage_audit.sh` (this is the textbook over-request case).

## Sources

- C-Phasing — wangyibin/CPhasing (Pore-C/HiFi-C/Hi-C polyploid phasing & scaffolding);
  https://github.com/wangyibin/CPhasing ; docs https://wangyibin.github.io/CPhasing/dev/
  (the `-n basic:ploidy` semantics: `-n 8:4` = tetraploid, 8 basic chromosomes; `-n 0:0` = auto).
- Method — "Enhanced Pore-C with C-Phasing Enables Chromosomal-Scale, Haplotype-Resolved Assembly
  of Ultra-Complex Genomes", Research Square 2025 (rs-7343323).
- Pore-C restriction enzymes (HindIII `AAGCTT` / NlaIII `CATG` / DpnII `GATC`) — Oxford Nanopore
  RE-Pore-C protocol & info sheet; https://nanoporetech.com/document/restriction-enzyme-pore-c
- Haplotype vs subgenome in polyploids — "Haplotype-Resolved Assembly in Polyploid Plants" review,
  https://pmc.ncbi.nlm.nih.gov/articles/PMC12192169/ ; hifiasm FAQ (contig modules are diploid-designed),
  https://hifiasm.readthedocs.io/en/latest/faq.html
