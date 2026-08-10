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
if command -v claude >/dev/null 2>&1 && [[ -d plugins/bioflow ]]; then
    printf '[TEST] Claude plugin\n'
    claude plugin validate plugins/bioflow
else
    printf '[WARN] Claude CLI or wrapper unavailable; skipped\n'
fi

printf '[TEST] Plugin drift dry-run\n'
scripts/sync_plugin_wrapper.sh

printf '[TEST] Git whitespace\n'
git diff --check

printf 'PASS | bioflow maintenance suite\n'
