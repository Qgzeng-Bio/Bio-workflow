#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pysam

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fill_gap_from_spanning_alignment.py"
SPEC = importlib.util.spec_from_file_location("fill_gap", SCRIPT)
assert SPEC and SPEC.loader
fill_gap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fill_gap)


def passed(label: str) -> None:
    print(f"PASS | {label}")


def expect_error(fragment: str, function, *args, **kwargs) -> None:
    try:
        function(*args, **kwargs)
    except fill_gap.GapFillError as exc:
        assert fragment in str(exc), (fragment, str(exc))
    else:
        raise AssertionError(f"expected GapFillError containing {fragment!r}")


class FakeFasta:
    def __init__(self, sequences: dict[str, str]):
        self.sequences = sequences
        self.references = tuple(sequences)
        self.lengths = tuple(len(sequences[name]) for name in self.references)

    def fetch(self, seqid: str) -> str:
        return self.sequences[seqid]


def make_alignment(
    reference: str,
    query: str,
    cigar: list[tuple[int, int]],
    *,
    name: str = "donor",
    flag: int = 0,
    mapq: int = 60,
    start: int = 0,
) -> pysam.AlignedSegment:
    header = pysam.AlignmentHeader.from_references(["chr1"], [len(reference)])
    alignment = pysam.AlignedSegment(header)
    alignment.query_name = name
    alignment.query_sequence = query
    alignment.flag = flag
    alignment.reference_id = 0
    alignment.reference_start = start
    alignment.mapping_quality = mapq
    alignment.cigartuples = cigar
    alignment.query_qualities = pysam.qualitystring_to_array("I" * len(query))
    return alignment


# Pure gap parsing and interval validation.
assert fill_gap.parse_gap_string("chr1:1,001-1,005") == ("chr1", 1001, 1005)
expect_error("invalid --gap", fill_gap.parse_gap_string, "chr1:5")
unique, duplicates = fill_gap.deduplicate_gaps(
    [("chr1", 21, 25), ("chr1", 21, 25), ("chr2", 21, 25)]
)
assert unique == [("chr1", 21, 25), ("chr2", 21, 25)] and duplicates == 1
passed("gap parser and exact duplicate reporting")

reference = "A" * 20 + "N" * 5 + "C" * 20
fasta = FakeFasta({"chr1": reference})
checked = fill_gap.validate_gap_intervals([("chr1", 21, 25)], fasta)
assert checked[0]["gap_s0"] == 20 and checked[0]["gap_e0"] == 24
for gap, fragment in [
    (("missing", 21, 25), "absent"),
    (("chr1", 0, 5), "outside"),
    (("chr1", 21, 46), "outside"),
    (("chr1", 1, 5), "terminal"),
    (("chr1", 20, 25), "non-N"),
    (("chr1", 22, 25), "part of a maximal"),
]:
    expect_error(fragment, fill_gap.validate_gap_intervals, [gap], fasta)
expect_error(
    "overlap",
    fill_gap.validate_gap_intervals,
    [("chr1", 20, 23), ("chr1", 22, 26)],
    fasta,
)
passed("bounds, N-only, maximal-run, terminal, and overlap gates")

# Alignment candidate behavior, including strand, indels, clipping, flags, and identity.
forward = make_alignment(reference, "A" * 20 + "G" * 5 + "C" * 20, [(0, 45)], name="forward")
candidate = fill_gap.analyze(forward, 20, 24, 10, reference)
assert candidate and candidate["fill"] == "G" * 5 and candidate["strand"] == "+"
reverse = make_alignment(
    reference, "A" * 20 + "T" * 5 + "C" * 20, [(0, 45)], name="reverse", flag=16
)
candidate = fill_gap.analyze(reverse, 20, 24, 10, reference)
assert candidate and candidate["fill"] == "T" * 5 and candidate["strand"] == "-"
insertion = make_alignment(
    reference,
    "A" * 20 + "GG" + "T" * 5 + "C" * 20,
    [(0, 20), (1, 2), (0, 25)],
    name="insertion",
)
candidate = fill_gap.analyze(insertion, 20, 24, 10, reference)
assert candidate and candidate["fill"] == "GG" + "T" * 5
deletion = make_alignment(reference, "A" * 20 + "C" * 20, [(0, 20), (2, 5), (0, 20)])
assert fill_gap.analyze(deletion, 20, 24, 10, reference) is None
clipped_at_gap = make_alignment(reference, "A" * 20 + "G" * 25, [(0, 20), (4, 25)])
assert fill_gap.analyze(clipped_at_gap, 20, 24, 10, reference) is None
secondary = make_alignment(reference, "A" * 20 + "G" * 5 + "C" * 20, [(0, 45)], flag=256)
supplementary = make_alignment(reference, "A" * 20 + "G" * 5 + "C" * 20, [(0, 45)], flag=2048)
assert fill_gap.analyze(secondary, 20, 24, 10, reference) is None
assert fill_gap.analyze(supplementary, 20, 24, 10, reference) is None
low_right_identity = make_alignment(reference, "A" * 20 + "G" * 5 + "T" * 20, [(0, 45)])
candidate = fill_gap.analyze(low_right_identity, 20, 24, 10, reference)
assert candidate and candidate["left_identity"] == 1.0 and candidate["right_identity"] == 0.0
passed("forward/reverse, insertion/deletion/clip, flags, and per-side identity")

