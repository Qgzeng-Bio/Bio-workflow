#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "prepare_paperplot_handoff.py"
SPEC = importlib.util.spec_from_file_location("paperplot_handoff", SCRIPT)
assert SPEC and SPEC.loader
handoff = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(handoff)


def passed(label: str) -> None:
    print(f"PASS | {label}")


def expect_error(fragment: str, function, *args, **kwargs) -> None:
    try:
        function(*args, **kwargs)
    except handoff.HandoffError as exc:
        assert fragment in str(exc), (fragment, str(exc))
    else:
        raise AssertionError(f"expected HandoffError containing {fragment!r}")


def write_tsv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def read_output(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


with tempfile.TemporaryDirectory(prefix="bioflow-paperplot-test.") as tmp_name:
    tmp = Path(tmp_name)
    header = [
        "Sample_ID",
        "Metric",
        "Value",
        "Unit",
        "Direction",
        "Group",
        "Weight",
        "Highlight",
        "Evidence_Path",
        "Claim_Status",
    ]
    input_path = tmp / "Genome_Quality_Metrics.tsv"
    rows = [
        ["S1", "N50", "1000000000", "bp", "Higher_better", "A", "1", "false", "", "supported"],
        ["S1", "Gap_Count", "100", "count", "Lower_better", "A", "1", "false", "", "supported"],
        ["S1", "Genome_Size", "1200000000", "bp", "Neutral", "A", "1", "false", "", "supported"],
        ["S2", "N50", "2", "bp", "Higher_better", "A", "1", "true", "", "supported"],
        ["S2", "Gap_Count", "50", "count", "Lower_better", "A", "1", "true", "", "supported"],
        ["S2", "Genome_Size", "1300000000", "bp", "Neutral", "A", "1", "true", "", "supported"],
        ["S3", "N50", "1", "bp", "Higher_better", "B", "1", "false", "", "supported"],
        ["S3", "Gap_Count", "1", "count", "Lower_better", "B", "1", "false", "", "supported"],
        ["S3", "Genome_Size", "1400000000", "bp", "Neutral", "B", "1", "false", "", "supported"],
    ]
    write_tsv(input_path, header, rows)
    output_tsv = tmp / "FigA_PaperPlot_Input.tsv"
    output_json = tmp / "FigA_PaperPlot_Handoff.json"
    command = [
        sys.executable,
        str(SCRIPT),
        "--input",
        str(input_path),
        "--output-tsv",
        str(output_tsv),
        "--output-json",
        str(output_json),
        "--figure-role",
        "publication",
        "--max-key-samples",
        "3",
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    output_rows = read_output(output_tsv)
    assert len(output_rows) == len(rows)
    assert list(output_rows[0]) == list(handoff.OUTPUT_COLUMNS)
    metadata = json.loads(output_json.read_text())
    assert metadata["Input"]["SHA256"] == hashlib.sha256(input_path.read_bytes()).hexdigest()
    assert metadata["Readiness"]["Status"] == "ready"
    assert metadata["Rank_Rules"]["Raw_Value_Means_Forbidden"] is True
    assert metadata["Rank_Rules"]["Directional_Metrics"] == ["Gap_Count", "N50"]
    scores = metadata["Sample_Rank"]
    assert scores["S1"]["Rank_Score"] == scores["S2"]["Rank_Score"] == scores["S3"]["Rank_Score"] == 0.5
    assert all(item["Metric_Coverage"] == 1.0 for item in scores.values())
    assert metadata["Key_Samples"][0]["Sample_ID"] == "S2"
    assert "Highlight" in metadata["Key_Samples"][0]["Reasons"]
    assert any("Group_best:B" in item["Reasons"] for item in metadata["Key_Samples"])
    passed("valid TSV, rank-only aggregate, stable highlight/group key samples")

    # Neutral raw values never affect rank scores.
    changed_neutral = tmp / "changed_neutral.tsv"
    changed_rows = [row[:] for row in rows]
    for row in changed_rows:
        if row[1] == "Genome_Size":
            row[2] = str(float(row[2]) * 1000000)
    write_tsv(changed_neutral, header, changed_rows)
    neutral_tsv, neutral_json = tmp / "neutral.tsv", tmp / "neutral.json"
    neutral_command = [
        value if value != str(input_path) else str(changed_neutral) for value in command
    ]
    neutral_command = [value if value != str(output_tsv) else str(neutral_tsv) for value in neutral_command]
    neutral_command = [value if value != str(output_json) else str(neutral_json) for value in neutral_command]
    changed = subprocess.run(neutral_command, check=False, capture_output=True, text=True)
    assert changed.returncode == 0, changed.stderr
    assert json.loads(neutral_json.read_text())["Sample_Rank"] == metadata["Sample_Rank"]
    passed("Neutral metric excluded from aggregate rank")

    # Explicit bp->Mb converts numbers and labels together; absent targets preserve values.
    targets = tmp / "Unit_Targets.tsv"
    write_tsv(targets, ["Metric", "Source_Unit", "Target_Unit"], [["N50", "bp", "Mb"]])
    converted_tsv, converted_json = tmp / "converted.tsv", tmp / "converted.json"
    conversion_command = command[:-2] + [
        "--unit-targets",
        str(targets),
        "--max-key-samples",
        "3",
    ]
    conversion_command = [
        value if value != str(output_tsv) else str(converted_tsv) for value in conversion_command
    ]
    conversion_command = [
        value if value != str(output_json) else str(converted_json) for value in conversion_command
    ]
    converted = subprocess.run(conversion_command, check=False, capture_output=True, text=True)
    assert converted.returncode == 0, converted.stderr
    converted_rows = read_output(converted_tsv)
    s1_n50 = next(row for row in converted_rows if row["Sample_ID"] == "S1" and row["Metric"] == "N50")
    assert s1_n50["Value"] == "1000" and s1_n50["Unit"] == "Mb"
    conversion_meta = json.loads(converted_json.read_text())
    assert conversion_meta["Unit_Conversions"][0]["Factor"] == 1e-6
    original_n50 = next(row for row in output_rows if row["Sample_ID"] == "S1" and row["Metric"] == "N50")
    assert original_n50["Value"] == "1000000000" and original_n50["Unit"] == "bp"
    passed("declared bp-to-Mb conversion changes value+label; default preserves both")

    # Re-running without force refuses; approved force is byte-for-byte deterministic.
    old_tsv, old_json = output_tsv.read_bytes(), output_json.read_bytes()
    refused = subprocess.run(command, check=False, capture_output=True, text=True)
    assert refused.returncode == 2 and "output exists" in refused.stderr
    assert output_tsv.read_bytes() == old_tsv and output_json.read_bytes() == old_json
    forced = subprocess.run(command + ["--force"], check=False, capture_output=True, text=True)
    assert forced.returncode == 0, forced.stderr
    assert output_tsv.read_bytes() == old_tsv and output_json.read_bytes() == old_json
    passed("existing outputs refused; force replacement deterministic")

    # Strict delimiter, unit, direction, duplicate, and conversion failures.
    csv_path = tmp / "bad.csv"
    csv_path.write_text("Sample_ID,Metric,Value,Unit,Direction\nS1,N50,1,bp,Higher_better\n")
    expect_error(
        "CSV/comma-delimited",
        handoff.read_tsv,
        csv_path,
        handoff.REQUIRED_COLUMNS,
        handoff.REQUIRED_COLUMNS + handoff.OPTIONAL_COLUMNS,
    )
    missing_unit = [
        {"Sample_ID": "S1", "Metric": "N50", "Value": "1", "Unit": "", "Direction": "Higher_better"}
    ]
    expect_error("Unit is required", handoff.validate_rows, missing_unit)
    conflicting = [
        {"Sample_ID": "S1", "Metric": "N50", "Value": "1", "Unit": "bp", "Direction": "Higher_better"},
        {"Sample_ID": "S2", "Metric": "N50", "Value": "2", "Unit": "Mb", "Direction": "Higher_better"},
    ]
    expect_error("conflicting Unit", handoff.validate_rows, conflicting)
    duplicate = [
        {"Sample_ID": "S1", "Metric": "N50", "Value": "1", "Unit": "bp", "Direction": "Higher_better"},
        {"Sample_ID": "S1", "Metric": "N50", "Value": "2", "Unit": "bp", "Direction": "Higher_better"},
    ]
    expect_error("duplicate Sample_ID+Metric", handoff.validate_rows, duplicate)
    bad_targets = tmp / "bad_targets.tsv"
    write_tsv(bad_targets, ["Metric", "Source_Unit", "Target_Unit"], [["N50", "bp", "percent"]])
    expect_error("only audited", handoff.load_unit_targets, bad_targets)
    passed("CSV, missing/conflicting unit, duplicate observation, and unknown conversion refused")

    # Output conflict, input equality, symlink, and protected path checks.
    link = tmp / "linked.tsv"
    link.symlink_to(output_tsv)
    expect_error(
        "different paths",
        handoff.validate_output_paths,
        tmp / "same",
        tmp / "same",
        [input_path],
        False,
    )
    expect_error(
        "resolves to an input",
        handoff.validate_output_paths,
        input_path,
        tmp / "fresh.json",
        [input_path],
        True,
    )
    expect_error(
        "symbolic link",
        handoff.validate_output_paths,
        link,
        tmp / "fresh.json",
        [input_path],
        True,
    )
    expect_error(
        "protected output",
        handoff.validate_output_paths,
        Path("/data9/home/qgzeng/data/FigA.tsv"),
        tmp / "fresh.json",
        [input_path],
        True,
    )
    passed("output conflict, input equality, symlink, and protected path refused")

    # Publication evidence in a layout-v2 tmp/ directory is never stable evidence.
    project = tmp / "layout_v2"
    (project / "config").mkdir(parents=True)
    (project / "results" / "01-genome-qc").mkdir(parents=True)
    (project / "tmp").mkdir()
    (project / "config" / "Project_Layout.tsv").write_text(
        "Schema_Version\tRawdata_Root\tDocumentation_Root\tManuscript_Root\tModule_Separator\n"
        "bioflow.layout.v2\trawdata\tdocs\tmanuscripts\t-\n"
    )
    temporary_evidence = project / "tmp" / "evidence.tsv"
    temporary_evidence.write_text("Metric\tValue\nN50\t1\n")
    expect_error(
        "must not come from disposable tmp/",
        handoff.resolve_evidence_readiness,
        [{"Claim_Status": "supported", "Evidence_Path": str(temporary_evidence)}],
        project / "results" / "01-genome-qc",
        "publication",
    )
    passed("layout-v2 publication handoff refuses tmp evidence")

    # An external input cannot bypass v2 tmp evidence when outputs target a v2 figure package.
    package = project / "results" / "01-genome-qc" / "figures" / "F001_Genome_QC"
    (package / "source-data").mkdir(parents=True)
    (package / "checks").mkdir()
    external_input = tmp / "external_metrics.tsv"
    external_rows = [row[:] for row in rows]
    external_rows[0][8] = str(temporary_evidence)
    write_tsv(external_input, header, external_rows)
    external_call = subprocess.run([
        sys.executable, str(SCRIPT), "--input", str(external_input),
        "--output-tsv", str(package / "source-data" / "F001_Genome_QC.tsv"),
        "--output-json", str(package / "checks" / "F001_Handoff.json"),
        "--figure-role", "publication",
    ], check=False, capture_output=True, text=True)
    assert external_call.returncode == 2 and "must not come from disposable tmp/" in external_call.stderr
    passed("external input plus v2 output still refuses tmp evidence")

print("PASS | PaperPlot handoff regression fixtures")
