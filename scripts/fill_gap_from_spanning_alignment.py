#!/usr/bin/env python3
"""Fill assembly gaps (N-runs) from a single spanning read/contig alignment.

This is the programmatic version of the manual "find a read/contig that bridges the
gap in IGV, splice it in" step (gap-finishing playbook, Stage F2, path B). It replaces
eyeballing IGV with deterministic extraction from a BAM.

Method (locked spec):
  * Donor (contigs or reads) is aligned to the gapped reference -> sorted, indexed BAM.
  * A valid spanner is ONE single linear PRIMARY alignment (secondary/supplementary records are
    skipped; a read clipped/split at the gap fails the exact-edge test) that anchors >= MIN_ANCHOR bp
    on BOTH flanks AND aligns EXACTLY up to both gap edges — the last ref base before the gap and the
    first after it must both be aligned, with MAPQ >= MIN_MAPQ.
  * Per donor type the anchor differs: contigs 50 kb, reads 1 kb (reads kept permissive so short reads
    are not missed; quality is enforced by ranking + per-flank gates, not by a big anchor).
  * Each flank, checked LEFT and RIGHT separately (excluding the N gap), must have enough aligned non-N
    columns and identity >= --min-identity (default 0.80) — a lopsided candidate can't pass on one side.
  * Among survivors: prefer MAPQ >= PREFER_MAPQ (default 50), then highest combined flank identity, then
    longest anchor, then longest fill -> query name -> fill (fully deterministic, reproducible).
  * The fill is the donor bases between the two gap-edge anchors, from the BAM-stored SEQ via pysam
    aligned-pairs. NOTE: BAM stores SEQ in reference orientation already, so a reverse-strand donor needs
    NO manual reverse-complement — pysam returns ref-oriented bases. Splice replaces ONLY the N run:
    ref[..gap_s0-1] + fill + ref[gap_e0+1..]. Overlapping fills on one contig are skipped (reported).

It does NOT validate by re-mapping; after filling, re-align long reads across each new join
and check for continuous depth (no drop at the seam) — see the playbook.

Read-only on inputs; writes a new FASTA + a per-gap TSV report. No SLURM, no submission.
"""
import argparse
import sys

try:
    import pysam
except ImportError:
    sys.exit("[ERROR] pysam not found. Use a python with pysam (e.g. anaconda3) or: micromamba install -c bioconda pysam")

ANCHOR_DEFAULT = {"contig": 50000, "read": 1000}


def parse_gaps(gaps_path, single_gap):
    """Yield (seqid, start1, end1) 1-based inclusive. From a get_gaps.py GFF3 or --gap."""
    gaps = []
    if single_gap:
        chrom, rng = single_gap.split(":")
        s, e = rng.replace(",", "").split("-")
        gaps.append((chrom, int(s), int(e)))
        return gaps
    with open(gaps_path) as fh:
        for line in fh:
            if line.startswith("#") or not line.strip():
                continue
            c = line.rstrip("\n").split("\t")
            if len(c) < 5:
                continue
            gaps.append((c[0], int(c[3]), int(c[4])))   # GFF3: seqid, .., type, start, end
    return list(dict.fromkeys(gaps))                     # dedupe identical gap entries


