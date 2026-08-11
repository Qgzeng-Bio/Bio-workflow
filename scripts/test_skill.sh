#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$root"

python_bin="${PYTHON_BIN:-}"
if [[ -z "$python_bin" ]]; then
    for candidate in "${HOME%/}/anaconda3/bin/python" python3 python; do
        if command -v "$candidate" >/dev/null 2>&1 \
            && "$candidate" -c 'import yaml' >/dev/null 2>&1; then
            python_bin="$candidate"
            break
        fi
    done
fi
[[ -n "$python_bin" ]] || { echo 'FAIL | no Python with PyYAML found' >&2; exit 1; }

claude_bin=""
choose_claude() {
    local candidate
    if [[ -n "${CLAUDE_BIN:-}" ]]; then
        if [[ ! -x "$CLAUDE_BIN" ]]; then
            printf 'FAIL | CLAUDE_BIN is not executable: %s\n' "$CLAUDE_BIN" >&2
            return 2
        fi
        claude_bin="$CLAUDE_BIN"
        return 0
    fi
    if candidate="$(command -v claude 2>/dev/null)"; then
        claude_bin="$candidate"
        return 0
    fi
    candidate="${HOME%/}/anaconda3/envs/claude/bin/claude"
    if [[ -x "$candidate" ]]; then
        claude_bin="$candidate"
        return 0
    fi
    return 1
}

cache="$(mktemp -d /tmp/bioflow-test-cache.XXXXXX)"
trap 'rm -rf "$cache"' EXIT
export PYTHONPYCACHEPREFIX="$cache/pycache"

printf '[TEST] Shell syntax\n'
bash -n scripts/*.sh assets/slurm-templates/*.sbatch

printf '[TEST] Python compile\n'
"$python_bin" -m py_compile scripts/*.py

printf '[TEST] Regression fixtures\n'
scripts/test_init_project.sh
scripts/test_project_lifecycle.sh
"$python_bin" scripts/test_project_dashboard.py
scripts/test_claim_audit.sh
scripts/test_slurm_preflight.sh
"$python_bin" scripts/test_result_contract.py
"$python_bin" scripts/test_fill_gap_from_spanning_alignment.py
"$python_bin" scripts/test_reference_consistency.py
"$python_bin" scripts/test_prepare_paperplot_handoff.py
"$python_bin" scripts/test_path_manager.py
"$python_bin" scripts/test_workspace_steward.py
bash scripts/test_workspace_integration.sh

quick_validate="${HOME%/}/.codex/skills/.system/skill-creator/scripts/quick_validate.py"
if [[ -f "$quick_validate" ]]; then
    printf '[TEST] Skill validation\n'
    "$python_bin" "$quick_validate" .
else
    printf '[WARN] Skill validator unavailable; skipped: %s\n' "$quick_validate"
fi

printf '[TEST] Pi integration\n'
pi_agent_dir="${PI_CODING_AGENT_DIR:-${HOME%/}/.pi/agent}"
pi_bioflow="$pi_agent_dir/skills/bioflow/SKILL.md"
pi_paperplot="$pi_agent_dir/skills/paperplot-skills/SKILL.md"
if [[ -f "$pi_bioflow" ]]; then
    cmp -s SKILL.md "$pi_bioflow" \
        || { printf 'FAIL | Pi bioflow SKILL.md drift: %s\n' "$pi_bioflow" >&2; exit 1; }
    printf 'PASS | Pi bioflow entry matches source\n'
else
    printf '[WARN] Pi bioflow entry unavailable; skipped: %s\n' "$pi_bioflow"
fi
if [[ -f "$pi_paperplot" ]]; then
    grep -Eq '^name:[[:space:]]*paperplot-skills[[:space:]]*$' "$pi_paperplot" \
        || { printf 'FAIL | Pi PaperPlot name mismatch: %s\n' "$pi_paperplot" >&2; exit 1; }
    if grep -Eq '^disable-model-invocation:[[:space:]]*true[[:space:]]*$' "$pi_paperplot"; then
        printf 'FAIL | Pi PaperPlot is hidden from model invocation: %s\n' "$pi_paperplot" >&2
        exit 1
    fi
    if [[ -f "$quick_validate" ]]; then
        "$python_bin" "$quick_validate" "$(dirname "$pi_paperplot")"
    fi
    printf 'PASS | Pi PaperPlot is discoverable for model delegation\n'
else
    printf '[WARN] Pi PaperPlot entry unavailable; plotting delegation will report a blocker: %s\n' "$pi_paperplot"
fi
if [[ -f "$pi_agent_dir/settings.json" ]]; then
    "$python_bin" -m json.tool "$pi_agent_dir/settings.json" >/dev/null
    printf 'PASS | Pi settings JSON valid\n'
fi
pi_ask_dir="${PI_ASK_DIR:-${HOME%/}/projects/3-Biotools_create/pi-ask}"
if [[ -x "$pi_ask_dir/scripts/test.sh" ]]; then
    "$pi_ask_dir/scripts/test.sh"
    if [[ -f "$pi_agent_dir/settings.json" ]]; then
        "$python_bin" - "$pi_agent_dir/settings.json" "$pi_ask_dir" <<'PY'
import json
import sys
from pathlib import Path
settings = Path(sys.argv[1]).resolve()
expected = Path(sys.argv[2]).resolve()
data = json.loads(settings.read_text())
resolved = []
for item in data.get("packages", []):
    source = item if isinstance(item, str) else item.get("source") if isinstance(item, dict) else None
    if not source or source.startswith(("npm:", "git:", "http:", "https:", "ssh:")):
        continue
    path = Path(source)
    resolved.append((path if path.is_absolute() else settings.parent / path).resolve())
assert expected in resolved, f"pi-ask is not registered in {settings}"
PY
        printf 'PASS | pi-ask package registered in Pi settings\n'
    fi
else
    printf '[WARN] Optional pi-ask package unavailable; Bioflow will use text questions: %s\n' "$pi_ask_dir"
fi

printf '[TEST] Program cards\n'
"$python_bin" scripts/validate_program_cards.py
"$python_bin" scripts/validate_program_cards.py --check-drafts

plugin_validate="${HOME%/}/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py"
if [[ -f "$plugin_validate" && -d plugins/bioflow ]]; then
    printf '[TEST] Codex plugin\n'
    "$python_bin" "$plugin_validate" plugins/bioflow
else
    printf '[WARN] Codex plugin validator or wrapper unavailable; skipped\n'
fi
if [[ ! -d plugins/bioflow ]]; then
    printf '[WARN] Claude plugin wrapper unavailable; skipped\n'
elif choose_claude; then
    printf '[TEST] Claude plugin | %s\n' "$claude_bin"
    "$claude_bin" plugin validate plugins/bioflow
else
    status=$?
    [[ "$status" -ne 2 ]] || exit 1
    printf '[WARN] Claude CLI not found in CLAUDE_BIN, PATH, or ~/anaconda3/envs/claude/bin; skipped\n'
fi

printf '[TEST] Plugin drift dry-run\n'
scripts/sync_plugin_wrapper.sh

printf '[TEST] Git whitespace\n'
git diff --check

printf 'PASS | bioflow maintenance suite\n'
