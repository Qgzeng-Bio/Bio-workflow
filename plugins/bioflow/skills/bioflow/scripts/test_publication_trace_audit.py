#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "publication_trace_audit.py"
INIT = ROOT / "scripts" / "init_project.sh"
SPEC = importlib.util.spec_from_file_location("publication_trace_audit", SCRIPT)
assert SPEC and SPEC.loader
trace = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = trace
SPEC.loader.exec_module(trace)


def cli(project: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--project", str(project), *extra],
        check=False, capture_output=True, text=True,
    )


def git(project: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(project), *arguments], check=False,
        capture_output=True, text=True,
    )
    assert result.returncode == 0, (arguments, result.stdout, result.stderr)
    return result.stdout.strip()


def write_tsv(path: Path, columns: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


def fingerprint(project: Path) -> dict[str, tuple[int, int, int, str]]:
    result: dict[str, tuple[int, int, int, str]] = {}
    for path in sorted(project.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(project).as_posix()
        stat = path.lstat()
        digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() and not path.is_symlink() else "NA"
        result[relative] = (stat.st_mode, stat.st_size, stat.st_mtime_ns, digest)
    return result


def manifest(evidence_path: str) -> dict:
    return {
        "schema_version": "result_manifest.v2",
        "analysis_id": "assembly_trace_fixture",
        "project": "fixture",
        "analysis_types": ["assembly_evaluation"],
        "assemblies": [{
            "key": "asm1", "role": "primary", "fasta": "asm1.fa",
            "total_length": 1000, "contig_N50": 500,
        }],
        "claims": [{
            "claim_id": "ASM_N50_OBS_001", "claim_type": "metric_observation",
            "metric": "N50", "subjects": ["asm1"],
            "protocol": {"n50_type": "contig_N50"},
            "evidence_paths": [evidence_path], "status": "supported", "caveats": [],
        }],
    }


def map_row(status: str = "Reviewed") -> dict[str, str]:
    return {
        "Schema_Version": "claim_evidence.v1", "Paper_ID": "P01",
        "Claim_ID": "ASM_N50_OBS_001",
        "Manuscript_Path": "manuscripts/P01-genome/Manuscript.md",
        "Figure_Refs": "assembly:F001",
        "Source_Table_Paths": "results/01-assembly/figures/F001_Assembly_Overview/source-data/F001_Assembly_Overview.tsv",
        "Version_Refs": "assembly:V01", "Mapping_Status": status, "Notes": "N50 fixture",
    }


with tempfile.TemporaryDirectory(prefix="bioflow-trace-test.") as tmp_name:
    base = Path(tmp_name)
    legacy = base / "legacy"
    subprocess.run([str(INIT), "--project", str(legacy), "--legacy-layout", "--yes"], check=True, stdout=subprocess.DEVNULL)
    legacy_result = cli(legacy, "--format", "tsv")
    assert legacy_result.returncode == 0 and "TRACE_LEGACY" in legacy_result.stdout
    legacy_config = base / "legacy-config"
    (legacy / "config").rename(legacy_config)
    (legacy / "config").symlink_to(legacy_config, target_is_directory=True)
    legacy_link_result = cli(legacy, "--format", "tsv")
    assert legacy_link_result.returncode == 0 and "TRACE_LEGACY" in legacy_link_result.stdout
    (legacy / "config").unlink()
    legacy_config.rename(legacy / "config")

    project = base / "project"
    subprocess.run([str(INIT), "--project", str(project), "--yes"], check=True, stdout=subprocess.DEVNULL)
    not_applicable = cli(project, "--format", "tsv")
    assert not_applicable.returncode == 0 and "TRACE_NOT_APPLICABLE" in not_applicable.stdout
    print("PASS | legacy and no-paper projects remain non-blocking")

    paper = project / "manuscripts" / "P01-genome"
    paper.mkdir()
    missing_map = cli(project, "--paper", "P01-genome", "--format", "tsv")
    assert missing_map.returncode == 1 and "TRACE_MAP_MISSING" in missing_map.stdout
    print("PASS | paper without map is a Draft-stage WARN")

    module = project / "results" / "01-assembly"
    version = module / "versions" / "V01"
    version.mkdir(parents=True)
    table = module / "tables" / "N50_Summary.tsv"
    table.parent.mkdir()
    table.write_text("Metric\tValue\nN50\t500\n", encoding="utf-8")
    write_tsv(module / "Version_Index.tsv", trace.VERSION_COLUMNS, [{
        "Version_ID": "V01", "Parent_Version": "NA", "Status": "Validated",
        "Selected": "Yes", "Input_Manifest": "config/Input_Manifest.tsv",
        "Parameter_File": "config/parameters/Assembly_V01.yaml",
        "Script_Commit": "abc1234", "Result_Path": "results/01-assembly/versions/V01",
        "Acceptance_Path": "docs/validation/Acceptance_Report.md", "Notes": "",
    }])
    package = module / "figures" / "F001_Assembly_Overview"
    source_dir = package / "source-data"
    source_dir.mkdir(parents=True)
    source_table = source_dir / "F001_Assembly_Overview.tsv"
    source_table.write_text("Metric\tValue\nN50\t500\n", encoding="utf-8")
    plot_script = project / "scripts" / "01-assembly" / "plotting" / "plot_F001.R"
    plot_script.parent.mkdir(parents=True)
    plot_script.write_text("# plotting fixture\n", encoding="utf-8")
    write_tsv(module / "figures" / "Figure_Index.tsv", trace.FIGURE_COLUMNS, [{
        "Figure_ID": "F001", "Figure_Title": "Assembly overview",
        "Figure_Directory": "F001_Assembly_Overview",
        "Source_Result": "results/01-assembly/tables/N50_Summary.tsv",
        "Plot_Script": "scripts/01-assembly/plotting/plot_F001.R",
        "Status": "Manuscript_ready", "Manuscript_Target": "P01:Fig1", "Notes": "",
    }])
    (project / "config" / "result_manifest.yaml").write_text(
        yaml.safe_dump(manifest("../results/01-assembly/tables/N50_Summary.tsv"), sort_keys=False),
        encoding="utf-8",
    )
    manuscript_path = paper / "Manuscript.md"
    manuscript_path.write_text(
        "# Manuscript\n\n## Results\n\n"
        "<!-- bioflow-claim: ASM_N50_OBS_001 -->\n\n"
        "The assembly has a contig N50 of 500 bp in this fixture.\n",
        encoding="utf-8",
    )
    map_path = paper / "Claim_Evidence_Map.tsv"
    write_tsv(map_path, trace.MAP_COLUMNS, [map_row()])

    before = fingerprint(project)
    reviewed = cli(project, "--paper", "P01-genome", "--format", "json")
    after = fingerprint(project)
    assert reviewed.returncode == 0, reviewed.stdout + reviewed.stderr
    payload = json.loads(reviewed.stdout)
    assert any(item["Rule_ID"] == "TRACE_OK" for item in payload["Findings"])
    assert before == after
    tsv = cli(project, "--paper", "P01-genome", "--format", "tsv")
    assert tsv.returncode == 0 and tsv.stdout.splitlines()[0].split("\t") == list(trace.AUDIT_COLUMNS)
    print("PASS | complete Reviewed Claim-Version-Figure-source-table-anchor trace is read-only PASS")

    original_row = map_row()
    draft = map_row("Draft")
    draft["Figure_Refs"] = "NA"
    draft["Source_Table_Paths"] = "NA"
    draft["Version_Refs"] = "NA"
    manuscript_path.write_text("# Manuscript\n\n## Results\nDraft text.\n", encoding="utf-8")
    write_tsv(map_path, trace.MAP_COLUMNS, [draft])
    draft_result = cli(project, "--format", "tsv")
    assert draft_result.returncode == 1
    for rule in ("TRACE_MAP_DRAFT", "TRACE_VERSION_MISSING", "TRACE_MARKDOWN_MISSING"):
        assert rule in draft_result.stdout
    print("PASS | incomplete Draft mapping produces WARN rather than false PASS/BLOCK")

    manuscript_path.write_text(
        "# Manuscript\n\n## Results\n\n<!-- bioflow-claim: ASM_N50_OBS_001 -->\n\nText.\n",
        encoding="utf-8",
    )
    write_tsv(map_path, trace.MAP_COLUMNS, [original_row])

    broken = dict(original_row); broken["Claim_ID"] = "MISSING_CLAIM"
    write_tsv(map_path, trace.MAP_COLUMNS, [broken])
    result = cli(project, "--format", "tsv")
    assert result.returncode == 2 and "TRACE_CLAIM_MISSING" in result.stdout

    broken = dict(original_row); broken["Version_Refs"] = "assembly:V99"
    write_tsv(map_path, trace.MAP_COLUMNS, [broken])
    result = cli(project, "--format", "tsv")
    assert result.returncode == 2 and "TRACE_VERSION_MISSING" in result.stdout

    figure_rows = [{
        "Figure_ID": "F001", "Figure_Title": "Assembly overview",
        "Figure_Directory": "F001_Assembly_Overview",
        "Source_Result": "results/01-assembly/tables/N50_Summary.tsv",
        "Plot_Script": "scripts/01-assembly/plotting/plot_F001.R",
        "Status": "Candidate", "Manuscript_Target": "NA", "Notes": "",
    }]
    write_tsv(module / "figures" / "Figure_Index.tsv", trace.FIGURE_COLUMNS, figure_rows)
    write_tsv(map_path, trace.MAP_COLUMNS, [original_row])
    result = cli(project, "--format", "tsv")
    assert result.returncode == 2 and "TRACE_FIGURE_STATUS" in result.stdout and "TRACE_FIGURE_TARGET" in result.stdout

    figure_rows[0]["Status"] = "Manuscript_ready"; figure_rows[0]["Manuscript_Target"] = "P01:Fig1"
    write_tsv(module / "figures" / "Figure_Index.tsv", trace.FIGURE_COLUMNS, figure_rows)
    source_table.write_text("Metric\tValue\n", encoding="utf-8")
    result = cli(project, "--format", "tsv")
    assert result.returncode == 2 and "TRACE_SOURCE_TABLE_FORMAT" in result.stdout
    source_table.write_text("Metric\tValue\nN50\t500\n", encoding="utf-8")

    manuscript_path.write_text(
        "<!-- bioflow-claim: ASM_N50_OBS_001 -->\n"
        "<!-- bioflow-claim: ASM_N50_OBS_001 -->\n",
        encoding="utf-8",
    )
    result = cli(project, "--format", "tsv")
    assert result.returncode == 2 and "TRACE_MARKDOWN_DUPLICATE" in result.stdout
    print("PASS | missing claim/version, non-ready figure, invalid source table, and duplicate anchor BLOCK")

    # Build a complete Frozen release in a temporary local Git repository.
    manuscript_text = (
        "# Manuscript\n\n## Results\n\n"
        "<!-- bioflow-claim: ASM_N50_OBS_001 -->\n\n"
        "The assembly has a contig N50 of 500 bp in this fixture.\n"
    )
    manuscript_path.write_text(manuscript_text, encoding="utf-8")
    frozen_row = map_row("Frozen")
    write_tsv(map_path, trace.MAP_COLUMNS, [frozen_row])
    version_rows = [{
        "Version_ID": "V01", "Parent_Version": "NA", "Status": "Frozen",
        "Selected": "Yes", "Input_Manifest": "config/Input_Manifest.tsv",
        "Parameter_File": "config/parameters/Assembly_V01.yaml",
        "Script_Commit": "abc1234", "Result_Path": "results/01-assembly/versions/V01",
        "Acceptance_Path": "docs/validation/Acceptance_Report.md", "Notes": "",
    }]
    write_tsv(module / "Version_Index.tsv", trace.VERSION_COLUMNS, version_rows)
    figure_rows[0]["Status"] = "Frozen"; figure_rows[0]["Manuscript_Target"] = "P01:Fig1"
    write_tsv(module / "figures" / "Figure_Index.tsv", trace.FIGURE_COLUMNS, figure_rows)
    (package / "README.md").write_text("# F001 Assembly Overview\n", encoding="utf-8")
    (package / "F001_Assembly_Overview.pdf").write_bytes(b"%PDF-1.4\nfixture\n")
    (package / "F001_Assembly_Overview.png").write_bytes(b"PNG fixture\n")
    checks = package / "checks"; checks.mkdir()
    (checks / "Figure_Check.md").write_text("PASS\n", encoding="utf-8")
    (checks / "Final_Review.json").write_text("{\"Status\": \"pass\"}\n", encoding="utf-8")
    (project / "docs/validation/Acceptance_Report.md").write_text(
        "# Acceptance\n\nAcceptance_Status: Accepted\n", encoding="utf-8"
    )
    rerun = project / "scripts/01-assembly/run_workflow.sh"
    rerun.write_text("#!/usr/bin/env bash\nset -euo pipefail\n", encoding="utf-8")

    git(project, "init", "-q")
    git(project, "config", "user.name", "Bioflow Test")
    git(project, "config", "user.email", "bioflow-test@example.invalid")
    git(project, "add", "-A")
    git(project, "commit", "-q", "-m", "source baseline")
    source_commit = git(project, "rev-parse", "HEAD")
    assert len(source_commit) == 40

    release_dir = paper / "releases/R01"
    files_dir = release_dir / "files"; files_dir.mkdir(parents=True)
    frozen_manuscript = files_dir / "Manuscript.md"
    frozen_figure = files_dir / "F001_Assembly_Overview.pdf"
    frozen_source = files_dir / "F001_Assembly_Overview.tsv"
    frozen_manuscript.write_bytes(manuscript_path.read_bytes())
    frozen_figure.write_bytes((package / "F001_Assembly_Overview.pdf").read_bytes())
    frozen_source.write_bytes(source_table.read_bytes())

    def artifact(artifact_id: str, role: str, canonical: Path, frozen: Path) -> dict:
        return {
            "artifact_id": artifact_id,
            "role": role,
            "canonical_path": canonical.relative_to(project).as_posix(),
            "release_path": frozen.relative_to(project).as_posix(),
            "sha256": hashlib.sha256(frozen.read_bytes()).hexdigest(),
        }

    release_manifest = {
        "schema_version": "bioflow.release.v1",
        "paper_id": "P01", "release_id": "P01-R01", "status": "Frozen",
        "release_date": "2026-08-15",
        "git": {"source_commit_sha": source_commit, "release_tag": "manuscript-P01-R01"},
        "authorities": {
            "result_manifest": "config/result_manifest.yaml",
            "claim_evidence_map": "manuscripts/P01-genome/Claim_Evidence_Map.tsv",
            "manuscript_source": "manuscripts/P01-genome/Manuscript.md",
            "acceptance_path": "docs/validation/Acceptance_Report.md",
            "rerun_entrypoint": "scripts/01-assembly/run_workflow.sh",
        },
        "selected": {
            "claims": ["ASM_N50_OBS_001"], "versions": ["assembly:V01"],
            "figures": ["assembly:F001"],
        },
        "artifacts": [
            artifact("A001", "Manuscript", manuscript_path, frozen_manuscript),
            artifact("A002", "Figure", package / "F001_Assembly_Overview.pdf", frozen_figure),
            artifact("A003", "Source_Table", source_table, frozen_source),
        ],
        "checklist": {key: True for key in trace.CHECKLIST_KEYS},
        "known_limitations": ["Synthetic fixture only."],
    }
    release_manifest_path = release_dir / "Release_Manifest.yaml"
    release_manifest_path.write_text(yaml.safe_dump(release_manifest, sort_keys=False), encoding="utf-8")
    git(project, "add", "-A")
    git(project, "commit", "-q", "-m", "freeze release")
    git(project, "tag", "-a", "manuscript-P01-R01", "-m", "P01 R01")

    before_frozen = fingerprint(project)
    frozen = cli(project, "--paper", "P01-genome", "--release", "R01", "--check-git", "--format", "json")
    after_frozen = fingerprint(project)
    assert frozen.returncode == 0, frozen.stdout + frozen.stderr
    assert before_frozen == after_frozen
    frozen_payload = json.loads(frozen.stdout)
    assert any(item["Rule_ID"] == "TRACE_OK" for item in frozen_payload["Findings"])
    print("PASS | complete Frozen release closure, SHA256, and local Git tag audit is read-only PASS")

    changed = yaml.safe_load(release_manifest_path.read_text())
    changed["selected"]["figures"] = []
    release_manifest_path.write_text(yaml.safe_dump(changed, sort_keys=False), encoding="utf-8")
    result = cli(project, "--paper", "P01-genome", "--release", "R01", "--format", "tsv")
    assert result.returncode == 2 and "TRACE_RELEASE_CLOSURE" in result.stdout

    changed = yaml.safe_load(yaml.safe_dump(release_manifest, sort_keys=False))
    changed["checklist"]["licenses_reviewed"] = False
    release_manifest_path.write_text(yaml.safe_dump(changed, sort_keys=False), encoding="utf-8")
    result = cli(project, "--paper", "P01-genome", "--release", "R01", "--format", "tsv")
    assert result.returncode == 2 and "TRACE_RELEASE_CHECKLIST" in result.stdout

    release_manifest_path.write_text(yaml.safe_dump(release_manifest, sort_keys=False), encoding="utf-8")
    frozen_source.write_text("Metric\tValue\nN50\t999\n", encoding="utf-8")
    result = cli(project, "--paper", "P01-genome", "--release", "R01", "--check-git", "--format", "tsv")
    assert result.returncode == 2 and "TRACE_RELEASE_HASH" in result.stdout and "TRACE_RELEASE_GIT" in result.stdout
    frozen_source.write_bytes(source_table.read_bytes())

    manuscript_path.write_text(manuscript_text + "\nCanonical source evolved after release.\n", encoding="utf-8")
    evolved = cli(project, "--paper", "P01-genome", "--release", "R01", "--check-git", "--format", "tsv")
    assert evolved.returncode == 1 and "TRACE_RELEASE_SOURCE_CHANGED" in evolved.stdout
    manuscript_path.write_text(manuscript_text, encoding="utf-8")
    print("PASS | selected closure, checklist, hash/tag mismatch BLOCK; later canonical evolution WARN")

    # Regression matrix for the latest bounded-read / missing-evidence hardening.
    # Collect failures so one unfixed case cannot hide the other independent cases.
    edge_failures: list[str] = []

    def edge_check(label: str, passed: bool) -> None:
        print(f"{'PASS' if passed else 'FAIL'} | {label}")
        if not passed:
            edge_failures.append(label)

    outside_supplement = base / "outside-supplement"
    outside_supplement.mkdir()
    (outside_supplement / "Proof.tsv").write_text("Metric\tValue\nN\t1\n")
    supplement = paper / "supplement"
    supplement.symlink_to(outside_supplement, target_is_directory=True)
    result = cli(project, "--paper", "P01-genome", "--format", "tsv")
    edge_check("supplement root symlink BLOCKs rather than disappearing from closure", result.returncode == 2 and "symlink" in (result.stdout + result.stderr).lower())
    supplement.unlink()
    supplement.mkdir()
    (supplement / "Proof.tsv").symlink_to(outside_supplement / "Proof.tsv")
    result = cli(project, "--paper", "P01-genome", "--format", "tsv")
    edge_check("supplement internal symlink BLOCKs", result.returncode == 2 and "symlink" in (result.stdout + result.stderr).lower())
    (supplement / "Proof.tsv").unlink()
    supplement.rmdir()

    canonical_pdf = package / "F001_Assembly_Overview.pdf"
    original_pdf = canonical_pdf.read_bytes()
    canonical_pdf.write_bytes(original_pdf + b"x" * 8193)
    original_hasher = trace.sha256_file
    oversized_hashed: list[str] = []

    def bounded_hash_spy(path: Path) -> str:
        if path.stat().st_size > 8192:
            oversized_hashed.append(str(path))
            raise AssertionError("oversized canonical file reached sha256_file")
        return original_hasher(path)

    limit_findings = []
    try:
        with mock.patch.object(trace, "MAX_RELEASE_ARTIFACT_BYTES", 8192), mock.patch.object(trace, "sha256_file", side_effect=bounded_hash_spy):
            limit_findings = trace.audit(project, "P01-genome", "R01", False)
    except AssertionError:
        pass
    finally:
        canonical_pdf.write_bytes(original_pdf)
    edge_check("oversized canonical files BLOCK without content hashing", not oversized_hashed and any(item.Status == "BLOCK" and item.Rule_ID == "TRACE_LIMIT" for item in limit_findings))

    map_bytes = map_path.read_bytes()
    write_tsv(map_path, trace.MAP_COLUMNS, [])
    result = cli(project, "--paper", "P01-genome", "--format", "tsv")
    edge_check("empty map plus existing Frozen release is BLOCK without --release", result.returncode == 2 and "TRACE_MAP_EMPTY" in result.stdout)
    map_path.unlink()
    result = cli(project, "--paper", "P01-genome", "--format", "tsv")
    edge_check("missing map plus existing Frozen release is BLOCK", result.returncode == 2 and "TRACE_MAP_MISSING" in result.stdout)
    result = cli(project, "--paper", "P01-genome", "--release", "R01", "--format", "tsv")
    edge_check("selected release without a map is BLOCK", result.returncode == 2 and "TRACE_MAP_MISSING" in result.stdout)
    map_path.write_bytes(map_bytes)

    release_bytes = release_manifest_path.read_bytes()
    for unsafe_tag in ["-bad", "a..b", "a//b", "a/", "bad@{1}"]:
        changed = yaml.safe_load(release_bytes)
        changed["git"]["release_tag"] = unsafe_tag
        release_manifest_path.write_text(yaml.safe_dump(changed, sort_keys=False))
        with mock.patch.object(trace, "run_local_git", side_effect=AssertionError("invalid tag reached Git")) as git_spy:
            findings = trace.audit(project, "P01-genome", "R01", True)
        edge_check(f"unsafe release tag rejected before Git: {unsafe_tag}", not git_spy.called and any(item.Status == "BLOCK" and item.Rule_ID == "TRACE_RELEASE_GIT" for item in findings))
    release_manifest_path.write_bytes(release_bytes)

    # Independent-review counterexamples: completeness must not silently truncate.
    deep = supplement / "a/b/c/d/e/Proof.tsv"
    deep.parent.mkdir(parents=True)
    deep.write_text("Metric\tValue\nN\t1\n")
    result = cli(project, "--paper", "P01-genome", "--format", "tsv")
    edge_check("over-depth supplement inventory BLOCKs instead of truncating", result.returncode == 2 and "depth" in (result.stdout + result.stderr).lower())
    shutil.rmtree(supplement)
    supplement.mkdir()
    (supplement / ".Hidden.tsv").write_text("Metric\tValue\nN\t1\n")
    result = cli(project, "--paper", "P01-genome", "--format", "tsv")
    edge_check("hidden supplement is included in required closure", result.returncode == 2 and "TRACE_RELEASE_CLOSURE" in result.stdout)
    shutil.rmtree(supplement)
    for extra_name in ["Unlisted.tsv", ".Hidden.tsv"]:
        extra = files_dir / extra_name
        extra.write_text("Metric\tValue\nN\t1\n")
        result = cli(project, "--paper", "P01-genome", "--format", "tsv")
        edge_check(f"unregistered Frozen file BLOCKs: {extra_name}", result.returncode == 2 and "TRACE_RELEASE_CLOSURE" in result.stdout)
        extra.unlink()
    extra = files_dir / "Unlisted_Link.tsv"
    extra.symlink_to(outside_supplement / "Proof.tsv")
    result = cli(project, "--paper", "P01-genome", "--format", "tsv")
    edge_check("unregistered Frozen symlink BLOCKs", result.returncode == 2)
    extra.unlink()

    # A size BLOCK must prevent later Git content reads of that same local file.
    frozen_bytes = frozen_source.read_bytes()
    frozen_source.write_bytes(frozen_bytes + b"x" * 8193)
    git_calls_for_oversized: list[tuple] = []
    original_git = trace.run_local_git
    frozen_relative = frozen_source.relative_to(project).as_posix()

    def git_read_spy(project_path: Path, *arguments: str) -> bytes:
        if any(argument.endswith(":" + frozen_relative) for argument in arguments):
            git_calls_for_oversized.append(arguments)
        return original_git(project_path, *arguments)

    with mock.patch.object(trace, "MAX_RELEASE_ARTIFACT_BYTES", 8192), mock.patch.object(trace, "run_local_git", side_effect=git_read_spy):
        findings = trace.audit(project, "P01-genome", "R01", True)
    edge_check("oversized local release file is excluded from Git content checks", not git_calls_for_oversized and any(item.Rule_ID == "TRACE_LIMIT" for item in findings))
    frozen_source.write_bytes(frozen_bytes)

    # Metadata limits use small injected budgets, never multi-megabyte fixtures.
    yaml_rejected = False
    with mock.patch.object(trace, "MAX_METADATA_BYTES", 128, create=True):
        try:
            trace.yaml_mapping(release_manifest_path, "oversized YAML fixture")
        except trace.TraceAuditError:
            yaml_rejected = True
    edge_check("YAML metadata size is bounded", yaml_rejected)
    acceptance = project / "docs/validation/Acceptance_Report.md"
    acceptance_bytes = acceptance.read_bytes()
    acceptance.write_bytes(acceptance_bytes + b"x" * 8193)
    oversized_acceptance_reads: list[str] = []
    original_read_text = Path.read_text

    def acceptance_read_spy(path: Path, *args, **kwargs):
        if path == acceptance and path.stat().st_size > 8192:
            oversized_acceptance_reads.append(str(path))
            raise AssertionError("oversized acceptance reached a downstream content read")
        return original_read_text(path, *args, **kwargs)

    with mock.patch.object(trace, "MAX_METADATA_BYTES", 8192, create=True), mock.patch.object(Path, "read_text", new=acceptance_read_spy):
        findings = trace.audit(project, "P01-genome", "R01", False)
    edge_check("acceptance metadata size is bounded", any(item.Status == "BLOCK" and item.Rule_ID == "TRACE_RELEASE_AUTHORITY" for item in findings))
    edge_check("oversized acceptance is not re-read by prerequisites", not oversized_acceptance_reads)

    # Even a custom safe authority must not leave the canonical prerequisite path unguarded.
    custom_acceptance = acceptance.with_name("Custom_Acceptance.md")
    custom_acceptance.write_bytes(acceptance_bytes)
    saved_manifest = release_manifest_path.read_bytes()
    changed = yaml.safe_load(saved_manifest)
    changed["authorities"]["acceptance_path"] = custom_acceptance.relative_to(project).as_posix()
    release_manifest_path.write_text(yaml.safe_dump(changed, sort_keys=False))
    oversized_acceptance_reads.clear()
    with mock.patch.object(trace, "MAX_METADATA_BYTES", 8192, create=True), mock.patch.object(Path, "read_text", new=acceptance_read_spy):
        findings = trace.audit(project, "P01-genome", "R01", False)
    edge_check("canonical acceptance prerequisite stays bounded with a custom authority", not oversized_acceptance_reads and any(item.Status == "BLOCK" for item in findings))
    release_manifest_path.write_bytes(saved_manifest)
    custom_acceptance.unlink()
    acceptance.write_bytes(acceptance_bytes)

    # Reviewed checks must bind paths without relying on Frozen prerequisite audits.
    saved_release = base / "held-release"
    release_dir.rename(saved_release)
    map_bytes = map_path.read_bytes()
    write_tsv(map_path, trace.MAP_COLUMNS, [map_row("Reviewed")])

    # Metadata ancestors must be checked before opening layout/manifest/index files.
    result_manifest_path = project / "config/result_manifest.yaml"
    original_manifest_bytes = result_manifest_path.read_bytes()
    absolute_evidence_manifest = yaml.safe_load(original_manifest_bytes)
    absolute_evidence_manifest["claims"][0]["evidence_paths"] = [str(table)]
    result_manifest_path.write_text(yaml.safe_dump(absolute_evidence_manifest, sort_keys=False))
    external_config = base / "external-config"
    (project / "config").rename(external_config)
    (project / "config").symlink_to(external_config, target_is_directory=True)
    opened_metadata: list[str] = []
    original_path_open = Path.open
    watched_metadata = {project / "config/Project_Layout.tsv", result_manifest_path}

    def metadata_open_spy(path: Path, *args, **kwargs):
        if path in watched_metadata:
            opened_metadata.append(str(path))
        return original_path_open(path, *args, **kwargs)

    blocked = False
    with mock.patch.object(Path, "open", new=metadata_open_spy):
        try:
            findings = trace.audit(project, "P01-genome", None, False)
            blocked = any(item.Status == "BLOCK" for item in findings)
        except (trace.TraceAuditError, trace.layout_contract.LayoutError):
            blocked = True
    edge_check("config parent symlink BLOCKs before layout and manifest reads", blocked and not opened_metadata)
    (project / "config").unlink()
    external_config.rename(project / "config")
    result_manifest_path.write_bytes(original_manifest_bytes)

    external_figures = base / "external-figures"
    (module / "figures").rename(external_figures)
    (module / "figures").symlink_to(external_figures, target_is_directory=True)
    watched_metadata = {module / "figures/Figure_Index.tsv"}
    opened_metadata.clear()
    with mock.patch.object(Path, "open", new=metadata_open_spy):
        findings = trace.audit(project, "P01-genome", None, False)
    edge_check("figures parent symlink BLOCKs before Figure_Index read", any(item.Status == "BLOCK" for item in findings) and not opened_metadata)
    (module / "figures").unlink()
    external_figures.rename(module / "figures")

    deep_markdown = paper / "a/b/c/d/e/Extra.md"
    deep_markdown.parent.mkdir(parents=True)
    for anchor in ["ASM_N50_OBS_001", "UNKNOWN_EXTRA_CLAIM"]:
        deep_markdown.write_text(f"<!-- bioflow-claim: {anchor} -->\n")
        result = cli(project, "--paper", "P01-genome", "--format", "tsv")
        edge_check(f"over-depth Markdown anchor inventory BLOCKs: {anchor}", result.returncode == 2 and "depth" in (result.stdout + result.stderr).lower())
    shutil.rmtree(paper / "a")

    version_index = module / "Version_Index.tsv"
    version_bytes = version_index.read_bytes()
    bad_version = dict(version_rows[0])
    bad_version["Result_Path"] = "results/01-assembly"
    write_tsv(version_index, trace.VERSION_COLUMNS, [bad_version])
    result = cli(project, "--paper", "P01-genome", "--format", "tsv")
    edge_check("Reviewed version must resolve to exact versions/VNN", result.returncode == 2 and "TRACE_VERSION_RESULT" in result.stdout)
    version_index.write_bytes(version_bytes)
    figure_index = module / "figures/Figure_Index.tsv"
    figure_bytes = figure_index.read_bytes()
    bad_figure = dict(figure_rows[0]); bad_figure["Figure_Directory"] = str(package)
    write_tsv(figure_index, trace.FIGURE_COLUMNS, [bad_figure])
    result = cli(project, "--paper", "P01-genome", "--format", "tsv")
    edge_check("Reviewed figure directory must be a scoped basename", result.returncode == 2 and "TRACE_FIGURE_PACKAGE" in result.stdout)
    figure_index.write_bytes(figure_bytes)

    second_package = module / "figures/F002_Second"
    shutil.copytree(package, second_package)
    for suffix in ["pdf", "png"]:
        (second_package / f"{package.name}.{suffix}").rename(second_package / f"{second_package.name}.{suffix}")
    second_table = second_package / "source-data/F002_Second.tsv"
    (second_package / "source-data/F001_Assembly_Overview.tsv").rename(second_table)
    second_figure = dict(figure_rows[0]); second_figure.update(Figure_ID="F002", Figure_Directory="F002_Second")
    write_tsv(figure_index, trace.FIGURE_COLUMNS, [figure_rows[0], second_figure])
    multiple = map_row("Reviewed"); multiple["Figure_Refs"] = "assembly:F001;assembly:F002"
    write_tsv(map_path, trace.MAP_COLUMNS, [multiple])
    result = cli(project, "--paper", "P01-genome", "--format", "tsv")
    edge_check("each mapped figure needs its own valid explicit source table", result.returncode == 2 and "TRACE_SOURCE_TABLE_MISSING" in result.stdout)
    multiple["Source_Table_Paths"] += ";" + second_table.relative_to(project).as_posix()
    write_tsv(map_path, trace.MAP_COLUMNS, [multiple])
    result = cli(project, "--paper", "P01-genome", "--format", "tsv")
    edge_check("complete multi-figure mapping remains PASS", result.returncode == 0)

    # Round-two efficiency: shared data is parsed once, while findings stay per claim.
    shared_manifest_bytes = result_manifest_path.read_bytes()
    shared_manuscript_bytes = manuscript_path.read_bytes()
    shared_source_bytes = source_table.read_bytes()
    shared_manifest = yaml.safe_load(shared_manifest_bytes)
    second_claim = dict(shared_manifest["claims"][0])
    second_claim["claim_id"] = "ASM_N50_OBS_002"
    shared_manifest["claims"].append(second_claim)
    result_manifest_path.write_text(yaml.safe_dump(shared_manifest, sort_keys=False))
    manuscript_path.write_bytes(shared_manuscript_bytes + b"\n<!-- bioflow-claim: ASM_N50_OBS_002 -->\nSecond shared-evidence observation.\n")
    second_mapping = dict(multiple); second_mapping["Claim_ID"] = second_claim["claim_id"]
    write_tsv(map_path, trace.MAP_COLUMNS, [multiple, second_mapping])
    with mock.patch.object(trace, "load_version_rows", wraps=trace.load_version_rows) as version_spy, mock.patch.object(trace, "load_figure_rows", wraps=trace.load_figure_rows) as figure_spy, mock.patch.object(trace, "validate_source_table", wraps=trace.validate_source_table) as source_spy:
        findings = trace.audit(project, "P01-genome", None, False)
    shared_ok = not any(item.Status in {"WARN", "BLOCK"} for item in findings)
    edge_check("shared indexes parsed once per module per paper", shared_ok and version_spy.call_count == 1 and figure_spy.call_count == 1)
    edge_check("shared source tables validated once per unique path", shared_ok and source_spy.call_count == 2)
    print(f"MEASURE | shared valid input calls: version={version_spy.call_count} figure={figure_spy.call_count} source={source_spy.call_count}")
    wrong_owner = dict(second_mapping)
    wrong_owner["Figure_Refs"] = "assembly:F002"
    wrong_owner["Source_Table_Paths"] = source_table.relative_to(project).as_posix()
    write_tsv(map_path, trace.MAP_COLUMNS, [multiple, wrong_owner])
    findings = trace.audit(project, "P01-genome", None, False)
    edge_check("cached valid source table cannot bypass current figure ownership", any(item.Claim_ID == "ASM_N50_OBS_002" and item.Status == "BLOCK" and item.Rule_ID == "TRACE_SOURCE_TABLE_PACKAGE" for item in findings))

    draft_mapping = dict(multiple); draft_mapping["Mapping_Status"] = "Draft"
    write_tsv(map_path, trace.MAP_COLUMNS, [draft_mapping, second_mapping])
    source_table.write_bytes(shared_source_bytes + b"Broken\tRow\tExtra\n")
    with mock.patch.object(trace, "validate_source_table", wraps=trace.validate_source_table) as source_spy:
        findings = trace.audit(project, "P01-genome", None, False)
    severities = {(item.Claim_ID, item.Status) for item in findings if item.Rule_ID == "TRACE_SOURCE_TABLE_FORMAT"}
    expected_severities = {("ASM_N50_OBS_001", "WARN"), ("ASM_N50_OBS_002", "BLOCK")}
    missing_severities = {(item.Claim_ID, item.Status) for item in findings if item.Rule_ID == "TRACE_SOURCE_TABLE_MISSING"}
    edge_check("shared invalid table preserves per-claim severity and missing coverage", source_spy.call_count == 2 and severities == expected_severities and missing_severities == expected_severities)
    source_table.write_bytes(shared_source_bytes)

    for kind, index_path, loader_name, rule, columns, valid_rows in [
        ("version", version_index, "load_version_rows", "TRACE_VERSION_INDEX", trace.VERSION_COLUMNS, version_rows),
        ("figure", figure_index, "load_figure_rows", "TRACE_FIGURE_INDEX", trace.FIGURE_COLUMNS, [figure_rows[0], second_figure]),
    ]:
        index_bytes = index_path.read_bytes()
        for failure in ["header", "duplicate", "missing"]:
            if failure == "header":
                index_path.write_text("Wrong\tHeader\n")
            elif failure == "duplicate":
                write_tsv(index_path, columns, [valid_rows[0], valid_rows[0]])
            else:
                index_path.unlink()
            with mock.patch.object(trace, loader_name, wraps=getattr(trace, loader_name)) as index_spy:
                findings = trace.audit(project, "P01-genome", None, False)
            severities = {(item.Claim_ID, item.Status) for item in findings if item.Rule_ID == rule}
            edge_check(f"shared {kind} index {failure} retains WARN/BLOCK without reparsing", index_spy.call_count == 1 and severities == expected_severities)
            index_path.write_bytes(index_bytes)

    write_tsv(map_path, trace.MAP_COLUMNS, [multiple, second_mapping])
    findings = trace.audit(project, "P01-genome", None, False)
    edge_check("index/table validation state does not persist into next audit", not any(item.Status in {"WARN", "BLOCK"} for item in findings))
    result_manifest_path.write_bytes(shared_manifest_bytes)
    manuscript_path.write_bytes(shared_manuscript_bytes)

    figure_index.write_bytes(figure_bytes)
    map_path.write_bytes(map_bytes)
    shutil.rmtree(second_package)
    saved_release.rename(release_dir)

    source_bytes = source_table.read_bytes()
    source_table.write_bytes(source_bytes + b"Malformed\tRow\tExtra\n")
    issue = trace.validate_source_table(source_table)
    edge_check("source table validates later data row widths", issue is not None)
    source_table.write_bytes(source_bytes)

    # Branch/HEAD names are not tags, even when their committed bytes all match.
    release_bytes = release_manifest_path.read_bytes()
    for revision in ["HEAD", "branch-only"]:
        changed = yaml.safe_load(release_bytes); changed["git"]["release_tag"] = revision
        release_manifest_path.write_text(yaml.safe_dump(changed, sort_keys=False))
        git(project, "add", str(release_manifest_path.relative_to(project)))
        git(project, "commit", "-q", "-m", "non-tag release fixture")
        if revision == "branch-only":
            git(project, "branch", revision)
        result = cli(project, "--paper", "P01-genome", "--release", "R01", "--check-git", "--format", "tsv")
        edge_check(f"release_tag cannot resolve through non-tag revision: {revision}", result.returncode == 2 and "TRACE_RELEASE_GIT" in result.stdout)
    release_manifest_path.write_bytes(release_bytes)

    # v1 exposes only roles for which it has an explicit closure authority.
    role_manifest_bytes = release_manifest_path.read_bytes()
    for unsupported_role in ["Methods", "Table", "Other"]:
        changed = yaml.safe_load(role_manifest_bytes)
        changed["artifacts"][0]["role"] = unsupported_role
        release_manifest_path.write_text(yaml.safe_dump(changed, sort_keys=False))
        result = cli(project, "--paper", "P01-genome", "--release", "R01", "--format", "tsv")
        edge_check(f"unsupported v1 role rejected at schema gate: {unsupported_role}", result.returncode == 2 and "TRACE_RELEASE_SCHEMA" in result.stdout)
    release_manifest_path.write_bytes(role_manifest_bytes)
    supplement.mkdir()
    supplemental_methods = supplement / "Methods.md"
    supplemental_methods.write_text("# Supplementary methods fixture\n")
    supplemental_copy = files_dir / "Supplement_Methods.md"
    supplemental_copy.write_bytes(supplemental_methods.read_bytes())
    changed = yaml.safe_load(role_manifest_bytes)
    changed["artifacts"].append(artifact("A004", "Supplement", supplemental_methods, supplemental_copy))
    release_manifest_path.write_text(yaml.safe_dump(changed, sort_keys=False))
    result = cli(project, "--paper", "P01-genome", "--release", "R01", "--format", "tsv")
    edge_check("extra file registered through Supplement closure remains PASS", result.returncode == 0)
    supplemental_methods.unlink(); supplement.rmdir(); supplemental_copy.unlink()
    release_manifest_path.write_bytes(role_manifest_bytes)

    # Unit-level immutable Git blob limit; uses only an 8 KiB synthetic object.
    historical = project / "Historical_Blob.txt"
    historical.write_bytes(b"x" * 8193)
    git(project, "add", "Historical_Blob.txt")
    git(project, "commit", "-q", "-m", "bounded blob fixture")
    historical_commit = git(project, "rev-parse", "HEAD")
    blob_reader = getattr(trace, "read_git_blob", None)
    blob_rejected = False
    content_reads = []
    original_popen = subprocess.Popen

    def popen_spy(arguments, *args, **kwargs):
        if "cat-file" in arguments and "blob" in arguments:
            content_reads.append(arguments)
        return original_popen(arguments, *args, **kwargs)

    if blob_reader is not None:
        with mock.patch.object(trace.subprocess, "Popen", side_effect=popen_spy):
            try:
                blob_reader(project, historical_commit, "Historical_Blob.txt", max_bytes=8192)
            except trace.TraceAuditError:
                blob_rejected = True
    edge_check("oversized Git blob rejected before content subprocess", blob_rejected and not content_reads)
    historical.unlink()

    assert not edge_failures, "Hardening regressions: " + "; ".join(edge_failures)

print("PASS | publication trace audit Draft/Reviewed/Frozen regression fixtures")
