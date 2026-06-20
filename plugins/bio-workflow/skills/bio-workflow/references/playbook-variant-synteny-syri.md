# Playbook — Structural variation & synteny: SyRI (chained vs all-to-reference) → SURVIVOR → plotsr

> **Status: DRAFT for review.** Distilled from completed, **verified-successful** quinoa runs
> (`6-Comparation/7-pangenome` chained SyRI; `…/3-syri_analysis/all2ref` all-to-reference), reconciled
> with the literature (sources at bottom). Style: flexible. Both topologies share **one SV-calling core**
> (minimap2 → SyRI) and diverge downstream. The judgment-heavy parts (chromosome-orientation fixes, VCF
> field patching) are flagged honestly, not dressed up as a clean recipe.
>
> Downstream of finished assemblies (`playbook-genome-finishing.md`). Design here; submit via the executor trio.
> Scope: **assembly-vs-assembly SV via SyRI**. The orthogonal multi-caller workflow (Sniffles2 **read-based**
> + SVIM-asm **assembly-based**) and graph-based complex SV (Swave) are a larger story — see
> `playbook-high-confidence-sv-multicaller.md`; pointers at the bottom.

## Two topologies (know which you're on, and why)

The SV-calling core is identical; **what you align against** decides what you can do downstream.

| | **Chained** (`syri_pairwise/`) | **All-to-reference** (`all2ref/`) |
|---|---|---|
| Alignment | consecutive pairs `Cqu→LM42→…→0321072RM` (20 genomes, 19 pairs) | every accession vs one fixed ref `Cqu` (19 pairs, all-to-one) |
| Coordinate system | each pair has its **own** ref — **no common coordinate** | **all SVs on the Cqu coordinate** |
| Primary purpose | **visualization-first** — the multi-genome plotsr panorama | **quantification-first** — a population SV set you can merge & count |
| Downstream | plotsr 18-chromosome column figure + summary tables | **SURVIVOR merge** → SV hotspots / subgenome bias / centromere / gene overlap |
| Why pick it | telling the structural-evolution story across a panel | one merged VCF in one coordinate for population genetics |

They are **complementary, not either/or** — the same SyRI pairs feed both. One sentence: chained is "string 20
genomes into one figure"; all2ref is "project everything onto one reference and measure the population SV spectrum".

**env:** `syri_env` (minimap2 + syri + plotsr). **Versions are not pinned in any run script** — `plotsr 1.1.1`
appears once as a path label and `syri 1.7.1` is inferred/unconfirmed; run `syri --version` / `plotsr --version`
to record the real versions. SURVIVOR is a local build at `/data9/home/qgzeng/tools/SURVIVOR/Debug/SURVIVOR`.
Hotspot analysis uses the `repeat` env python.

---

## Stage 0 — Genome prep (both paths)

SyRI/plotsr want **18 clean chromosomes** (`Cq1A…Cq9B`), no `chr0`/scaffold bucket, no `CqU` unplaced.

```bash
# filter_chrom.py: keep only Cq1–Cq9 (A/B) = 18 chr; drop Cq0* and CqU
#   keep = prefix.startswith("Cq") and prefix[2].isdigit() and prefix[2] != "0"
python filter_chrom.py     # <x>.fasta -> <x>.filtered.fasta  (drops the chr0 bucket + unplaced)
```

- LM lines and `Cqu_final.fa` come from RagTag/polish already as 18 bare-named chromosomes (`>Cq1A …`) — used directly.
- **Header-naming trap that bites plotsr later:** LM/Cqu/QQ74 fastas use **bare** names (`>Cq1A`); the 8 imported
  accessions (CHEN199, CHEN90, D10126, D12282, Javi, PI614919, Regalona, 0321072RM) carry a **suffix**
  (`>Cq1A_CHEN199`). SyRI is fine with either, but plotsr marker/`--chr` matching is not — see Visualization.
- Drop genomes too fragmented for synteny (here J075/J100/Cqu_r1.0/Real were excluded from the panel).

---

## Stage 1 — SV calling core: minimap2 → SyRI (both paths)

