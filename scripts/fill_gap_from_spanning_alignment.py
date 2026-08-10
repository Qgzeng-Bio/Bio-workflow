#!/usr/bin/env python3
"""Fill complete internal assembly N-runs from one spanning primary alignment.

The command is deliberately conservative: every requested gap and every output path
is validated before BAM regions are fetched or output files are created.  A fill
replaces only a complete, maximal internal N-run.  Outputs are staged in their own
parent directories and committed as a pair; existing outputs require ``--force``.

This command does not validate the new joins biologically.  A ``filled`` report row
means only that sequence replacement completed.  Re-run gap detection and remap
HiFi/ONT reads across both joins before accepting a finished assembly.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable

try:
    import pysam
except ImportError:
    sys.exit(
        "[ERROR] pysam not found. Use an existing Python environment with pysam; "
        "do not install dependencies implicitly."
    )

ANCHOR_DEFAULT = {"contig": 50000, "read": 1000}
REPORT_HEADER = (
    "Seqid\tGap_Start\tGap_End\tGap_Len\tStatus\tDonor\tStrand\tMAPQ\t"
    "Flank_Identity\tFill_Len\tAnchor_Total\tN_Candidates\n"
)
PROTECTED_RE = re.compile(r"^/data9/home/[^/]+/(?:data|tools)(?:/|$)")


class GapFillError(ValueError):
    """Expected input, interval, or output-safety failure."""


def parse_gap_string(value: str) -> tuple[str, int, int]:
    """Parse ``SEQID:START-END`` as a 1-based inclusive interval."""
    match = re.fullmatch(r"([^:\s]+):([0-9][0-9,]*)-([0-9][0-9,]*)", value.strip())
    if not match:
        raise GapFillError(f"invalid --gap value {value!r}; expected SEQID:START-END")
    seqid, start, end = match.groups()
    return seqid, int(start.replace(",", "")), int(end.replace(",", ""))


def parse_gff3(path: Path) -> list[tuple[str, int, int]]:
    """Read gap coordinates from non-comment GFF3 rows; malformed rows are fatal."""
    gaps: list[tuple[str, int, int]] = []
    try:
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip() or line.startswith("#"):
                    continue
                fields = line.rstrip("\n").split("\t")
                if len(fields) != 9:
                    raise GapFillError(
                        f"{path}:{line_number}: expected 9 tab-separated GFF3 columns, got {len(fields)}"
                    )
                try:
                    start, end = int(fields[3]), int(fields[4])
                except ValueError as exc:
                    raise GapFillError(
                        f"{path}:{line_number}: non-integer GFF3 start/end"
                    ) from exc
                gaps.append((fields[0], start, end))
    except OSError as exc:
        raise GapFillError(f"cannot read gap GFF3 {path}: {exc}") from exc
    if not gaps:
        raise GapFillError(f"gap GFF3 has no data rows: {path}")
    return gaps


def deduplicate_gaps(
    gaps: Iterable[tuple[str, int, int]],
) -> tuple[list[tuple[str, int, int]], int]:
    """Remove exact duplicates while preserving input order."""
    unique: list[tuple[str, int, int]] = []
    seen: set[tuple[str, int, int]] = set()
    duplicates = 0
    for gap in gaps:
        if gap in seen:
            duplicates += 1
        else:
            seen.add(gap)
            unique.append(gap)
    if not unique:
        raise GapFillError("no valid gap intervals were supplied")
    return unique, duplicates


def is_protected(path: Path) -> bool:
    return bool(PROTECTED_RE.match(str(path)))


def resolved(path: Path) -> Path:
    """Resolve symlinked parents without requiring the final path to exist."""
    return path.expanduser().resolve(strict=False)


def validate_readable_file(path: Path, label: str) -> Path:
    if not path.exists() or not path.is_file():
        raise GapFillError(f"{label} does not exist or is not a regular file: {path}")
    if not os.access(path, os.R_OK):
        raise GapFillError(f"{label} is not readable: {path}")
    return resolved(path)


def validate_output_paths(
    out: Path,
    report: Path,
    inputs: Iterable[Path],
    force: bool = False,
) -> tuple[Path, Path]:
    """Validate output identity, destination, protected-path, and overwrite rules."""
    outputs = [out.expanduser(), report.expanduser()]
    input_resolved = {resolved(path) for path in inputs}
    output_resolved = [resolved(path) for path in outputs]
    if output_resolved[0] == output_resolved[1]:
        raise GapFillError("--out and --report must resolve to different paths")

    for raw, target in zip(outputs, output_resolved):
        if raw.is_symlink():
            raise GapFillError(f"output path must not be a symbolic link: {raw}")
        if target in input_resolved:
            raise GapFillError(f"output path resolves to an input file: {raw}")
        if is_protected(target):
            raise GapFillError(f"refusing protected output path: {target}")
        parent = target.parent
        if not parent.exists() or not parent.is_dir():
            raise GapFillError(f"output parent must already exist: {parent}")
        if not os.access(parent, os.W_OK):
            raise GapFillError(f"output parent is not writable: {parent}")
        if target.exists():
            if not target.is_file():
                raise GapFillError(f"existing output is not a regular file: {target}")
            if not force:
                raise GapFillError(f"output already exists (use --force only after approval): {target}")
    return output_resolved[0], output_resolved[1]


def validate_gap_intervals(
    gaps: Iterable[tuple[str, int, int]], fasta: Any
) -> list[dict[str, Any]]:
    """Validate coordinates and require each interval to be one maximal internal N-run."""
    references = set(fasta.references)
    lengths = dict(zip(fasta.references, fasta.lengths))
    coordinate_checked: list[dict[str, Any]] = []
    for seqid, start, end in gaps:
        if seqid not in references:
            raise GapFillError(f"gap seqid is absent from reference FASTA: {seqid}")
        length = lengths[seqid]
        if not 1 <= start <= end <= length:
            raise GapFillError(
                f"gap {seqid}:{start}-{end} is outside 1-{length} or has start > end"
            )
        coordinate_checked.append(
            {"seqid": seqid, "s1": start, "e1": end, "gap_s0": start - 1, "gap_e0": end - 1}
        )

    ordered = sorted(
        coordinate_checked, key=lambda item: (item["seqid"], item["gap_s0"], item["gap_e0"])
    )
    for previous, current in zip(ordered, ordered[1:]):
        if previous["seqid"] == current["seqid"] and current["gap_s0"] <= previous["gap_e0"]:
            raise GapFillError(
                "different gap intervals overlap: "
                f"{previous['seqid']}:{previous['s1']}-{previous['e1']} and "
                f"{current['seqid']}:{current['s1']}-{current['e1']}"
            )

    checked: list[dict[str, Any]] = []
    for item in coordinate_checked:
        seqid, start, end = item["seqid"], item["s1"], item["e1"]
        start0, end0 = item["gap_s0"], item["gap_e0"]
        length = lengths[seqid]
        if start0 == 0 or end0 == length - 1:
            raise GapFillError(
                f"gap {seqid}:{start}-{end} is terminal; two-sided anchors are required"
            )
        sequence = fasta.fetch(seqid)
        interval = sequence[start0 : end0 + 1]
        if not interval or any(base.upper() != "N" for base in interval):
            raise GapFillError(f"gap {seqid}:{start}-{end} contains non-N sequence")
        if sequence[start0 - 1].upper() == "N" or sequence[end0 + 1].upper() == "N":
            raise GapFillError(
                f"gap {seqid}:{start}-{end} covers only part of a maximal N-run"
            )
        item["ref_seq"] = sequence
        checked.append(item)
    return checked


def analyze(aln: Any, gap_s0: int, gap_e0: int, anchor: int, ref_seq: str) -> dict[str, Any] | None:
    """Return a candidate only for a primary linear two-sided exact-edge spanner."""
    if aln.is_unmapped or aln.is_secondary or aln.is_supplementary:
        return None
    if aln.reference_start is None or aln.reference_end is None:
        return None
    left_anchor = gap_s0 - aln.reference_start
    right_anchor = (aln.reference_end - 1) - gap_e0
    if left_anchor < anchor or right_anchor < anchor:
        return None

    left_ref = gap_s0 - 1
    right_ref = gap_e0 + 1
    left_lo = gap_s0 - anchor
    right_hi = gap_e0 + anchor
    query = aln.query_sequence
    if query is None:
        return None

    q_left = r_left = q_right = r_right = None
    left_matches = left_columns = right_matches = right_columns = 0
    for qpos, rpos in aln.get_aligned_pairs():
        if rpos is None or qpos is None:
            continue
        if rpos > right_hi:
            break
        if rpos <= left_ref and (r_left is None or rpos > r_left):
            r_left, q_left = rpos, qpos
        if rpos >= right_ref and (r_right is None or rpos < r_right):
            r_right, q_right = rpos, qpos
        if left_lo <= rpos <= left_ref:
            ref_base = ref_seq[rpos].upper()
            if ref_base != "N":
                left_columns += 1
                left_matches += query[qpos].upper() == ref_base
        elif right_ref <= rpos <= right_hi:
            ref_base = ref_seq[rpos].upper()
            if ref_base != "N":
                right_columns += 1
                right_matches += query[qpos].upper() == ref_base

    if (
        r_left != left_ref
        or r_right != right_ref
        or q_left is None
        or q_right is None
        or q_right <= q_left + 1
        or left_columns == 0
        or right_columns == 0
    ):
        return None
    fill = query[q_left + 1 : q_right]
    if not fill:
        return None
    return {
        "qname": aln.query_name,
        "strand": "-" if aln.is_reverse else "+",
        "mapq": aln.mapping_quality,
        "left_cols": left_columns,
        "right_cols": right_columns,
        "left_identity": left_matches / left_columns,
        "right_identity": right_matches / right_columns,
        "identity": (left_matches + right_matches) / (left_columns + right_columns),
        "anchor_total": left_anchor + right_anchor,
        "fill": fill,
    }


def candidate_sort_key(candidate: dict[str, Any], prefer_mapq: int) -> tuple[Any, ...]:
    return (
        0 if candidate["mapq"] >= prefer_mapq else 1,
        -round(candidate["identity"], 6),
        -candidate["anchor_total"],
        -len(candidate["fill"]),
        candidate["qname"],
        candidate["fill"],
    )


def pick(candidates: Iterable[dict[str, Any]], prefer_mapq: int) -> dict[str, Any] | None:
    """Pick deterministically without mutating the caller's collection."""
    ordered = sorted(candidates, key=lambda item: candidate_sort_key(item, prefer_mapq))
    return ordered[0] if ordered else None


