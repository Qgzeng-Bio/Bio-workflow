#!/usr/bin/env python3
"""Gate result claims against Bioflow's claim-specific manifest contract.

Exit codes are stable: PASS=0, WARN=1, BLOCK=2, UNCERTAIN=3.  A PASS is
possible only for ``result_manifest.v2`` with explicit, supported claims whose
subjects, protocols, provenance, and readable evidence paths all match.
Legacy manifests remain readable but cannot receive a claim-grade PASS.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.stderr.write("PyYAML is required; use an existing Python environment with yaml support.\n")
    raise SystemExit(2)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RULES = REPO_ROOT / "references" / "interpretation-rules.tsv"
DEFAULT_ANCHORS = REPO_ROOT / "references" / "project-anchors.yaml"
SCHEMA_V2 = "result_manifest.v2"
SUPPORTED_ANALYSIS_TYPES = {
    "assembly_evaluation": ("assemblies", "busco", "merqury", "lai", "quast", "mapping", "telomere"),
    "kmeria_association": ("kmeria",),
    "sv_confidence": ("sv",),
    "rnaseq_differential_expression": ("rnaseq_de",),
    "population_variant_calling": ("population_variants",),
    "gwas": ("gwas",),
}
ASSEMBLY_METRICS = {"N50", "BUSCO", "QV", "LAI", "MAPPING", "TELOMERE"}
CLAIM_TYPES = {
    "metric_observation",
    "metric_comparison",
    "assembly_quality_overview",
    "sv_high_confidence",
    "rnaseq_differential_expression",
    "population_variant_calling",
    "gwas",
}
CLAIM_STATUSES = {"supported", "uncertain", "blocked"}

Finding = tuple[str, str, str]


def layout_v2_project_root(manifest_dir: Path) -> Path | None:
    """Return a v2 project root only for the canonical config/ manifest location."""
    if manifest_dir.name != "config":
        return None
    project = manifest_dir.parent.resolve(strict=False)
    marker = project / "config" / "Project_Layout.tsv"
    if not marker.is_file() or marker.is_symlink():
        return None
    try:
        first_two = marker.read_text(encoding="utf-8").splitlines()[:2]
    except (OSError, UnicodeError):
        return None
    if len(first_two) != 2 or not first_two[1].startswith("bioflow.layout.v2\t"):
        return None
    return project


def path_is_in_tmp(path: Path, project: Path | None) -> bool:
    if project is None:
        return False
    try:
        path.relative_to(project / "tmp")
    except ValueError:
        return False
    return True


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = yaml.safe_load(handle) or {}
    if not isinstance(value, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return value


def load_rules(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def list_of(mapping: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = mapping.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def field_present(mapping: dict[str, Any], field: str) -> bool:
    return field in mapping and mapping[field] is not None and mapping[field] != ""


def normalized_metric(value: Any) -> str:
    metric = str(value or "").strip().upper().replace("MERQURY_", "")
    aliases = {"CONTIG_N50": "N50", "SCAFFOLD_N50": "N50", "SV_HIGH_CONFIDENCE": "SV"}
    return aliases.get(metric, metric)


def declared_analysis_types(manifest: dict[str, Any]) -> list[str]:
    declared = manifest.get("analysis_types")
    if isinstance(declared, str):
        return [declared.strip()] if declared.strip() else []
    if isinstance(declared, list):
        return sorted({str(item).strip() for item in declared if str(item).strip()})
    inferred: list[str] = []
    for analysis_type, blocks in SUPPORTED_ANALYSIS_TYPES.items():
        if any(manifest.get(block) for block in blocks):
            inferred.append(analysis_type)
    return inferred


def analysis_coverage_findings(manifest: dict[str, Any]) -> list[Finding]:
    types = declared_analysis_types(manifest)
    if not types:
        return [(
            "UNCERTAIN",
            "COVERAGE",
            "analysis_types is absent and no supported evidence block can be inferred",
        )]
    findings: list[Finding] = []
    for analysis_type in types:
        blocks = SUPPORTED_ANALYSIS_TYPES.get(analysis_type)
        if blocks is None:
            findings.append((
                "UNCERTAIN",
                "COVERAGE",
                f"analysis_type={analysis_type!r} has no active claim rules",
            ))
        elif not any(manifest.get(block) for block in blocks):
            findings.append((
                "UNCERTAIN",
                "COVERAGE",
                f"analysis_type={analysis_type!r} has none of its evidence blocks {list(blocks)}",
            ))
    return findings


def by_key(entries: Iterable[dict[str, Any]], field: str = "assembly_key") -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        grouped.setdefault(str(entry.get(field) or ""), []).append(entry)
    return grouped


def claim_label(claim: dict[str, Any], index: int) -> str:
    return str(claim.get("claim_id") or f"claims[{index}]")


def add_missing(findings: list[Finding], rule_id: str, claim_id: str, fields: Iterable[str]) -> None:
    for field in fields:
        findings.append(("WARN", rule_id, f"{claim_id}: missing publication provenance {field}"))


def validate_claim_schema(claim: dict[str, Any], index: int) -> list[Finding]:
    claim_id = claim_label(claim, index)
    findings: list[Finding] = []
    for field in ("claim_id", "claim_type", "metric", "subjects", "protocol", "evidence_paths", "status", "caveats"):
        if field not in claim:
            findings.append(("BLOCK", "CLAIM_SCHEMA_001", f"{claim_id}: missing claim field {field}"))
    if claim.get("claim_type") not in CLAIM_TYPES:
        findings.append((
            "BLOCK",
            "CLAIM_SCHEMA_001",
            f"{claim_id}: unsupported claim_type={claim.get('claim_type')!r}",
        ))
    subjects = claim.get("subjects")
    if not isinstance(subjects, list) or not subjects or any(not str(item).strip() for item in subjects):
        findings.append(("BLOCK", "CLAIM_SCHEMA_001", f"{claim_id}: subjects must be a non-empty list"))
    elif len({str(item) for item in subjects}) != len(subjects):
        findings.append(("BLOCK", "CLAIM_SCHEMA_001", f"{claim_id}: subjects contain duplicates"))
    protocol = claim.get("protocol")
    if not isinstance(protocol, dict):
        findings.append(("BLOCK", "CLAIM_SCHEMA_001", f"{claim_id}: protocol must be a mapping"))
    evidence = claim.get("evidence_paths")
    if not isinstance(evidence, list) or not evidence or any(not str(item).strip() for item in evidence):
        findings.append(("BLOCK", "CLAIM_SCHEMA_001", f"{claim_id}: evidence_paths must be non-empty"))
    if claim.get("status") not in CLAIM_STATUSES:
        findings.append((
            "BLOCK",
            "CLAIM_SCHEMA_001",
            f"{claim_id}: invalid status={claim.get('status')!r}",
        ))
    if not isinstance(claim.get("caveats"), list):
        findings.append(("BLOCK", "CLAIM_SCHEMA_001", f"{claim_id}: caveats must be a list"))
    claim_type = claim.get("claim_type")
    if claim_type == "metric_observation" and isinstance(subjects, list) and len(subjects) != 1:
        findings.append(("BLOCK", "CLAIM_SCHEMA_001", f"{claim_id}: metric_observation requires one subject"))
    if claim_type == "metric_comparison" and isinstance(subjects, list) and len(subjects) < 2:
        findings.append(("BLOCK", "CLAIM_SCHEMA_001", f"{claim_id}: metric_comparison requires >=2 subjects"))
    return findings


def evidence_findings(claim: dict[str, Any], index: int, manifest_dir: Path) -> list[Finding]:
    claim_id = claim_label(claim, index)
    if not isinstance(claim.get("evidence_paths"), list):
        return []
    findings: list[Finding] = []
    for value in claim["evidence_paths"]:
        if not isinstance(value, str) or not value.strip():
            continue
        raw = Path(value).expanduser()
        path = raw if raw.is_absolute() else manifest_dir / raw
        path = path.resolve(strict=False)
        project = layout_v2_project_root(manifest_dir)
        if claim.get("status") == "supported" and path_is_in_tmp(path, project):
            findings.append((
                "BLOCK",
                "CLAIM_EVIDENCE_002",
                f"{claim_id}: supported claim evidence must not come from disposable tmp/: {path}",
            ))
        if claim.get("status") == "supported" and (
            not path.exists() or not path.is_file() or not os.access(path, os.R_OK)
        ):
            findings.append((
                "BLOCK",
                "CLAIM_EVIDENCE_001",
                f"{claim_id}: supported claim evidence is missing or unreadable: {path}",
            ))
    return findings


def assembly_by_subject(manifest: dict[str, Any], subject: str) -> dict[str, Any] | None:
    for assembly in list_of(manifest, "assemblies"):
        if str(assembly.get("key") or "") == subject:
            return assembly
    return None


def select_entries(
    manifest: dict[str, Any],
    block: str,
    subject: str,
    protocol: dict[str, Any],
    protocol_fields: Iterable[str],
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for entry in list_of(manifest, block):
        if str(entry.get("assembly_key") or "") != subject:
            continue
        if all(entry.get(field) == protocol.get(field) for field in protocol_fields):
            selected.append(entry)
    return selected


def require_protocol(claim_id: str, protocol: dict[str, Any], fields: Iterable[str]) -> list[Finding]:
    return [
        ("BLOCK", "CLAIM_SCHEMA_001", f"{claim_id}: protocol.{field} is required")
        for field in fields
        if not field_present(protocol, field)
    ]


def n50_findings(manifest: dict[str, Any], claim: dict[str, Any], index: int) -> list[Finding]:
    claim_id = claim_label(claim, index)
    protocol = claim.get("protocol") if isinstance(claim.get("protocol"), dict) else {}
    findings = require_protocol(claim_id, protocol, ("n50_type",))
    n50_type = protocol.get("n50_type")
    if n50_type not in {"contig_N50", "scaffold_N50"}:
        findings.append((
            "BLOCK", "ASM_N50_001", f"{claim_id}: n50_type must be contig_N50 or scaffold_N50"
        ))
        return findings
    for subject in claim.get("subjects") or []:
        assembly = assembly_by_subject(manifest, str(subject))
        if assembly is None:
            findings.append(("BLOCK", "ASM_N50_001", f"{claim_id}: unknown assembly subject {subject}"))
        elif not field_present(assembly, n50_type):
            alternate = "scaffold_N50" if n50_type == "contig_N50" else "contig_N50"
            findings.append((
                "BLOCK",
                "ASM_N50_001",
                f"{claim_id}: {subject} lacks {n50_type}; available alternate={field_present(assembly, alternate)}",
            ))
        elif n50_type == "scaffold_N50" and assembly.get("misjoin_validated") is not True:
            findings.append((
                "WARN",
                "ASM_N50_002",
                f"{claim_id}: {subject} scaffold_N50 lacks misjoin_validated=true",
            ))
    return findings


def busco_findings(manifest: dict[str, Any], claim: dict[str, Any], index: int) -> list[Finding]:
    claim_id = claim_label(claim, index)
    protocol = claim.get("protocol") if isinstance(claim.get("protocol"), dict) else {}
    findings = require_protocol(claim_id, protocol, ("lineage", "mode"))
    if findings:
        return findings
    required = ("lineage", "mode", "db_version", "busco_version", "n_busco", "C", "D", "F", "M")
    for subject in claim.get("subjects") or []:
        matches = select_entries(manifest, "busco", str(subject), protocol, ("lineage", "mode"))
        if len(matches) != 1:
            available = sorted({
                f"{entry.get('lineage')}/{entry.get('mode')}"
                for entry in list_of(manifest, "busco")
                if str(entry.get("assembly_key") or "") == str(subject)
            })
            findings.append((
                "BLOCK",
                "ASM_BUSCO_002",
                f"{claim_id}: {subject} has {len(matches)} BUSCO records matching "
                f"{protocol.get('lineage')}/{protocol.get('mode')}; available={available}",
            ))
            continue
        entry = matches[0]
        add_missing(findings, "ASM_BUSCO_001", claim_id, [f"busco[{subject}].{f}" for f in required if not field_present(entry, f)])
        d_value = entry.get("D")
        assembly = assembly_by_subject(manifest, str(subject)) or {}
        if isinstance(d_value, (int, float)) and d_value > 20 and "haplotype" in str(assembly.get("role") or "").lower():
            findings.append((
                "NOTE",
                "ASM_BUSCO_003",
                f"{claim_id}: {subject} BUSCO D={d_value}; interpret in polyploid/subgenome context",
            ))
    return findings


def has_independence_caveat(claim: dict[str, Any]) -> bool:
    text = " ".join(str(item).lower() for item in (claim.get("caveats") or []))
    return "independen" in text or "非独立" in text


def qv_findings(manifest: dict[str, Any], claim: dict[str, Any], index: int) -> list[Finding]:
    claim_id = claim_label(claim, index)
    protocol = claim.get("protocol") if isinstance(claim.get("protocol"), dict) else {}
    findings = require_protocol(claim_id, protocol, ("k", "read_db_type"))
    if findings:
        return findings
    required = ("k", "read_db_type", "coverage", "independence", "QV")
    for subject in claim.get("subjects") or []:
        matches = select_entries(manifest, "merqury", str(subject), protocol, ("k", "read_db_type"))
        if len(matches) != 1:
            available = sorted({
                f"k={entry.get('k')},read_db_type={entry.get('read_db_type')}"
                for entry in list_of(manifest, "merqury")
                if str(entry.get("assembly_key") or "") == str(subject)
            })
            findings.append((
                "BLOCK",
                "ASM_QV_002",
                f"{claim_id}: {subject} has {len(matches)} QV records matching k={protocol.get('k')},"
                f"read_db_type={protocol.get('read_db_type')}; available={available}",
            ))
            continue
        entry = matches[0]
        add_missing(findings, "ASM_QV_001", claim_id, [f"merqury[{subject}].{f}" for f in required if not field_present(entry, f)])
        if entry.get("independence") is False:
            findings.append((
                "WARN",
                "ASM_QV_003",
                f"{claim_id}: {subject} QV is non-independent (assembly-read truth set reused)",
            ))
            if not has_independence_caveat(claim):
                findings.append((
                    "WARN",
                    "CLAIM_STATUS_001",
                    f"{claim_id}: non-independent QV requires an explicit caveat",
                ))
    return findings


def lai_findings(manifest: dict[str, Any], claim: dict[str, Any], index: int) -> list[Finding]:
    claim_id = claim_label(claim, index)
    findings: list[Finding] = []
    required = ("LAI", "total_LTR_RT_pct", "intact_LTR_RT_pct")
    for subject in claim.get("subjects") or []:
        matches = [
            entry for entry in list_of(manifest, "lai")
            if str(entry.get("assembly_key") or "") == str(subject)
        ]
        if len(matches) != 1:
            findings.append(("BLOCK", "ASM_LAI_001", f"{claim_id}: {subject} has {len(matches)} LAI records"))
            continue
        entry = matches[0]
        add_missing(findings, "ASM_LAI_001", claim_id, [f"lai[{subject}].{f}" for f in required if not field_present(entry, f)])
        try:
            total = float(entry["total_LTR_RT_pct"])
            intact = float(entry["intact_LTR_RT_pct"])
        except (KeyError, TypeError, ValueError):
            continue
        if total < 5 or intact < 0.1:
            findings.append((
                "BLOCK",
                "ASM_LAI_001",
                f"{claim_id}: {subject} LAI not applicable (total={total}%, intact={intact}%)",
            ))
    return findings


def mapping_findings(manifest: dict[str, Any], claim: dict[str, Any], index: int) -> list[Finding]:
    claim_id = claim_label(claim, index)
    protocol = claim.get("protocol") if isinstance(claim.get("protocol"), dict) else {}
    findings = require_protocol(claim_id, protocol, ("read_type",))
    if findings:
        return findings
    for subject in claim.get("subjects") or []:
        matches = select_entries(manifest, "mapping", str(subject), protocol, ("read_type",))
        if len(matches) != 1:
            findings.append((
                "BLOCK", "ASM_OVERVIEW_001", f"{claim_id}: {subject} lacks one mapping record for {protocol.get('read_type')}"
            ))
        elif not field_present(matches[0], "rate_pct"):
            findings.append(("WARN", "ASM_OVERVIEW_001", f"{claim_id}: mapping[{subject}].rate_pct missing"))
    return findings


def telomere_findings(manifest: dict[str, Any], claim: dict[str, Any], index: int) -> list[Finding]:
    claim_id = claim_label(claim, index)
    findings: list[Finding] = []
    grouped = by_key(list_of(manifest, "telomere"))
    for subject in claim.get("subjects") or []:
        matches = grouped.get(str(subject), [])
        if len(matches) != 1:
            findings.append(("BLOCK", "ASM_OVERVIEW_001", f"{claim_id}: {subject} has {len(matches)} telomere records"))
        else:
            add_missing(
                findings,
                "ASM_OVERVIEW_001",
                claim_id,
                [f"telomere[{subject}].{field}" for field in ("repeats", "expected") if not field_present(matches[0], field)],
            )
    return findings


def metric_findings(manifest: dict[str, Any], claim: dict[str, Any], index: int) -> list[Finding]:
    metric = normalized_metric(claim.get("metric"))
    dispatch = {
        "N50": n50_findings,
        "BUSCO": busco_findings,
        "QV": qv_findings,
        "LAI": lai_findings,
        "MAPPING": mapping_findings,
        "TELOMERE": telomere_findings,
    }
    checker = dispatch.get(metric)
    if checker is None:
        return [(
            "UNCERTAIN",
            "COVERAGE",
            f"{claim_label(claim, index)}: metric={claim.get('metric')!r} has no active claim rule",
        )]
    return checker(manifest, claim, index)


def overview_findings(manifest: dict[str, Any], claim: dict[str, Any], index: int) -> list[Finding]:
    claim_id = claim_label(claim, index)
    protocol = claim.get("protocol") if isinstance(claim.get("protocol"), dict) else {}
    findings = require_protocol(
        claim_id, protocol, ("n50_type", "lineage", "mode", "k", "read_db_type", "mapping_read_type")
    )
    if findings:
        return findings
    axis_claims = [
        dict(claim, metric="N50"),
        dict(claim, metric="BUSCO"),
        dict(claim, metric="QV"),
        dict(claim, metric="LAI"),
        dict(claim, metric="MAPPING", protocol=dict(protocol, read_type=protocol["mapping_read_type"])),
        dict(claim, metric="TELOMERE"),
    ]
    for axis_claim in axis_claims:
        findings.extend(metric_findings(manifest, axis_claim, index))
    return findings


def sv_findings(manifest: dict[str, Any], claim: dict[str, Any], index: int) -> list[Finding]:
    claim_id = claim_label(claim, index)
    callers = (manifest.get("sv") or {}).get("callers") if isinstance(manifest.get("sv"), dict) else []
    if not isinstance(callers, list):
        callers = []
    axes = {
        str(caller.get("evidence_axis") or "").lower()
        for caller in callers
        if isinstance(caller, dict) and caller.get("name")
    }
    if not {"read", "assembly"}.issubset(axes):
        return [(
            "BLOCK",
            "SV_001",
            f"{claim_id}: high-confidence SV requires evidence_axis=read and assembly; found={sorted(axes)}",
        )]
    return []


def explicit_path_findings(
    values: Iterable[tuple[str, Any]], claim_id: str, rule_id: str, manifest_dir: Path
) -> list[Finding]:
    findings: list[Finding] = []
    for label, value in values:
        if not isinstance(value, str) or not value.strip():
            findings.append(("BLOCK", rule_id, f"{claim_id}: missing explicit path {label}"))
            continue
        raw = Path(value).expanduser()
        path = raw if raw.is_absolute() else manifest_dir / raw
        path = path.resolve(strict=False)
        project = layout_v2_project_root(manifest_dir)
        if path_is_in_tmp(path, project):
            findings.append(("BLOCK", "CLAIM_EVIDENCE_002", f"{claim_id}: {label} must not come from disposable tmp/: {path}"))
        if not path.exists() or not path.is_file() or not os.access(path, os.R_OK):
            findings.append(("BLOCK", rule_id, f"{claim_id}: {label} missing or unreadable: {path}"))
    return findings


def rnaseq_de_findings(
    manifest: dict[str, Any], claim: dict[str, Any], index: int, manifest_dir: Path
) -> list[Finding]:
    claim_id = claim_label(claim, index)
    block = manifest.get("rnaseq_de") if isinstance(manifest.get("rnaseq_de"), dict) else {}
    findings: list[Finding] = []
    for field in ("design_formula", "contrast", "strandedness", "biological_replicates"):
        if not field_present(block, field):
            findings.append(("BLOCK", "RNA_DE_001", f"{claim_id}: rnaseq_de.{field} is required"))
    if block.get("strandedness") not in {"unstranded", "forward", "reverse"}:
        findings.append((
            "BLOCK", "RNA_DE_003", f"{claim_id}: strandedness must be unstranded, forward, or reverse"
        ))
    contrast = block.get("contrast")
    if not isinstance(contrast, list) or len(contrast) != 3 or any(not str(item).strip() for item in contrast):
        findings.append((
            "BLOCK", "RNA_DE_001", f"{claim_id}: contrast must be [Factor, Numerator, Denominator]"
        ))
    replicates = block.get("biological_replicates")
    if not isinstance(replicates, dict) or not replicates:
        findings.append(("BLOCK", "RNA_DE_002", f"{claim_id}: biological replicate counts are missing"))
    else:
        invalid = {group: value for group, value in replicates.items() if not isinstance(value, int) or value < 1}
        if invalid:
            findings.append(("BLOCK", "RNA_DE_002", f"{claim_id}: invalid replicate counts {invalid}"))
        elif any(value < 2 for value in replicates.values()):
            findings.append((
                "BLOCK", "RNA_DE_002", f"{claim_id}: each contrasted group needs >=2 biological replicates; {replicates}"
            ))
        elif any(value == 2 for value in replicates.values()):
            findings.append((
                "WARN", "RNA_DE_002", f"{claim_id}: two biological replicates in at least one group; >=3 is recommended"
            ))
    if block.get("batch_condition_confounding") is not False:
        findings.append((
            "BLOCK", "RNA_DE_004", f"{claim_id}: batch_condition_confounding must be explicitly false"
        ))
    count_input = block.get("count_input") if isinstance(block.get("count_input"), dict) else {}
    if count_input.get("type") != "raw_integer_counts":
        findings.append((
            "BLOCK", "RNA_DE_003", f"{claim_id}: DE input must be type=raw_integer_counts, not TPM/FPKM"
        ))
    statistics = block.get("statistics") if isinstance(block.get("statistics"), dict) else {}
    for field in ("fdr_method", "alpha", "effect_size", "shrinkage"):
        if not field_present(statistics, field):
            findings.append(("BLOCK", "RNA_DE_005", f"{claim_id}: statistics.{field} is required"))
    qc_paths = block.get("qc_evidence_paths")
    if not isinstance(qc_paths, list) or not qc_paths:
        findings.append(("BLOCK", "RNA_DE_005", f"{claim_id}: qc_evidence_paths must be non-empty"))
        qc_paths = []
    paths: list[tuple[str, Any]] = [
        ("sample_metadata_path", block.get("sample_metadata_path")),
        ("count_input.path", count_input.get("path")),
    ]
    paths.extend((f"qc_evidence_paths[{position}]", value) for position, value in enumerate(qc_paths))
    findings.extend(explicit_path_findings(paths, claim_id, "RNA_DE_005", manifest_dir))
    return findings


def population_variant_findings(
    manifest: dict[str, Any], claim: dict[str, Any], index: int, manifest_dir: Path
) -> list[Finding]:
    claim_id = claim_label(claim, index)
    block = manifest.get("population_variants") if isinstance(manifest.get("population_variants"), dict) else {}
    findings: list[Finding] = []
    reference = block.get("reference") if isinstance(block.get("reference"), dict) else {}
    for field in ("path", "version", "checksum"):
        if not field_present(reference, field):
            findings.append(("BLOCK", "VARIANT_001", f"{claim_id}: reference.{field} is required"))
    for field in ("ploidy_assumption", "caller", "caller_version", "calling_mode", "multiallelic_policy"):
        if not field_present(block, field):
            findings.append(("BLOCK", "VARIANT_001", f"{claim_id}: population_variants.{field} is required"))
    if block.get("sample_match") is not True:
        findings.append((
            "BLOCK", "VARIANT_002", f"{claim_id}: genotype/BAM/manifest sample IDs are not explicitly matched"
        ))
    normalization = block.get("normalization") if isinstance(block.get("normalization"), dict) else {}
    if normalization.get("left_aligned") is not True or normalization.get("split_multiallelic") is not True:
        findings.append((
            "BLOCK", "VARIANT_003", f"{claim_id}: normalization must record left alignment and multiallelic splitting"
        ))
    if not field_present(normalization, "tool") or not field_present(normalization, "version"):
        findings.append(("BLOCK", "VARIANT_003", f"{claim_id}: normalization tool/version are required"))
    filters = block.get("filter_provenance")
    if not isinstance(filters, dict) or not filters:
        findings.append(("BLOCK", "VARIANT_003", f"{claim_id}: filter_provenance must be explicit"))
    paths = [
        ("reference.path", reference.get("path")),
        ("sample_manifest_path", block.get("sample_manifest_path")),
        ("vcf_path", block.get("vcf_path")),
        ("index_path", block.get("index_path")),
    ]
    findings.extend(explicit_path_findings(paths, claim_id, "VARIANT_004", manifest_dir))
    return findings


def gwas_findings(
    manifest: dict[str, Any], claim: dict[str, Any], index: int, manifest_dir: Path
) -> list[Finding]:
    claim_id = claim_label(claim, index)
    block = manifest.get("gwas") if isinstance(manifest.get("gwas"), dict) else {}
    findings: list[Finding] = []
    if block.get("sample_match") is not True:
        findings.append((
            "BLOCK", "GWAS_001", f"{claim_id}: phenotype/genotype sample IDs are not explicitly matched"
        ))
    route = block.get("route")
    if route == "D":
        compatible = (
            block.get("ploidy_model") == "disomic_diploid_approximation"
            and block.get("homeolog_resolved") is True
            and block.get("biallelic") is True
            and str(block.get("engine") or "").upper() == "GEMMA"
            and str(block.get("qc_engine") or "").upper() == "PLINK2"
            and block.get("engine_validated") is True
        )
        if not compatible:
            findings.append((
                "BLOCK", "GWAS_002", f"{claim_id}: D route requires homeolog-resolved biallelic disomic PLINK2+GEMMA"
            ))
    elif route == "P":
        compatible = (
            block.get("dosage_aware") is True
            and block.get("polyploid_model") is True
            and field_present(block, "engine")
            and block.get("engine_validated") is True
        )
        if not compatible:
            findings.append((
                "BLOCK", "GWAS_002", f"{claim_id}: P route requires a selected validated dosage/polyploid-aware engine"
            ))
    else:
        findings.append(("BLOCK", "GWAS_002", f"{claim_id}: gwas.route must be D or P"))
    if block.get("model_compatibility") is not True:
        findings.append(("BLOCK", "GWAS_002", f"{claim_id}: model_compatibility must be explicitly true"))
    thresholds = block.get("qc_thresholds")
    if not isinstance(thresholds, dict) or not thresholds:
        findings.append(("BLOCK", "GWAS_003", f"{claim_id}: qc_thresholds must be explicit"))
    if not isinstance(block.get("covariates"), list):
        findings.append(("BLOCK", "GWAS_003", f"{claim_id}: covariates must be an explicit list"))
    testing = block.get("multiple_testing") if isinstance(block.get("multiple_testing"), dict) else {}
    if not field_present(testing, "method") or not field_present(testing, "threshold"):
        findings.append(("BLOCK", "GWAS_004", f"{claim_id}: multiple_testing method/threshold are required"))
    if block.get("effect_allele_reported") is not True:
        findings.append(("BLOCK", "GWAS_004", f"{claim_id}: effect_allele_reported must be true"))
    paths = [
        ("phenotype_path", block.get("phenotype_path")),
        ("genotype_path", block.get("genotype_path")),
        ("pca_path", block.get("pca_path")),
        ("kinship_path", block.get("kinship_path")),
        ("qq_evidence_path", block.get("qq_evidence_path")),
    ]
    findings.extend(explicit_path_findings(paths, claim_id, "GWAS_003", manifest_dir))
    return findings


def claim_gate_findings(
    manifest: dict[str, Any], claim: dict[str, Any], index: int, manifest_dir: Path
) -> list[Finding]:
    claim_type = claim.get("claim_type")
    if claim_type in {"metric_observation", "metric_comparison"}:
        return metric_findings(manifest, claim, index)
    if claim_type == "assembly_quality_overview":
        return overview_findings(manifest, claim, index)
    if claim_type == "sv_high_confidence":
        return sv_findings(manifest, claim, index)
    if claim_type == "rnaseq_differential_expression":
        return rnaseq_de_findings(manifest, claim, index, manifest_dir)
    if claim_type == "population_variant_calling":
        return population_variant_findings(manifest, claim, index, manifest_dir)
    if claim_type == "gwas":
        return gwas_findings(manifest, claim, index, manifest_dir)
    return []


def status_consistency_findings(
    claim: dict[str, Any], index: int, claim_findings: list[Finding]
) -> list[Finding]:
    claim_id = claim_label(claim, index)
    status = claim.get("status")
    if status == "blocked":
        return [("BLOCK", "CLAIM_STATUS_001", f"{claim_id}: manifest declares status=blocked")]
    if status == "uncertain":
        return [("UNCERTAIN", "CLAIM_STATUS_001", f"{claim_id}: manifest declares status=uncertain")]
    if status == "supported":
        if any(severity == "BLOCK" for severity, _, _ in claim_findings):
            return [(
                "BLOCK", "CLAIM_STATUS_001", f"{claim_id}: status=supported conflicts with a BLOCK gate"
            )]
        if any(severity in {"WARN", "MISSING"} for severity, _, _ in claim_findings):
            return [(
                "WARN", "CLAIM_STATUS_001", f"{claim_id}: status=supported conflicts with incomplete provenance/caveats"
            )]
    return []


def legacy_findings(manifest: dict[str, Any]) -> list[Finding]:
    claims = list_of(manifest, "claims")
    message = (
        "legacy/v1 manifest is readable but cannot receive claim-grade PASS; add "
        "schema_version=result_manifest.v2 and explicit claim_type/metric/subjects/protocol/evidence_paths/status/caveats"
    )
    findings: list[Finding] = [("WARN", "CLAIM_SCHEMA_001", message)]
    sv = manifest.get("sv") if isinstance(manifest.get("sv"), dict) else {}
    if sv.get("high_confidence_claim"):
        callers = sv.get("callers") if isinstance(sv.get("callers"), list) else []
        axes = {
            str(caller.get("evidence_axis") or "").lower()
            for caller in callers
            if isinstance(caller, dict)
        }
        if not {"read", "assembly"}.issubset(axes):
            findings.append((
                "BLOCK", "SV_001", f"legacy high-confidence SV lacks read+assembly axes; found={sorted(axes)}"
            ))
    if claims:
        findings.append(("WARN", "CLAIM_SCHEMA_001", "legacy claims were not destructively migrated or treated as v2"))
    return findings


def run(
    manifest: dict[str, Any],
    rules: list[dict[str, str]],
    anchors: dict[str, Any],
    manifest_dir: Path | None = None,
) -> tuple[str, list[Finding]]:
    """Return overall status and findings for one manifest."""
    del anchors  # anchors constrain narrative; claim protocol matching is local-manifest based.
    manifest_dir = (manifest_dir or Path.cwd()).resolve()
    findings = analysis_coverage_findings(manifest)
    claims = list_of(manifest, "claims")
    if manifest.get("schema_version") != SCHEMA_V2:
        findings.extend(legacy_findings(manifest))
    elif not claims:
        findings.append((
            "WARN",
            "CLAIM_SCHEMA_001",
            "result_manifest.v2 has no explicit claims; populated analysis blocks are observations only",
        ))
    else:
        seen_claim_ids: set[str] = set()
        active_rule_ids = {row.get("rule_id", "").strip() for row in rules}
        for index, claim in enumerate(claims):
            claim_id = str(claim.get("claim_id") or "")
            claim_findings = validate_claim_schema(claim, index)
            if claim_id and claim_id in seen_claim_ids:
                claim_findings.append(("BLOCK", "CLAIM_SCHEMA_001", f"duplicate claim_id={claim_id}"))
            seen_claim_ids.add(claim_id)
            claim_findings.extend(evidence_findings(claim, index, manifest_dir))
            if not any(severity == "BLOCK" and rule == "CLAIM_SCHEMA_001" for severity, rule, _ in claim_findings):
                claim_findings.extend(claim_gate_findings(manifest, claim, index, manifest_dir))
            claim_findings.extend(status_consistency_findings(claim, index, claim_findings))
            findings.extend(claim_findings)
        internal_ids = {"COVERAGE", "SCHEMA"}
        for severity, rule_id, detail in list(findings):
            if rule_id not in internal_ids and rule_id not in active_rule_ids:
                findings.append((
                    "WARN",
                    "SCHEMA",
                    f"active checker finding {rule_id} is absent from interpretation-rules.tsv ({detail})",
                ))

    if any(severity == "BLOCK" for severity, _, _ in findings):
        return "BLOCK", findings
    if any(severity == "UNCERTAIN" for severity, _, _ in findings):
        return "UNCERTAIN", findings
    if any(severity in {"WARN", "MISSING"} for severity, _, _ in findings):
        return "WARN", findings
    return "PASS", findings


def render(status: str, findings: list[Finding]) -> str:
    lines = [f"STATUS\t{status}"]

    def section(label: str, severities: set[str]) -> None:
        selected = [finding for finding in findings if finding[0] in severities]
        if selected:
            lines.append(f"\n{label}:")
            for _, rule_id, detail in selected:
                lines.append(f"  {rule_id}\t{detail}")

    section("BLOCKED", {"BLOCK"})
    section("UNCERTAINTY", {"UNCERTAIN"})
    section("WARNINGS", {"WARN"})
    section("NOTES", {"NOTE"})
    section("SUGGESTIONS", {"SUGGEST"})
    section("MISSING", {"MISSING"})
    if status == "PASS":
        lines.append("\nALL DECLARED CLAIMS SATISFY THEIR SUBJECT, PROTOCOL, AND EVIDENCE GATES.")
    elif status == "UNCERTAIN":
        lines.append("\nCLAIM COVERAGE INCOMPLETE -- report accepted observations only.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check claim-specific Bioflow result contracts.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--rules", default=str(DEFAULT_RULES))
    parser.add_argument("--anchors", default=str(DEFAULT_ANCHORS))
    args = parser.parse_args(argv)
    paths = {
        "manifest": Path(args.manifest),
        "rules": Path(args.rules),
        "anchors": Path(args.anchors),
    }
    for label, path in paths.items():
        if path.is_symlink():
            sys.stderr.write(f"{label} must not be a symbolic link: {path}\n")
            return 2
        if not path.exists() or not path.is_file() or not os.access(path, os.R_OK):
            sys.stderr.write(f"{label} not found or unreadable: {path}\n")
            return 2
    try:
        manifest = load_yaml(paths["manifest"])
        rules = load_rules(paths["rules"])
        anchors = load_yaml(paths["anchors"])
        # Keep the lexical canonical config/ location for project-layout
        # detection; individual evidence paths are resolved separately.
        manifest_path = paths["manifest"].absolute()
        status, findings = run(manifest, rules, anchors, manifest_path.parent)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        sys.stderr.write(f"cannot check manifest: {exc}\n")
        return 2
    print(render(status, findings))
    return {"PASS": 0, "WARN": 1, "BLOCK": 2, "UNCERTAIN": 3}[status]


if __name__ == "__main__":
    raise SystemExit(main())