```bash
conda activate syri_env
# 1) whole-genome alignment — asm5 preset, --eqx is MANDATORY (SyRI needs =/X CIGAR to split match/mismatch)
minimap2 -ax asm5 -t "$THREADS" --eqx "$REF" "$QRY" > "$PFX.sam"     # SAM (not BAM/PAF); ~3 GB/pair
# 2) SyRI — synteny + inversions + translocations + duplications + local SNP/indel
cd "$PAIR_DIR"
syri -c "$PFX.sam" -r "$REF" -q "$QRY" --dir "$PAIR_DIR" --prefix "$PFX" -k -F S
#   -F S = SAM input, -k = keep intermediates, default --nc
```

**Outputs per pair** (`-k` keeps all): `<PFX>syri.out` (~200 MB), `<PFX>syri.vcf` (~290–350 MB),
`<PFX>syri.summary` (the QC file), `<PFX>syri.log`, plus intermediate tables
(`synOut/invOut/TLOut/invTLOut/ctxOut/dupOut/invDupOut/notAligned/sv/snps.txt` — `snps.txt` alone ~2 GB).
~25 min/pair (alignment ~7 min of it). **Resume guard:** skip minimap2 if `[[ -s "$PFX.sam" ]]`, skip SyRI if
`[[ -s "$PFX"syri.out ]]`.

### ⚠️ The orientation problem (the #1 real-world failure — read before scaling)

Independently-assembled accessions frequently have a **whole chromosome reverse-complemented** vs the
reference. Here it hit **8 of the 9 non-LM accessions**: CHEN199 first (fixed in a separate earlier round),
then 6 more (CHEN90/D10126/D12282/PI614919/0321072RM/Regalona) on **Cq3B** alone, plus QQ74 with **10**
flipped chromosomes (Cq1B/4A/4B/5A/5B/7A/7B/8A/8B/9A — *not* Cq3B). Two failure modes:

1. **Hard fail:** SyRI exits with `No syntenic region found` for that chromosome → the whole pair dies.
2. **Silent artifact:** a real **central inversion** gets rendered as a **two-segment translocation / INVTR**
   (QQ74 & Javi Cq3B). The "translocation" is a direction artifact, **not** a real rearrangement.

**Fix (manual, per offending chromosome):** reverse-complement **only that chromosome** in the *query* fasta
(header + sequence), validate (still 18 chr, same IDs, total length unchanged), then **force re-alignment**
(`mv old.sam old.sam.bak`) and rerun minimap2 + SyRI. Diagnose direction from SyRI parent intervals
("ref left ↔ query right" = inverted). After the fix Cq3B reads as one `INV ~9.4–69 Mb`. Keep the legacy
run as an artifact comparison; prefer the corrected version for all downstream SV/figures.

---

## Path A — Chained (multi-genome plotsr panorama)

**Chain order** (20 genomes / 19 adjacent pairs), authoritative list in `build_20genome_summary_and_plotsr.sh`:
`Cqu→LM42→LM96→LM172→LM176→LM177→LM225→LM270→LM320→LM393→LM411→CHEN199→CHEN90→D10126→D12282→Javi→PI614919→QQ74→Regalona→0321072RM`.

Run in two segments, then stitch at the boundary pair **`LM411_CHEN199`** (bare-name LM411 vs suffixed CHEN199):

```bash
# first 10 pairs (all LM/_final.fa) — SLURM array, 4 concurrent
#SBATCH --array=0-9%4          # pairs=( "Cqu LM42" "LM42 LM96" ... ); ref/qry = pairs[$SLURM_ARRAY_TASK_ID]
# last 9 pairs (imported .filtered.fasta) — shell job pool (wait_for_slot / MAX_JOBS), separate output dir
```

Each pair → `syri_pairwise/<ref>_<qry>/` (or `syri_pairwise_9genomes/…`). Then aggregate every `syri.summary`
into a wide TSV (`syri_summary_chain_20genomes.tsv`: `chain_index, group, pair, ref, qry, …` + 32 metric
columns: syntenic/inversions/translocations/dup_ref/dup_qry/not_aligned/snps/insertions/deletions/…) and a
`sr_inputs.chain.20.tsv` listing the 19 `syri.out` in chain order for plotsr.

