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

    # RNA-seq DE: complete design PASS; n=2 WARN; n<2/confounding BLOCK.
    for filename in (
        "Sample_Metadata.tsv",
        "Raw_Counts.tsv",
        "RNA_QC.tsv",
        "Reference.fa",
        "Population_Samples.tsv",
        "Calls.vcf.gz",
        "Calls.vcf.gz.tbi",
        "Phenotypes.tsv",
        "Genotypes.bed",
        "PCA.tsv",
        "Kinship.tsv",
        "QQ.tsv",
    ):
        (tmp / filename).write_text("ID\tValue\nX\t1\n")
    rnaseq = {
        "schema_version": "result_manifest.v2",
        "analysis_types": ["rnaseq_differential_expression"],
        "rnaseq_de": {
            "sample_metadata_path": "Sample_Metadata.tsv",
            "biological_replicates": {"Control": 3, "Treatment": 3},
            "design_formula": "~ Batch + Condition",
            "contrast": ["Condition", "Treatment", "Control"],
            "strandedness": "reverse",
            "batch_condition_confounding": False,
            "count_input": {"path": "Raw_Counts.tsv", "type": "raw_integer_counts"},
            "statistics": {
                "fdr_method": "BH",
                "alpha": 0.05,
                "effect_size": "log2FoldChange",
                "shrinkage": "apeglm",
            },
            "qc_evidence_paths": ["RNA_QC.tsv"],
        },
        "claims": [
            claim(
                "RNA_DE_001",
                "rnaseq_differential_expression",
                "differential_expression",
                ["Treatment", "Control"],
                {},
            )
        ],
    }
    assert_status("PASS", rnaseq, tmp)
    rnaseq_two = copy.deepcopy(rnaseq)
    rnaseq_two["rnaseq_de"]["biological_replicates"]["Treatment"] = 2
    assert_status("WARN", rnaseq_two, tmp, "RNA_DE_002")
    rnaseq_one = copy.deepcopy(rnaseq)
    rnaseq_one["rnaseq_de"]["biological_replicates"]["Treatment"] = 1
    assert_status("BLOCK", rnaseq_one, tmp, "RNA_DE_002")
    rnaseq_confounded = copy.deepcopy(rnaseq)
    rnaseq_confounded["rnaseq_de"]["batch_condition_confounding"] = True
    assert_status("BLOCK", rnaseq_confounded, tmp, "RNA_DE_004")
    rnaseq_tpm = copy.deepcopy(rnaseq)
    rnaseq_tpm["rnaseq_de"]["count_input"]["type"] = "TPM"
    assert_status("BLOCK", rnaseq_tpm, tmp, "RNA_DE_003")
    passed("RNA DE complete PASS; n=2 WARN; n<2/confounding/non-count input BLOCK")

    # Population variant calling requires reference/ploidy, sample match, normalization, VCF+index.
    variants = {
        "schema_version": "result_manifest.v2",
        "analysis_types": ["population_variant_calling"],
        "population_variants": {
            "reference": {"path": "Reference.fa", "version": "V2", "checksum": "sha256:fixture"},
            "ploidy_assumption": "homeolog_resolved_disomic",
            "caller": "GATK",
            "caller_version": "fixture",
            "calling_mode": "joint_genotyping",
            "multiallelic_policy": "split_after_joint_calling",
            "sample_manifest_path": "Population_Samples.tsv",
            "sample_match": True,
            "normalization": {
                "left_aligned": True,
                "split_multiallelic": True,
                "tool": "bcftools norm",
                "version": "fixture",
            },
            "filter_provenance": {"Variant_Missing_Max": 0.1, "MAC_Min": 5},
            "vcf_path": "Calls.vcf.gz",
            "index_path": "Calls.vcf.gz.tbi",
        },
        "claims": [
            claim(
                "VARIANT_001",
                "population_variant_calling",
                "variant_callset",
                ["Population_1"],
                {},
            )
        ],
    }
    assert_status("PASS", variants, tmp)
    variants_missing_index = copy.deepcopy(variants)
    variants_missing_index["population_variants"]["index_path"] = "Missing.tbi"
    assert_status("BLOCK", variants_missing_index, tmp, "VARIANT_004")
    variants_mismatch = copy.deepcopy(variants)
    variants_mismatch["population_variants"]["sample_match"] = False
    assert_status("BLOCK", variants_mismatch, tmp, "VARIANT_002")
    passed("population variant complete PASS; sample/index failures BLOCK")

    # GWAS D route must be homeolog-resolved disomic PLINK2+GEMMA and calibrated.
    gwas = {
        "schema_version": "result_manifest.v2",
        "analysis_types": ["gwas"],
        "gwas": {
            "route": "D",
            "ploidy_model": "disomic_diploid_approximation",
            "homeolog_resolved": True,
            "biallelic": True,
            "qc_engine": "PLINK2",
            "engine": "GEMMA",
            "engine_validated": True,
            "model_compatibility": True,
            "sample_match": True,
            "phenotype_path": "Phenotypes.tsv",
            "genotype_path": "Genotypes.bed",
            "qc_thresholds": {"Sample_Call_Rate_Min": 0.9, "Variant_Missing_Max": 0.1, "MAC_Min": 5},
            "pca_path": "PCA.tsv",
            "kinship_path": "Kinship.tsv",
            "covariates": ["PC1", "PC2", "Trial"],
            "multiple_testing": {"method": "Bonferroni", "threshold": 5e-8},
            "qq_evidence_path": "QQ.tsv",
            "effect_allele_reported": True,
        },
        "claims": [claim("GWAS_001", "gwas", "association", ["Trait_1"], {})],
    }
    assert_status("PASS", gwas, tmp)
    incompatible = copy.deepcopy(gwas)
    incompatible["gwas"]["ploidy_model"] = "allele_dosage_polyploid"
    assert_status("BLOCK", incompatible, tmp, "GWAS_002")
    no_match = copy.deepcopy(gwas)
    no_match["gwas"]["sample_match"] = False
    assert_status("BLOCK", no_match, tmp, "GWAS_001")
    p_unselected = copy.deepcopy(gwas)
    p_unselected["gwas"].update(
        {"route": "P", "engine": "", "dosage_aware": True, "polyploid_model": True}
    )
    assert_status("BLOCK", p_unselected, tmp, "GWAS_002")
    passed("GWAS D fixture PASS; sample/model/P-engine mismatches BLOCK")

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
