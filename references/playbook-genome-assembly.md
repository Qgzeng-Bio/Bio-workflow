# Playbook — Primary assembly (hifiasm) + assembly QC (polyploid, PacBio HiFi ± ONT)

> **Status: DRAFT for review.** Distilled from completed quinoa runs (`2-primary_assembly/` hifiasm —
> `5-Pangenome` HiFi-only ×10, `2-Hifi+ONT` hybrid for CHLi-134-1), reconciled with the literature
> (sources at bottom). Style: **flexible**. Lines marked **〔verify〕** still need sign-off.
>
> **Stage 2 of the Genome-assembly pipeline** (survey → **assembly** → scaffolding → gap-fill & polish →
> evaluation → SV calling). **Takes the survey's estimates as input** (`playbook-genome-survey.md`: genome
> size/coverage → downsampling call; ploidy AABB → expected BUSCO duplication). Design here; submit via the
> executor trio. Output: a QC'd primary (+ optional haplotypes) → `playbook-chromosome-scaffolding-cphasing.md`.

## When to use

Going from a QC'd, surveyed read set to a primary assembly + immediate QC. Two stages, **each its own SLURM job**:

- **Stage B — primary assembly** (hifiasm; HiFi-only ~hours, HiFi+ONT ~1 day).
- **Stage C — assembly QC** (~1 h): QUAST + BUSCO + telomere.

**Bring from the survey:** coverage vs ~1.33 Gb (1C), ploidy = **AABB**, heterozygosity. The polyploid anchors
(survey monoploid ~0.5 Gb ≠ assembly 1C ~1.3 Gb; high BUSCO duplication = the two subgenomes) come from
`playbook-genome-survey.md` — the three-way consistency check in Stage C closes that loop.

---

## Stage B — primary assembly (hifiasm)

### Decision: HiFi-only vs HiFi+ONT  ✅ confirmed

- **HiFi-only** — default for **breadth** (many accessions → pangenome). Fast, clean primary at ~70 Mb-class N50.
  (All 10 `5-Pangenome` samples.)
- **HiFi + ONT (`--ul`)** — for a **reference-grade individual**: ONT ultralong resolves complex/repetitive
  polyploid regions and improves long-range phasing. (CHLi-134-1 reference.)

### Coverage & OPTIONAL downsampling  ✅ confirmed

~**50–70×** is enough; beyond that adds compute without improving the assembly. **Downsampling is optional** —
by default assemble the full data as-is. Only downsample when the data is **very large** and you want to save
time/memory (an optimization, not a required step; uses the coverage number from the survey):

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

Flags: **`--telo-m CCCTAAA`** (plant telomere, constant); **`--ul <ONT>`** (makes it hybrid); **`-t`** — forward
`${SLURM_CPUS_PER_TASK}` 〔standardize to one middle value, e.g. 24–32, then tune by data size + queue pressure —
prior runs varied 16/24/32 by data volume on purpose〕; `--ctg-n N` optional (cap contigs; seen only in a
downsampled re-run — leave unset normally).

### Which GFA output to take  ✅ confirmed

| Output | Use for |
|---|---|
| `bp.p_ctg` → `*_primary.fa` | **default** — pangenome / most downstream (collapsed primary) |
| `bp.hap1.p_ctg`, `bp.hap2.p_ctg` | **phasing** — haplotype-resolved / allele-specific |
| `bp.p_utg` | **debugging** — graph exploration (pre-bubble-collapse; many small contigs) |

### Resources & orchestration

