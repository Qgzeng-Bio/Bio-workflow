#!/usr/bin/env python3
"""Fill assembly gaps (N-runs) from a single spanning read/contig alignment.

This is the programmatic version of the manual "find a read/contig that bridges the
gap in IGV, splice it in" step (gap-finishing playbook, Stage F2, path B). It replaces
eyeballing IGV with deterministic extraction from a BAM.

Method (locked spec):
  * Donor (contigs or reads) is aligned to the gapped reference -> sorted, indexed BAM.
  * A valid spanner is ONE single linear PRIMARY alignment (no secondary/supplementary,
    i.e. not a split read) whose reference span anchors >= MIN_ANCHOR bp on BOTH flanks of
    the gap, with MAPQ >= MIN_MAPQ.
  * Per donor type the anchor differs: contigs 50 kb, reads 1 kb (reads kept permissive so
    short reads are not missed; quality is enforced by ranking, not by a big anchor).
  * Among candidates: prefer MAPQ >= PREFER_MAPQ (default 50), then highest FLANK identity
    (computed only over the anchored flanks, EXCLUDING the N gap), then a deterministic
    tie-break (longest anchor -> leftmost coord -> query name) so the result is reproducible.
  * The fill is the donor bases between the two flank anchors, taken from the BAM-stored
    SEQ via pysam aligned-pairs. NOTE: BAM stores SEQ in reference orientation already, so a
    reverse-strand donor needs NO manual reverse-complement here — pysam returns ref-oriented
    bases. Splice: ref[..left_anchor] + fill + ref[right_anchor..] (replaces only the gap).

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
    return gaps


def analyze(aln, gap_s0, gap_e0, anchor, ref_seq):
    """Return a candidate dict if `aln` linearly spans the gap with >= anchor on both flanks,
    else None. gap_s0/gap_e0 are 0-based inclusive first/last N of the gap."""
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
    matches = total = 0
    for q, r in aln.get_aligned_pairs():
        if r is None or q is None:   # insertion (r None) or deletion (q None) -> not an anchor/identity column
            continue
        if r > right_hi:             # aligned ref positions are monotonic; nothing useful past here
            break
        if r <= left_ref and (r_left is None or r > r_left):
            r_left, q_left = r, q
        if r >= right_ref and (r_right is None or r < r_right):
            r_right, q_right = r, q
        if (left_lo <= r <= left_ref) or (right_ref <= r <= right_hi):
            rb = ref_seq[r].upper()
            if rb == "N":
                continue
            total += 1
            if qseq[q].upper() == rb:
                matches += 1

    if q_left is None or q_right is None or q_right <= q_left:
        return None
    return {
        "qname": aln.query_name,
        "strand": "-" if aln.is_reverse else "+",
        "mapq": aln.mapping_quality,
        "identity": (matches / total) if total else 0.0,
        "anchor_total": left_anchor + right_anchor,
        "r_left": r_left, "r_right": r_right,
        "fill": qseq[q_left + 1:q_right],
    }


def pick(cands, prefer_mapq):
    """Deterministic selection: MAPQ tier (>=prefer first) -> identity -> longest anchor ->
    leftmost coord -> query name."""
    cands.sort(key=lambda c: (
        0 if c["mapq"] >= prefer_mapq else 1,
        -round(c["identity"], 6),
        -c["anchor_total"],
        c["r_left"],
        c["qname"],
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
    ap.add_argument("--out", required=True, help="output gap-filled FASTA")
    ap.add_argument("--report", required=True, help="output per-gap TSV report")
    args = ap.parse_args()

    anchor = args.min_anchor if args.min_anchor is not None else ANCHOR_DEFAULT[args.donor_type]
    fasta = pysam.FastaFile(args.ref)
    try:
        bam = pysam.AlignmentFile(args.bam, "rb")
    except Exception as e:
        sys.exit(f"[ERROR] cannot open BAM (is it sorted+indexed?): {e}")

    gaps = parse_gaps(args.gaps, args.gap)
    fills = {}   # seqid -> list of (r_left, r_right, fill)
    rows = []
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
        best = pick(cands, args.prefer_mapq)
        if best:
            fills.setdefault(seqid, []).append((best["r_left"], best["r_right"], best["fill"]))
            rows.append([seqid, s1, e1, e1 - s1 + 1, "filled", best["qname"], best["strand"],
                         best["mapq"], f"{best['identity']:.4f}", len(best["fill"]),
                         best["anchor_total"], len(cands)])
        else:
            rows.append([seqid, s1, e1, e1 - s1 + 1, "unfilled", "NA", "NA", "NA", "NA", 0, 0, len(cands)])

    # rebuild each contig, applying its fills left-to-right (replace ref (r_left,r_right) -> fill)
    with open(args.out, "w") as out:
        for seqid in fasta.references:
            seq = fasta.fetch(seqid)
            cf = sorted(fills.get(seqid, []), key=lambda x: x[0])
            if cf:
                parts, pos = [], 0
                for r_left, r_right, fill in cf:
                    parts.append(seq[pos:r_left + 1]); parts.append(fill); pos = r_right
                parts.append(seq[pos:])
                seq = "".join(parts)
            out.write(f">{seqid}\n")
            for i in range(0, len(seq), 60):
                out.write(seq[i:i + 60] + "\n")

    with open(args.report, "w") as r:
        r.write("Seqid\tGap_Start\tGap_End\tGap_Len\tStatus\tDonor\tStrand\tMAPQ\tFlank_Identity\tFill_Len\tAnchor_Total\tN_Candidates\n")
        for row in rows:
            r.write("\t".join(map(str, row)) + "\n")

    n_fill = sum(1 for x in rows if x[4] == "filled")
    sys.stderr.write(f"[fill_gap] donor_type={args.donor_type} anchor={anchor} min_mapq={args.min_mapq} "
                     f"prefer_mapq={args.prefer_mapq} -> filled {n_fill}/{len(rows)} gaps\n")
    sys.stderr.write(f"[fill_gap] wrote {args.out} and {args.report}\n")


if __name__ == "__main__":
    main()
