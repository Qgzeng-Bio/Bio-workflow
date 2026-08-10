#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REFS = ROOT / "references"
anchors = yaml.safe_load((REFS / "project-anchors.yaml").read_text())
frame = anchors["quinoa_v2_reference_frame"]

qv_protocol = frame["qv_protocol"]
assert qv_protocol["read_db_type"] == "hifi", qv_protocol
assert qv_protocol["independence"] is False, qv_protocol
assert qv_protocol["k"] == 21 and qv_protocol["coverage"] == 70.0, qv_protocol
print("PASS | anchor QV protocol is historical HiFi and non-independent")

busco_protocol = frame["busco_protocol"]
assert busco_protocol["lineage"] == "embryophyta_odb12", busco_protocol
assert busco_protocol["mode"] == "genome" and busco_protocol["n_busco"] == 2026
print("PASS | headline BUSCO lineage matches quinoa anchor")

primary = frame["assemblies"]["Cqu_final"]
assert primary["role"] == "primary", primary
assert "merged" not in primary["role"].lower()
assert "not a simple concatenation" in frame["notes"]
print("PASS | Cqu_final role is primary A+B, not merged haplotypes")

quality = (REFS / "playbook-genome-quality-evaluation.md").read_text()
finishing = (REFS / "playbook-genome-finishing.md").read_text()
assembly = (REFS / "playbook-genome-assembly.md").read_text()
combined = "\n".join((quality, finishing, assembly, (REFS / "project-anchors.yaml").read_text()))
for forbidden in (
    "QV ≥ 60 ≈ T2T-grade",
    "Q50+ T2T-grade",
    "Q50 ≈ 1/10⁵ (T2T bar)",
    "primary_merged",
    "merging two near-identical haplotypes",
):
    assert forbidden not in combined, forbidden
assert not re.search(r"merged[- `]*Cqu_final", combined, re.IGNORECASE)
assert "QV ≥ 60 indicates very high consensus accuracy" in quality
assert "all expected chromosome ends have telomeric-repeat support" in quality
assert "gap-free sequence, all expected telomeric ends, structural continuity" in quality
print("PASS | QV/telomere wording does not substitute for T2T evidence")

assert "### Historical quinoa V2 evaluation" in quality
assert "### Recommended independent evaluation" in quality
historical = quality.split("### Historical quinoa V2 evaluation", 1)[1].split(
    "### Recommended independent evaluation", 1
)[0]
recommended = quality.split("### Recommended independent evaluation", 1)[1].split(
    "## 2 — BUSCO", 1
)[0]
assert "cqu_hifi_70x.fa.gz" in historical
assert "independence=false" in historical
assert "PCR-free Illumina" in recommended
assert "historical 63.24/66.93/65.78 values" in recommended
assert "Do **not** attach" in recommended
assert "Historical quinoa V2 QV context" in finishing
assert "Recommended independent post-polish QV" in finishing
print("PASS | historical and recommended Merqury protocols are separated with caveats")

assert "-l embryophyta_odb12" in assembly
assert "eudicots_odb10" in assembly and "supplemental" in assembly
assert "must not be directly ranked against odb12" in assembly
print("PASS | assembly playbook uses odb12 headline and isolates other lineages")

rnaseq_path = REFS / "playbook-rnaseq-differential-expression.md"
population_path = REFS / "playbook-population-variants-gwas.md"
assert rnaseq_path.is_file() and population_path.is_file()
rnaseq = rnaseq_path.read_text()
population = population_path.read_text()
skill = (ROOT / "SKILL.md").read_text()
assert "references/playbook-rnaseq-differential-expression.md" in skill
assert "references/playbook-population-variants-gwas.md" in skill
assert "analysis_type: rnaseq" in rnaseq and "UNCERTAIN" in rnaseq
assert "raw integer counts" in rnaseq and "batch" in rnaseq and "homeolog" in rnaseq
assert "D route" in population and "P route" in population and "KMERIA" in population
assert not re.search(r"^#SBATCH --time", rnaseq + "\n" + population, re.MULTILINE)
print("PASS | RNA DE and population GWAS routes exist and are linked")

required_headers = (
    "Sample_ID\tCondition\tBiological_Replicate\tBatch\tTissue\tRead1\tRead2",
    "Gene_ID\tBase_Mean\tLog2FC\tLFC_SE\tStatistic\tP_Value\tAdjusted_P_Value\tContrast\tStatus",
    "Sample_ID\tBAM_or_VCF_ID\tPopulation\tFamily\tBatch\tPloidy_Model\tInput_Path",
    "Trait\tChr\tPosition_bp\tRef_Allele\tEffect_Allele\tEffect\tSE\tP_Value\tAdjusted_P_Value\tMAF\tMAC\tN\tModel",
)
for header in required_headers:
    assert header in rnaseq or header in population, header
    assert "  " not in header and "\t" in header
print("PASS | playbook table schemas use explicit TSV and canonical columns")

print("PASS | genome evaluation and workflow reference consistency")
