# Playbook — High-confidence SV: three-caller orthogonal calling (SyRI + SVIM-asm + Sniffles2) → SURVIVOR → overlap

> **Status: METHOD DRAFT — run IN PROGRESS, not yet complete.** Distilled from the live quinoa run
> `6-Comparation/7-pangenome/6-high_quality_sv_calling` (HANDOFF 2026-06-15). The **method and code are
> complete and partly validated**: SyRI normalization **19/19**, SVIM-asm calling **19/19** done; but the
> **read side is barely started** (align + Sniffles2 only **2/19**) and the **3-caller integration (C2/C3)
> has not run** — so the terminal high-confidence set does not exist yet and the cross-support numbers are
> **provisional**. Treat command/param/version facts as solid; treat counts beyond SyRI/SVIM-asm normalization
> as TBD. Sources at bottom.
>
> This is the **orthogonal / "advanced" extension** of `playbook-variant-synteny-syri.md`: SyRI alone is
> assembly-only; here we add a second assembly caller (SVIM-asm) and a read caller (Sniffles2) on the **same
> reference**, and the **read∩assembly cross-support** becomes the high-confidence axis.

## Design — why three callers (know the axis you're buying)

One reference (`Cqu_final.fa` = LM134, 18 chr, 1.27 Gbp — the **same** file SyRI all2ref used), three callers
per sample, integrated by SURVIVOR **union** (no hard filter — annotate support, filter downstream):

| Caller | Evidence | Input | What it adds |
|---|---|---|---|
| **SyRI** (reuse) | assembly → ref, synteny-aware | orientation-corrected assembly | rich SV classes (INV/TRANS/DUP/CPG/CPL/HDR) |
| **SVIM-asm** (new) | assembly → ref, alignment-based | same assembly | a *second, independent* assembly opinion (mostly INS/DEL/DUP/BND) |
| **Sniffles2** (new) | **reads → ref** | long-read BAM | the **orthogonal** read-level axis |

- **"High-confidence" lever:** an SV supported by **reads (Sniffles2) ∩ assembly (SyRI or SVIM-asm)** is the
  high-confidence subset — read evidence confirms an assembly call. This is computed, not pre-filtered.
- **Samples:** 19 = 10 LM (lab, Revio HiFi ~72 GB / ~60×) + 9 non-LM (public). Read-based covers **18**
  (0321072RM read-blocked — both public runs were corrupt). Reference is the coordinate base, not a sample.

**env / tools (versions verified, recorded in `sv_caller_tool_versions.tsv`):** micromamba env `svcall` —
**sniffles 2.8.0, svim-asm 1.0.3, bcftools 1.23.1, samtools 1.23.1**; minimap2 2.30-r1287 (TGS-GapCloser build);
SURVIVOR **1.0.7** (`…/tools/SURVIVOR/Debug/SURVIVOR`).
**⚠️ Call env binaries by ABSOLUTE PATH** (`/data9/home/qgzeng/.local/share/mamba/envs/svcall/bin/<tool>`) —
**never `micromamba run` under concurrency** (it deadlocks on "Could not set lock").

---

## Stage A2 — SVIM-asm (assembly → reference)

The second assembly caller, directly comparable to SyRI because it consumes the **same A0-locked,
orientation-corrected assembly** that fed the final SyRI VCF.

```bash
SVCALL=/data9/home/qgzeng/.local/share/mamba/envs/svcall/bin
MM2=/data9/home/qgzeng/tools/TGS-GapCloser/minimap2
# 1) assembly -> reference, asm5 (same preset SyRI all2ref used), --cs for svim-asm
"$MM2" -a -x asm5 --cs -t $((cpus-3)) "$REF_FA" "$ASM" | samtools sort -@ 3 -m 2G -T "$tmp" -o "$asm_bam" -
samtools index "$asm_bam"; samtools quickcheck "$asm_bam"
# 2) svim-asm haploid (single assembly vs reference) -> <work_dir>/variants.vcf
"$SVCALL/svim-asm" haploid --min_sv_size 50 --max_sv_size 100000000 --min_mapq 20 "$work_dir" "$asm_bam" "$REF_FA"
```