def splice_sequence(sequence: str, fills: Iterable[tuple[int, int, str]]) -> str:
    """Replace validated, non-overlapping 0-based inclusive intervals."""
    pieces: list[str] = []
    position = 0
    previous_end = -1
    for start0, end0, fill in sorted(fills, key=lambda item: item[0]):
        if start0 <= previous_end:
            raise GapFillError("internal error: overlapping fills reached FASTA splice")
        pieces.extend((sequence[position:start0], fill))
        position = end0 + 1
        previous_end = end0
    pieces.append(sequence[position:])
    return "".join(pieces)


def render_fasta(fasta: Any, applied: dict[str, list[tuple[int, int, str]]]) -> str:
    chunks: list[str] = []
    for seqid in fasta.references:
        sequence = splice_sequence(fasta.fetch(seqid), applied.get(seqid, []))
        chunks.append(f">{seqid}\n")
        chunks.extend(sequence[offset : offset + 60] + "\n" for offset in range(0, len(sequence), 60))
    return "".join(chunks)


def render_report(results: Iterable[dict[str, Any]]) -> str:
    lines = [REPORT_HEADER]
    for result in results:
        best = result["best"]
        if best is not None:
            row = [
                result["seqid"],
                result["s1"],
                result["e1"],
                result["e1"] - result["s1"] + 1,
                "filled",
                best["qname"],
                best["strand"],
                best["mapq"],
                f"{min(best['left_identity'], best['right_identity']):.4f}",
                len(best["fill"]),
                best["anchor_total"],
                result["n_cands"],
            ]
        else:
            status = "unfilled_low_identity_or_coverage" if result["n_cands"] else "unfilled_no_spanner"
            row = [
                result["seqid"],
                result["s1"],
                result["e1"],
                result["e1"] - result["s1"] + 1,
                status,
                "NA",
                "NA",
                "NA",
                "NA",
                0,
                0,
                result["n_cands"],
            ]
        lines.append("\t".join(map(str, row)) + "\n")
    return "".join(lines)


