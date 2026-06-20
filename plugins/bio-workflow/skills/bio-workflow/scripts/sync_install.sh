#!/usr/bin/env bash
# sync_install.sh - guarded source-to-Codex-runtime sync for bio-workflow.
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage:
  scripts/sync_install.sh [--yes] [--source DIR] [--target DIR] [--python PYTHON] [--skip-validate]

Synchronize this source skill into the Codex runtime copy.

Defaults:
  --source  directory above this script
  --target  /data9/home/qgzeng/.codex/skills/bio-workflow

Behavior:
  - without --yes: dry-run only; prints rsync itemized changes and writes nothing.
  - with    --yes: validates source, rsyncs with --delete, then validates target.

Excluded from sync:
  .git, .claude, .codex, .agents, tmp, __pycache__, *.pyc

Options:
  --yes            actually write to the Codex runtime copy
  --source DIR     source skill directory
  --target DIR     Codex runtime skill directory; must be under ~/.codex/skills
  --python PYTHON  Python interpreter to use for quick_validate.py
  --skip-validate  skip quick_validate.py
  -h, --help       show this help
USAGE
}

do_sync=0
source_dir=""
target_dir="/data9/home/qgzeng/.codex/skills/bio-workflow"
python_bin="${PYTHON_BIN:-}"
skip_validate=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --yes) do_sync=1; shift ;;
        --source) [[ $# -ge 2 ]] || { echo "ERROR | --source requires a value" >&2; exit 2; }; source_dir="$2"; shift 2 ;;
        --target) [[ $# -ge 2 ]] || { echo "ERROR | --target requires a value" >&2; exit 2; }; target_dir="$2"; shift 2 ;;
        --python) [[ $# -ge 2 ]] || { echo "ERROR | --python requires a value" >&2; exit 2; }; python_bin="$2"; shift 2 ;;
        --skip-validate) skip_validate=1; shift ;;
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
target_dir="$(resolve_path "$target_dir")"

[[ -f "$source_dir/SKILL.md" ]] || { echo "ERROR | Source is not a skill directory: $source_dir" >&2; exit 2; }
case "$target_dir" in
    /data9/home/qgzeng/.codex/skills/*) ;;
    *) echo "ERROR | Target must be under /data9/home/qgzeng/.codex/skills: $target_dir" >&2; exit 2 ;;
esac
[[ "$source_dir" != "$target_dir" ]] || { echo "ERROR | Source and target are identical; refusing to sync" >&2; exit 2; }

validator="/data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py"

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
    for candidate in /data9/home/qgzeng/anaconda3/bin/python python3 python; do
        if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import yaml' >/dev/null 2>&1; then
            command -v "$candidate"
            return 0
        fi
    done
    echo "ERROR | No Python with PyYAML found; pass --python or use --skip-validate" >&2
    exit 2
}

run_validate() {
    local path="$1"
    [[ "$skip_validate" -eq 0 ]] || return 0
    [[ -r "$validator" ]] || { echo "ERROR | quick_validate.py not readable: $validator" >&2; exit 2; }
    "$python_bin" "$validator" "$path"
}

python_bin="$(choose_python)"

rsync_args=(
    -a
    --delete
    --itemize-changes
    --omit-dir-times
    --exclude '/.git/'
    --exclude '/.claude/'
    --exclude '/.codex/'
    --exclude '/.agents/'
    --exclude '/tmp/'
    --exclude '__pycache__/'
    --exclude '*.pyc'
)

if [[ "$do_sync" -eq 0 ]]; then
    rsync_args=(-n "${rsync_args[@]}")
fi

echo "SOURCE | $source_dir"
echo "TARGET | $target_dir"
if [[ "$do_sync" -eq 0 ]]; then
    echo "MODE   | dry-run; add --yes to write"
else
    echo "MODE   | write"
fi
echo "PYTHON | $python_bin"

run_validate "$source_dir"

if [[ "$do_sync" -eq 1 ]]; then
    mkdir -p "$target_dir"
fi

rsync "${rsync_args[@]}" "$source_dir/" "$target_dir/"

if [[ "$do_sync" -eq 1 ]]; then
    run_validate "$target_dir"
    echo "DIFF   | source vs Codex runtime, expected differences should be source-local only"
    diff -qr \
        --exclude=.git \
        --exclude=.claude \
        --exclude=.codex \
        --exclude=.agents \
        --exclude=tmp \
        --exclude=__pycache__ \
        "$source_dir" "$target_dir" || true
fi
