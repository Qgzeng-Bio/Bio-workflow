#!/usr/bin/env python3
from __future__ import annotations

import csv
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "project_structure_audit.py"
INIT = ROOT / "scripts" / "init_project.sh"
TEMPLATES = ROOT / "assets" / "project-templates"
SPEC = importlib.util.spec_from_file_location("project_structure_audit", SCRIPT)
assert SPEC and SPEC.loader
structure = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = structure
SPEC.loader.exec_module(structure)


def cli(project: Path):
    return subprocess.run([sys.executable, str(SCRIPT), "--project", str(project), "--format", "tsv"], check=False, capture_output=True, text=True)


def write_tsv(path: Path, columns: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


with tempfile.TemporaryDirectory(prefix="bioflow-structure-test.") as tmp_name:
    project = Path(tmp_name) / "project"
    initialized = subprocess.run([str(INIT), "--project", str(project), "--yes"], check=False, capture_output=True, text=True)
    assert initialized.returncode == 0, initialized.stderr
    module = project / "results" / "01-assembly"
    package = module / "figures" / "F001_Assembly_Overview"
    (package / "source-data").mkdir(parents=True)
    (package / "checks").mkdir()
    (module / "versions" / "V01").mkdir(parents=True)
    (package / "README.md").write_bytes((TEMPLATES / "Figure_README.md").read_bytes())
    (package / "F001_Assembly_Overview.pdf").write_text("pdf", encoding="utf-8")
    (package / "F001_Assembly_Overview.png").write_text("png", encoding="utf-8")
    (package / "source-data" / "F001_Assembly_Overview.tsv").write_text("Metric\tValue\nN50\t10\n", encoding="utf-8")
    (package / "checks" / "Figure_Check.md").write_text("pass\n", encoding="utf-8")
    (package / "checks" / "Final_Review.json").write_text("{}\n", encoding="utf-8")
    (module / "tables").mkdir()
    (module / "tables" / "Assembly_Summary.tsv").write_text("Metric\tValue\nN50\t10\n", encoding="utf-8")
    (project / "scripts" / "01-assembly" / "plotting").mkdir(parents=True)
    (project / "scripts" / "01-assembly" / "plotting" / "plot_F001.R").write_text("# plot\n", encoding="utf-8")
    write_tsv(module / "Version_Index.tsv", structure.VERSION_COLUMNS, [{
        "Version_ID": "V01", "Parent_Version": "NA", "Status": "Validated", "Selected": "Yes",
        "Input_Manifest": "config/Input_Manifest.tsv", "Parameter_File": "config/parameters/Assembly_V01.yaml",
        "Script_Commit": "abc1234", "Result_Path": "results/01-assembly/versions/V01",
        "Acceptance_Path": "docs/validation/Acceptance_Report.md", "Notes": "",
    }])
    write_tsv(module / "figures" / "Figure_Index.tsv", structure.FIGURE_COLUMNS, [{
        "Figure_ID": "F001", "Figure_Title": "Assembly overview", "Figure_Directory": "F001_Assembly_Overview",
        "Source_Result": "results/01-assembly/tables/Assembly_Summary.tsv",
        "Plot_Script": "scripts/01-assembly/plotting/plot_F001.R", "Status": "Validated",
        "Manuscript_Target": "NA", "Notes": "",
    }])
    clean = cli(project)
    assert clean.returncode == 0, clean.stdout + clean.stderr

    figure_index = module / "figures" / "Figure_Index.tsv"
    bad_status = [{
        "Figure_ID": "F001", "Figure_Title": "Assembly overview", "Figure_Directory": "F001_Assembly_Overview",
        "Source_Result": "results/01-assembly/tables/Assembly_Summary.tsv",
        "Plot_Script": "scripts/01-assembly/plotting/plot_F001.R", "Status": "Validatedd",
        "Manuscript_Target": "NA", "Notes": "",
    }]
    write_tsv(figure_index, structure.FIGURE_COLUMNS, bad_status)
    blocked = cli(project)
    assert blocked.returncode == 2 and "invalid figure Status" in blocked.stdout
    write_tsv(figure_index, structure.FIGURE_COLUMNS, [{
        "Figure_ID": "F001", "Figure_Title": "Assembly overview", "Figure_Directory": "F001_Assembly_Overview",
        "Source_Result": "results/01-assembly/tables/Assembly_Summary.tsv",
        "Plot_Script": "scripts/01-assembly/plotting/plot_F001.R", "Status": "Validated",
        "Manuscript_Target": "NA", "Notes": "",
    }])

    saved_pdf = package / "F001_Assembly_Overview.pdf"
    saved_pdf.unlink()
    (project / "tmp" / "draft.pdf").write_text("draft", encoding="utf-8")
    saved_pdf.symlink_to(project / "tmp" / "draft.pdf")
    blocked = cli(project)
    assert blocked.returncode == 2 and "STRUCT_FIGURE_PACKAGE" in blocked.stdout
    saved_pdf.unlink(); saved_pdf.write_text("pdf", encoding="utf-8")

    (project / "data").mkdir()
    blocked = cli(project)
    assert blocked.returncode == 2 and "STRUCT_MIXED_LAYOUT" in blocked.stdout
    (project / "data").rmdir()

    skipped = project / "results" / "03-genome-qc"
    skipped.mkdir()
    blocked = cli(project)
    assert blocked.returncode == 2 and "STRUCT_MODULE_STAGE" in blocked.stdout
    skipped.rmdir()

    rogue = project / "results" / "02-assembly-v2-final"
    rogue.mkdir()
    blocked = cli(project)
    assert blocked.returncode == 2 and "STRUCT_MODULE_VERSION" in blocked.stdout
    rogue.rmdir()

    bad_version = module / "V02"
    bad_version.mkdir()
    blocked = cli(project)
    assert blocked.returncode == 2 and "STRUCT_VERSION_PATH" in blocked.stdout
    bad_version.rmdir()

    manifest = project / "config" / "result_manifest.yaml"
    manifest.write_text("schema_version: result_manifest.v2\nclaims:\n  - evidence_paths: [../tmp/test.tsv]\n", encoding="utf-8")
    blocked = cli(project)
    assert blocked.returncode == 2 and "STRUCT_TMP_REFERENCE" in blocked.stdout

    manifest.write_text("schema_version: result_manifest.v2\nclaims: []\n", encoding="utf-8")
    (package / "F001_Assembly_Overview.png").unlink()
    blocked = cli(project)
    assert blocked.returncode == 2 and "STRUCT_FIGURE_PACKAGE" in blocked.stdout

    legacy = Path(tmp_name) / "legacy"
    subprocess.run([str(INIT), "--project", str(legacy), "--legacy-layout", "--yes"], check=True)
    old = cli(legacy)
    assert old.returncode == 0 and "STRUCT_LEGACY" in old.stdout

print("PASS | result-module, version, tmp-evidence, figure-package, and legacy structure contracts")
