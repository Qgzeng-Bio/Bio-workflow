#!/usr/bin/env python3
"""Build a minimal BlobToolKit BlobDir for a snail plot.

This helper was adapted from the completed C. quinoa evaluation run. It expects
seqkit `fx2tab -n -i -l -g -C N -H` output plus a BUSCO full_table.tsv, then
writes the minimal BlobDir fields needed by `blobtk plot --view snail`.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


STATUS_KEYS = ["Complete", "Fragmented", "Duplicated"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a minimal BlobDir from seqkit FASTA stats and BUSCO full_table.tsv."
    )
    parser.add_argument("--seqkit-tsv", required=True, type=Path)
    parser.add_argument("--busco-tsv", required=True, type=Path)
    parser.add_argument("--blobdir", required=True, type=Path)
    parser.add_argument("--sequence-stats", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--assembly-id", default="Cqu_final")
    parser.add_argument("--assembly-file", default="Cqu_final.fa")
    parser.add_argument("--assembly-level", default="chromosome")
    parser.add_argument("--taxon-name", default="Chenopodium quinoa")
    parser.add_argument("--taxid", default="63459")
    return parser.parse_args()


def parse_seqkit_stats(path: Path) -> tuple[list[str], list[int], list[float], list[int]]:
    ids: list[str] = []
    lengths: list[int] = []
    gc_values: list[float] = []
    n_counts: list[int] = []
    with path.open() as handle:
        header = handle.readline().rstrip("\n").split("\t")
        expected = ["#id", "length", "GC", "N"]
        if header[:4] != expected:
            raise ValueError(f"Unexpected seqkit header: {header!r}")
        for line in handle:
            if not line.strip():
                continue
            seq_id, length, gc_percent, n_count = line.rstrip("\n").split("\t")[:4]
            ids.append(seq_id)
            lengths.append(int(length))
            gc_values.append(round(float(gc_percent) / 100.0, 4))
            n_counts.append(int(n_count))
    if not ids:
        raise ValueError(f"No FASTA records parsed from {path}")
    return ids, lengths, gc_values, n_counts


def parse_busco(
    path: Path, ids: list[str]
) -> tuple[str, int, str, list[list[list[str | int]]]]:
    id_set = set(ids)
    status_index = {name: idx for idx, name in enumerate(STATUS_KEYS)}
    busco_by_seq: defaultdict[str, list[list[str | int]]] = defaultdict(list)
    busco_version = "unknown"
    lineage = "unknown_odb"
    busco_count = 0
    columns: list[str] | None = None

    with path.open() as handle:
        for raw in handle:
            line = raw.rstrip("\n")
            if not line:
                continue
            if line.startswith("# BUSCO version is:"):
                busco_version = line.split(":", 1)[1].strip()
                continue
            if line.startswith("# The lineage dataset is:"):
                match = re.search(r"is:\s*(\S+).*number of BUSCOs:\s*(\d+)", line)
                if match:
                    lineage = match.group(1)
                    busco_count = int(match.group(2))
                continue
            if line.startswith("# Busco id"):
                columns = [col.strip() for col in line.lstrip("# ").split("\t")]
                continue
            if line.startswith("#") or columns is None:
                continue

            row = line.split("\t")
            if len(row) < len(columns):
                continue
            record = dict(zip(columns, row))
            seq_id = re.sub(r":\d+-\d+$", "", record.get("Sequence", ""))
            status = record.get("Status", "")
            busco_id = record.get("Busco id", "")
            if not seq_id or seq_id not in id_set or status not in status_index:
                continue
            busco_by_seq[seq_id].append([busco_id, status_index[status]])

    values = [busco_by_seq.get(seq_id, []) for seq_id in ids]
    assigned = sum(len(value) for value in values)
    if assigned == 0:
        raise ValueError(f"No BUSCO rows matched FASTA identifiers in {path}")
    return lineage, busco_count, busco_version, values


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n")


def write_sequence_stats(
    path: Path, ids: list[str], lengths: list[int], gc_values: list[float], n_counts: list[int]
) -> None:
    with path.open("w") as handle:
        handle.write("Sequence_ID\tLength\tGC_Fraction\tN_Count\n")
        for row in zip(ids, lengths, gc_values, n_counts):
            handle.write("\t".join(str(value) for value in row) + "\n")


def write_summary(path: Path, summary: dict[str, object]) -> None:
    with path.open("w") as handle:
        handle.write("Metric\tValue\n")
        for key, value in summary.items():
            handle.write(f"{key}\t{value}\n")


def main() -> None:
    args = parse_args()
    ids, lengths, gc_values, n_counts = parse_seqkit_stats(args.seqkit_tsv)
    lineage, busco_count, busco_version, busco_values = parse_busco(args.busco_tsv, ids)
    busco_field = f"{lineage}_busco"

    args.blobdir.mkdir(parents=True, exist_ok=False)
    args.sequence_stats.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)

    meta = {
        "id": args.assembly_id,
        "assembly": {
            "file": args.assembly_file,
            "level": args.assembly_level,
            "prefix": args.assembly_id,
            "scaffold-count": len(ids),
            "span": sum(lengths),
        },
        "fields": [
            {"id": "identifiers", "type": "identifier"},
            {
                "id": "gc",
                "preload": True,
                "scale": "scaleLinear",
                "name": "GC",
                "datatype": "float",
                "range": [min(gc_values), max(gc_values)],
                "type": "variable",
            },
            {
                "id": "length",
                "preload": True,
                "scale": "scaleLog",
                "name": "Length",
                "clamp": False,
                "datatype": "integer",
                "range": [min(lengths), max(lengths)],
                "type": "variable",
            },
            {
                "id": "ncount",
                "scale": "scaleLinear",
                "name": "N count",
                "datatype": "integer",
                "range": [min(n_counts), max(n_counts)],
                "type": "variable",
            },
            {
                "datatype": "mixed",
                "type": "array",
                "id": "busco",
                "name": "Busco",
                "children": [
                    {
                        "version": busco_version,
                        "set": lineage,
                        "count": busco_count,
                        "file": str(args.busco_tsv),
                        "id": busco_field,
                        "type": "multiarray",
                        "category_slot": 1,
                        "headers": ["Busco id", "Status"],
                        "parent": "busco",
                    }
                ],
            },
        ],
        "links": {},
        "name": args.assembly_id,
        "plot": {"x": "gc", "z": "length"},
        "record_type": args.assembly_level,
        "records": len(ids),
        "taxon": {
            "name": args.taxon_name,
            "taxid": int(args.taxid),
            "species": args.taxon_name,
            "genus": args.taxon_name.split()[0],
        },
        "version": 1,
        "revision": 0,
    }

    write_json(args.blobdir / "identifiers.json", {"values": ids, "keys": []})
    write_json(args.blobdir / "length.json", {"values": lengths, "keys": []})
    write_json(args.blobdir / "gc.json", {"values": gc_values, "keys": []})
    write_json(args.blobdir / "ncount.json", {"values": n_counts, "keys": []})
    write_json(
        args.blobdir / f"{busco_field}.json",
        {
            "values": busco_values,
            "keys": STATUS_KEYS,
            "category_slot": 1,
            "headers": ["Busco id", "Status"],
        },
    )
    (args.blobdir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n")

    summary = {
        "Records": len(ids),
        "Span_bp": sum(lengths),
        "GC_Min": min(gc_values),
        "GC_Max": max(gc_values),
        "N_Count_Total": sum(n_counts),
        "BUSCO_Lineage": lineage,
        "BUSCO_Total": busco_count,
        "BUSCO_Rows_Assigned": sum(len(value) for value in busco_values),
        "BUSCO_Records_With_Hits": sum(1 for value in busco_values if value),
        "Taxon_Name": args.taxon_name,
        "Taxid": args.taxid,
    }
    write_sequence_stats(args.sequence_stats, ids, lengths, gc_values, n_counts)
    write_summary(args.summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
