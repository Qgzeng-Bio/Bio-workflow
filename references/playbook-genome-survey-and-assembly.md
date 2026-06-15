# Playbook — Read QC → k-mer survey → primary assembly (polyploid, PacBio HiFi ± ONT)

> **Status: DRAFT v2 for review.** Distilled from two completed quinoa runs
> (`1-Survey/5-pangenome` k-mer survey ×10; `2-primary_assembly/` hifiasm — `5-Pangenome`
> HiFi-only ×10, `2-Hifi+ONT` hybrid for CHLi-134-1), then reconciled with the literature
> (sources at the bottom). Lines marked **〔verify〕** still need your sign-off.
>
> Style: **flexible** — ranges + decision logic, not rigid prescribed values.
>
> This is the **domain brain** (what to run, why, what "good" looks like). The **how to run
> it safely** is the executor trio (`gen_sbatch` → `prepare_submission` → `submit_and_log`)
> plus the audit scripts. Design here; submit there.

## When to use

Going from raw long reads to a QC'd primary assembly for a (poly)ploid plant genome. Stages
run in order but **each is its own SLURM job** — you do not chain them in one allocation:

- **Stage 0 — Read QC** (minutes): length/quality distribution, yield, coverage → decide whether to downsample.
- **Stage A — k-mer survey** (~2 h/sample): genome size, heterozygosity, **ploidy** before assembling.
- **Stage B — primary assembly** (hifiasm; HiFi-only ~hours, HiFi+ONT ~1 day).
- **Stage C — assembly QC** (~1 h): QUAST + BUSCO + telomere.

**One combined playbook, on purpose:** the polyploid interpretation thread — survey ploidy →
assembly duplication → subgenome sizes — ties all stages together and would fragment if split.
The long runtimes are handled by each stage being an independent job, not by splitting the doc.

## Biological frame (quinoa) — the anchors that separate "wrong" from "expected"

*Chenopodium quinoa* is an **allotetraploid, AABB, 2n = 4x = 36** (18 haploid chromosomes: 9 A +
9 B). Published chromosome-scale reference **QQ74-V2**: **1.326 Gb** total (A subgenome **530.6 Mb**,
B subgenome **669.5 Mb**), N50 ~**66.9 Mb**, **BUSCO 98.4%** (embryophyta_odb10).

- **Survey size ≠ assembly size — relate them through ploidy.** GenomeScope2 `-p 4` reports a
  "Genome Haploid Length" on the order of **one monoploid chromosome set** (~**0.5 Gb** observed,
  matching a single subgenome ≈ A 0.53 Gb). The hifiasm **primary** (~**1.3 Gb**) is the full **1C
  gametic genome (A+B)**, i.e. ~**2×** the GenomeScope monoploid; **hap1+hap2** (~2.55 Gb) ≈ the 2C
  diploid content. So the ~0.5 Gb survey number and the ~1.3 Gb assembly are both correct and
  ~ploidy apart. 〔GenomeScope's polyploid length output isn't crisply documented as
  monoploid-vs-gametic; treat it as a 1×-scale estimate and reconcile against the subgenome sizes.〕
- **High BUSCO duplication (~93–94%) is EXPECTED**, not contamination — it is the two homeologous
  subgenomes. Low duplication on a *phased haplotype* would be the surprise.
- Telomere motif = canonical plant **`CCCTAAA`** (used by `hifiasm --telo-m` and `tidk search -s`).

---

## Stage 0 — Read QC (before anything else)

HiFi usually needs no trimming, but you must **characterize the reads** first — yield, length, and
quality decide whether to assemble as-is or downsample, and catch a bad run early.

```bash
conda activate <qc-env>          # NanoPack/NanoPlot + seqkit  〔name your env〕
seqkit stats -a -T "$READS" > "${ID}.seqkit_stats.tsv"            # N50, mean/median len, total bases, Q
NanoPlot --fastq "$READS" -t 16 -o "nanoplot_${ID}" --N50 --tsv_stats   # length & length-vs-quality density plots
```

