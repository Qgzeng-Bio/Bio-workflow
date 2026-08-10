#!/usr/bin/env python3
from __future__ import annotations

import copy
import csv
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "check_result_contract.py"
SPEC = importlib.util.spec_from_file_location("check_result_contract", CHECKER)
assert SPEC and SPEC.loader
contract = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(contract)
with (ROOT / "references" / "interpretation-rules.tsv").open() as handle:
    RULES = list(csv.DictReader(handle, delimiter="\t"))


def passed(label: str) -> None:
    print(f"PASS | {label}")


def status_for(manifest: dict, manifest_dir: Path) -> tuple[str, list[tuple[str, str, str]]]:
    return contract.run(manifest, RULES, {}, manifest_dir)


def assert_status(expected: str, manifest: dict, manifest_dir: Path, rule_id: str | None = None) -> None:
    status, findings = status_for(manifest, manifest_dir)
    assert status == expected, (expected, status, findings)
    if rule_id:
        assert any(rule == rule_id for _, rule, _ in findings), (rule_id, findings)


def assembly(subject: str, *, both_n50: bool = False) -> dict:
    value = {
        "key": subject,
        "role": "primary",
        "fasta": f"{subject}.fa",
        "total_length": 1000,
        "contig_N50": 500,
    }
    if both_n50:
        value["scaffold_N50"] = 900
        value["misjoin_validated"] = True
    return value


def busco(subject: str, lineage: str = "embryophyta_odb12") -> dict:
    return {
        "assembly_key": subject,
        "lineage": lineage,
        "mode": "genome",
        "db_version": "2025-07-01",
        "busco_version": "6.0.0",
        "n_busco": 2026,
        "C": 99.7,
        "S": 3.3,
        "D": 96.4,
        "F": 0.0,
        "M": 0.3,
    }


def qv(subject: str, *, k: int = 21, read_db_type: str = "illumina_pcrfree", independence: bool = True) -> dict:
    return {
        "assembly_key": subject,
        "k": k,
        "read_db_type": read_db_type,
        "coverage": 30.0,
        "independence": independence,
        "QV": 60.0,
    }


def lai(subject: str) -> dict:
    return {
        "assembly_key": subject,
        "LAI": 16.0,
        "total_LTR_RT_pct": 50.0,
        "intact_LTR_RT_pct": 2.0,
    }


def claim(
    claim_id: str,
    claim_type: str,
    metric: str,
    subjects: list[str],
    protocol: dict,
    evidence: str = "evidence.tsv",
    status: str = "supported",
    caveats: list[str] | None = None,
) -> dict:
    return {
        "claim_id": claim_id,
        "claim_type": claim_type,
        "metric": metric,
        "subjects": subjects,
        "protocol": protocol,
        "evidence_paths": [evidence],
        "status": status,
        "caveats": [] if caveats is None else caveats,
    }


def base_manifest(subjects: tuple[str, ...] = ("asm1", "asm2")) -> dict:
    return {
        "schema_version": "result_manifest.v2",
        "analysis_types": ["assembly_evaluation"],
        "assemblies": [assembly(subject) for subject in subjects],
    }