def _stage_text(target: Path, text: str) -> Path:
    descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    temp_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        return temp_path
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_write_pair(out: Path, fasta_text: str, report: Path, report_text: str) -> None:
    """Stage and transactionally replace two outputs, restoring old files on failure."""
    staged: dict[Path, Path] = {}
    backups: dict[Path, Path] = {}
    committed: list[Path] = []
    targets = [(out, fasta_text), (report, report_text)]
    try:
        for target, text in targets:
            staged[target] = _stage_text(target, text)
        for target, _ in targets:
            if target.exists():
                descriptor, backup_name = tempfile.mkstemp(
                    prefix=f".{target.name}.", suffix=".backup", dir=target.parent
                )
                os.close(descriptor)
                backup = Path(backup_name)
                backup.unlink()
                os.replace(target, backup)
                backups[target] = backup
        try:
            for target, _ in targets:
                os.replace(staged[target], target)
                committed.append(target)
            for parent in {target.parent for target, _ in targets}:
                _fsync_directory(parent)
        except Exception:
            for target in committed:
                target.unlink(missing_ok=True)
            for target, backup in backups.items():
                if backup.exists():
                    os.replace(backup, target)
            raise
        for backup in backups.values():
            backup.unlink(missing_ok=True)
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)
        for target, backup in backups.items():
            if backup.exists() and not target.exists():
                os.replace(backup, target)
            else:
                backup.unlink(missing_ok=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fill complete internal N-runs from a single spanning donor alignment."
    )
    parser.add_argument("--bam", required=True, help="sorted and indexed donor-to-reference BAM")
    parser.add_argument("--ref", required=True, help="faidx-indexed gapped reference FASTA")
    gaps = parser.add_mutually_exclusive_group(required=True)
    gaps.add_argument("--gaps", help="9-column GFF3 of gap intervals")
    gaps.add_argument("--gap", help="single gap as SEQID:START-END (1-based inclusive)")
    parser.add_argument("--donor-type", choices=["contig", "read"], default="contig")
    parser.add_argument("--min-anchor", type=int, default=None, help="minimum aligned anchor per flank")
    parser.add_argument("--min-mapq", type=int, default=30)
    parser.add_argument("--prefer-mapq", type=int, default=50)
    parser.add_argument("--min-identity", type=float, default=0.80)
    parser.add_argument("--out", required=True, help="new gap-filled FASTA")
    parser.add_argument("--report", required=True, help="per-gap TSV report")
    parser.add_argument("--force", action="store_true", help="replace existing safe outputs")
    return parser


