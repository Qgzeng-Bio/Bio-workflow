#!/usr/bin/env python3
"""Check a result manifest against the bio-workflow interpretation rules.

Usage:
  python3 scripts/check_result_contract.py --manifest <result_manifest.yaml>
  [--rules references/interpretation-rules.tsv]
  [--anchors references/project-anchors.yaml]

Output is the short Field<TAB>Value style used by program_card_lookup.py so
the calling agent can parse it without a heavy template. Exit code:
  0 = PASS (no rules fired, no missing fields)
  1 = WARN (only WARN/NOTE/SUGGEST fired, or only MISSING fields)
  2 = BLOCK (at least one BLOCK rule fired)

The point of this script is NOT to interpret biology -- it is to gate
publication-grade claims by checking provenance fields, invalid
comparisons, silent traps, and project-anchor sanity. See
references/result-manifest-schema.md for the manifest contract and
references/interpretation-rules.tsv for the rule list.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any, Callable

try:
    import yaml
except ImportError:  # pragma: no cover -- yaml is required
    sys.stderr.write(
        "PyYAML is required. Use a Python that has PyYAML installed (e.g. your conda/anaconda Python).\n"
    )
    raise SystemExit(2)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RULES = REPO_ROOT / "references" / "interpretation-rules.tsv"
DEFAULT_ANCHORS = REPO_ROOT / "references" / "project-anchors.yaml"

REQUIRED_BUSCO = ("lineage", "mode", "db_version", "C", "D", "F", "M")
REQUIRED_MERQURY = ("k", "read_db_type", "QV")
REQUIRED_LAI = ("LAI", "total_LTR_RT_pct", "intact_LTR_RT_pct")
REQUIRED_ASSEMBLY = ("key", "fasta", "total_length")


# ---------- helpers ----------------------------------------------------------


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open() as handle:
        return yaml.safe_load(handle) or {}


def load_rules(path: Path) -> list[dict[str, str]]:
    with path.open() as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return list(reader)


def list_of(manifest: dict, key: str) -> list[dict[str, Any]]:
    value = manifest.get(key) or []
    return value if isinstance(value, list) else []


def by_assembly(blocks: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for block in blocks:
        key = str(block.get("assembly_key") or "")
        grouped.setdefault(key, []).append(block)
    return grouped


def field_present(block: dict[str, Any], field: str) -> bool:
    if field not in block:
        return False
    value = block[field]
    return value is not None and value != ""


# ---------- per-rule check functions -----------------------------------------
#
# Each returns a list of (severity, detail) tuples. Severity is one of
# OK / WARN / BLOCK / NOTE / SUGGEST / MISSING (uppercase, matches the rule
# table). Detail is one short line.


def chk_ASM_BUSCO_001(m: dict, a: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for entry in list_of(m, "busco"):
        for f in REQUIRED_BUSCO:
            if not field_present(entry, f):
                out.append(("MISSING", f"busco[{entry.get('assembly_key', '?')}].{f}"))
    return out


def chk_ASM_BUSCO_002(m: dict, a: dict) -> list[tuple[str, str]]:
    lineages = {e.get("lineage") for e in list_of(m, "busco") if e.get("lineage")}
    if len(lineages) > 1:
        return [(
            "BLOCK",
            f"BUSCO percentages compared across lineages {sorted(lineages)} "
            "-- rerun same lineage or report each separately"
        )]
    return []


def chk_ASM_BUSCO_003(m: dict, a: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for entry in list_of(m, "busco"):
        d = entry.get("D")
        c = entry.get("C")
        role = ""
        for asm in list_of(m, "assemblies"):
            if asm.get("key") == entry.get("assembly_key"):
                role = str(asm.get("role") or "")
                break
        if isinstance(d, (int, float)) and d > 20 and "haplotype" in role.lower():
            detail = (
                f"busco[{entry.get('assembly_key')}] D={d} on phased haplotype "
                f"-- expected for polyploid; check ploidy/subgenome context, do not call over-duplication"
            )
            out.append(("NOTE", detail))
    return out


def chk_ASM_QV_001(m: dict, a: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for entry in list_of(m, "merqury"):
        for f in REQUIRED_MERQURY:
            if not field_present(entry, f):
                out.append(("MISSING", f"merqury[{entry.get('assembly_key', '?')}].{f}"))
    return out


def chk_ASM_QV_002(m: dict, a: dict) -> list[tuple[str, str]]:
    types = {
        e.get("read_db_type")
        for e in list_of(m, "merqury")
        if e.get("read_db_type")
    }
    if len(types) > 1:
        return [(
            "BLOCK",
            f"Merqury QV ranked across read_db_type {sorted(types)} "
            "-- harmonize read_db or report each separately"
        )]
    return []


def chk_ASM_QV_003(m: dict, a: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for entry in list_of(m, "merqury"):
        if entry.get("independence") is False:
            out.append((
                "WARN",
                f"merqury[{entry.get('assembly_key')}] QV is not independent "
                f"(read_db built from same read source as assembly input); caveat required"
            ))
    return out


def chk_ASM_LAI_001(m: dict, a: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for entry in list_of(m, "lai"):
        total = entry.get("total_LTR_RT_pct")
        intact = entry.get("intact_LTR_RT_pct")
        if total is None or intact is None:
            continue  # MISSING already covered by ASM_LAI inputs check
        try:
            t = float(total)
            i = float(intact)
        except (TypeError, ValueError):
            continue
        if t < 5 or i < 0.1:
            out.append((
                "BLOCK",
                f"lai[{entry.get('assembly_key')}] LTR content below applicability "
                f"(total={t}%, intact={i}%); LAI grade not_applicable"
            ))
    return out


def chk_ASM_LAI_002(m: dict, a: dict) -> list[tuple[str, str]]:
    # Cannot reliably detect cross-organism comparison from a single manifest.
    # Surface as a NOTE when LAI grades are claimed (presence of LAI block).
    if list_of(m, "lai"):
        return [(
            "NOTE",
            "LAI grades (draft/reference/gold) are not directly portable across taxa; "
            "prefer within-organism comparison"
        )]
    return []


def chk_ASM_REPEAT_001(m: dict, a: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    busco_by = by_assembly(list_of(m, "busco"))
    lai_by = by_assembly(list_of(m, "lai"))
    for asm_key in busco_by:
        if asm_key not in lai_by:
            continue
        c_vals = [b.get("C") for b in busco_by[asm_key] if b.get("C") is not None]
        l_vals = [l.get("LAI") for l in lai_by[asm_key] if l.get("LAI") is not None]
        if not c_vals or not l_vals:
            continue
        try:
            c = float(c_vals[0])
            li = float(l_vals[0])
        except (TypeError, ValueError):
            continue
        if c >= 98 and li < 10:
            out.append((
                "WARN",
                f"{asm_key}: BUSCO C={c}% but LAI={li} -- gene-space complete does NOT imply "
                "repeat-space complete; phrase as 'gene-space complete; repeat-space draft/reference boundary'"
            ))
    return out


def chk_ASM_N50_001(m: dict, a: dict) -> list[tuple[str, str]]:
    has_contig = any(asm.get("contig_N50") is not None for asm in list_of(m, "assemblies"))
    has_scaffold = any(asm.get("scaffold_N50") is not None for asm in list_of(m, "assemblies"))
    if has_contig and has_scaffold:
        # OK if every assembly is consistent (each labels its own type clearly)
        # but if the SAME comparison group mixes them, BLOCK.
        mixed = [
            asm.get("key")
            for asm in list_of(m, "assemblies")
            if asm.get("contig_N50") is not None and asm.get("scaffold_N50") is not None
        ]
        if mixed:
            return [(
                "BLOCK",
                f"assemblies {mixed} carry both contig_N50 and scaffold_N50 -- "
                "label each comparison explicitly; do not mix"
            )]
    return []


def chk_ASM_N50_002(m: dict, a: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for asm in list_of(m, "assemblies"):
        if asm.get("scaffold_N50") is not None and not asm.get("misjoin_validated"):
            out.append((
                "WARN",
                f"assemblies[{asm.get('key')}] reports scaffold_N50 without misjoin_validated=true; "
                "Hi-C/Pore-C scaffolding can inflate N50 via false joins -- require contact-map review"
            ))
    return out


def chk_KMERIA_001(m: dict, a: dict) -> list[tuple[str, str]]:
    kmeria = m.get("kmeria") or {}
    if not kmeria:
        return []
    if kmeria.get("pilot_only") or kmeria.get("full_count_incomplete"):
        return [(
            "BLOCK",
            f"kmeria.{ 'pilot_only' if kmeria.get('pilot_only') else 'full_count_incomplete' } "
            "-- do not make population-level association claim; mark as exploratory"
        )]
    return []


def chk_KMERIA_002(m: dict, a: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for hit in (m.get("kmeria") or {}).get("hits") or []:
        if hit.get("in_sd") or hit.get("in_centromere"):
            zones = []
            if hit.get("in_sd"):
                zones.append("SD")
            if hit.get("in_centromere"):
                zones.append("centromere")
            out.append((
                "WARN",
                f"kmeria hit {hit.get('id', '?')} overlaps {'/'.join(zones)} -- "
                "causal phrasing not supported without unique mappability evidence"
            ))
    return out


def chk_SV_001(m: dict, a: dict) -> list[tuple[str, str]]:
    sv = m.get("sv") or {}
    callers = sv.get("callers") or []
    high_conf = sv.get("high_confidence_claim", False)
    if high_conf and len(callers) < 2:
        return [(
            "BLOCK",
            f"sv.high_confidence_claim with only {len(callers)} caller(s) -- "
            "require >=2 caller intersection (read+assembly axes)"
        )]
    return []


CHECKS: dict[str, Callable[[dict, dict], list[tuple[str, str]]]] = {
    "ASM_BUSCO_001": chk_ASM_BUSCO_001,
    "ASM_BUSCO_002": chk_ASM_BUSCO_002,
    "ASM_BUSCO_003": chk_ASM_BUSCO_003,
    "ASM_QV_001": chk_ASM_QV_001,
    "ASM_QV_002": chk_ASM_QV_002,
    "ASM_QV_003": chk_ASM_QV_003,
    "ASM_LAI_001": chk_ASM_LAI_001,
    "ASM_LAI_002": chk_ASM_LAI_002,
    "ASM_REPEAT_001": chk_ASM_REPEAT_001,
    "ASM_N50_001": chk_ASM_N50_001,
    "ASM_N50_002": chk_ASM_N50_002,
    "KMERIA_001": chk_KMERIA_001,
    "KMERIA_002": chk_KMERIA_002,
    "SV_001": chk_SV_001,
}


# ---------- additional schema-level missing-field checks ---------------------


def chk_required_fields(manifest: dict) -> list[tuple[str, str]]:
    """Catch fields the rule table does not enumerate but the schema requires."""
    out: list[tuple[str, str]] = []
    for asm in list_of(manifest, "assemblies"):
        for f in REQUIRED_ASSEMBLY:
            if not field_present(asm, f):
                out.append(("MISSING", f"assemblies[{asm.get('key', '?')}].{f}"))
        if not field_present(asm, "contig_N50") and not field_present(asm, "scaffold_N50"):
            out.append(("MISSING", f"assemblies[{asm.get('key', '?')}].(contig_N50|scaffold_N50)"))
    for entry in list_of(manifest, "lai"):
        for f in REQUIRED_LAI:
            if not field_present(entry, f):
                out.append(("MISSING", f"lai[{entry.get('assembly_key', '?')}].{f}"))
    return out


# ---------- runner -----------------------------------------------------------


def run(manifest: dict, rules: list[dict[str, str]], anchors: dict) -> tuple[str, list[tuple[str, str, str]]]:
    """Return (overall_status, [(severity, rule_id, detail), ...]).

    overall_status is one of PASS / WARN / BLOCK.
    """
    findings: list[tuple[str, str, str]] = []
    for rule in rules:
        rule_id = rule.get("rule_id", "").strip()
        if not rule_id:
            continue
        check = CHECKS.get(rule_id)
        if check is None:
            findings.append(("WARN", rule_id, f"rule {rule_id} declared in TSV but no check function -- skipped"))
            continue
        for severity, detail in check(manifest, anchors):
            findings.append((severity, rule_id, detail))

    # Manifest-level required fields not enumerated by individual rules
    for severity, detail in chk_required_fields(manifest):
        findings.append((severity, "SCHEMA", detail))

    if any(s == "BLOCK" for s, _, _ in findings):
        return "BLOCK", findings
    if any(s in {"WARN", "MISSING"} for s, _, _ in findings):
        return "WARN", findings
    # NOTE / SUGGEST alone are informational and do not gate the claim.
    return "PASS", findings


def render(status: str, findings: list[tuple[str, str, str]]) -> str:
    lines: list[str] = [f"STATUS\t{status}"]

    def section(label: str, kept: list[tuple[str, str, str]]) -> None:
        if not kept:
            return
        lines.append(f"\n{label}:")
        for severity, rule_id, detail in kept:
            lines.append(f"  {rule_id}\t{detail}")

    blocks = [f for f in findings if f[0] == "BLOCK"]
    warns = [f for f in findings if f[0] == "WARN"]
    notes = [f for f in findings if f[0] == "NOTE"]
    suggests = [f for f in findings if f[0] == "SUGGEST"]
    missing = [f for f in findings if f[0] == "MISSING"]
    section("BLOCKED", blocks)
    section("WARNINGS", warns)
    section("NOTES", notes)
    section("SUGGESTIONS", suggests)
    section("MISSING", missing)

    if status == "PASS":
        lines.append("\nALL RULES SATISFIED -- publication-grade claims may proceed within scope.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a result manifest against bio-workflow interpretation rules.")
    parser.add_argument("--manifest", required=True, help="Path to result_manifest.yaml")
    parser.add_argument("--rules", default=str(DEFAULT_RULES), help="Path to interpretation-rules.tsv")
    parser.add_argument("--anchors", default=str(DEFAULT_ANCHORS), help="Path to project-anchors.yaml")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        sys.stderr.write(f"manifest not found: {manifest_path}\n")
        return 2
    rules_path = Path(args.rules)
    if not rules_path.exists():
        sys.stderr.write(f"rules not found: {rules_path}\n")
        return 2
    anchors_path = Path(args.anchors)
    if not anchors_path.exists():
        sys.stderr.write(f"anchors not found: {anchors_path}\n")
        return 2

    manifest = load_yaml(manifest_path)
    rules = load_rules(rules_path)
    anchors = load_yaml(anchors_path)

    status, findings = run(manifest, rules, anchors)
    print(render(status, findings))

    return {"PASS": 0, "WARN": 1, "BLOCK": 2}[status]


if __name__ == "__main__":
    raise SystemExit(main())
