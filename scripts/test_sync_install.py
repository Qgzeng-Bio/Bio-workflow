#!/usr/bin/env python3
"""Exercise runtime payload sync only in disposable sources and isolated HOME."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

SCRIPT = Path(__file__).resolve().with_name("sync_install.sh")
ROLES = ("references", "scripts", "assets", "agents")


def fingerprint(root: Path) -> dict:
    result = {}
    if not root.exists():
        return result
    for path in sorted(root.rglob("*")):
        stat = path.lstat()
        value = os.readlink(path) if path.is_symlink() else hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "DIRECTORY"
        result[path.relative_to(root).as_posix()] = (stat.st_mode, stat.st_mtime_ns, value)
    return result


def source_tree(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "SKILL.md").write_text("---\nname: fixture\ndescription: Synthetic fixture\n---\n")
    for role in ROLES:
        (path / role).mkdir()
        (path / role / "Payload.txt").write_text(role + "\n")
    for relative in ["README.md", "HANDOFF.md", "docs/history/Old.md", "reports/Evidence.md", "plugins/Wrapper.md", ".pi/settings.json", ".git/config", "tmp/Scratch.txt", "references/__pycache__/cache.pyc"]:
        item = path / relative
        item.parent.mkdir(parents=True, exist_ok=True)
        item.write_text("development-only fixture\n")
    return path


with tempfile.TemporaryDirectory(prefix="bioflow-sync-install-test.") as temporary:
    base = Path(temporary)
    home = base / "home"
    home.mkdir()
    source = source_tree(base / "source")
    target = home / ".codex/skills/bioflow"
    env = {**os.environ, "HOME": str(home)}

    def run(src: Path = source, dst: Path | str = target, *, write: bool = False) -> subprocess.CompletedProcess[str]:
        args = ["bash", str(SCRIPT), "--source", str(src), "--target", str(dst), "--skip-validate"]
        if write:
            args.append("--yes")
        return subprocess.run(args, env=env, text=True, capture_output=True, check=False)

    before = fingerprint(home)
    result = run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert fingerprint(home) == before and not target.exists()
    print("PASS | sync dry-run leaves an absent target and HOME unchanged")

    target.mkdir(parents=True)
    (target / "references").mkdir()
    (target / "references/Stale.md").write_text("old managed payload\n")
    (target / "reports").mkdir()
    (target / "reports/Keep.md").write_text("target-local evidence\n")
    (target / "HANDOFF.md").write_text("target-local historical handoff\n")
    (target / "Local.txt").write_text("target-local file\n")
    excluded_before = {name: (target / name).read_bytes() for name in ["reports/Keep.md", "HANDOFF.md", "Local.txt"]}
    before = fingerprint(home)
    assert run().returncode == 0
    assert fingerprint(home) == before
    result = run(write=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (target / "SKILL.md").read_bytes() == (source / "SKILL.md").read_bytes()
    for role in ROLES:
        assert (target / role / "Payload.txt").read_bytes() == (source / role / "Payload.txt").read_bytes()
    assert (target / "references/Stale.md").read_text() == "old managed payload\n"
    for name, data in excluded_before.items():
        assert (target / name).read_bytes() == data
    for relative in ["README.md", "docs", "reports/Evidence.md", "plugins", ".pi", ".git", "tmp", "references/__pycache__"]:
        assert not (target / relative).exists(), relative
    assert "target extras retained (not a strict mirror)" in result.stdout
    print("PASS | only runtime payload copied; target-local files retained inside and outside payload roots")

    before = fingerprint(home)
    result = run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert fingerprint(home) == before
    assert not any(line.startswith((">f", "cd", "*deleting", ".d", ".f")) for line in result.stdout.splitlines()), result.stdout

    # Same size and mtime changes must still be detected through --checksum.
    item = source / "references/Payload.txt"
    old_stat = item.stat()
    item.write_text("REFERENCES\n")
    os.utime(item, ns=(old_stat.st_atime_ns, old_stat.st_mtime_ns))
    assert item.stat().st_size == (target / "references/Payload.txt").stat().st_size
    result = run(write=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert item.read_bytes() == (target / "references/Payload.txt").read_bytes()
    retained = target / "agents/Payload.txt"
    retained_bytes = retained.read_bytes()
    (source / "agents/Payload.txt").unlink()
    result = run(write=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert retained.read_bytes() == retained_bytes
    assert "not a strict mirror" in result.stdout
    print("PASS | repeated dry-run clean; same-size/mtime drift repaired; removed source files retained at target")

    incomplete = source_tree(base / "incomplete")
    shutil.rmtree(incomplete / "agents")
    before = fingerprint(home)
    assert run(incomplete, write=True).returncode == 2
    assert fingerprint(home) == before
    assert run(dst=base / "outside", write=True).returncode == 2
    assert not (base / "outside").exists()

    source_link = source_tree(base / "source-link")
    shutil.rmtree(source_link / "references")
    (source_link / "references").symlink_to(source / "references", target_is_directory=True)
    assert run(source_link, write=True).returncode == 2
    assert fingerprint(home) == before

    unsafe = home / ".codex/skills/unsafe"
    unsafe.mkdir()
    outside = base / "outside-data"
    outside.mkdir()
    (outside / "Keep.md").write_text("must remain unchanged\n")
    (unsafe / "references").symlink_to(outside, target_is_directory=True)
    before = fingerprint(home)
    outside_before = fingerprint(outside)
    assert run(dst=unsafe, write=True).returncode == 2
    assert fingerprint(home) == before and fingerprint(outside) == outside_before

    linked = home / ".codex/skills/linked"
    linked.symlink_to(target, target_is_directory=True)
    before = fingerprint(home)
    assert run(dst=linked, write=True).returncode == 2
    assert fingerprint(home) == before
    (source / "SKILL.md").write_text((source / "SKILL.md").read_text() + "\n# Sentinel update\n")
    for spelling in [str(linked) + "/", str(linked) + "/.", str(linked) + "/.///./"]:
        result = run(dst=spelling, write=True)
        assert result.returncode == 2, f"symlink target spelling was accepted: {spelling}\n{result.stdout}{result.stderr}"
        assert fingerprint(home) == before
    print("PASS | symlink targets with trailing slash/dot spellings rejected without referent writes")

    overlap = source_tree(home / ".codex/skills/source")
    before = fingerprint(home)
    assert run(overlap, overlap / "nested", write=True).returncode == 2
    assert run(overlap, overlap, write=True).returncode == 2
    assert fingerprint(home) == before
    print("PASS | incomplete sources, unsafe paths, symlink roots, and source/target overlap blocked")

print("PASS | isolated runtime sync regression")
