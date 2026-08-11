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

path_contract = (REFS / "path-management.md").read_text()
workspace_contract = (REFS / "workspace-steward.md").read_text()
layout = (REFS / "project-layout.md").read_text()
lifecycle = (REFS / "project-lifecycle.md").read_text()
monitoring = (REFS / "task-monitoring.md").read_text()
executor = (REFS / "executor-safety.md").read_text()
agent_metadata = (ROOT / "agents" / "openai.yaml").read_text()
assert "references/path-management.md" in skill
assert "references/workspace-steward.md" in skill
assert "scripts/path_manager.py suggest" in skill
assert "scripts/workspace_steward.py inspect" in skill
assert "project workspace stewardship" in skill.split("---", 2)[1]
assert "03_RNA_DE" in path_contract and "Directory_Index.tsv" in path_contract
assert "01_TEMR_core" in path_contract and "tmp/<module>" in path_contract
assert "Never derive stage order from alphabetic sorting" in path_contract
assert "assign consecutive stages `01`, `02`, `03`, ..." in path_contract
assert "no rename, move, delete" in path_contract
assert "Workspace stewardship" in layout and "24-character" in layout
assert "separate from both unnumbered role subdirectories" in layout
assert "Leave increments of 10 for" in layout
assert "Workspace_Policy.tsv" in lifecycle and "Workspace" in monitoring
assert "--project DIR --module M001 --task-id T001" in executor
assert "exact `Task_Status.Script_Path`" in executor and "every BLOCK" in executor
assert "workspace_steward.py" in workspace_contract and "WS014" in workspace_contract
assert "must contain at least one row" in workspace_contract
assert "combined parent/dependency" in workspace_contract
assert "root/control/lock symlinks are never followed" in workspace_contract
assert "supplied\nscript path must exactly match" in workspace_contract
assert "Producer_Tasks`/`Consumer_Tasks` must exist" in monitoring
assert "项目工作区管理" in agent_metadata and "module DAGs" in agent_metadata
expected_headers = {
    "Workspace_Policy.tsv": "Schema_Version\tEnforcement_Mode\tPlan_Status\tPlan_SHA256\tMax_Audit_Depth\tUpdated_Time",
    "Workspace_Modules.tsv": "Module_ID\tParent_Module\tStage\tShort_Name\tModule_Kind\tDepends_On\tPurpose\tOwner\tCompatibility\tNotes",
    "Workspace_Routes.tsv": "Route_ID\tModule_ID\tPath_Type\tPath_Role\tRelative_Path\tProducer_Tasks\tConsumer_Tasks\tRetention\tRequired\tCompatibility\tPurpose\tNotes",
}
for filename, header in expected_headers.items():
    assert (ROOT / "assets" / "project-templates" / filename).read_text().splitlines()[0] == header
    assert header in workspace_contract
print("PASS | path manager and Workspace Steward contracts, triggers, schemas, and gates are linked")

print("PASS | genome evaluation and workflow reference consistency")