Report and read:

- **Read length / density distribution plot** (NanoPlot) — for HiFi expect a peak ~**15 kb**, Q≥20;
  a skewed/short distribution flags a sequencing problem.
- **Coverage** = `total_bases / 1C_genome_size` (≈ 1.33 Gb for quinoa). **Enough is ~50–70×; plant
  minimum >50×.** hifiasm handles higher coverage fine, so this number only tells you *whether you
  may want* the **optional** downsampling in Stage B — it is not a quality gate.

Resources: `--partition=normal`, ~16 CPU, modest mem; minutes.

---

## Stage A — k-mer survey (genome size / heterozygosity / ploidy)

### Design & decision points

1. Count k-mers at **two k**: GenomeScope2 on **k=17**, Smudgeplot/FastK on **k=21** (two
   independent engines — KMC and FastK — cross-checking monoploid coverage).
2. GenomeScope2 with **`-p 4`** (the real quinoa model) **and** **`-p 2`** as a sanity comparison.
3. **#1 pitfall — the Smudgeplot `cov` value.** It must come from the GenomeScope2 `-p 4` model's
   `kmercov`, rounded. A wrong `cov` gives a wrong ploidy smudge (the LM_96/LM_270 re-run cause).
   If the smudge looks implausible, re-sweep `-l` (GenomeScope) and `-cov` (Smudgeplot) near the
   estimate.

### Exact commands

```bash
conda activate survey            # KMC + GenomeScope2   (wrap activation: set +u; source ~/.bashrc; ...; set -u)
kmc  -k17 -t16 -m96 -ci1 -cs10000 -fq "$READS" "$OUT/$ID.k17" "$TMP/kmc17"
kmc_tools transform "$OUT/$ID.k17" histogram "$OUT/$ID.k17.cov1_10000.histo" -cx10000
kmc  -k21 -t16 -m96 -ci1 -cs10000 -fq "$READS" "$OUT/$ID.k21" "$TMP/kmc21"
kmc_tools transform "$OUT/$ID.k21" histogram "$OUT/$ID.k21.cov1_10000.histo" -cx10000

genomescope2 -i "$OUT/$ID.k17.cov1_10000.histo" -k 17 -p 4 -l 40 -n "$ID.k17.p4" -o "$GS/$ID.k17.p4" --verbose --testing
genomescope2 -i "$OUT/$ID.k17.cov1_10000.histo" -k 17 -p 2 -l 80 -n "$ID.k17.p2" -o "$GS/$ID.k17.p2" --verbose --testing

conda activate smudgeplot_v2     # FastK + Smudgeplot
FastK -k21 -t1 -v -N"$SM/$ID.k21" -T16 -M96 "$READS"
smudgeplot hetmers -L 4 -o "$SM/$ID.k21" -t16 -tmp "$TMPDIR" "$SM/$ID.k21.ktab"
COV="$(awk '$1=="kmercov"{printf "%.0f",$2}' "$GS/$ID.k17.p4/$ID.k17.p4_model.txt")"
[[ -n "$COV" ]] || { echo "ERROR: kmercov unparsed — fix the GenomeScope p4 fit; do NOT default to 40" >&2; exit 1; }  # the archived script silently fell back to COV=40 here; a wrong cov is the #1 re-run cause
smudgeplot all -cov "$COV" --format png -o "$SM/$ID.k21.cov$COV" -t "$ID ploidy (k=21, cov=$COV)" "$SM/$ID.k21.smu"
```

Knobs: `-ci1 -cs10000`/`-cx10000` (KMC caps); `-p 4` (ploidy); `-l` (GenomeScope peak — sweep on a
bad fit); `smudgeplot all -cov <kmercov>` (the value that must be right).

### Resources & multi-sample

