# Playbook — Genome survey: Read QC → k-mer survey (genome size / heterozygosity / ploidy)

> **Status: DRAFT for review.** Distilled from the completed quinoa survey runs (`1-Survey/5-pangenome`
> k-mer survey ×10), reconciled with the literature (sources at bottom). Style: **flexible** — ranges +
> decision logic, not rigid values. Lines marked **〔verify〕** still need sign-off.
>
> **Stage 1 of the Genome-assembly pipeline** (survey → assembly → scaffolding → gap-fill & polish →
> evaluation → SV calling). This is the **domain brain**; submit via the executor trio
> (`gen_sbatch` → `prepare_submission` → `submit_and_log`). Its outputs — **genome size, heterozygosity,
> ploidy, coverage** — set up `playbook-genome-assembly.md` (the next stage).

## When to use

Before assembling a (poly)ploid plant genome: characterize the raw long reads, then estimate **genome size,
heterozygosity, and especially ploidy** from k-mers — so the assembly stage starts with the biology pinned down.
Two stages, **each its own SLURM job**:

- **Stage 0 — Read QC** (minutes): length/quality distribution, yield, coverage → decide whether to downsample later.
- **Stage A — k-mer survey** (~2 h/sample): genome size, heterozygosity, **ploidy** before assembling.

## Biological frame (quinoa) — the anchors that separate "wrong" from "expected"

*Chenopodium quinoa* is an **allotetraploid, AABB, 2n = 4x = 36** (18 haploid chromosomes: 9 A + 9 B). Published
chromosome-scale reference **QQ74-V2**: **1.326 Gb** total (A subgenome **530.6 Mb**, B subgenome **669.5 Mb**).

- **Survey size ≠ assembly size — relate them through ploidy.** GenomeScope2 `-p 4` reports a "Genome Haploid
  Length" on the order of **one monoploid chromosome set** (~**0.5 Gb** observed, ≈ a single subgenome A 0.53 Gb).
  The hifiasm **primary** (~**1.3 Gb**, next stage) is the full **1C gametic genome (A+B)**, ~**2×** the
  GenomeScope monoploid; **hap1+hap2** (~2.55 Gb) ≈ the 2C diploid. So a ~0.5 Gb survey number and a ~1.3 Gb
  assembly are both correct and ~ploidy apart. 〔GenomeScope's polyploid length output isn't crisply documented
  as monoploid-vs-gametic; treat it as a 1×-scale estimate, reconcile against subgenome sizes.〕