with tempfile.TemporaryDirectory(prefix="bioflow-contract-test.") as tmp_name:
    tmp = Path(tmp_name)
    (tmp / "evidence.tsv").write_text("Metric\tValue\nN50\t500\n")

    # Full six-axis overview for every subject.
    overview = base_manifest()
    overview.update(
        {
            "busco": [busco("asm1"), busco("asm2")],
            "merqury": [qv("asm1"), qv("asm2")],
            "lai": [lai("asm1"), lai("asm2")],
            "mapping": [
                {"assembly_key": "asm1", "read_type": "hifi", "rate_pct": 99.0},
                {"assembly_key": "asm2", "read_type": "hifi", "rate_pct": 98.5},
            ],
            "telomere": [
                {"assembly_key": "asm1", "repeats": 36, "expected": 36},
                {"assembly_key": "asm2", "repeats": 36, "expected": 36},
            ],
            "claims": [
                claim(
                    "ASM_OVERVIEW_001",
                    "assembly_quality_overview",
                    "assembly_quality",
                    ["asm1", "asm2"],
                    {
                        "n50_type": "contig_N50",
                        "lineage": "embryophyta_odb12",
                        "mode": "genome",
                        "k": 21,
                        "read_db_type": "illumina_pcrfree",
                        "mapping_read_type": "hifi",
                    },
                )
            ],
        }
    )
    assert_status("PASS", overview, tmp)
    passed("complete assembly_quality_overview PASS")

    # A populated analysis block without explicit v2 claims cannot PASS.
    no_claim = base_manifest(("asm1",))
    no_claim["claims"] = []
    assert_status("WARN", no_claim, tmp, "CLAIM_SCHEMA_001")
    passed("assembly block without claim is WARN")

    # Multiple BUSCO lineages are legal; only claim-selected comparisons are gated.
    multi_lineage = base_manifest(("asm1",))
    multi_lineage["busco"] = [busco("asm1"), busco("asm1", "eudicots_odb10")]
    multi_lineage["claims"] = [
        claim(
            "BUSCO_OBS_001",
            "metric_observation",
            "BUSCO",
            ["asm1"],
            {"lineage": "embryophyta_odb12", "mode": "genome"},
        )
    ]
    assert_status("PASS", multi_lineage, tmp)
    crossed = base_manifest()
    crossed["busco"] = [busco("asm1"), busco("asm2", "eudicots_odb10")]
    crossed["claims"] = [
        claim(
            "BUSCO_COMPARE_001",
            "metric_comparison",
            "BUSCO",
            ["asm1", "asm2"],
            {"lineage": "embryophyta_odb12", "mode": "genome"},
        )
    ]
    assert_status("BLOCK", crossed, tmp, "ASM_BUSCO_002")
    passed("BUSCO multi-lineage storage legal; cross-lineage comparison blocked")

    # QV comparison must match both k and read_db_type.
    qv_compare = base_manifest()
    qv_compare["merqury"] = [qv("asm1"), qv("asm2")]
    qv_compare["claims"] = [
        claim(
            "QV_COMPARE_001",
            "metric_comparison",
            "QV",
            ["asm1", "asm2"],
            {"k": 21, "read_db_type": "illumina_pcrfree"},
        )
    ]
    assert_status("PASS", qv_compare, tmp)
    changed_k = copy.deepcopy(qv_compare)
    changed_k["merqury"][1]["k"] = 31
    assert_status("BLOCK", changed_k, tmp, "ASM_QV_002")
    changed_type = copy.deepcopy(qv_compare)
    changed_type["merqury"][1]["read_db_type"] = "hifi"
    assert_status("BLOCK", changed_type, tmp, "ASM_QV_002")
    passed("QV same protocol PASS; k/read_db_type mismatches BLOCK")

    # One assembly may store both N50 types; a claim selects exactly one shared type.
    n50_compare = base_manifest()
    n50_compare["assemblies"][0] = assembly("asm1", both_n50=True)
    n50_compare["claims"] = [
        claim(
            "N50_COMPARE_001",
            "metric_comparison",
            "N50",
            ["asm1", "asm2"],
            {"n50_type": "contig_N50"},
        )
    ]
    assert_status("PASS", n50_compare, tmp)
    cross_n50 = copy.deepcopy(n50_compare)
    del cross_n50["assemblies"][1]["contig_N50"]
    cross_n50["assemblies"][1]["scaffold_N50"] = 900
    cross_n50["assemblies"][1]["misjoin_validated"] = True
    assert_status("BLOCK", cross_n50, tmp, "ASM_N50_001")
    passed("dual N50 storage legal; cross-type comparison BLOCK")

    # High-confidence SV requires orthogonal read and assembly axes.
    sv_manifest = {
        "schema_version": "result_manifest.v2",
        "analysis_types": ["sv_confidence"],
        "sv": {
            "callers": [
                {"name": "SyRI", "evidence_axis": "assembly"},
                {"name": "SVIM-asm", "evidence_axis": "assembly"},
            ]
        },
        "claims": [claim("SV_001", "sv_high_confidence", "SV", ["asm1-vs-asm2"], {})],
    }
    assert_status("BLOCK", sv_manifest, tmp, "SV_001")
    sv_manifest["sv"]["callers"][1] = {"name": "Sniffles2", "evidence_axis": "read"}
    assert_status("PASS", sv_manifest, tmp)
    passed("SV assembly+assembly BLOCK; read+assembly PASS")

    missing_evidence = copy.deepcopy(n50_compare)
    missing_evidence["claims"][0]["evidence_paths"] = ["missing.tsv"]
    assert_status("BLOCK", missing_evidence, tmp, "CLAIM_EVIDENCE_001")
    passed("supported claim missing relative evidence path BLOCK")

    # Legacy manifests remain readable but cannot produce false PASS.
    legacy = {"schema_version": "result_manifest.v1", "analysis_types": ["assembly_evaluation"], "assemblies": [assembly("asm1")]}
    assert_status("WARN", legacy, tmp, "CLAIM_SCHEMA_001")
    no_version = {"analysis_types": ["assembly_evaluation"], "assemblies": [assembly("asm1")]}
    assert_status("WARN", no_version, tmp, "CLAIM_SCHEMA_001")
    assert_status("UNCERTAIN", {"schema_version": "result_manifest.v1"}, tmp, "COVERAGE")
    passed("v1/unversioned manifests readable without false PASS")

    # Claim status and gate consistency.
    non_independent = copy.deepcopy(qv_compare)
    non_independent["merqury"][0]["independence"] = False
    non_independent["claims"][0]["caveats"] = ["QV is non-independent because assembly reads were reused."]
    assert_status("WARN", non_independent, tmp, "CLAIM_STATUS_001")
    uncertain = copy.deepcopy(n50_compare)
    uncertain["claims"][0]["status"] = "uncertain"
    assert_status("UNCERTAIN", uncertain, tmp, "CLAIM_STATUS_001")
    blocked = copy.deepcopy(n50_compare)
    blocked["claims"][0]["status"] = "blocked"
    assert_status("BLOCK", blocked, tmp, "CLAIM_STATUS_001")
    passed("supported/WARN, uncertain, and blocked status consistency")

    # Single-axis observations remain independently claimable.
    single = base_manifest(("asm1",))
    single["claims"] = [
        claim("N50_OBS_001", "metric_observation", "N50", ["asm1"], {"n50_type": "contig_N50"})
    ]
    assert_status("PASS", single, tmp)
    passed("single metric observation does not require six-axis overview")

    # CLI sections and stable exit codes, including generic RNA uncertainty.
    cli_cases = [
        ("pass.yaml", single, 0, "STATUS\tPASS", None),
        ("warn.yaml", no_claim, 1, "STATUS\tWARN", "WARNINGS:"),
        ("block.yaml", missing_evidence, 2, "STATUS\tBLOCK", "BLOCKED:"),
        (
            "uncertain.yaml",
            {"schema_version": "result_manifest.v2", "analysis_types": ["rnaseq"], "rnaseq": {"samples": 6}, "claims": []},
            3,
            "STATUS\tUNCERTAIN",
            "UNCERTAINTY:",
        ),
    ]
    for filename, manifest, returncode, prefix, section in cli_cases:
        path = tmp / filename
        path.write_text(yaml.safe_dump(manifest, sort_keys=False))
        completed = subprocess.run(
            [sys.executable, str(CHECKER), "--manifest", str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == returncode, (filename, completed.stdout, completed.stderr)
        assert completed.stdout.startswith(prefix + "\n"), completed.stdout
        if section:
            assert section in completed.stdout, completed.stdout
    passed("CLI PASS/WARN/BLOCK/UNCERTAIN sections and exit codes")

print("PASS | claim-specific result contract regression fixtures")