`--partition=normal`, `--cpus-per-task=16`, `--mem=128G` (KMC `-m96`, FastK `-M96`; MaxRSS ~93 G).
No `--time`. ~2 h/sample. Multi-sample = SLURM array over `samples.tsv` (one accession/row), each
task reading its row; **pilot `--array=1` first, then `--array=2-N%2`** (`%2` because each task is
16 CPU/~93 G). The script refuses to overwrite an existing per-sample status table (idempotent).

### QC / acceptance

| Check | Reading | Quinoa observed |
|---|---|---|
| GenomeScope2 `-p 4` model fit | sanity, not a hard bar — much below the run's level signals a bad k-mer model → re-sweep `-l` | ~90.7–92.1% |
| Monoploid size (p4 "haploid length") | ~one subgenome (~0.5–0.65 Gb); cross-check vs A/B subgenome sizes | ~0.49–0.51 Gb |
| Smudgeplot ploidy | dominant smudge = **AABB**, with the **allotetraploid signature `aaab < aabb`** (autotetraploid would be `aaab > aabb`) | all 10 = AABB |

> **Smudgeplot caveat:** high repetitiveness + low heterozygosity can fake an AABB smudge from
> repetitive k-mer pairs (the classic *Fragaria iinumae* false-tetraploid case). Confirm ploidy by
> agreement across **GenomeScope p4 + Smudgeplot + known biology**, not Smudgeplot alone.

### Gotchas

- **`set -u` + conda**: wrap activation `set +u; source ~/.bashrc; conda activate <env>; set -u`.
- **FastK temp disk ~240–290 GB/sample** (decompresses FASTQ under `$TMPDIR`) — point `TMPDIR` at
  big scratch and clean up (with confirmation).
- Report as a **HiFi-based survey** (error/het models differ from Illumina).
- On failure read BOTH the array log and the per-sample tool logs.

---

## Stage B — primary assembly (hifiasm)

### Decision: HiFi-only vs HiFi+ONT  ✅ confirmed

- **HiFi-only** — default for **breadth** (many accessions → pangenome). Fast, clean primary at
  ~70 Mb-class N50. (All 10 `5-Pangenome` samples.)
- **HiFi + ONT (`--ul`)** — for a **reference-grade individual**: ONT ultralong resolves complex
  /repetitive polyploid regions and improves long-range phasing. (CHLi-134-1 reference.)

### Coverage & OPTIONAL downsampling  ✅ confirmed

~**50–70×** is enough; beyond that adds compute without improving the assembly. **Downsampling is
optional** — by default assemble the full data as-is. Only downsample when the data is **very large**
and you want to save time/memory (the reason it was used here — an optimization, not a required step):

```bash
# OPTIONAL — only when coverage is much higher than ~70x
# fraction = target_x / observed_x   (e.g. 0.38 to take ~70x from ~184x)
seqtk sample -s100 "$HIFI" <fraction> | gzip > "${ID}_70x.fa.gz"
```

### Exact commands

```bash
conda activate assembly
# HiFi-only
hifiasm -o "${ID}_hifi.asm" -t "${SLURM_CPUS_PER_TASK}" --telo-m CCCTAAA "$HIFI"
# HiFi + ONT ultralong
hifiasm -o "${ID}.asm" -t "${SLURM_CPUS_PER_TASK}" --telo-m CCCTAAA --ul "$ONT" "$HIFI"
# GFA → FASTA. The GFA prefix = your hifiasm -o (HiFi-only "${ID}_hifi.asm"; hybrid "${ID}.asm").
gfatools gfa2fa "<asm-prefix>.bp.p_ctg.gfa" > "${ID}_primary.fa"   # primary; use .bp.hap1.p_ctg / .bp.hap2.p_ctg for haplotypes
hifiasm --version  # record it (reproducibility)
```