def analyze(aln, gap_s0, gap_e0, anchor, ref_seq):
    """Return a candidate dict only if `aln` is a single linear PRIMARY alignment that anchors EXACTLY at
    both gap edges (last ref base before the gap AND first ref base after it are both aligned, no
    deletion/clip there) with >= anchor flank on each side — so the fill corresponds exactly to the N run
    and the splice never touches non-gap reference bases. gap_s0/gap_e0 are 0-based inclusive first/last N."""
    if aln.is_unmapped or aln.is_secondary or aln.is_supplementary:
        return None
    # hard anchor gate from the alignment's reference span (reference_end is exclusive)
    left_anchor = gap_s0 - aln.reference_start
    right_anchor = (aln.reference_end - 1) - gap_e0
    if left_anchor < anchor or right_anchor < anchor:
        return None

    left_ref = gap_s0 - 1            # last ref base before gap (0-based)
    right_ref = gap_e0 + 1           # first ref base after gap
    left_lo = gap_s0 - anchor
    right_hi = gap_e0 + anchor
    qseq = aln.query_sequence
    if qseq is None:
        return None

    q_left = r_left = q_right = r_right = None
    lm = lc = rm = rc = 0            # left/right flank: matches, aligned non-N columns
    for q, r in aln.get_aligned_pairs():
        if r is None or q is None:   # insertion (r None) or deletion (q None) -> not an anchor/identity column
            continue
        if r > right_hi:             # aligned ref positions are monotonic; nothing useful past here
            break
        if r <= left_ref and (r_left is None or r > r_left):
            r_left, q_left = r, q
        if r >= right_ref and (r_right is None or r < r_right):
            r_right, q_right = r, q
        if left_lo <= r <= left_ref:
            rb = ref_seq[r].upper()
            if rb != "N":
                lc += 1
                lm += (qseq[q].upper() == rb)
        elif right_ref <= r <= right_hi:
            rb = ref_seq[r].upper()
            if rb != "N":
                rc += 1
                rm += (qseq[q].upper() == rb)

    # the donor must align EXACTLY up to both gap edges (else the splice would delete flank bases), and
    # have genuinely-aligned bases on each flank
    if r_left != left_ref or r_right != right_ref or q_left is None or q_right is None or q_right <= q_left:
        return None
    if lc == 0 or rc == 0:
        return None
    return {
        "qname": aln.query_name,
        "strand": "-" if aln.is_reverse else "+",
        "mapq": aln.mapping_quality,
        "left_cols": lc, "right_cols": rc,
        "left_identity": lm / lc, "right_identity": rm / rc,
        "identity": (lm + rm) / (lc + rc),     # combined, for ranking only
        "anchor_total": left_anchor + right_anchor,
        "fill": qseq[q_left + 1:q_right],
    }


def pick(cands, prefer_mapq):
    """Deterministic selection: MAPQ tier (>=prefer first) -> flank identity -> longest anchor ->
    longest fill -> query name -> fill (equal candidates resolve reproducibly, not by BAM order)."""
    cands.sort(key=lambda c: (
        0 if c["mapq"] >= prefer_mapq else 1,
        -round(c["identity"], 6),
        -c["anchor_total"],
        -len(c["fill"]),
        c["qname"], c["fill"],
    ))
    return cands[0] if cands else None


