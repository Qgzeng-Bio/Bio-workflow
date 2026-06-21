#!/usr/bin/env bash
# sync_plugin_wrapper.sh - guarded raw-skill to Codex plugin-wrapper sync.
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage:
  scripts/sync_plugin_wrapper.sh [--yes] [--source DIR] [--plugin DIR] [--python PYTHON] [--skip-validate] [--skip-claude-validate]

Synchronize the raw bio-workflow skill source into the repo-local plugin wrapper
at plugins/bio-workflow/skills/bio-workflow. The same wrapper contains Codex and
Claude Code plugin manifests when both are present.

Defaults:
  --source  directory above this script
  --plugin  <source>/plugins/bio-workflow

Behavior:
  - without --yes: dry-run only; prints rsync itemized changes and writes nothing.
  - with    --yes: validates source, syncs the skill copy, then validates plugin manifests.

Synced into the plugin skill copy:
  SKILL.md, references/, scripts/, assets/, agents/

Excluded:
  .git, .claude, .codex, .agents, tmp, __pycache__, *.pyc

Options:
  --yes            actually write to the plugin wrapper skill copy
  --source DIR     source skill directory
  --plugin DIR     plugin root directory containing .codex-plugin/plugin.json
  --python PYTHON  Python interpreter to use for validators
  --skip-validate  skip quick_validate.py and plugin validators
  --skip-claude-validate
                  skip `claude plugin validate` even when Claude Code is available
  -h, --help       show this help
USAGE
}