Flags: **`--telo-m CCCTAAA`** (plant telomere, constant); **`--ul <ONT>`** (makes it hybrid);
**`-t`** — forward `${SLURM_CPUS_PER_TASK}` 〔standardize to one middle value, e.g. 24–32, then tune
by data size + current queue pressure — prior runs varied 16/24/32 by data volume on purpose〕;
`--ctg-n N` optional (cap contigs; seen only in a downsampled re-run — leave unset normally).

### Which GFA output to take  ✅ confirmed

| Output | Use for |
|---|---|
| `bp.p_ctg` → `*_primary.fa` | **default** — pangenome / most downstream (collapsed primary) |
| `bp.hap1.p_ctg`, `bp.hap2.p_ctg` | **phasing** — haplotype-resolved / allele-specific |
| `bp.p_utg` | **debugging** — graph exploration (pre-bubble-collapse; many small contigs) |

### Resources & orchestration

`--partition=fat` (memory-heavy). HiFi-only: 16–32 CPU, **150–200 G**. HiFi+ONT: 16 CPU, **512 G**,
~24–30 h. No `--time`. Per-accession assembly (one job each), then a QC loop over the primaries:

```bash
for i in $(basename -s _primary.fa $(ls *primary.fa)); do quast.py -o "${i}_quast" -t 16 "${i}_primary.fa"; done
```

**Naming discipline:** fix one prefix scheme (e.g. `${ID}`) *before* submitting — prior runs mixed
`lm96`/`LM96`/`LM_177` and needed a `rename_for.sh` afterward.

---

## Stage C — assembly QC & acceptance (QUAST + BUSCO + telomere)

### Commands

```bash
conda activate access
quast.py -o "${name}_quast" -t 16 "${name}.fa"
conda activate busco
busco -i "${name}.fa" -c 16 -f -o "busco_${name}" -m geno -l eudicots_odb10 --offline   # BUSCO v6, miniprot
conda activate access
tidk search -s CCCTAAA -o "${name}_telo" -d . "${name}.fa"                # standard post-assembly QC
tidk plot   -t "${name}_telo_telomeric_repeat_windows.tsv" -o "${name}_telo"
```

BUSCO lineage = **`eudicots_odb10`** (2,326 orthologs; more specific than embryophyta for quinoa).

### Acceptance — read these against the quinoa benchmark

- **QUAST**: total length, # contigs, **N50**, largest contig, **# N's per 100 kbp** (HiFi(+ONT)
  contigs should be gap-free, ~0 N's).
- **BUSCO**: `C:%[S:%,D:%],F:%,M:%,n:2326` — **C ≥ 95% = high quality, ≥ 90% acceptable**; published
  quinoa reference is **98.4%**, so aim ≥ ~97%. **High D is expected (subgenomes) — do not flag it.**
- **TIDK telomeres**: `CCCTAAA` arrays at contig ends (~7 ends/haplotype seen) — telomere-bearing ends
  *recovered*, not near-T2T: an 18-chromosome gametic set has 36 ends, so full telomere completeness
  (both ends capped per chromosome) needs the finishing-stage end audit, not this count.

"This is what good looks like for quinoa" (CHLi-134-1 HiFi+ONT, plus the published reference):

| Assembly | # contigs | Total | N50 | Largest | BUSCO (C/S/D/F/M) | N/100kbp |
|---|---|---|---|---|---|---|
| **Primary** | 326 | 1.31 Gb | **70.1 Mb** | 81.8 Mb | 98.4 / 4.2 / 94.2 / 0.0 / 1.6 | 0.00 |
| Hap1 | 269 | 1.28 Gb | 68.3 Mb | 81.8 Mb | 98.2 / 5.0 / 93.1 / 0.1 / 1.7 | 0.00 |
| Hap2 | 153 | 1.27 Gb | 70.1 Mb | 81.8 Mb | 98.3 / 5.2 / 93.2 / 0.0 / 1.6 | 0.00 |
| `p_utg` (pre-phasing) | 4,257 | 1.44 Gb | 9.9 Mb | 40.1 Mb | 98.3 / 4.2 / 94.2 / 0.0 / 1.6 | 0.00 |
| *Published QQ74-V2* | *18 chr* | *1.326 Gb* | *66.9 Mb* | — | *98.4 (embryophyta)* | — |