- `--min_sv_size 50` — match the project ≥50 bp convention (= Sniffles2 `--minsvlen 50`).
- **`--max_sv_size 100000000`** — OVERRIDE the default 100 kb. Per svim-asm's own help this size is what
  **distinguishes long DEL/INV from translocations**: above it a large deletion/inversion is reported as a
  **translocation (BND)**, not a DEL/INV — so the default would mis-render the ~80 Mb Cq3B inversion as a
  translocation. The override lets it be called as an INV (the single most important non-default flag here).
  **Trade-off:** lifting the cap also lets genuine translocations be mis-called as giant DEL/INV and admits more
  large-alignment artifacts → it *rescues candidates*, it does not *confirm* them; large events still need the
  separate reciprocal-overlap + manual check in C2/C3. Accuracy comes from that confirmation, not from this flag.
- `--min_mapq 20` (default) — assembly contigs map at high MAPQ, default is fine.

**Resources:** `normal` (or `debug`=fat2), 12 CPU, **96 G** — asm5 of ~80 Mb whole-chromosome contigs peaks
**>33 G**; 32 G is OOM-killed (`sacct` → `OUT_OF_MEMORY 0:125`). **Run state: 19/19 variants.vcf done.**

---

## Stage B1 — read alignment (long reads → reference)

```bash
# per-sample: merge ALL runs of a sample into one sorted BAM; preset is per-sample
"$MM2" -t $((cpus-st)) -ax "$preset" --MD -R "@RG\tID:$S\tSM:$S\tPL:PACBIO" "$REF_FA" "${fastqs[@]}" \
  | samtools sort -@ $st -m 3G -T "$tmp" -o "$bam" -
samtools index "$bam"; samtools quickcheck "$bam"; samtools flagstat "$bam" > "$bam.flagstat.txt"
```

- **Preset is per-sample:** `map-hifi` for HiFi/CCS samples, **`map-pb` for QQ74 (CLR)** — column in
  `read_sv_samples.tsv`. Picking the wrong preset silently degrades calls.
- **Align from the FASTA, NOT a prebuilt `.mmi`** — on-the-fly indexing then uses preset-correct `k`/`w`; a
  single `.mmi` cannot be optimal for both `map-hifi` and `map-pb`. (Contrast: the asm5 step in A2 *can* share
  one `.mmi` — see Pitfalls.)
- **Resources:** `normal`, 16 CPU, 64 G. **Run state: 2/19 BAM** (bottleneck — big Revio HiFi + cluster contention).

## Stage B2 — Sniffles2 (reads → reference)

```bash
"$SVCALL/sniffles" --input "$bam" --reference "$REF_FA" --vcf "$S.sniffles.vcf" --snf "$S.sniffles.snf" \
    --threads $cpus --minsvlen 50
```

- Same command for HiFi and CLR — Sniffles2 auto-adapts. `--minsvlen 50` matches the convention.
- `.snf` is kept for optional later **multi-sample/population** re-genotyping.
- **Resources:** `normal`, 8 CPU, 32 G. **Run state: 2/19** (gated on B1 BAMs).

---

## Stage C1 — uniform normalization (`normalize_sv_vcf.py --caller {syri,svimasm,sniffles}`)

One script, three caller modes, then `bcftools sort | bgzip | tabix`. Common rules:

- **Guarantee `INFO/SVTYPE` + `INFO/SVLEN`** (infer when missing — symbolic `<…>` alt → `END-POS+1`, literal →
  `|len(ALT)-len(REF)|`).
