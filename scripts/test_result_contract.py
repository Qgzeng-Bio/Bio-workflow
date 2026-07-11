#!/usr/bin/env python3
from __future__ import annotations

import csv
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "check_result_contract", ROOT / "scripts" / "check_result_contract.py"
)
assert SPEC and SPEC.loader
contract = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(contract)


with (ROOT / "references" / "interpretation-rules.tsv").open() as handle:
    RULES = list(csv.DictReader(handle, delimiter="\t"))


def assembly_manifest(**extra: object) -> dict:
    manifest = {
        "analysis_types": ["assembly_evaluation"],
        "assemblies": [
            {
                "key": "asm1",
                "role": "primary",
                "fasta": "asm1.fa",
                "total_length": 1000,
                "contig_N50": 500,
            }
        ],
    }
    manifest.update(extra)
    return manifest


def assert_status(expected: str, manifest: dict) -> None:
    status, findings = contract.run(manifest, RULES, {})
    assert status == expected, (expected, status, findings)
    print(f"PASS | {expected}")


assert_status("PASS", assembly_manifest())
assert_status("UNCERTAIN", {"analysis_types": ["rnaseq"], "rnaseq": {"samples": 6}})
assert_status(
    "UNCERTAIN",
    assembly_manifest(analysis_types=["assembly_evaluation", "rnaseq"]),
)

legacy = assembly_manifest()
legacy.pop("analysis_types")
assert_status("PASS", legacy)
assert_status("UNCERTAIN", {"schema_version": "result_manifest.v1"})

blocked = assembly_manifest(
    analysis_types=["assembly_evaluation", "rnaseq"],
    busco=[
        {"assembly_key": "asm1", "lineage": "a", "mode": "genome", "db_version": "1", "C": 99, "D": 1, "F": 0, "M": 0},
        {"assembly_key": "asm1", "lineage": "b", "mode": "genome", "db_version": "1", "C": 99, "D": 1, "F": 0, "M": 0},
    ],
)
assert_status("BLOCK", blocked)

with tempfile.TemporaryDirectory(prefix="bioflow-contract-test.") as tmp:
    manifest_path = Path(tmp) / "unknown.yaml"
    manifest_path.write_text(yaml.safe_dump({"analysis_types": ["rnaseq"], "rnaseq": {"samples": 6}}))
    completed = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parent / "check_result_contract.py"),
            "--manifest",
            str(manifest_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 3, completed
    assert completed.stdout.startswith("STATUS\tUNCERTAIN\n"), completed.stdout
    assert "UNCERTAINTY:" in completed.stdout, completed.stdout
    print("PASS | UNCERTAIN CLI status and exit code")

print("PASS | result contract coverage regression fixtures")