def run(args: argparse.Namespace) -> tuple[int, int]:
    if not 0.0 <= args.min_identity <= 1.0:
        raise GapFillError("--min-identity must be in [0, 1]")
    anchor = args.min_anchor if args.min_anchor is not None else ANCHOR_DEFAULT[args.donor_type]
    if anchor < 1:
        raise GapFillError("--min-anchor must be at least 1")
    if not 0 <= args.min_mapq <= 255 or not 0 <= args.prefer_mapq <= 255:
        raise GapFillError("MAPQ thresholds must be in [0, 255]")

    ref_path = Path(args.ref).expanduser()
    bam_path = Path(args.bam).expanduser()
    validate_readable_file(ref_path, "reference FASTA")
    validate_readable_file(bam_path, "BAM")
    input_paths = [ref_path, bam_path]
    if args.gaps:
        gaps_path = Path(args.gaps).expanduser()
        validate_readable_file(gaps_path, "gap GFF3")
        input_paths.append(gaps_path)
        raw_gaps = parse_gff3(gaps_path)
    else:
        raw_gaps = [parse_gap_string(args.gap)]
    gaps, duplicate_count = deduplicate_gaps(raw_gaps)

    out_path, report_path = validate_output_paths(
        Path(args.out), Path(args.report), input_paths, force=args.force
    )
    fai_path = Path(f"{ref_path}.fai")
    if not fai_path.exists() or not fai_path.is_file():
        raise GapFillError(f"reference FASTA index is missing: {fai_path}")

    try:
        fasta = pysam.FastaFile(str(ref_path))
    except Exception as exc:
        raise GapFillError(f"cannot open indexed reference FASTA {ref_path}: {exc}") from exc
    try:
        checked = validate_gap_intervals(gaps, fasta)
        try:
            bam = pysam.AlignmentFile(str(bam_path), "rb")
        except Exception as exc:
            raise GapFillError(f"cannot open BAM {bam_path}: {exc}") from exc
        try:
            if not bam.has_index():
                raise GapFillError(f"BAM index is missing or unreadable: {bam_path}")
            results: list[dict[str, Any]] = []
            for gap in checked:
                fetch_start = max(0, gap["gap_s0"] - anchor)
                fetch_end = min(len(gap["ref_seq"]), gap["gap_e0"] + anchor + 1)
                candidates: list[dict[str, Any]] = []
                try:
                    alignments = bam.fetch(gap["seqid"], fetch_start, fetch_end)
                    for alignment in alignments:
                        if alignment.mapping_quality < args.min_mapq:
                            continue
                        candidate = analyze(
                            alignment,
                            gap["gap_s0"],
                            gap["gap_e0"],
                            anchor,
                            gap["ref_seq"],
                        )
                        if candidate is not None:
                            candidates.append(candidate)
                except (ValueError, OSError) as exc:
                    raise GapFillError(
                        f"BAM region is not fetchable: {gap['seqid']}:{fetch_start + 1}-{fetch_end}: {exc}"
                    ) from exc
                acceptable = [
                    candidate
                    for candidate in candidates
                    if candidate["left_cols"] >= max(1, anchor // 2)
                    and candidate["right_cols"] >= max(1, anchor // 2)
                    and candidate["left_identity"] >= args.min_identity
                    and candidate["right_identity"] >= args.min_identity
                ]
                result = dict(gap)
                result.pop("ref_seq")
                result.update(
                    {
                        "best": pick(acceptable, args.prefer_mapq),
                        "n_cands": len(candidates),
                    }
                )
                results.append(result)
        finally:
            bam.close()

        applied: dict[str, list[tuple[int, int, str]]] = {}
        for result in results:
            if result["best"] is not None:
                applied.setdefault(result["seqid"], []).append(
                    (result["gap_s0"], result["gap_e0"], result["best"]["fill"])
                )
        fasta_text = render_fasta(fasta, applied)
        report_text = render_report(results)
        atomic_write_pair(out_path, fasta_text, report_path, report_text)
    finally:
        fasta.close()

    filled = sum(result["best"] is not None for result in results)
    if duplicate_count:
        sys.stderr.write(f"[fill_gap] removed {duplicate_count} exact duplicate gap row(s)\n")
    sys.stderr.write(
        f"[fill_gap] donor_type={args.donor_type} anchor={anchor} min_mapq={args.min_mapq} "
        f"prefer_mapq={args.prefer_mapq} min_identity={args.min_identity} -> "
        f"filled {filled}/{len(results)} gaps\n"
    )
    sys.stderr.write(f"[fill_gap] atomically wrote {out_path} and {report_path}\n")
    return filled, len(results)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        run(args)
    except (GapFillError, OSError, ValueError) as exc:
        sys.stderr.write(f"[ERROR] {exc}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