- **Canonical contigs** `Cq1A…Cq9B` (strip any `_<suffix>`), de-dupe contig headers.
- **Size filter:** drop **length-bearing** types (DEL/INS/DUP/INV) `< 50 bp`; **keep TRANS/BND/CPG/CPL/HDR
  regardless of length** (they have no meaningful SVLEN).
- Per-caller: **SyRI** infers SVTYPE from the record-ID prefix and **drops alignment-level entries**
  (`SYN`/`NOTAL`/`SNP`/`*AL`); **SVIM-asm** collapses `DUP:TANDEM`/`DUP:INT` → `DUP`; **Sniffles2** already has SVTYPE.

Normalization is where SyRI shrinks hardest: **~2.0 M input → ~20–27 k SVs/sample** (drops ~1.7 M SYN/NOTAL/SNP
+ ~350 k `*AL`), **472,996 SVs across 19** (✅ done). SVIM-asm barely shrinks: ~38 k → ~38 k, dominated by
INS/DEL (e.g. 0321072RM: 38,003 = INS 19,928 / DEL 17,964 / DUP 57 / BND 54) — **far more INS/DEL than SyRI**,
which is exactly the second-opinion value. **Run state: SyRI 19/19, SVIM-asm 2/19, Sniffles2 0/19.**

---

## Stage C2 — SURVIVOR merge per sample (union, type-concordant, support-annotated)

```bash
# caller order FIXED [syri, svimasm, sniffles] so SUPP_VEC positions are comparable across samples
for caller in syri svimasm sniffles; do [[ -s "$NORM/$S.$caller.norm.vcf" ]] && echo "$NORM/$S.$caller.norm.vcf" >> list; done
SURVIVOR merge list 1000 1 1 0 0 50 "$S.3caller.vcf"
#                   │    │ │ │ │ │  └ min SV size 50 bp
#                   │    │ │ │ │ └ estimate_distance — DISABLED in 1.0.7 (no effect; max_dist stays fixed bp)
#                   │    │ │ │ └ agree on STRAND 0 (off — minor; matters mainly for INV/BND)
#                   │    │ │ └ agree on TYPE 1  ← REQUIRE same SVTYPE to merge
#                   │    │ └ min support 1 (= union: annotate SUPP_VEC, don't filter)
#                   │    └ (callers slot)
#                   └ max breakpoint distance 1000 bp
```

**Use `type=1` — verified empirically on SURVIVOR 1.0.7.** With `type=0`, a DEL + INS + DEL within 1 kb collapse
into ONE `SUPP=3` record whose `INFO/SVTYPE` is just one representative member's — possibly the *minority* type
(a 2×DEL + 1×INS cluster emitted `SVTYPE=INS` with `SVLEN=-500`, internally inconsistent). Because this set is
defined by **caller agreement**, `type=0` inflates concordance and mislabels type; `type=1` correctly keeps the
two DELs together (SUPP=2) and the INS separate. **Tradeoff:** `type=1` splits the *same* event when callers
label it differently (DUP↔INS, INV↔BND) — the conservative cost of a clean high-confidence set.

Notes: per-caller type is **not** lost — SURVIVOR records it in the FORMAT **`TY`** subfield (not INFO).
`est_dist` is **Disabled** in 1.0.7, so `max_dist` is a fixed 1000 bp — very large SVs whose breakpoints differ
by >1 kb between callers will NOT merge; handle chromosome-scale events (e.g. the ~80 Mb Cq3B inversion)
separately. Contrast the all2ref SyRI merge `50 1 1 1 0 50` (cross-*sample*, tight 50 bp) vs this
`1000 1 1 0 0 50` (cross-*caller*, loose 1 kb). A sample missing Sniffles2 yields a 2-char `SUPP_VEC`
(via `callers_order.txt`).

> **The archived `16_survivor_merge_per_sample.slurm` used `type=0`** — re-merge with `type=1`. (Caught by an
> empirical SURVIVOR probe — DEL+INS+DEL→one `SUPP=3` record — not by the run itself.)