def main():
    ap = argparse.ArgumentParser(description="Fill N-gaps from a single spanning read/contig alignment.")
    ap.add_argument("--bam", required=True, help="donor (contigs|reads) aligned to the gapped reference, sorted+indexed")
    ap.add_argument("--ref", required=True, help="the gapped reference FASTA (faidx-indexed)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--gaps", help="GFF3 of gaps from get_gaps.py")
    g.add_argument("--gap", help="single gap as CHR:START-END (1-based inclusive)")
    ap.add_argument("--donor-type", choices=["contig", "read"], default="contig",
                    help="sets default min-anchor (contig 50kb, read 1kb)")
    ap.add_argument("--min-anchor", type=int, default=None, help="override per-flank min anchor (bp)")
    ap.add_argument("--min-mapq", type=int, default=30, help="hard MAPQ floor (default 30)")
    ap.add_argument("--prefer-mapq", type=int, default=50, help="preferred MAPQ tier (default 50)")
    ap.add_argument("--min-identity", type=float, default=0.80,
                    help="reject a fill whose flank identity is below this -> mark unfilled (0 disables)")
    ap.add_argument("--out", required=True, help="output gap-filled FASTA")
    ap.add_argument("--report", required=True, help="output per-gap TSV report")
    args = ap.parse_args()

    anchor = args.min_anchor if args.min_anchor is not None else ANCHOR_DEFAULT[args.donor_type]
    fasta = pysam.FastaFile(args.ref)
    try:
        bam = pysam.AlignmentFile(args.bam, "rb")
    except Exception as e:
        sys.exit(f"[ERROR] cannot open BAM (is it sorted+indexed?): {e}")

    if not 0.0 <= args.min_identity <= 1.0:
        sys.exit("[ERROR] --min-identity must be in [0, 1]")

    gaps = parse_gaps(args.gaps, args.gap)

    # phase 1: per gap, pick the best clean spanner (gate on per-flank coverage AND per-flank identity)
    results = []
    for seqid, s1, e1 in gaps:
        gap_s0, gap_e0 = s1 - 1, e1 - 1
        ref_seq = fasta.fetch(seqid)
        fetch_lo = max(0, gap_s0 - anchor)
        fetch_hi = min(len(ref_seq), gap_e0 + anchor + 1)
        cands = []
        for aln in bam.fetch(seqid, fetch_lo, fetch_hi):
            if aln.mapping_quality < args.min_mapq:
                continue
            c = analyze(aln, gap_s0, gap_e0, anchor, ref_seq)
            if c:
                cands.append(c)
        good = [c for c in cands
                if c["left_cols"] >= anchor // 2 and c["right_cols"] >= anchor // 2
                and c["left_identity"] >= args.min_identity and c["right_identity"] >= args.min_identity]
        results.append({"seqid": seqid, "s1": s1, "e1": e1, "gap_s0": gap_s0, "gap_e0": gap_e0,
                        "best": pick(good, args.prefer_mapq), "n_cands": len(cands), "status": None})

    # phase 2: per contig, sort the filled gaps and drop any that overlaps an already-applied fill
    applied = {}
    for seqid in {r["seqid"] for r in results}:
        prev_end = -1
        for r in sorted((x for x in results if x["seqid"] == seqid and x["best"]), key=lambda x: x["gap_s0"]):
            if r["gap_s0"] <= prev_end:
                r["status"] = "skipped_overlap"
                sys.stderr.write(f"[WARN] {seqid}: skipping overlapping fill at gap {r['s1']}-{r['e1']}\n")
                continue
            r["status"] = "filled"
            applied.setdefault(seqid, []).append((r["gap_s0"], r["gap_e0"], r["best"]["fill"]))
            prev_end = r["gap_e0"]

    # phase 3: write the gap-filled FASTA, replacing ONLY each N run [gap_s0..gap_e0] with its fill
    with open(args.out, "w") as out:
        for seqid in fasta.references:
            seq = fasta.fetch(seqid)
            af = sorted(applied.get(seqid, []), key=lambda x: x[0])
            if af:
                parts, pos = [], 0
                for gs, ge, fill in af:
                    parts.append(seq[pos:gs]); parts.append(fill); pos = ge + 1
                parts.append(seq[pos:])
                seq = "".join(parts)
            out.write(f">{seqid}\n")
            for i in range(0, len(seq), 60):
                out.write(seq[i:i + 60] + "\n")

    # report (status now matches exactly what went into the FASTA)
    with open(args.report, "w") as rep:
        rep.write("Seqid\tGap_Start\tGap_End\tGap_Len\tStatus\tDonor\tStrand\tMAPQ\tFlank_Identity\tFill_Len\tAnchor_Total\tN_Candidates\n")
        for r in results:
            b = r["best"]
            if b and r["status"] == "filled":
                row = [r["seqid"], r["s1"], r["e1"], r["e1"] - r["s1"] + 1, "filled", b["qname"], b["strand"],
                       b["mapq"], f"{min(b['left_identity'], b['right_identity']):.4f}", len(b["fill"]),
                       b["anchor_total"], r["n_cands"]]
            else:
                status = r["status"] or ("unfilled_low_identity_or_coverage" if r["n_cands"] else "unfilled_no_spanner")
                row = [r["seqid"], r["s1"], r["e1"], r["e1"] - r["s1"] + 1, status, "NA", "NA", "NA", "NA", 0, 0, r["n_cands"]]
            rep.write("\t".join(map(str, row)) + "\n")

    n_fill = sum(1 for r in results if r["status"] == "filled")
    sys.stderr.write(f"[fill_gap] donor_type={args.donor_type} anchor={anchor} min_mapq={args.min_mapq} "
                     f"prefer_mapq={args.prefer_mapq} min_identity={args.min_identity} -> filled {n_fill}/{len(results)} gaps\n")
    sys.stderr.write(f"[fill_gap] wrote {args.out} and {args.report}\n")


if __name__ == "__main__":
    main()