`--partition=fat` (memory-heavy). HiFi-only: 16–32 CPU, **150–200 G**. HiFi+ONT: 16 CPU, **512 G**, ~24–30 h.
No `--time`. Per-accession assembly (one job each), then a QC loop over the primaries:

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
busco -i "${name}.fa" -c 16 -f -o "busco_${name}" -m genome -l eudicots_odb10 --offline   # BUSCO v6 + miniprot. `-m genome` (the `geno` shorthand is also valid in v6 — `--help`: "geno or genome"). `-c` = threads, tune per node.
conda activate access
tidk search -s CCCTAAA -o "${name}_telo" -d . "${name}.fa"                # standard post-assembly QC
tidk plot   -t "${name}_telo_telomeric_repeat_windows.tsv" -o "${name}_telo"
```

BUSCO lineage = **`eudicots_odb10`** (2,326 orthologs; more specific than embryophyta for quinoa).

### Acceptance — read these against the quinoa benchmark

- **QUAST**: total length, # contigs, **N50**, largest contig, **# N's per 100 kbp** (HiFi(+ONT) contigs should
  be gap-free, ~0 N's).
- **BUSCO**: `C:%[S:%,D:%],F:%,M:%,n:2326` — **C ≥ 95% = high quality, ≥ 90% acceptable**; published quinoa
  reference is **98.4%**, so aim ≥ ~97%. **High D is expected (subgenomes) — do not flag it.**
- **TIDK telomeres**: `CCCTAAA` arrays at contig ends (~7 ends/haplotype seen) — telomere-bearing ends
  *recovered*, not near-T2T: an 18-chromosome gametic set has 36 ends, so full telomere completeness (both ends
  capped per chromosome) needs the finishing-stage end audit, not this count.

"This is what good looks like for quinoa" (CHLi-134-1 HiFi+ONT, plus the published reference):

| Assembly | # contigs | Total | N50 | Largest | BUSCO (C/S/D/F/M) | N/100kbp |
|---|---|---|---|---|---|---|
| **Primary** | 326 | 1.31 Gb | **70.1 Mb** | 81.8 Mb | 98.4 / 4.2 / 94.2 / 0.0 / 1.6 | 0.00 |
| Hap1 | 269 | 1.28 Gb | 68.3 Mb | 81.8 Mb | 98.2 / 5.0 / 93.1 / 0.1 / 1.7 | 0.00 |
| Hap2 | 153 | 1.27 Gb | 70.1 Mb | 81.8 Mb | 98.3 / 5.2 / 93.2 / 0.0 / 1.6 | 0.00 |
| `p_utg` (pre-phasing) | 4,257 | 1.44 Gb | 9.9 Mb | 40.1 Mb | 98.3 / 4.2 / 94.2 / 0.0 / 1.6 | 0.00 |
| *Published QQ74-V2* | *18 chr* | *1.326 Gb* | *66.9 Mb* | — | *98.4 (embryophyta)* | — |

### Interpretation hooks

- **N50 ~70 Mb on ~1.3 Gb** = chromosome-scale (matches the published 66.9 Mb). The `p_utg` N50 ~10 Mb shows the
  graph before phasing — the jump to ~70 Mb is what bubble-collapse + ONT buy you.
- **BUSCO C ~98%, D ~94%**: near-complete gene space; duplication = the two subgenomes, exactly as the survey's
  AABB call predicts. **Three-way consistency check** (closes the survey↔assembly loop): survey ploidy (AABB) ↔
  BUSCO duplication (~94%) ↔ hap1+hap2 ≈ 2× primary ≈ 2C. If these disagree, stop and investigate (contamination,
  mis-ploidy, under-purged haplotigs).
- **Subgenome sanity**: primary ≈ A+B (1.31 ≈ 0.53+0.67+unplaced); a primary far from ~1.3 Gb is suspect.

This QC is the *first* look; the systematic, full quality scoring (QV, LAI, mapping rate, complete telomere audit)
is the dedicated `playbook-genome-quality-evaluation.md`, run after finishing.

---

## How this maps onto the bio-workflow safety layer

1. **Design** with this playbook → tool, params, expected QC (carrying the survey's ploidy/coverage).
2. **Generate** the sbatch with `gen_sbatch.sh` (`--partition fat --mem 150G`/`512G`; forwards
   `${SLURM_CPUS_PER_TASK}`, absolute logs, strict mode, no stray `--time`).
3. **Gate** with `prepare_submission.sh` (inputs, preflight, **quota** — `fat` assembly is heavy; mind 200/100/600).
4. **Submit + record** with `submit_and_log.sh --yes`.
5. **Validate** with Stage C + `references/validation-checklists.md`; right-size repeats with
   `resource_usage_audit.sh` (hifiasm memory).

## Pitfalls

- Standardize output prefixes up front (`${ID}`) — avoids a post-hoc rename.
- `fat`/high-mem; record `hifiasm --version`.
- Downsampling to ~50–70× is **optional** (only when data is very large — saves compute, does not improve quality).
- **High BUSCO duplication is EXPECTED** for an allotetraploid — do not "purge" it. Verify the
  survey-ploidy ↔ BUSCO-duplication ↔ hap-sum consistency; a mismatch means contamination / mis-ploidy / under-purged haplotigs.
- Take the right GFA output: `bp.p_ctg` for the collapsed primary, `bp.hap1/hap2.p_ctg` for phasing, `bp.p_utg` only for debugging.

## Sources

- hifiasm — Cheng et al., *Nat Methods* 2021 / 2024 (`--ul`, `--telo-m`); https://github.com/chhylp123/hifiasm
- QUAST — Gurevich et al., *Bioinformatics* 2013. BUSCO — Manni et al., *MBE* 2021 (v5+; miniprot in v6).
- tidk — Brown et al.; https://github.com/tolkit/telomeric-identifier
- Quinoa reference quality — QQ74-V2, https://pmc.ncbi.nlm.nih.gov/articles/PMC10719370/ (1.326 Gb; BUSCO 98.4%).
- BUSCO completeness norms — >95% high quality / >90% acceptable (general practice; Manni et al. 2021).