do_sync=0
source_dir=""
plugin_dir=""
python_bin="${PYTHON_BIN:-}"
skip_validate=0
skip_claude_validate=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --yes) do_sync=1; shift ;;
        --source) [[ $# -ge 2 ]] || { echo "ERROR | --source requires a value" >&2; exit 2; }; source_dir="$2"; shift 2 ;;
        --plugin) [[ $# -ge 2 ]] || { echo "ERROR | --plugin requires a value" >&2; exit 2; }; plugin_dir="$2"; shift 2 ;;
        --python) [[ $# -ge 2 ]] || { echo "ERROR | --python requires a value" >&2; exit 2; }; python_bin="$2"; shift 2 ;;
        --skip-validate) skip_validate=1; shift ;;
        --skip-claude-validate) skip_claude_validate=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "ERROR | Unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -z "$source_dir" ]]; then
    source_dir="$(cd "$script_dir/.." && pwd)"
fi

resolve_path() {
    local p="$1"
    command -v realpath >/dev/null 2>&1 || { echo "ERROR | realpath is required" >&2; exit 2; }
    realpath -m -- "$p"
}

source_dir="$(resolve_path "$source_dir")"
if [[ -z "$plugin_dir" ]]; then
    plugin_dir="$source_dir/plugins/bio-workflow"
fi
plugin_dir="$(resolve_path "$plugin_dir")"
target_skill_dir="$plugin_dir/skills/bio-workflow"

[[ -f "$source_dir/SKILL.md" ]] || { echo "ERROR | Source is not a skill directory: $source_dir" >&2; exit 2; }
[[ -f "$plugin_dir/.codex-plugin/plugin.json" || -f "$plugin_dir/.claude-plugin/plugin.json" ]] || {
    echo "ERROR | Plugin manifest missing: expected .codex-plugin/plugin.json or .claude-plugin/plugin.json under $plugin_dir" >&2
    exit 2
}
case "$plugin_dir" in
    "$source_dir"/plugins/*) ;;
    *) echo "ERROR | Plugin dir must stay under source plugins/: $plugin_dir" >&2; exit 2 ;;
esac
[[ "$source_dir" != "$target_skill_dir" ]] || { echo "ERROR | Source and target skill directories are identical" >&2; exit 2; }

skill_validator="${HOME%/}/.codex/skills/.system/skill-creator/scripts/quick_validate.py"
plugin_validator="${HOME%/}/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py"

choose_python() {
    local candidate
    if [[ -n "$python_bin" ]]; then
        [[ -x "$python_bin" ]] || { echo "ERROR | --python is not executable: $python_bin" >&2; exit 2; }
        "$python_bin" -c 'import yaml' >/dev/null 2>&1 || {
            echo "ERROR | --python cannot import yaml: $python_bin" >&2
            exit 2
        }
        printf '%s\n' "$python_bin"
        return 0
    fi
    for candidate in "${HOME%/}/anaconda3/bin/python" python3 python; do
        if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import yaml' >/dev/null 2>&1; then
            command -v "$candidate"
            return 0
        fi
    done
    echo "ERROR | No Python with PyYAML found; pass --python or use --skip-validate" >&2
    exit 2
}

run_source_validate() {
    [[ "$skip_validate" -eq 0 ]] || return 0
    # Multi-user: the skill-creator validator lives under each user's own ~/.codex.
    # If it is absent, warn and skip rather than fail.
    [[ -r "$skill_validator" ]] || { echo "WARN   | quick_validate.py not found, skipping skill validation: $skill_validator" >&2; return 0; }
    "$python_bin" "$skill_validator" "$source_dir"
}

run_plugin_validate() {
    [[ "$skip_validate" -eq 0 ]] || return 0
    if [[ -f "$plugin_dir/.codex-plugin/plugin.json" ]]; then
        if [[ -r "$plugin_validator" ]]; then
            "$python_bin" "$plugin_validator" "$plugin_dir"
        else
            echo "WARN   | validate_plugin.py not found, skipping Codex plugin validation: $plugin_validator" >&2
        fi
    fi
    if [[ -f "$plugin_dir/.claude-plugin/plugin.json" ]]; then
        if [[ "$skip_claude_validate" -eq 1 ]]; then
            echo "WARN   | skipping Claude plugin validation by request"
        elif command -v claude >/dev/null 2>&1; then
            claude plugin validate "$plugin_dir"
        else
            echo "WARN   | claude command not found; skipping Claude plugin validation"
        fi
    fi
}

# Only a validating run needs a PyYAML Python. If validation is skipped or both
# validators are absent (multi-user / non-Codex install), do not hard-require one.
if [[ "$skip_validate" -eq 0 && ( -r "$skill_validator" || -r "$plugin_validator" ) ]]; then
    python_bin="$(choose_python)"
fi

rsync_args=(
    -a
    --delete
    --delete-excluded
    --itemize-changes
    --omit-dir-times
    --exclude '/.git/'
    --exclude '/.claude/'
    --exclude '/.codex/'
    --exclude '/.agents/'
    --exclude '/tmp/'
    --exclude '/scripts/__pycache__/'
    --exclude '__pycache__/'
    --exclude '*.pyc'
    --include '/SKILL.md'
    --include '/references/***'
    --include '/scripts/***'
    --include '/assets/***'
    --include '/agents/***'
    --exclude '*'
)

if [[ "$do_sync" -eq 0 ]]; then
    rsync_args=(-n "${rsync_args[@]}")
fi

echo "SOURCE | $source_dir"
echo "PLUGIN | $plugin_dir"
echo "TARGET | $target_skill_dir"
if [[ "$do_sync" -eq 0 ]]; then
    echo "MODE   | dry-run; add --yes to write"
else
    echo "MODE   | write"
fi
echo "PYTHON | $python_bin"

run_source_validate

if [[ "$do_sync" -eq 1 ]]; then
    mkdir -p "$target_skill_dir"
elif [[ ! -d "$target_skill_dir" ]]; then
    echo "DRYRUN | would create $target_skill_dir"
fi

rsync "${rsync_args[@]}" "$source_dir/" "$target_skill_dir/"

if [[ "$do_sync" -eq 1 || -f "$target_skill_dir/SKILL.md" ]]; then
    run_plugin_validate
fi