# Deterministic ranking: preferred MAPQ tier, then identity/anchor/fill/name/fill.
base = {
    "mapq": 60,
    "identity": 1.0,
    "anchor_total": 20,
    "fill": "GGGGG",
    "qname": "z",
}
ranked = [dict(base), dict(base, qname="a"), dict(base, qname="low", mapq=49, identity=1.0)]
assert fill_gap.pick(reversed(ranked), 50)["qname"] == "a"
assert fill_gap.pick(ranked, 50)["qname"] == "a"
passed("deterministic candidate tie-break")

# Output path safety and force semantics.
with tempfile.TemporaryDirectory(prefix="bioflow-gap-paths.") as tmp_name:
    tmp = Path(tmp_name)
    ref = tmp / "ref.fa"
    bam = tmp / "reads.bam"
    gaps = tmp / "gaps.gff3"
    for path in (ref, bam, gaps):
        path.write_text("input\n")
    out, report = tmp / "out.fa", tmp / "report.tsv"
    assert fill_gap.validate_output_paths(out, report, [ref, bam, gaps]) == (
        out.resolve(),
        report.resolve(),
    )
    out.write_text("old fasta\n")
    report.write_text("old report\n")
    expect_error("already exists", fill_gap.validate_output_paths, out, report, [ref, bam, gaps])
    fill_gap.validate_output_paths(out, report, [ref, bam, gaps], force=True)
    expect_error("input file", fill_gap.validate_output_paths, ref, report, [ref, bam, gaps], True)
    expect_error("different paths", fill_gap.validate_output_paths, report, report, [ref, bam, gaps], True)
    link = tmp / "linked.fa"
    link.symlink_to(out)
    expect_error("symbolic link", fill_gap.validate_output_paths, link, tmp / "new.tsv", [ref], True)
    expect_error(
        "protected output",
        fill_gap.validate_output_paths,
        Path("/data9/home/qgzeng/data/gap-test.fa"),
        tmp / "new.tsv",
        [ref],
        True,
    )
    expect_error(
        "parent must already exist",
        fill_gap.validate_output_paths,
        tmp / "missing" / "out.fa",
        tmp / "new.tsv",
        [ref],
    )
passed("existing, force, symlink, input-equality, conflict, and protected-path gates")

# Staging failure leaves no final output and preserves pre-existing outputs.
with tempfile.TemporaryDirectory(prefix="bioflow-gap-atomic.") as tmp_name:
    tmp = Path(tmp_name)
    out, report = tmp / "out.fa", tmp / "report.tsv"
    original_stage = fill_gap._stage_text
    calls = 0

    def fail_second(target: Path, text: str) -> Path:
        global calls
        calls += 1
        if calls == 2:
            raise OSError("simulated write failure")
        return original_stage(target, text)

    with mock.patch.object(fill_gap, "_stage_text", side_effect=fail_second):
        try:
            fill_gap.atomic_write_pair(out, ">x\nA\n", report, "Header\n")
        except OSError:
            pass
        else:
            raise AssertionError("simulated output failure did not propagate")
    assert not out.exists() and not report.exists()
    out.write_text("old fasta\n")
    report.write_text("old report\n")
    calls = 0
    with mock.patch.object(fill_gap, "_stage_text", side_effect=fail_second):
        try:
            fill_gap.atomic_write_pair(out, "new fasta\n", report, "new report\n")
        except OSError:
            pass
    assert out.read_text() == "old fasta\n" and report.read_text() == "old report\n"
    assert not list(tmp.glob(".*.tmp")) and not list(tmp.glob(".*.backup"))
passed("staging failure produces no partial result and preserves old outputs")


