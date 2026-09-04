#!/usr/bin/env python3
"""Prepare a strict, deterministic Bioflow-to-PaperPlot TSV/JSON handoff.

The script validates units and directions, performs only explicitly declared
length conversions, ranks heterogeneous metrics within metric (never by raw-value
means), and chooses reproducible key samples.  It does not draw figures.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

REQUIRED_COLUMNS = ("Sample_ID", "Metric", "Value", "Unit", "Direction")
OPTIONAL_COLUMNS = ("Group", "Weight", "Highlight", "Evidence_Path", "Claim_Status")
OUTPUT_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS + (
    "Rank_Score",
    "Metric_Coverage",
    "Key_Sample",
    "Key_Reason",
)
UNIT_TARGET_COLUMNS = ("Metric", "Source_Unit", "Target_Unit")
DIRECTION_MAP = {
    "higher_better": "Higher_better",
    "higher-is-better": "Higher_better",
    "higher": "Higher_better",
    "lower_better": "Lower_better",
    "lower-is-better": "Lower_better",
    "lower": "Lower_better",
    "neutral": "Neutral",
}
LENGTH_TO_BP = {"bp": 1.0, "kb": 1e3, "mb": 1e6, "gb": 1e9}
PROTECTED_RE = re.compile(r"^/data9/home/[^/]+/(?:data|tools)(?:/|$)")


class HandoffError(ValueError):
    """Expected contract or output-safety failure."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_tsv(path: Path, required: tuple[str, ...], allowed: tuple[str, ...]) -> list[dict[str, str]]:
    if not path.exists() or not path.is_file() or not os.access(path, os.R_OK):
        raise HandoffError(f"input is missing or unreadable: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        first = handle.readline()
        if not first:
            raise HandoffError(f"input is empty: {path}")
        if "\t" not in first:
            if "," in first:
                raise HandoffError(f"CSV/comma-delimited input is refused; provide a true TSV: {path}")
            raise HandoffError(f"header has no tab delimiter: {path}")
        handle.seek(0)
        reader = csv.DictReader(handle, delimiter="\t")
        header = reader.fieldnames or []
        if len(header) != len(set(header)):
            raise HandoffError(f"duplicate header columns: {path}")
        missing = [column for column in required if column not in header]
        unknown = [column for column in header if column not in allowed]
        if missing:
            raise HandoffError(f"missing required columns {missing}: {path}")
        if unknown:
            raise HandoffError(f"unknown columns {unknown}: {path}")
        rows: list[dict[str, str]] = []
        for line_number, row in enumerate(reader, 2):
            if None in row:
                raise HandoffError(f"{path}:{line_number}: too many tab-separated fields")
            cleaned = {column: (row.get(column) or "").strip() for column in header}
            if not any(cleaned.values()):
                raise HandoffError(f"{path}:{line_number}: blank data row")
            rows.append(cleaned)
    if not rows:
        raise HandoffError(f"input has a header but no data rows: {path}")
    return rows


def parse_finite(value: str, label: str) -> float:
    try:
        number = float(value)
    except ValueError as exc:
        raise HandoffError(f"{label} must be numeric: {value!r}") from exc
    if not math.isfinite(number):
        raise HandoffError(f"{label} must be finite: {value!r}")
    return number


def canonical_number(value: float) -> str:
    if value == 0:
        value = 0.0
    return format(value, ".15g")


def parse_bool(value: str, label: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"", "0", "false", "no", "n"}:
        return False
    if normalized in {"1", "true", "yes", "y"}:
        return True
    raise HandoffError(f"{label} must be true/false: {value!r}")


def normalize_direction(value: str, label: str) -> str:
    key = value.strip().lower().replace(" ", "_")
    if key not in DIRECTION_MAP:
        raise HandoffError(
            f"{label} must be Higher_better, Lower_better, or Neutral: {value!r}"
        )
    return DIRECTION_MAP[key]


def validate_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    normalized: list[dict[str, Any]] = []
    metric_specs: dict[str, dict[str, Any]] = {}
    sample_groups: dict[str, str] = {}
    seen: set[tuple[str, str]] = set()
    for index, source in enumerate(rows, 2):
        sample = source["Sample_ID"]
        metric = source["Metric"]
        unit = source["Unit"]
        if not sample or not metric:
            raise HandoffError(f"row {index}: Sample_ID and Metric must be non-empty")
        if not unit:
            raise HandoffError(f"row {index}: Unit is required for metric {metric}; units are never guessed")
        key = (sample, metric)
        if key in seen:
            raise HandoffError(
                f"duplicate Sample_ID+Metric observation {sample!r}+{metric!r}; aggregate explicitly upstream"
            )
        seen.add(key)
        direction = normalize_direction(source["Direction"], f"row {index} Direction")
        value = parse_finite(source["Value"], f"row {index} Value")
        weight = parse_finite(source.get("Weight", "") or "1", f"row {index} Weight")
        if weight <= 0:
            raise HandoffError(f"row {index} Weight must be >0")
        group = source.get("Group", "")
        if sample in sample_groups and sample_groups[sample] != group:
            raise HandoffError(f"Sample_ID {sample!r} has conflicting Group values")
        sample_groups[sample] = group
        spec = metric_specs.setdefault(metric, {"Unit": unit, "Direction": direction, "Weight": weight})
        for field, observed in (("Unit", unit), ("Direction", direction), ("Weight", weight)):
            if spec[field] != observed:
                raise HandoffError(
                    f"metric {metric!r} has conflicting {field}: {spec[field]!r} vs {observed!r}"
                )
        claim_status = source.get("Claim_Status", "")
        if claim_status and claim_status not in {"supported", "uncertain", "blocked"}:
            raise HandoffError(
                f"row {index} Claim_Status must be supported, uncertain, blocked, or empty"
            )
        row: dict[str, Any] = {column: source.get(column, "") for column in REQUIRED_COLUMNS + OPTIONAL_COLUMNS}
        row.update(
            {
                "Value_Number": value,
                "Direction": direction,
                "Weight_Number": weight,
                "Highlight_Bool": parse_bool(source.get("Highlight", ""), f"row {index} Highlight"),
            }
        )
        normalized.append(row)
    return normalized, metric_specs


def load_unit_targets(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    rows = read_tsv(path, UNIT_TARGET_COLUMNS, UNIT_TARGET_COLUMNS)
    targets: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows, 2):
        metric = row["Metric"]
        source = row["Source_Unit"]
        target = row["Target_Unit"]
        if not metric or not source or not target:
            raise HandoffError(f"{path}:{index}: unit target fields must be non-empty")
        if metric in targets:
            raise HandoffError(f"{path}:{index}: duplicate unit target for metric {metric!r}")
        source_key, target_key = source.lower(), target.lower()
        if source_key not in LENGTH_TO_BP or target_key not in LENGTH_TO_BP:
            raise HandoffError(
                f"{path}:{index}: only audited bp/kb/Mb/Gb conversions are supported"
            )
        factor = LENGTH_TO_BP[source_key] / LENGTH_TO_BP[target_key]
        targets[metric] = {
            "Metric": metric,
            "Source_Unit": source,
            "Target_Unit": target,
            "Factor": factor,
        }
    return targets


def apply_unit_targets(
    rows: list[dict[str, Any]],
    metric_specs: dict[str, dict[str, Any]],
    targets: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    for metric, target in targets.items():
        if metric not in metric_specs:
            raise HandoffError(f"unit target references absent metric {metric!r}")
        observed = metric_specs[metric]["Unit"]
        if observed != target["Source_Unit"]:
            raise HandoffError(
                f"unit target for {metric!r} expects {target['Source_Unit']!r}, observed {observed!r}"
            )
        metric_specs[metric]["Unit"] = target["Target_Unit"]
        for row in rows:
            if row["Metric"] == metric:
                row["Value_Number"] *= target["Factor"]
                row["Unit"] = target["Target_Unit"]
    return [targets[key] for key in sorted(targets)]


def fractional_rank_scores(values: dict[str, float], higher_better: bool) -> dict[str, float]:
    """Return tie-aware scores in [0,1], where 1 is best."""
    ordered = sorted(values.items(), key=lambda item: ((-item[1]) if higher_better else item[1], item[0]))
    ranks: dict[str, float] = {}
    position = 0
    while position < len(ordered):
        end = position + 1
        while end < len(ordered) and ordered[end][1] == ordered[position][1]:
            end += 1
        average_rank = ((position + 1) + end) / 2.0
        score = 1.0 if len(ordered) == 1 else (len(ordered) - average_rank) / (len(ordered) - 1)
        for sample, _ in ordered[position:end]:
            ranks[sample] = score
        position = end
    return ranks


def calculate_ranks(
    rows: list[dict[str, Any]], metric_specs: dict[str, dict[str, Any]]
) -> tuple[dict[str, dict[str, float | None]], dict[str, dict[str, float]], list[str]]:
    samples = sorted({row["Sample_ID"] for row in rows})
    directional_metrics = sorted(
        metric for metric, spec in metric_specs.items() if spec["Direction"] != "Neutral"
    )
    per_metric: dict[str, dict[str, float]] = {}
    for metric in directional_metrics:
        values = {
            row["Sample_ID"]: row["Value_Number"] for row in rows if row["Metric"] == metric
        }
        per_metric[metric] = fractional_rank_scores(
            values, metric_specs[metric]["Direction"] == "Higher_better"
        )
    aggregate: dict[str, dict[str, float | None]] = {}
    for sample in samples:
        numerator = denominator = 0.0
        present = 0
        for metric in directional_metrics:
            if sample in per_metric[metric]:
                weight = float(metric_specs[metric]["Weight"])
                numerator += per_metric[metric][sample] * weight
                denominator += weight
                present += 1
        aggregate[sample] = {
            "Rank_Score": (numerator / denominator) if denominator else None,
            "Metric_Coverage": (present / len(directional_metrics)) if directional_metrics else 0.0,
        }
    return aggregate, per_metric, directional_metrics


def select_key_samples(
    rows: list[dict[str, Any]],
    aggregate: dict[str, dict[str, float | None]],
    max_key_samples: int,
) -> tuple[list[str], dict[str, list[str]]]:
    samples = sorted(aggregate)
    highlights = sorted({row["Sample_ID"] for row in rows if row["Highlight_Bool"]})
    if len(highlights) > max_key_samples:
        raise HandoffError(
            f"{len(highlights)} highlighted samples exceed --max-key-samples={max_key_samples}"
        )
    reasons: dict[str, list[str]] = defaultdict(list)
    selected: list[str] = []

    def add(sample: str, reason: str) -> None:
        if reason not in reasons[sample]:
            reasons[sample].append(reason)
        if sample not in selected and len(selected) < max_key_samples:
            selected.append(sample)

    for sample in highlights:
        add(sample, "Highlight")
    ranked = sorted(
        (sample for sample in samples if aggregate[sample]["Rank_Score"] is not None),
        key=lambda sample: (-float(aggregate[sample]["Rank_Score"]), sample),
    )
    if ranked:
        add(ranked[0], "Global_best")
        add(ranked[-1], "Global_worst")
    groups: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        if row["Group"]:
            groups[row["Group"]].add(row["Sample_ID"])
    for group in sorted(groups):
        group_ranked = [sample for sample in ranked if sample in groups[group]]
        if group_ranked:
            add(group_ranked[0], f"Group_best:{group}")
    left, right = 0, len(ranked) - 1
    while len(selected) < max_key_samples and left <= right:
        add(ranked[left], "Rank_extreme_high")
        left += 1
        if len(selected) < max_key_samples and left <= right:
            add(ranked[right], "Rank_extreme_low")
            right -= 1
    return selected, {sample: reasons[sample] for sample in selected}


def find_v2_project_root(start: Path) -> Path | None:
    current = start.resolve(strict=False)
    for _ in range(8):
        marker = current / "config" / "Project_Layout.tsv"
        if marker.is_file() and not marker.is_symlink():
            try:
                lines = marker.read_text(encoding="utf-8").splitlines()[:2]
            except (OSError, UnicodeError):
                return None
            if len(lines) == 2 and lines[1].startswith("bioflow.layout.v2\t"):
                return current
            return None
        if current.parent == current:
            break
        current = current.parent
    return None


def path_is_in_project_tmp(path: Path, project: Path | None) -> bool:
    if project is None:
        return False
    try:
        path.relative_to(project / "tmp")
    except ValueError:
        return False
    return True


def resolve_evidence_readiness(
    rows: list[dict[str, Any]], input_dir: Path, figure_role: str,
    project_root: Path | None = None,
) -> dict[str, Any]:
    statuses = sorted({row["Claim_Status"] for row in rows if row["Claim_Status"]})
    project_root = project_root or find_v2_project_root(input_dir)
    missing_evidence: list[str] = []
    for row in rows:
        value = row["Evidence_Path"]
        if not value:
            continue
        raw = Path(value).expanduser()
        path = raw if raw.is_absolute() else input_dir / raw
        path = path.resolve(strict=False)
        if figure_role == "publication" and path_is_in_project_tmp(path, project_root):
            raise HandoffError(
                f"publication handoff Evidence_Path must not come from disposable tmp/: {path}"
            )
        if not path.exists() or not path.is_file() or not os.access(path, os.R_OK):
            missing_evidence.append(str(path))
    if figure_role == "publication" and ("blocked" in statuses or "uncertain" in statuses):
        raise HandoffError(
            f"publication handoff contains non-supported Claim_Status values: {statuses}"
        )
    if figure_role == "publication" and missing_evidence:
        raise HandoffError(
            f"publication handoff has missing/unreadable Evidence_Path entries: {sorted(set(missing_evidence))}"
        )
    if "blocked" in statuses or missing_evidence:
        status = "blocked"
    elif "uncertain" in statuses:
        status = "review_required"
    else:
        status = "ready"
    return {
        "Status": status,
        "Claim_Statuses": statuses,
        "Missing_Evidence": sorted(set(missing_evidence)),
    }


def validate_output_paths(
    output_tsv: Path,
    output_json: Path,
    inputs: Iterable[Path],
    force: bool,
) -> tuple[Path, Path]:
    resolved_inputs = {path.expanduser().resolve(strict=False) for path in inputs}
    outputs = [output_tsv.expanduser(), output_json.expanduser()]
    resolved_outputs = [path.resolve(strict=False) for path in outputs]
    if resolved_outputs[0] == resolved_outputs[1]:
        raise HandoffError("--output-tsv and --output-json must be different paths")
    for raw, target in zip(outputs, resolved_outputs):
        if raw.is_symlink():
            raise HandoffError(f"output path must not be a symbolic link: {raw}")
        if target in resolved_inputs:
            raise HandoffError(f"output path resolves to an input: {raw}")
        if PROTECTED_RE.match(str(target)):
            raise HandoffError(f"refusing protected output path: {target}")
        if not target.parent.exists() or not target.parent.is_dir():
            raise HandoffError(f"output parent must already exist: {target.parent}")
        if not os.access(target.parent, os.W_OK):
            raise HandoffError(f"output parent is not writable: {target.parent}")
        if target.exists():
            if not target.is_file():
                raise HandoffError(f"existing output is not a regular file: {target}")
            if not force:
                raise HandoffError(f"output exists (use --force only after approval): {target}")
    return resolved_outputs[0], resolved_outputs[1]


def render_tsv(
    rows: list[dict[str, Any]],
    aggregate: dict[str, dict[str, float | None]],
    key_reasons: dict[str, list[str]],
) -> str:
    ordered = sorted(
        rows,
        key=lambda row: (
            aggregate[row["Sample_ID"]]["Rank_Score"] is None,
            -(float(aggregate[row["Sample_ID"]]["Rank_Score"] or 0.0)),
            row["Sample_ID"],
            row["Metric"],
        ),
    )
    buffer: list[str] = []
    # csv.writer needs a file-like object; StringIO keeps newline handling exact.
    import io

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=OUTPUT_COLUMNS, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    for row in ordered:
        sample = row["Sample_ID"]
        score = aggregate[sample]["Rank_Score"]
        output = {column: row.get(column, "") for column in REQUIRED_COLUMNS + OPTIONAL_COLUMNS}
        output["Value"] = canonical_number(row["Value_Number"])
        output["Weight"] = canonical_number(row["Weight_Number"])
        output["Highlight"] = "true" if row["Highlight_Bool"] else "false"
        output.update(
            {
                "Rank_Score": "NA" if score is None else format(float(score), ".6f"),
                "Metric_Coverage": format(float(aggregate[sample]["Metric_Coverage"]), ".6f"),
                "Key_Sample": "true" if sample in key_reasons else "false",
                "Key_Reason": ";".join(key_reasons.get(sample, [])),
            }
        )
        writer.writerow(output)
    buffer.append(stream.getvalue())
    return "".join(buffer)


def _stage(target: Path, content: str) -> Path:
    descriptor, name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    path = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        return path
    except Exception:
        path.unlink(missing_ok=True)
        raise


def atomic_write_pair(targets: list[tuple[Path, str]]) -> None:
    staged: dict[Path, Path] = {}
    backups: dict[Path, Path] = {}
    committed: list[Path] = []
    try:
        for target, content in targets:
            staged[target] = _stage(target, content)
        for target, _ in targets:
            if target.exists():
                descriptor, name = tempfile.mkstemp(
                    prefix=f".{target.name}.", suffix=".backup", dir=target.parent
                )
                os.close(descriptor)
                backup = Path(name)
                backup.unlink()
                os.replace(target, backup)
                backups[target] = backup
        try:
            for target, _ in targets:
                os.replace(staged[target], target)
                committed.append(target)
        except Exception:
            for target in committed:
                target.unlink(missing_ok=True)
            for target, backup in backups.items():
                if backup.exists():
                    os.replace(backup, target)
            raise
        for backup in backups.values():
            backup.unlink(missing_ok=True)
    finally:
        for path in staged.values():
            path.unlink(missing_ok=True)
        for target, backup in backups.items():
            if backup.exists() and not target.exists():
                os.replace(backup, target)
            else:
                backup.unlink(missing_ok=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare strict TSV/JSON data for PaperPlot delegation.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-tsv", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--figure-role", choices=["qc", "exploratory", "publication"], required=True)
    parser.add_argument("--unit-targets")
    parser.add_argument("--max-key-samples", type=int, default=8)
    parser.add_argument("--force", action="store_true")
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.max_key_samples < 1:
        raise HandoffError("--max-key-samples must be >=1")
    input_path = Path(args.input).expanduser()
    unit_path = Path(args.unit_targets).expanduser() if args.unit_targets else None
    input_files = [input_path] + ([unit_path] if unit_path else [])
    output_tsv, output_json = validate_output_paths(
        Path(args.output_tsv), Path(args.output_json), input_files, args.force
    )
    rows = read_tsv(input_path, REQUIRED_COLUMNS, REQUIRED_COLUMNS + OPTIONAL_COLUMNS)
    rows, metric_specs = validate_rows(rows)
    targets = load_unit_targets(unit_path)
    conversions = apply_unit_targets(rows, metric_specs, targets)
    aggregate, per_metric, directional_metrics = calculate_ranks(rows, metric_specs)
    selected, key_reasons = select_key_samples(rows, aggregate, args.max_key_samples)
    candidate_roots = {
        root for root in (
            find_v2_project_root(input_path.resolve().parent),
            find_v2_project_root(output_tsv.parent),
            find_v2_project_root(output_json.parent),
        ) if root is not None
    }
    if len(candidate_roots) > 1:
        raise HandoffError(
            "input and output paths belong to different layout-v2 projects: "
            + ", ".join(str(root) for root in sorted(candidate_roots))
        )
    project_root = next(iter(candidate_roots), None)
    readiness = resolve_evidence_readiness(
        rows, input_path.resolve().parent, args.figure_role, project_root
    )
    all_metrics = sorted(metric_specs)
    missing_metrics = {
        sample: sorted(
            set(all_metrics)
            - {row["Metric"] for row in rows if row["Sample_ID"] == sample}
        )
        for sample in sorted(aggregate)
    }
    metadata = {
        "Schema_Version": "paperplot_handoff.v1",
        "Figure_Role": args.figure_role,
        "Input": {
            "Path": str(input_path.resolve()),
            "SHA256": sha256_file(input_path),
            "Unit_Targets_Path": str(unit_path.resolve()) if unit_path else None,
            "Unit_Targets_SHA256": sha256_file(unit_path) if unit_path else None,
        },
        "Unit_Conversions": conversions,
        "Metric_Spec": {metric: metric_specs[metric] for metric in sorted(metric_specs)},
        "Rank_Rules": {
            "Method": "fractional_rank_within_metric_then_coverage_aware_weighted_mean",
            "Best_Score": 1.0,
            "Worst_Score": 0.0,
            "Neutral_Excluded": True,
            "Directional_Metrics": directional_metrics,
            "Raw_Value_Means_Forbidden": True,
        },
        "Per_Metric_Rank": {
            metric: {sample: per_metric[metric][sample] for sample in sorted(per_metric[metric])}
            for metric in sorted(per_metric)
        },
        "Sample_Rank": {sample: aggregate[sample] for sample in sorted(aggregate)},
        "Missing_Metrics": missing_metrics,
        "Key_Samples": [
            {"Sample_ID": sample, "Reasons": key_reasons[sample]} for sample in selected
        ],
        "Readiness": readiness,
    }
    tsv_text = render_tsv(rows, aggregate, key_reasons)
    json_text = json.dumps(metadata, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    atomic_write_pair([(output_tsv, tsv_text), (output_json, json_text)])
    return metadata


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        metadata = run(args)
    except (HandoffError, OSError, ValueError) as exc:
        sys.stderr.write(f"[ERROR] {exc}\n")
        return 2
    sys.stderr.write(
        f"[paperplot_handoff] {metadata['Readiness']['Status']} | "
        f"{len(metadata['Sample_Rank'])} samples | "
        f"{len(metadata['Metric_Spec'])} metrics\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