**Large events (≥ ~50 kb) — confirm separately by reciprocal overlap, NOT the per-record merge.** The fixed
1 kb window under-merges them (verified: a 100 kb DEL whose breakpoints differ by 1.5 kb stays two SUPP=1
records — SURVIVOR requires *both* endpoints inside `max_dist`). So pull large SVs out and match read-vs-assembly
by ≥50% reciprocal overlap instead of breakpoint distance:

```bash
# per caller: large SVs -> BED(chrom,start,end), then 50% reciprocal overlap of read (sniffles) vs assembly
for c in syri svimasm sniffles; do
  awk -F'\t' '!/^#/{ if (match($8,/SVLEN=(-?[0-9]+)/,m) && (m[1]<0?-m[1]:m[1])>=50000){
      match($8,/END=([0-9]+)/,e); print $1"\t"($2-1)"\t"(e[1]?e[1]:$2)"\t"c }}' results/norm/$S.$c.norm.vcf > $S.$c.large.bed
done
cat $S.syri.large.bed $S.svimasm.large.bed | sort -k1,1 -k2,2n > $S.asm.large.bed
bedtools intersect -a $S.sniffles.large.bed -b $S.asm.large.bed -f 0.5 -r -wo > $S.large.read_int_asm.tsv
```

Caveat: read callers emit **Mb-scale inversions as BND breakends**, not one INV record — for the very largest
events (the ~80 Mb Cq3B inversion) overlap is unreliable; confirm those by **IGV / dot-plot manual review**.
(Truvari is the cleaner SV-aware matcher if installed; the bedtools route needs no extra install.)

## Stage C3 — caller-overlap report (`17_caller_overlap_report.py`) → the high-confidence subset

Decode `SUPP_VEC` → the set of supporting callers per SV, tabulate by **combo × SVTYPE × size-bin**
(50 bp–1 kb / 1–10 kb / 10–100 kb / >100 kb) — it reads `INFO/SVTYPE`, which is trustworthy only because C2
uses `type=1` (with `type=0` the merged type can be a minority/mislabeled call) — and report the orthogonal axis:

- `assembly_any` = supported by SyRI or SVIM-asm; `read_any` = supported by Sniffles2;
  **`read_int_assembly` = the high-confidence subset** (read ∩ assembly). Nothing is hard-filtered — you select
  on these columns downstream.
- Outputs `caller_overlap_per_sample.tsv` (long) + `caller_overlap_summary.tsv` (one row/sample + TOTAL).
- **Run state: not run** (needs C2). The full high-confidence cross-support is only computable once B1/B2 finish.

---

## Current run state (honest snapshot — this is why the playbook is a DRAFT)

| Stage | Done | Note |
|---|---|---|
| SyRI normalize (C1) | **19/19** ✅ | 472,996 SVs |
| SVIM-asm call (A2) | **19/19** ✅ | overnight "too slow" issue resolved |
| SVIM-asm normalize (C1) | 2/19 🔄 | |
| Read align (B1) | 2/19 🔄 | **bottleneck** — big Revio HiFi + cluster contention |
| Sniffles2 (B2) | 2/19 🔄 | gated on B1 |
| C2 merge / C3 report | 0 ❌ | `results/merged` does not exist yet |

→ The terminal **per-sample 3-caller VCF** and the **high-confidence read∩assembly counts do not exist yet**.
Finish B1→B2→C2→C3 (and add 0321072RM once its read download passes md5) before quoting any overlap numbers.

## How this maps onto the bio-workflow safety layer

1. **Design** here → confirm reference == the SyRI all2ref reference; lock A0 (orientation-corrected assemblies).
2. **Generate** with `gen_sbatch.sh`: SVIM-asm `--mem 96G` (sized from a real 32 G OOM); read align 16 CPU / 64 G;
   forward `${SLURM_CPUS_PER_TASK}`; **bake the absolute `svcall` binary paths** (no `micromamba run`).
