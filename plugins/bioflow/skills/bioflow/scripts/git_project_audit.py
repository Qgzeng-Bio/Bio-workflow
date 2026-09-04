#!/usr/bin/env python3
"""Read-only Git safety audit for Bioflow projects."""
from __future__ import annotations

import argparse
import csv
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import project_layout as layout_contract

WARN_SIZE = 50 * 1024 * 1024
BLOCK_SIZE = 100 * 1024 * 1024
MAX_CANDIDATES = 10_000
MAX_SECRET_SCAN = 512 * 1024
AUDIT_COLUMNS = ("Status", "Rule_ID", "Git_State", "Relative_Path", "Size_MiB", "Detail", "Action")
SEVERITY = {"PASS": 0, "WARN": 1, "BLOCK": 2}
BLOCK_EXTENSIONS = {".fastq", ".fq", ".bam", ".bai", ".cram", ".crai", ".sam", ".sra", ".kdb", ".meryl", ".sif"}
WARN_EXTENSIONS = {".fa", ".fasta", ".fna", ".fas", ".vcf", ".bcf", ".gvcf", ".gff", ".gff3", ".gtf", ".bed", ".bw", ".bigwig", ".bigbed", ".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".xlsx", ".docx"}
BLOCK_BASENAMES = {".env", ".netrc", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"}
BLOCK_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".kdb", ".mmi", ".bt2", ".bt2l", ".amb", ".ann", ".bwt", ".pac", ".sa"}
BLOCK_DIR_NAMES = {"logs", "tmp", "work", ".snakemake", ".nextflow", ".conda", "venv", ".venv", "env", "secrets", "credentials"}
SECRET_PATTERNS = (
    re.compile(r"(?i)-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
    re.compile(r"(?i)(?:github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,})"),
    re.compile(r"(?i)(?:api[_-]?key|access[_-]?token|secret[_-]?key|password)\s*[:=]\s*['\"]?[^\s'\"]{8,}"),
)


class AuditError(ValueError):
    pass


@dataclass(frozen=True)
class Finding:
    Status: str
    Rule_ID: str
    Git_State: str
    Relative_Path: str
    Size_MiB: str
    Detail: str
    Action: str


def run_git(project: Path, *arguments: str) -> str:
    result = subprocess.run(["git", "-C", str(project), *arguments], check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise AuditError(f"git {' '.join(arguments)} failed: {(result.stderr or result.stdout).strip() or result.returncode}")
    return result.stdout


def resolve_project(value: str) -> Path:
    raw = Path(value).expanduser()
    if not raw.is_dir():
        raise AuditError(f"project must be an existing directory: {raw}")
    project = raw.resolve(strict=True)
    if project in {Path("/"), Path("/data9"), Path("/data9/home"), Path.home(), Path.home() / "projects"}:
        raise AuditError(f"refusing broad project root: {project}")
    if not (project / ".git").exists():
        raise AuditError(f"project is not a Git worktree: {project}")
    run_git(project, "rev-parse", "--is-inside-work-tree")
    return project


def normalize(path: str) -> str:
    candidate = Path(path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise AuditError(f"unsafe Git relative path: {path!r}")
    return candidate.as_posix()


def git_paths(project: Path, *arguments: str) -> set[str]:
    return {normalize(path) for path in run_git(project, *arguments).split("\0") if path}


def size_mib(path: Path) -> str:
    try:
        return f"{path.stat().st_size / (1024 * 1024):.2f}"
    except OSError:
        return "NA"


def state_for(path: str, staged: set[str], tracked: set[str], untracked: set[str]) -> str:
    states = (["Staged"] if path in staged else []) + (["Tracked"] if path in tracked else []) + (["Untracked"] if path in untracked else [])
    return "+".join(states) if states else "Unknown"


def ancestor_name(path: Path) -> str | None:
    return next((part for part in path.parts[:-1] if part in BLOCK_DIR_NAMES), None)


def scan_secret(path: Path) -> bool:
    try:
        if path.stat().st_size > MAX_SECRET_SCAN:
            return False
        data = path.read_bytes()[:MAX_SECRET_SCAN]
    except OSError:
        return False
    if b"\0" in data:
        return False
    text = data.decode("utf-8", errors="ignore")
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def audit_one(project: Path, layout: layout_contract.ProjectLayout, relative_text: str, state: str) -> list[Finding]:
    relative = Path(relative_text)
    path = project / relative
    size = size_mib(path)
    found: list[Finding] = []

    def add(status: str, rule: str, detail: str, action: str) -> None:
        found.append(Finding(status, rule, state, relative_text, size, detail, action))

    if path.is_symlink():
        try:
            path.resolve(strict=False).relative_to(project)
        except ValueError:
            add("BLOCK", "GIT004", "symbolic link resolves outside project", "remove from index; record external source in manifest")
        else:
            add("BLOCK", "GIT004", "symbolic links are not versioned project evidence", "replace with manifest path/checksum")
        return found
    if not path.exists() or not path.is_file():
        add("WARN", "GIT005", "Git path is missing or not a regular worktree file", "inspect deletion or special-file intent")
        return found
    if relative.parts and relative.parts[0] == layout.rawdata_root and relative.as_posix() != f"{layout.rawdata_root}/README.md":
        add("BLOCK", "GIT001", f"raw input under {layout.rawdata_root}/", "remove from index; retain manifest/checksum only")
        return found
    if (blocked_dir := ancestor_name(relative)):
        add("BLOCK", "GIT002", f"runtime/cache/secret path under {blocked_dir}/", "remove from index and retain ignore rule")
        return found
    name, suffix = relative.name, relative.suffix.lower()
    if name in BLOCK_BASENAMES or name.startswith(".env.") or suffix in BLOCK_SUFFIXES:
        add("BLOCK", "GIT003", "credential/private-key/large-index filename pattern", "remove from index; rotate real credentials")
        return found
    if suffix in BLOCK_EXTENSIONS:
        add("BLOCK", "GIT006", f"raw/alignment/binary bioinformatics extension {suffix}", "store externally; commit manifest/checksum")
        return found
    try:
        byte_size = path.stat().st_size
    except OSError:
        byte_size = 0
    if byte_size >= BLOCK_SIZE:
        add("BLOCK", "GIT007", "file is at least 100 MiB", "remove from index; use external storage/manifest")
        return found
    if byte_size >= WARN_SIZE:
        add("WARN", "GIT008", "file is at least 50 MiB", "review size/licence before ordinary Git")
    if suffix in WARN_EXTENSIONS:
        add("WARN", "GIT009", f"bioinformatics or binary-delivery extension {suffix}", "confirm compact reviewed deliverable")
    if scan_secret(path):
        add("BLOCK", "GIT010", "content matches credential/private-key heuristic", "remove from index; rotate/revoke any real credential")
    if not found:
        add("PASS", "GIT_OK", "reviewable text/config/source-table candidate", "review git diff before explicit staging")
    return found


def ignore_findings(project: Path, layout: layout_contract.ProjectLayout) -> list[Finding]:
    path = project / ".gitignore"
    if path.is_symlink() or not path.is_file():
        return [Finding("WARN", "GIT011", "Worktree", ".gitignore", "NA", "missing or symlinked .gitignore", "add Bioflow Gitignore template")]
    lines = {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#")}
    required = {"logs/", "tmp/", ".snakemake/", ".nextflow/", ".env", "*.bam", "*.cram"}
    if layout.is_v2:
        required.add("rawdata/*")
    missing = sorted(required - lines)
    if missing:
        return [Finding("WARN", "GIT011", "Worktree", ".gitignore", size_mib(path), f"missing recommended ignore rules: {', '.join(missing)}", "merge Bioflow Gitignore template; manually untrack prior files")]
    return [Finding("PASS", "GIT_IGNORE_OK", "Worktree", ".gitignore", size_mib(path), "core Bioflow ignore rules present", "keep ignore policy reviewed")]


def audit(project: Path, include_untracked: bool) -> list[Finding]:
    layout = layout_contract.detect_layout(project)
    tracked = git_paths(project, "ls-files", "-z")
    staged = git_paths(project, "diff", "--cached", "--name-only", "-z")
    untracked = git_paths(project, "ls-files", "--others", "--exclude-standard", "-z") if include_untracked else set()
    candidates = sorted((tracked | staged | untracked) if include_untracked else staged, key=lambda value: (value.casefold(), value))
    if len(candidates) > MAX_CANDIDATES:
        raise AuditError(f"candidate count exceeds bounded cap {MAX_CANDIDATES}")
    findings = ignore_findings(project, layout)
    for relative in candidates:
        findings.extend(audit_one(project, layout, relative, state_for(relative, staged, tracked, untracked)))
    return sorted(findings, key=lambda item: (-SEVERITY[item.Status], item.Relative_Path.casefold(), item.Rule_ID, item.Git_State))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Bioflow Git safety audit")
    parser.add_argument("--project", required=True)
    parser.add_argument("--format", choices=("text", "tsv", "json"), default="text")
    parser.add_argument("--staged-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        project = resolve_project(args.project)
        findings = audit(project, include_untracked=not args.staged_only)
    except (AuditError, layout_contract.LayoutError, OSError, subprocess.SubprocessError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        import json
        print(json.dumps({"Project": str(project), "Findings": [asdict(item) for item in findings]}, indent=2, ensure_ascii=False))
    elif args.format == "tsv":
        writer = csv.DictWriter(sys.stdout, fieldnames=AUDIT_COLUMNS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for item in findings:
            writer.writerow(asdict(item))
    else:
        for item in findings:
            print(f"{item.Status} | {item.Rule_ID} | {item.Git_State} | {item.Relative_Path} | {item.Detail}")
    worst = max((SEVERITY[item.Status] for item in findings), default=0)
    return 2 if worst == 2 else 1 if worst == 1 else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        # A bounded shell preview such as `--format tsv | head` is diagnostic,
        # not an audit failure; avoid an interpreter traceback after head closes.
        try:
            sys.stdout.close()
        except OSError:
            pass
        raise SystemExit(0)
