#!/usr/bin/env python3
"""Verify suite routing using an isolated fake toolchain, without running suites recursively."""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

RUNNER = Path(__file__).resolve().with_name("test_skill.sh")

with tempfile.TemporaryDirectory(prefix="bioflow-maintenance-mode-test.") as name:
    base = Path(name)
    root = base / "repo"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    runner = scripts / "test_skill.sh"
    shutil.copy2(RUNNER, runner)
    text = runner.read_text()
    events = base / "Events.txt"
    home = base / "home"
    home.mkdir()
    binaries = base / "bin"
    binaries.mkdir()

    def executable(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/bin/bash\nset -euo pipefail\n" + content)
        path.chmod(0o755)

    for relative in set(re.findall(r"(?:^|\n)(?:bash )?(scripts/test_[A-Za-z0-9_]+\.sh)", text)):
        path = root / relative
        if path == runner:
            continue
        executable(path, 'printf "SHELL %s\\n" "$(basename "$0")" >> "$TEST_EVENTS"\n')
    templates = root / "assets/slurm-templates"
    templates.mkdir(parents=True)
    (templates / "fixture.sbatch").write_text("#!/bin/bash\nset -euo pipefail\n")
    executable(binaries / "python", 'printf "PY %s\\n" "$*" >> "$TEST_EVENTS"\n')
    executable(binaries / "git", '[[ "$*" == "diff --check" ]]\nprintf "GIT %s\\n" "$*" >> "$TEST_EVENTS"\n')
    executable(binaries / "claude", 'printf "CLAUDE %s\\n" "$*" >> "$TEST_EVENTS"\n')
    executable(scripts / "sync_plugin_wrapper.sh", 'printf "WRAPPER %s\\n" "$*" >> "$TEST_EVENTS"\nexit "${FAKE_DRIFT_RC:-0}"\n')
    env = {
        **os.environ,
        "HOME": str(home),
        "PYTHON_BIN": str(binaries / "python"),
        "CLAUDE_BIN": str(binaries / "claude"),
        "PI_CODING_AGENT_DIR": str(home / ".pi/agent"),
        "PI_ASK_DIR": str(home / "missing-pi-ask"),
        "PATH": str(binaries) + os.pathsep + os.environ.get("PATH", ""),
        "TEST_EVENTS": str(events),
    }

    def run(*args: str, drift: int = 0):
        events.write_text("")
        result = subprocess.run(["bash", str(runner), *args], env={**env, "FAKE_DRIFT_RC": str(drift)}, text=True, capture_output=True, check=False)
        return result, events.read_text()

    result, calls = run("--help")
    assert result.returncode == 0 and "--source-only" in result.stdout and not calls
    result, calls = run("--invalid")
    assert result.returncode == 2 and "Unknown argument" in result.stderr and not calls
    print("PASS | help and invalid arguments stop before test execution")

    result, calls = run("--source-only", drift=1)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS | bioflow source suite (runtime/plugin distribution not checked)" in result.stdout
    assert "PASS | bioflow maintenance suite" not in result.stdout
    assert "WRAPPER" not in calls and "CLAUDE" not in calls
    assert "[TEST] Pi integration" not in result.stdout
    for required in ["test_publication_trace_audit.py", "test_sync_install.py", "test_maintenance_modes.py", "test_slurm_preflight.sh", "validate_program_cards.py --check-drafts", "GIT diff --check"]:
        assert required in calls, required
    assert calls.count("PY scripts/validate_program_cards.py") == 1, "active-card validation must not be repeated before --check-drafts"
    print("PASS | source-only retains source checks without claiming runtime/distribution validation")

    result, calls = run(drift=1)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "WRAPPER --check" in calls
    assert "[TEST] Pi integration" in result.stdout
    assert "PASS | bioflow maintenance suite" not in result.stdout
    result, calls = run(drift=0)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "WRAPPER --check" in calls and "GIT diff --check" in calls
    assert "PASS | bioflow maintenance suite" in result.stdout
    print("PASS | default suite retains strict plugin drift failure and full-mode success marker")

    # Bash accepts just one script filename; later argv entries are not syntax-checked.
    for broken, args in [(scripts / "zz_invalid.sh", ("--source-only",)), (templates / "zz_invalid.sbatch", ())]:
        broken.write_text("#!/bin/bash\nif true; then\n")
        result, calls = run(*args)
        assert result.returncode != 0 and "PASS | bioflow" not in result.stdout, f"invalid later shell/template escaped syntax gate: {broken}\n{result.stdout}"
        assert not calls, "syntax failures must stop before Python/fixture execution"
        broken.unlink()
    print("PASS | later shell scripts and sbatch templates are each syntax-checked")

print("PASS | isolated maintenance-mode routing regression")