3. **Gate** with `prepare_submission.sh`; the 19-sample fan-outs are SLURM **arrays** + `%N` cap (200/100/600 quota;
   SVIM-asm at 96 G × many is heavy — chunk it, and `debug`=fat2 when `normal`/`high` are jammed).
4. **Submit + record** with `submit_and_log.sh --yes`; downloads go through **admin2 only** (compute nodes have no internet).
5. **Validate** layered: BAM `quickcheck`/`flagstat`; per-sample SV counts sane; spot-check `SUPP=high` in IGV;
   the QQ74/Javi Cq3B inversion should be **read-and-assembly consistent** (that consistency validates the A0 orientation fix).

## Pitfalls (hard-won, from the run)

- **Never `micromamba run` under concurrency** — it locks ("Could not set lock"). Call `…/envs/svcall/bin/<tool>`
  by absolute path; the shebang already points at the env python, no activation needed.
- **SVIM-asm needs ~96 G** (asm5 of ~80 Mb contigs peaks >33 G; 32 G → `OUT_OF_MEMORY 0:125`).
- **SVIM-asm re-indexing storm:** 12 concurrent jobs each re-index the 1.27 GB reference from FASTA + contend for
  /data9 I/O → ~0 output in 40 min. Fix: prebuild the asm5 index once
  (`minimap2 -x asm5 -d Cqu_final.asm5.mmi Cqu_final.fa`) and point the **A2 (asm5)** minimap2 at it. **Do NOT do
  this for B1 read align** — that step must stay on the FASTA to keep preset-correct `k`/`w` for map-hifi vs map-pb.
- **Preset per data type:** HiFi → `map-hifi`, **CLR (QQ74) → `map-pb`**. Wrong preset silently degrades.
- **`--max_sv_size 1e8` for SVIM-asm** — the default 100 kb does NOT drop large events, it **reclassifies** long
  DEL/INV as translocations (BND); the override keeps them as DEL/INV. Price: real translocations can be
  mis-called as giant DEL/INV — confirm large events separately, don't trust them on the strength of this flag.
- **`debug` partition = fat2 (384 cores / 6 TB)** — use it when `normal`/`high` are starving jobs; `TotalCPU`
  reads 0 until job end (accounting lag) — confirm real compute with `scontrol show node <n>` CPULoad.
- **Download integrity = md5 vs ENA's reported md5** (corrupt OR incomplete both fail). `wget --continue` on a
  byte-complete-but-corrupt file never re-fetches — that was the original corruption root cause; prefer fresh
  `aria2c -x16` + md5 verify. **No `#SBATCH --time`** (project rule).
- **SURVIVOR: use `type=1` for a consensus set; `est_dist` is Disabled in 1.0.7.** `type=0` merges across SV
  types (empirically verified: DEL+INS+DEL → one mislabeled `SUPP=3` record) and inflates apparent concordance.
  Params here `1000 1 1 0 0 50` (cross-caller) vs `50 1 1 1 0 50` (cross-sample, all2ref); `max_dist` is fixed
  (est_dist off), so very large SVs can under-merge — handle chromosome-scale events separately.

## Sources

- Sniffles2 — Smolka et al., *Nature Biotechnology* 2024 (mosaic & population SV from long reads);
  https://github.com/fritzsedlazeck/Sniffles
- SVIM-asm — Heller & Vingron, *Bioinformatics* 2021, 37:5519 (SV from haploid/diploid assemblies);
  https://github.com/eldariont/svim-asm
- SURVIVOR — Jeffares et al., *Nature Communications* 2017, 8:14061;
  https://github.com/fritzsedlazeck/SURVIVOR (`merge max_dist min_support type strand est_dist min_size`).
- SyRI — Goel et al., *Genome Biology* 2019 (assembly-vs-assembly SV; see `playbook-variant-synteny-syri.md`).
- minimap2 — Li, *Bioinformatics* 2018 (`map-hifi` / `map-pb` / `asm5` presets).
