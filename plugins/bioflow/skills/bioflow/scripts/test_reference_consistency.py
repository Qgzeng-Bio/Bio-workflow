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

print("PASS | genome evaluation reference consistency")