**Acceptance gate per pair:** non-empty `.sam`, non-empty `syri.out` **and** `syri.summary`; the chain build
asserts the genomes file is exactly 20 lines **in order** and the `--sr` list is exactly **19**.

→ visualization in the **Visualization** section.

---

## Path B — All-to-reference (population SV set + quantitative analysis)

```bash
#SBATCH --array=0-18           # SAMPLES=( "LM42_final.fa|LM42" ... ); REF is always Cqu_final.fa
# each task: minimap2 -ax asm5 --eqx  +  syri -k -F S   ->  Cqu_vs_<sample>/
# NOTE: the reference Cqu is the same assembly as LM134 — the SURVIVOR/hotspot/centromere/gene analysis below is on LM134 coordinates.
```

### ⚠️ B1 — Patch SyRI VCFs BEFORE SURVIVOR (the #2 real-world failure)

**SyRI's VCF has neither `INFO/SVLEN` nor `INFO/SVTYPE`** (audit confirmed: 100% of records in all 19 VCFs
lack both). Feeding them straight to SURVIVOR is silently wrong:

| What you patch | Merged records | SVTYPE distribution | Verdict |
|---|---|---|---|
| SVLEN only | 199,343 | NA 168828 / INV 15301 / TRA 8194 / DUP 7020 | INS+DEL **collapse into NA** |
| SVTYPE only | 159,824 | NA 94051 / DEL 35228 / INV / TRA / DUP, **INS 0** | literal INS dropped (no SVLEN → fails `min_size=50`) |
| **SVLEN + SVTYPE** | **202,406** | NA 94103 / **INS 42567** / DEL 35205 / INV 15314 / TRA 8196 / DUP 7021 | ✅ complete |

> Only the **202,406** row was re-counted live (total + type breakdown verified against the merged VCF). The
> **199,343** total is from the run log; the SVLEN-only / SVTYPE-only **per-type** numbers and the **159,824**
> total were not preserved in the handoffs — re-count (`grep -oE 'SVTYPE=[A-Z]+' | sort | uniq -c`) before citing them.

So **patch both** (per-sample → `vcf_patched/`):
- **SVLEN:** symbolic `<…>` alt → `END-POS+1`; literal → `abs(len(ALT)-len(REF))`; append `;SVLEN=`.
- **SVTYPE:** infer from the record-ID prefix letters (`INS…`/`DEL…`/`INV…`), else symbolic alt / REF-ALT
  length; insert the `##INFO=<ID=SVTYPE…>` header line.

### B2 — SURVIVOR merge (population SV set)

```bash
# build sample_files = one patched VCF path per line (assert 19), then:
SURVIVOR merge sample_files 50 1 1 1 0 50 merged.vcf
#                            │  │ │ │ │ │  └ min SV size (bp) — needs SVLEN, hence B1
#                            │  │ │ │ │ └ estimate_distance: 0 = fixed 50 bp
#                            │  │ │ │ └ agree on STRAND: 1
#                            │  │ │ └ agree on TYPE: 1
#                            │  │ └ min supporting samples: 1 (= union, no filtering)
#                            │  └ (callers slot)
#                            └ max breakpoint distance: 50 bp
```

For the corrected run, swap Javi/QQ74 to their rcCq3B-rerun VCFs and record an `input_vcf_manifest.tsv`.

### B3 — SV hotspots + subgenome / centromere / gene analysis

```bash
# repeat-env python; sliding window over the merged VCF
WINDOW=100kb  STEP=50kb  SUPP_MIN=2  TOP_PCT=10        # hotspot = top 10% of windows by weighted SV load
# weighting: NA(NOTAL) spreads SUPP across POS→END windows (×0.5 if span>5 Mb); INV/DUP/TRA score at breakpoint
```