def add_record(
    bam: pysam.AlignmentFile,
    ref_id: int,
    name: str,
    query: str,
    *,
    flag: int = 0,
    mapq: int = 60,
    cigar: list[tuple[int, int]] | None = None,
) -> None:
    record = pysam.AlignedSegment(bam.header)
    record.query_name = name
    record.query_sequence = query
    record.flag = flag
    record.reference_id = ref_id
    record.reference_start = 0
    record.mapping_quality = mapq
    record.cigartuples = cigar or [(0, len(query))]
    record.query_qualities = pysam.qualitystring_to_array("I" * len(query))
    bam.write(record)


# Real indexed FASTA/BAM CLI fixture; this is not a mock.
with tempfile.TemporaryDirectory(prefix="bioflow-gap-cli.") as tmp_name:
    tmp = Path(tmp_name)
    ref_path = tmp / "ref.fa"
    chr1 = "A" * 20 + "N" * 5 + "C" * 20
    chr2 = "T" * 20 + "N" * 5 + "G" * 20
    ref_path.write_text(f">chr1\n{chr1}\n>chr2\n{chr2}\n")
    pysam.faidx(str(ref_path))
    bam_path = tmp / "donors.bam"
    header = {"HD": {"VN": "1.6", "SO": "coordinate"}, "SQ": [{"SN": "chr1", "LN": 45}, {"SN": "chr2", "LN": 45}]}
    with pysam.AlignmentFile(str(bam_path), "wb", header=header) as bam:
        add_record(bam, 0, "low_mapq", "A" * 20 + "A" * 5 + "C" * 20, mapq=10)
        add_record(bam, 0, "secondary", "A" * 20 + "A" * 5 + "C" * 20, flag=256)
        add_record(bam, 0, "supplementary", "A" * 20 + "A" * 5 + "C" * 20, flag=2048)
        add_record(bam, 0, "z_forward", "A" * 20 + "G" * 5 + "C" * 20)
        add_record(bam, 1, "a_reverse", "T" * 20 + "C" * 5 + "G" * 20, flag=16)
    pysam.index(str(bam_path))
    gaps_path = tmp / "gaps.gff3"
    gaps_path.write_text(
        "##gff-version 3\n"
        "chr1\tget_gaps\tgap\t21\t25\t.\t.\t.\tID=gap1\n"
        "chr1\tget_gaps\tgap\t21\t25\t.\t.\t.\tID=gap1_duplicate\n"
        "chr2\tget_gaps\tgap\t21\t25\t.\t.\t.\tID=gap2\n"
    )
    out_path, report_path = tmp / "filled.fa", tmp / "fill.tsv"
    command = [
        sys.executable,
        str(SCRIPT),
        "--bam",
        str(bam_path),
        "--ref",
        str(ref_path),
        "--gaps",
        str(gaps_path),
        "--donor-type",
        "read",
        "--min-anchor",
        "10",
        "--out",
        str(out_path),
        "--report",
        str(report_path),
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert "removed 1 exact duplicate" in completed.stderr
    with pysam.FastaFile(str(out_path)) as filled:
        assert filled.fetch("chr1") == "A" * 20 + "G" * 5 + "C" * 20
        assert filled.fetch("chr2") == "T" * 20 + "C" * 5 + "G" * 20
    rows = report_path.read_text().splitlines()
    assert rows[0].split("\t") == fill_gap.REPORT_HEADER.rstrip().split("\t")
    assert len(rows) == 3
    assert rows[1].split("\t")[4:7] == ["filled", "z_forward", "+"]
    assert rows[2].split("\t")[4:7] == ["filled", "a_reverse", "-"]
    original_fasta = out_path.read_bytes()
    original_report = report_path.read_bytes()
    refused = subprocess.run(command, check=False, capture_output=True, text=True)
    assert refused.returncode == 2 and "already exists" in refused.stderr
    assert out_path.read_bytes() == original_fasta and report_path.read_bytes() == original_report
    forced = subprocess.run(command + ["--force"], check=False, capture_output=True, text=True)
    assert forced.returncode == 0, forced.stderr

    no_index_bam = tmp / "no_index.bam"
    no_index_bam.write_bytes(bam_path.read_bytes())
    missing_out, missing_report = tmp / "missing.fa", tmp / "missing.tsv"
    missing_index_command = [
        value if value != str(bam_path) else str(no_index_bam) for value in command
    ]
    missing_index_command = [
        value if value != str(out_path) else str(missing_out) for value in missing_index_command
    ]
    missing_index_command = [
        value if value != str(report_path) else str(missing_report) for value in missing_index_command
    ]
    no_index = subprocess.run(missing_index_command, check=False, capture_output=True, text=True)
    assert no_index.returncode == 2 and "BAM index" in no_index.stderr
    assert not missing_out.exists() and not missing_report.exists()
passed("real pysam CLI fixture, exact splice/report, overwrite refusal/force, and index gate")

print("PASS | gap-fill safety regression fixtures")