- **A later high BUSCO duplication (~93–94%) will be EXPECTED**, not contamination — the two homeologous
  subgenomes. (That check lives in the assembly playbook; flagged here because the survey's AABB call predicts it.)
- Telomere motif = canonical plant **`CCCTAAA`**.

---

## Stage 0 — Read QC (before anything else)

HiFi usually needs no trimming, but **characterize the reads** first — yield, length, quality decide whether to
assemble as-is or downsample, and catch a bad run early.

```bash
conda activate <qc-env>          # NanoPack/NanoPlot + seqkit  〔name your env〕
seqkit stats -a -T "$READS" > "${ID}.seqkit_stats.tsv"                  # N50, mean/median len, total bases, Q
NanoPlot --fastq "$READS" -t 16 -o "nanoplot_${ID}" --N50 --tsv_stats   # length & length-vs-quality density
```

- **Read length / density plot** (NanoPlot) — HiFi expect a peak ~**15 kb**, Q≥20; skewed/short = sequencing problem.
- **Coverage** = `total_bases / 1C_genome_size` (≈ 1.33 Gb for quinoa). **~50–70× is enough; plant minimum >50×.**
  hifiasm handles higher coverage fine, so this number only tells you *whether you may want* the **optional**
  downsampling at assembly time — it is not a quality gate.

Resources: `--partition=normal`, ~16 CPU, modest mem; minutes.

---

## Stage A — k-mer survey (genome size / heterozygosity / ploidy)

### Design & decision points

1. Count k-mers at **two k**: GenomeScope2 on **k=17**, Smudgeplot/FastK on **k=21** (two independent engines —
   KMC and FastK — cross-checking monoploid coverage).
2. GenomeScope2 with **`-p 4`** (the real quinoa model) **and** **`-p 2`** as a sanity comparison.
3. **#1 pitfall — the Smudgeplot `cov` value.** It must come from the GenomeScope2 `-p 4` model's `kmercov`,
   rounded. A wrong `cov` gives a wrong ploidy smudge (the LM_96/LM_270 re-run cause). If the smudge looks
   implausible, re-sweep `-l` (GenomeScope) and `-cov` (Smudgeplot) near the estimate.

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
[[ -n "$COV" ]] || { echo "ERROR: kmercov unparsed — fix the GenomeScope p4 fit; do NOT default to 40" >&2; exit 1; }  # archived script silently fell back to COV=40; a wrong cov is the #1 re-run cause
smudgeplot all -cov "$COV" --format png -o "$SM/$ID.k21.cov$COV" -t "$ID ploidy (k=21, cov=$COV)" "$SM/$ID.k21.smu"
```

Knobs: `-ci1 -cs10000`/`-cx10000` (KMC caps); `-p 4` (ploidy); `-l` (GenomeScope peak — sweep on a bad fit);
`smudgeplot all -cov <kmercov>` (the value that must be right).

### Resources & multi-sample

`--partition=normal`, `--cpus-per-task=16`, `--mem=128G` (KMC `-m96`, FastK `-M96`; MaxRSS ~93 G). No `--time`.
~2 h/sample. Multi-sample = SLURM array over `samples.tsv` (one accession/row); **pilot `--array=1` first, then
`--array=2-N%2`** (`%2` because each task is 16 CPU/~93 G). The script refuses to overwrite an existing
per-sample status table (idempotent).

### QC / acceptance

| Check | Reading | Quinoa observed |
|---|---|---|
| GenomeScope2 `-p 4` model fit | sanity, not a hard bar — much below the run's level signals a bad k-mer model → re-sweep `-l` | ~90.7–92.1% |
| Monoploid size (p4 "haploid length") | ~one subgenome (~0.5–0.65 Gb); cross-check vs A/B subgenome sizes | ~0.49–0.51 Gb |
| Smudgeplot ploidy | dominant smudge = **AABB**, with the **allotetraploid signature `aaab < aabb`** (autotetraploid would be `aaab > aabb`) | all 10 = AABB |

> **Smudgeplot caveat:** high repetitiveness + low heterozygosity can fake an AABB smudge from repetitive k-mer
> pairs (the classic *Fragaria iinumae* false-tetraploid case). Confirm ploidy by agreement across **GenomeScope
> p4 + Smudgeplot + known biology**, not Smudgeplot alone.

### Gotchas

- **`set -u` + conda**: wrap activation `set +u; source ~/.bashrc; conda activate <env>; set -u`.
- **FastK temp disk ~240–290 GB/sample** (decompresses FASTQ under `$TMPDIR`) — point `TMPDIR` at big scratch and
  clean up (with confirmation).
- Report as a **HiFi-based survey** (error/het models differ from Illumina).
- On failure read BOTH the array log and the per-sample tool logs.

---

## Handoff to the next stage

Carry forward to `playbook-genome-assembly.md`: **(1)** genome size / coverage (vs ~1.33 Gb — sets the optional
downsampling decision), **(2)** ploidy = **AABB** (predicts the assembly's high BUSCO duplication and the
hap-sum ≈ 2× primary check), **(3)** heterozygosity. The survey→assembly→QC interpretation thread is the reason
these two playbooks are tightly cross-linked.

## How this maps onto the bio-workflow safety layer

1. **Design** with this playbook → k=17/21, `-p 4`, expected QC.
2. **Generate** with `gen_sbatch.sh` (`--partition normal --mem 128G` + array manifest; forwards `${SLURM_CPUS_PER_TASK}`, absolute logs, strict mode, no stray `--time`).
3. **Gate** with `prepare_submission.sh` (inputs, preflight, array+manifest, quota — survey arrays use `%2`).
4. **Submit + record** with `submit_and_log.sh --yes`.
5. **Validate** with the QC table above; right-size repeats with `resource_usage_audit.sh` (FastK memory/temp).

## Pitfalls

- Always characterize reads first; compute coverage vs ~1.33 Gb before deciding to downsample (at assembly time).
- `set +u` around conda; FastK temp ~250 G/sample → big `$TMPDIR`.
- **Smudgeplot `cov` must come from the GenomeScope p4 `kmercov`** (the #1 re-run cause) — never silently default to 40.
- Confirm ploidy by **tool agreement** (GenomeScope p4 + Smudgeplot + biology), not Smudgeplot alone.
- Survey monoploid (~0.5 Gb) ≠ assembly 1C (~1.3 Gb) — they are ~ploidy apart, both correct.

## Sources

- GenomeScope2 / Smudgeplot — Ranallo-Benavidez et al. 2020, *Nat Commun* 11:1432;
  https://github.com/tbenavi1/genomescope2.0 (allotetraploid signature `aaab < aabb`; repeat-driven false-AABB caveat).
- Quinoa subgenome sizes / reference — chromosome-scale QQ74-V2, https://pmc.ncbi.nlm.nih.gov/articles/PMC10719370/
  (1.326 Gb; A 530.6 Mb, B 669.5 Mb).
- Quinoa diversity-panel assemblies — *Sci Data* 2024, https://www.nature.com/articles/s41597-024-04200-4 (~1.42 Gb avg).
- Read QC — NanoPack/NanoPlot (De Coster et al.); SeqKit (Shen et al.).