Five modules: ① hotspot calling; ② A/B subgenome bias (Mann-Whitney + paired Wilcoxon over 9 homeolog pairs);
③ centromere proximity (distance bins 0–5/5–10/10–20/>20 Mb); ④ functional-gene overlap (GFF3 + EggNOG/NR,
keyword search: saponin / shattering / storage_protein / subgenome_dominance); ⑤ summary master table.
`plot_sv_hotspots.py` emits per-chromosome density, A-vs-B, centromere-distance, type-distribution, and a
hotspot heatmap (pdf+png @300 dpi).

> **Known inconsistency to fix when you adopt this:** the hotspot script reads the **SVLEN-only** merged VCF
> (4 classes, no INS/DEL), not the `svlen_svtype_fixed` one. **And `parse_vcf_weighted` only models 4 types**
> (na/inv/dup/tra) — INS/DEL land in an uncounted `other` bin, so swapping in the complete VCF is **not enough**;
> you must also extend the type/weight logic, or INS/DEL still get dropped from the hotspot weighting.

---

## Visualization — plotsr (shared by both paths), two layouts

```bash
# per-sample (all2ref): one accession vs ref
plotsr --sr "$syri_out" --genomes genomes.txt -o out.pdf -W 8 -H 6 -f 8          # PDF
plotsr --sr "$syri_out" --genomes genomes.txt -o out.png -W 8 -H 6 -f 8 -d 300   # PNG @300 dpi
# chained panorama: 19 --sr in chain order + a 20-line genomes file
plotsr $(printf -- '--sr %s ' "${syri_outs[@]}") --genomes genomes.chain.20.txt \
       -o plotsr_chain_20genomes.pdf -W 16 -H 30 -f 7 -S 0.5                      # -S = homologous-chromosome space
```

- **`genomes.txt`** format: `#file<TAB>name<TAB>tags`, one fasta per line **in chain order**; chromosome-bar
  colour comes from the **`lc:` tag** here (e.g. `lw:1.2;lc:#888888`), *not* from the cfg.
- **`--cfg base.cfg`** styling: plotsr 1.1.1 accepts a fixed set of styling keys — colours `syncol:#DEDEDE invcol:#2E8B57
  tracol:#1E90FF dupcol:#CD2626 alpha:0.85`, layout `chrmar exmar marginchr bbox bbox_v bboxmar`, and `legend:F genlegcol`
  (INVTR/INVDP reuse inv/tra colours; unknown keys are rejected).
- **`--markers markers.tsv`** (`chrom<TAB>start<TAB>end<TAB>genome<TAB>tags`, centromere tag `mt:s;mc:#222222;ms:6`;
  note the breakpoint-marker colour is inconsistent — `#000000` in `build_markers.py` vs `#333333` in the assembled legend).

