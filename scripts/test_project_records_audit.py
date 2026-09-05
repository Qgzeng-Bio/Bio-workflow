#!/usr/bin/env python3
from __future__ import annotations

import csv
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "project_records_audit.py"
INIT = ROOT / "scripts" / "init_project.sh"
SPEC = importlib.util.spec_from_file_location("project_records_audit", SCRIPT)
assert SPEC and SPEC.loader
records = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = records
SPEC.loader.exec_module(records)


def cli(project: Path):
    return subprocess.run([sys.executable, str(SCRIPT), "--project", str(project), "--format", "tsv"], check=False, capture_output=True, text=True)


def write_tsv(path: Path, columns: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


with tempfile.TemporaryDirectory(prefix="bioflow-records-test.") as tmp_name:
    project = Path(tmp_name) / "project"
    initialized = subprocess.run([str(INIT), "--project", str(project), "--yes"], check=False, capture_output=True, text=True)
    assert initialized.returncode == 0, initialized.stderr
    for relative in (
        "PROJECT_STATUS.md", "CHANGELOG.md", "docs/research-log/README.md",
        "docs/research-log/TEMPLATE.md", "docs/research-log/Log_Index.tsv",
        "docs/decisions/Decision_Index.tsv",
    ):
        assert (project / relative).is_file(), relative
    clean = cli(project)
    assert clean.returncode == 0, clean.stdout + clean.stderr
    print("PASS | initialized v2 record templates pass the empty-project audit")

    module = project / "results" / "01-assembly"
    module.mkdir(parents=True)
    (module / "Assembly_Summary.tsv").write_text("Metric\tValue\nN50\t10\n", encoding="utf-8")
    log = project / "docs/research-log" / "20260811_Assembly_QC.md"
    log.write_text(
        "# Research Log: Assembly QC\n\n"
        "Research_Log_ID: R001\nDate: 2026-08-11\nAnalysis_Key: assembly\n"
        "Module_ID: NA\nTask_ID: NA\nResult_Maturity: Verified\n\n"
        "## Scientific question\nIs the assembly contiguous?\n\n"
        "## Inputs and versions\n- Assembly: V01\n\n"
        "## Exact commands and parameters\n```bash\nquast.py assembly.fa\n```\n\n"
        "## Outputs\n- Path: results/01-assembly/Assembly_Summary.tsv\n\n"
        "## Checks\n- [x] Data layer checked\n\n"
        "## Observations\nN50 is 10 bp in the fixture.\n\n"
        "## Interpretation\nThe fixture demonstrates record linkage only.\n\n"
        "## Limitations\nFixture data are synthetic.\n\n"
        "## Impact\n- Affected claims: C001\n- Affected figures/tables: NA\n\n"
        "## Next action\nReplace fixture values with accepted analysis evidence.\n",
        encoding="utf-8",
    )
    log_index = project / "docs/research-log" / "Log_Index.tsv"
    write_tsv(log_index, records.LOG_COLUMNS, [{
        "Research_Log_ID": "R001", "Date": "2026-08-11", "Filename": "20260811_Assembly_QC.md",
        "Analysis_Key": "assembly", "Module_ID": "NA", "Task_ID": "NA",
        "Result_Maturity": "Verified", "Record_Status": "Complete",
        "Title": "Assembly QC", "Notes": "",
    }])
    decision_index = project / "docs/decisions" / "Decision_Index.tsv"
    write_tsv(decision_index, records.DECISION_COLUMNS, [{
        "Decision_ID": "D001", "Date": "2026-08-11", "Decision": "Retain assembly V01",
        "Evidence_Path": "results/01-assembly/Assembly_Summary.tsv", "Affected_Modules": "M001",
        "Affected_Claims": "C001", "Status": "Accepted", "Decided_By": "tester", "Notes": "",
    }])
    populated = cli(project)
    assert populated.returncode == 0, populated.stdout + populated.stderr
    print("PASS | complete research and decision records pass with linked evidence")

    write_tsv(decision_index, records.DECISION_COLUMNS, [{
        "Decision_ID": "D001", "Date": "2026-08-11", "Decision": "Retain assembly V01",
        "Evidence_Path": "results/01-assembly", "Affected_Modules": "M001",
        "Affected_Claims": "C001", "Status": "Accepted", "Decided_By": "tester", "Notes": "",
    }])
    directory_evidence = cli(project)
    assert directory_evidence.returncode == 0, directory_evidence.stdout + directory_evidence.stderr

    write_tsv(decision_index, records.DECISION_COLUMNS, [{
        "Decision_ID": "D002", "Date": "2026-08-11", "Decision": "Replace assembly V01",
        "Evidence_Path": "NA", "Affected_Modules": "M001",
        "Affected_Claims": "C001", "Status": "Superseded", "Decided_By": "tester", "Notes": "",
    }])
    blocked = cli(project)
    assert blocked.returncode == 2 and "superseded decision must cite the evidence that changed it" in blocked.stdout
    write_tsv(decision_index, records.DECISION_COLUMNS, [{
        "Decision_ID": "D001", "Date": "2026-08-11", "Decision": "Retain assembly V01",
        "Evidence_Path": "results/01-assembly/Assembly_Summary.tsv", "Affected_Modules": "M001",
        "Affected_Claims": "C001", "Status": "Accepted", "Decided_By": "tester", "Notes": "",
    }])
    print("PASS | accepted directory evidence is valid and superseded decisions require evidence")

    bad_name = project / "docs/research-log" / "bad.md"
    bad_name.write_text("# Bad\n", encoding="utf-8")
    blocked = cli(project)
    assert blocked.returncode == 2 and "REC_LOG_NAME" in blocked.stdout
    bad_name.unlink()

    archive = project / "docs/research-log" / "archive"
    archive.mkdir()
    (archive / "20260902_Escape.md").write_text("# Escape\n", encoding="utf-8")
    blocked = cli(project)
    assert blocked.returncode == 2 and "research-log subdirectories are forbidden" in blocked.stdout
    (archive / "20260902_Escape.md").unlink()
    archive.rmdir()

    write_tsv(log_index, records.LOG_COLUMNS, [])
    blocked = cli(project)
    assert blocked.returncode == 2 and "research log is not indexed: R001" in blocked.stdout
    write_tsv(log_index, records.LOG_COLUMNS, [{
        "Research_Log_ID": "R001", "Date": "2026-08-11", "Filename": "20260811_Assembly_QC.md",
        "Analysis_Key": "assembly", "Module_ID": "NA", "Task_ID": "NA",
        "Result_Maturity": "Verified", "Record_Status": "Complete",
        "Title": "Assembly QC", "Notes": "",
    }])

    original_log = log.read_text(encoding="utf-8")
    log.write_text(original_log.replace("results/01-assembly/Assembly_Summary.tsv", "missing.tsv"), encoding="utf-8")
    blocked = cli(project)
    assert blocked.returncode == 2 and "formal output is missing-or-unreadable" in blocked.stdout
    log.write_text(original_log.replace("results/01-assembly/Assembly_Summary.tsv", "tmp/disposable.tsv"), encoding="utf-8")
    blocked = cli(project)
    assert blocked.returncode == 2 and "REC_LOG_TMP" in blocked.stdout
    log.write_text(original_log.replace("## Limitations\nFixture data are synthetic.", "## Limitations\nUNKNOWN"), encoding="utf-8")
    blocked = cli(project)
    assert blocked.returncode == 2 and "REC_LOG_FORMAL" in blocked.stdout
    log.write_text(original_log, encoding="utf-8")

    write_tsv(decision_index, records.DECISION_COLUMNS, [{
        "Decision_ID": "D001", "Date": "2026-08-11", "Decision": "Retain assembly V01",
        "Evidence_Path": "NA", "Affected_Modules": "M001",
        "Affected_Claims": "C001", "Status": "Accepted", "Decided_By": "tester", "Notes": "",
    }])
    blocked = cli(project)
    assert blocked.returncode == 2 and "accepted decision must name readable non-tmp evidence" in blocked.stdout

    nested_tmp = project / "results" / "01-assembly" / "tmp"
    nested_tmp.mkdir()
    (nested_tmp / "Evidence.tsv").write_text("Metric\tValue\n", encoding="utf-8")
    write_tsv(decision_index, records.DECISION_COLUMNS, [{
        "Decision_ID": "D001", "Date": "2026-08-11", "Decision": "Retain assembly V01",
        "Evidence_Path": "results/01-assembly/tmp/Evidence.tsv", "Affected_Modules": "M001",
        "Affected_Claims": "C001", "Status": "Accepted", "Decided_By": "tester", "Notes": "",
    }])
    blocked = cli(project)
    assert blocked.returncode == 2 and "accepted evidence is tmp" in blocked.stdout
    (nested_tmp / "Evidence.tsv").unlink()
    nested_tmp.rmdir()

    write_tsv(decision_index, records.DECISION_COLUMNS, [{
        "Decision_ID": "D001", "Date": "2026-08-11", "Decision": "Retain assembly V01",
        "Evidence_Path": "missing.tsv", "Affected_Modules": "M001",
        "Affected_Claims": "C001", "Status": "Accepted", "Decided_By": "tester", "Notes": "",
    }])
    blocked = cli(project)
    assert blocked.returncode == 2 and "REC_DECISION_EVIDENCE" in blocked.stdout
    write_tsv(decision_index, records.DECISION_COLUMNS, [{
        "Decision_ID": "D001", "Date": "2026-08-11", "Decision": "Retain assembly V01",
        "Evidence_Path": "results/01-assembly/Assembly_Summary.tsv", "Affected_Modules": "M001",
        "Affected_Claims": "C001", "Status": "Accepted", "Decided_By": "tester", "Notes": "",
    }])
    print("PASS | malformed filenames, nested directories, missing index rows, tmp evidence, formal placeholders, and decision evidence are blocked")

    bom_index = project / "docs/research-log" / "Log_Index.tsv"
    bom_rows = [{
        "Research_Log_ID": "R001", "Date": "2026-08-11", "Filename": "20260811_Assembly_QC.md",
        "Analysis_Key": "assembly", "Module_ID": "NA", "Task_ID": "NA",
        "Result_Maturity": "Verified", "Record_Status": "Complete",
        "Title": "Assembly QC", "Notes": "",
    }]
    write_tsv(bom_index, records.LOG_COLUMNS, bom_rows)
    bom_index.write_bytes(b"\xef\xbb\xbf" + bom_index.read_bytes())
    with_bom = cli(project)
    assert with_bom.returncode == 0, with_bom.stdout + with_bom.stderr
    original_log = log.read_text(encoding="utf-8")
    spoofed = original_log.replace(
        "## Observations\nN50 is 10 bp in the fixture.",
        "## Observations\nN50 is 10 bp in the fixture.\nA narrative Date: 1999-01-01 is not metadata.",
    )
    log.write_text(spoofed, encoding="utf-8")
    metadata_spoof = cli(project)
    assert metadata_spoof.returncode == 0, metadata_spoof.stdout + metadata_spoof.stderr
    log.write_text(original_log, encoding="utf-8")
    print("PASS | BOM indexes are readable and narrative metadata-like text cannot override record metadata")

    legacy = Path(tmp_name) / "legacy"
    subprocess.run([str(INIT), "--project", str(legacy), "--legacy-layout", "--yes"], check=True)
    old = cli(legacy)
    assert old.returncode == 0 and "REC_LEGACY" in old.stdout
    print("PASS | legacy projects remain unaffected")

print("PASS | project records audit regression fixtures")