### Interpretation hooks

- **N50 ~70 Mb on ~1.3 Gb** = chromosome-scale (matches the published 66.9 Mb). The `p_utg` N50 ~10 Mb
  shows the graph before phasing — the jump to ~70 Mb is what bubble-collapse + ONT buy you.
- **BUSCO C ~98%, D ~94%**: near-complete gene space; duplication = the two subgenomes, exactly as the
  survey's AABB call predicts. **Three-way consistency check**: survey ploidy (AABB) ↔ BUSCO duplication
  (~94%) ↔ hap1+hap2 ≈ 2× primary ≈ 2C. If these disagree, stop and investigate (contamination, mis-ploidy, under-purged haplotigs).
- **Subgenome sanity**: primary ≈ A+B (1.31 ≈ 0.53+0.67+unplaced); a primary far from ~1.3 Gb is suspect.

---

## How this maps onto the bio-workflow safety layer

1. **Design** with this playbook → stage, tool, params, expected QC.
2. **Generate** the sbatch with `gen_sbatch.sh` (survey → `--partition normal --mem 128G` + array
   manifest; assembly → `--partition fat --mem 150G`/`512G`). Generator guarantees absolute logs,
   strict mode, `${SLURM_CPUS_PER_TASK}` forwarding, no stray `--time`.
3. **Gate** with `prepare_submission.sh` (inputs, preflight, array+manifest, **quota** — `fat`
   assembly is heavy; mind 200/100/600; survey arrays use `%2`).
4. **Submit + record** with `submit_and_log.sh --yes`.
5. **Validate** with Stage C + `references/validation-checklists.md`; right-size repeats with
   `resource_usage_audit.sh` (FastK/hifiasm memory).

## Consolidated pitfalls

- Stage 0: always characterize reads first; compute coverage vs ~1.33 Gb before deciding to downsample.
- Survey: `set +u` around conda; FastK temp ~250 G/sample; **Smudgeplot `cov` must come from
  GenomeScope p4** (the #1 re-run cause); confirm ploidy by tool agreement, not Smudgeplot alone.
- Assembly: standardize output prefixes up front; `fat`/high-mem; record `hifiasm --version`.
  Downsampling to ~50–70× is **optional** (only when data is very large — saves compute, does not
  improve quality).
- Polyploid interpretation: survey monoploid (~0.5 Gb) ≠ assembly 1C (~1.3 Gb); high BUSCO
  duplication is expected; verify the survey-ploidy ↔ BUSCO-duplication ↔ hap-sum consistency.

## Sources (for the researched facts)

- GenomeScope2 / Smudgeplot — Ranallo-Benavidez et al. 2020, *Nat Commun* 11:1432;
  https://www.nature.com/articles/s41467-020-14998-3 ; https://github.com/tbenavi1/genomescope2.0
  (allotetraploid signature `aaab < aabb`; repeat-driven false-AABB caveat).
- Quinoa subgenome sizes / reference quality — chromosome-scale QQ74-V2 assembly,
  https://pmc.ncbi.nlm.nih.gov/articles/PMC10719370/ (1.326 Gb; A 530.6 Mb, B 669.5 Mb; BUSCO 98.4%).
- Quinoa diversity-panel assemblies — *Sci Data* 2024,
  https://www.nature.com/articles/s41597-024-04200-4 (genome sizes avg ~1.42 Gb).
- BUSCO completeness norms — >95% high quality / >90% acceptable (general practice; BioBam, Manni et al. 2021).
- Read QC — NanoPack/NanoPlot (De Coster et al.); SeqKit (Shen et al.).