### ⚠️ Visualization gotchas
- **The 18-chromosome "column" layout is NOT native plotsr.** It's per-chromosome panels (`--chr Cq1A … -W 1.35
  -H 8.8`, 18×) **assembled by PIL/matplotlib** (auto-crop whitespace, zebra row stripes on near-white pixels
  only, self-drawn legend). Don't expect one plotsr call to produce it.
- **`--chr` on 20-genome input is slow (~17 min/panel)** → never run 18 serially. Two-stage: all panels at
  **6-way concurrency**, then assemble — so a failed chromosome is re-runnable alone.
- **matplotlib cache races** under concurrency → `export MPLCONFIGDIR=… XDG_CACHE_HOME=…` to a per-output dir.
- **plotsr chromosome IDs must match `syri.out`.** The `_<sample>` suffix must be consistent between the fasta
  fed to SyRI and the fasta fed to plotsr, or plotsr dies with `ImportError: Chromosome ID … not present in
  genome fasta` (this killed Javi's first rcCq3B rerun).

---

## QC / acceptance — the quinoa benchmark

| Stage | Metric | Bar | Quinoa observed |
|---|---|---|---|
| minimap2 | peak RSS | size for it | **100–113 G** (80 G OOMs → request ≥150 G) |
| SyRI/pair | `syri.out` + `syri.summary` | non-empty both | e.g. Cqu_LM42: syntenic 905 / inv 125 / transloc 1231 / **SNP 2,001,754** |
| Chain | genomes file / `--sr` count | 20 lines in order / 19 sr | ✓ (validated in `input_validation.log`) |
| all2ref | pairs completed | 19/19 | 19/19 after orientation fixes |
| SURVIVOR | merged SVs (complete) | type-complete (INS present) | **202,406** (INS 42567 / DEL 35205 / INV 15314 / TRA 8196 / DUP 7021 / NA 94103) |
| Hotspots | windows / hotspots | top 10% | 25,430 windows → **2,586 (10.17%)** |

---

## How this maps onto the bio-workflow safety layer

1. **Design** here → pick chained (panorama) vs all2ref (population set); both share Stage 0–1.
2. **Generate** with `gen_sbatch.sh`: SyRI `--mem 150G` (asm5 OOMs at 80 G — measure, don't guess), forward
   `${SLURM_CPUS_PER_TASK}` to minimap2 `-t`; SURVIVOR `--mem 80G`; plotsr panels `--mem 96G` with a 6-way array.
3. **Gate** with `prepare_submission.sh`; for the 19-pair fan-out use a SLURM **array** + `%N` cap, mind the
   200/100/600 quota (19 pairs × 150 G is heavy — chunk it).
4. **Submit + record** with `submit_and_log.sh --yes`.
5. **Validate** with the table above + `resource_usage_audit.sh` (150 G was sized from a real OOM; re-measure
   per dataset). Run the orientation check and the SVLEN+SVTYPE patch **before** trusting any merged count.

## Pitfalls (consolidated)

- **minimap2 asm5 whole-genome peak ~100–113 G** — request ≥150 G; 80 G OOMs mid-array (only the cached pair survives).
- **Whole-chromosome reverse-complement** (esp. Cq3B) → SyRI `No syntenic region found`, **or** a real inversion
  drawn as a two-segment translocation/INVTR. Reverse-complement the offending chromosome in the query, **force
  re-alignment** (old SAM → `.bak`), rerun. Don't report the artifact translocation as a real event.
- **SyRI VCF lacks SVLEN *and* SVTYPE** — patch **both** before SURVIVOR or you lose all INS (SVTYPE-only) or
  collapse INS+DEL into NA (SVLEN-only). The complete count needs both.
- **SURVIVOR `merge 50 1 1 1 0 50`** = max-dist 50 / min-support 1 (union) / agree type / agree strand / fixed
  distance / min-size 50 bp. `min-support 1` is a **union**, not a filtered set — filter afterwards if needed.
- **plotsr name consistency** — query fasta chromosome IDs (with/without `_<sample>`) must match `syri.out`.
- **plotsr 18-column layout is post-assembled, `--chr` is slow, and cfg accepts only ~12 keys** — bar colour is
  the genomes-file `lc:` tag, not cfg; run panels 6-wide with isolated `MPLCONFIGDIR`.
- **Chained pairs share no coordinate** — never SURVIVOR-merge chained pairs; population merging requires all2ref.

## Sources

- SyRI — Goel et al., *Genome Biology* 2019, 20:277; https://github.com/schneebergerlab/syri
  (needs minimap2 `--eqx` SAM; `-F S`, `-k`).
- plotsr — Goel & Schneeberger, *Bioinformatics* 2022, 38:2922; https://github.com/schneebergerlab/plotsr
  (cfg ≈12 keys; chromosome-bar colour via genomes-file `lc:` tag; `--markers`, `--chr`).
- minimap2 — Li, *Bioinformatics* 2018, 34:3094 (`-ax asm5` for ≤~5% divergent assemblies).
- SURVIVOR — Jeffares et al., *Nature Communications* 2017, 8:14061;
  https://github.com/fritzsedlazeck/SURVIVOR (`merge max_dist min_support type strand est_dist min_size`).
- (Out of scope, for the fuller SV story) Swave — graph-pangenome complex SV; Sniffles2 — read-based SV; SVIM-asm — assembly-based SV.
