#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "scripts" / "git_project_audit.py"
INIT = ROOT / "scripts" / "init_project.sh"
SPEC = importlib.util.spec_from_file_location("git_project_audit", AUDIT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def git(project: Path, *args: str) -> None:
    result = subprocess.run(["git", "-C", str(project), *args], check=False, capture_output=True, text=True)
    assert result.returncode == 0, (args, result.stdout, result.stderr)


def states(findings, path: str) -> set[str]:
    return {item.Status for item in findings if item.Relative_Path == path}


with tempfile.TemporaryDirectory(prefix="bioflow-git-audit.") as tmp_name:
    root = Path(tmp_name)
    project = root / "v2"
    initialized = subprocess.run([str(INIT), "--project", str(project), "--yes"], check=False, capture_output=True, text=True)
    assert initialized.returncode == 0, initialized.stderr
    git(project, "init", "-q")

    safe_script = project / "scripts" / "01-assembly" / "run.sh"
    safe_script.parent.mkdir(parents=True)
    safe_script.write_text("#!/usr/bin/env bash\necho ok\n", encoding="utf-8")
    source_table = project / "results" / "01-assembly" / "tables" / "Assembly_Summary.tsv"
    source_table.parent.mkdir(parents=True)
    source_table.write_text("Metric\tValue\nN50\t10\n", encoding="utf-8")
    note = project / "docs" / "research-log" / "20260811_Assembly.md"
    note.write_text("# Assembly\n", encoding="utf-8")
    git(project, "add", "scripts/01-assembly/run.sh", "results/01-assembly/tables/Assembly_Summary.tsv")

    findings = module.audit(project, include_untracked=True)
    assert "PASS" in states(findings, "scripts/01-assembly/run.sh")
    assert "PASS" in states(findings, "results/01-assembly/tables/Assembly_Summary.tsv")
    assert "PASS" in states(findings, "docs/research-log/20260811_Assembly.md")
    assert any(item.Rule_ID == "GIT_IGNORE_OK" and item.Status == "PASS" for item in findings)
    assert any(item.Relative_Path == "scripts/01-assembly/run.sh" and "Staged" in item.Git_State for item in findings)
    staged_only = module.audit(project, include_untracked=False)
    assert not any(item.Relative_Path == "docs/research-log/20260811_Assembly.md" for item in staged_only)
    print("PASS | safe staged/text candidates, state classification, and staged-only mode")

    raw = project / "rawdata" / "Reads.fastq"
    raw.write_text("@r\nAC\n+\n!!\n", encoding="utf-8")
    log = project / "logs" / "job.out"
    log.write_text("done\n", encoding="utf-8")
    temporary = project / "tmp" / "intermediate.tsv"
    temporary.write_text("x\n", encoding="utf-8")
    alignment = project / "results" / "01-assembly" / "reads.bam"
    alignment.write_bytes(b"BAM\x01")
    secret = project / "config" / "local.txt"
    secret.write_text("api_" + "key=supersecretvalue123\n", encoding="utf-8")
    external = root / "external.txt"
    external.write_text("outside\n", encoding="utf-8")
    link = project / "config" / "outside_link"
    link.symlink_to(external)
    large = project / "results" / "01-assembly" / "large.bin"
    with large.open("wb") as handle:
        handle.truncate(101 * 1024 * 1024)
    figure = project / "results" / "01-assembly" / "fig.pdf"
    figure.write_bytes(b"%PDF\n")
    git(project, "add", "-f", "rawdata/Reads.fastq", "logs/job.out", "tmp/intermediate.tsv", "results/01-assembly/reads.bam", "config/local.txt", "config/outside_link", "results/01-assembly/large.bin", "results/01-assembly/fig.pdf")

    findings = module.audit(project, include_untracked=True)
    expected_blocks = {
        "rawdata/Reads.fastq": "GIT001",
        "logs/job.out": "GIT002",
        "tmp/intermediate.tsv": "GIT002",
        "results/01-assembly/reads.bam": "GIT006",
        "config/local.txt": "GIT010",
        "config/outside_link": "GIT004",
        "results/01-assembly/large.bin": "GIT007",
    }
    for relative, rule in expected_blocks.items():
        assert any(item.Relative_Path == relative and item.Status == "BLOCK" and item.Rule_ID == rule for item in findings), (relative, findings)
    assert any(item.Relative_Path == "results/01-assembly/fig.pdf" and item.Status == "WARN" and item.Rule_ID == "GIT009" for item in findings)
    print("PASS | rawdata/runtime/alignment/secret/symlink/large-file BLOCK and figure WARN gates")

    cli = subprocess.run([sys.executable, str(AUDIT), "--project", str(project), "--format", "tsv"], check=False, capture_output=True, text=True)
    assert cli.returncode == 2 and cli.stdout.splitlines()[0].split("\t") == list(module.AUDIT_COLUMNS)
    assert "GIT001" in cli.stdout and "GIT010" in cli.stdout
    print("PASS | CLI TSV and BLOCK exit status")

    legacy = root / "legacy"
    initialized = subprocess.run([str(INIT), "--project", str(legacy), "--legacy-layout", "--yes"], check=False, capture_output=True, text=True)
    assert initialized.returncode == 0, initialized.stderr
    git(legacy, "init", "-q")
    legacy_ignore = legacy / ".gitignore"
    legacy_ignore.write_text("data/*\n!data/README.md\nlogs/\ntmp/\n.snakemake/\n.nextflow/\n.env\n*.bam\n*.cram\n", encoding="utf-8")
    legacy_raw = legacy / "data" / "reads.fq"
    legacy_raw.write_text("@r\nAC\n+\n!!\n", encoding="utf-8")
    git(legacy, "add", "-f", "data/reads.fq")
    legacy_findings = module.audit(legacy, include_untracked=True)
    assert any(item.Relative_Path == "data/reads.fq" and item.Rule_ID == "GIT001" and item.Status == "BLOCK" for item in legacy_findings)
    print("PASS | legacy data root receives the same raw-input protection")

print("PASS | Git project audit regression fixtures")
