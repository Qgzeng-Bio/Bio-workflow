#!/usr/bin/env bash
# sync_install.sh - guarded source-to-Codex-runtime sync for bioflow.
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage:
  scripts/sync_install.sh [--yes] [--source DIR] [--target DIR] [--python PYTHON] [--skip-validate]

Synchronize only the managed Bioflow runtime payload into the Codex copy.

Defaults:
  --source  directory above this script
  --target  $HOME/.codex/skills/bioflow

Behavior:
  - without --yes: dry-run only; prints rsync itemized changes and writes nothing.
  - with    --yes: validates source, syncs the managed payload, then validates target.
  - requires a complete source: SKILL.md, references/, scripts/, assets/, agents/.
  - target-only files are retained, even inside payload directories; this is not a strict mirror.
  - removal of obsolete or local target files requires a separate reviewed cleanup.

Managed runtime payload:
  SKILL.md, references/, scripts/, assets/, agents/

Not sent or automatically cleaned from the target:
  README.md, HANDOFF.md, docs/, reports/, plugins/, .git, local agent settings,
  tmp/, __pycache__, *.pyc, and all other paths outside the managed payload.

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
target_dir="${HOME%/}/.codex/skills/bioflow"
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

# Trailing '/' and '/.' dereference a link for Bash -L. Remove only those
# suffixes, without collapsing '..' or resolving links before this guard.
target_guard="$target_dir"
while :; do
    case "$target_guard" in
        */) target_guard="${target_guard%/}" ;;
        */.) target_guard="${target_guard%/.}" ;;
        *) break ;;
    esac
done
[[ -n "$target_guard" ]] || target_guard=/
[[ ! -L "$target_guard" ]] || { echo "ERROR | Target must not be a symlink: $target_dir" >&2; exit 2; }
source_dir="$(resolve_path "$source_dir")"
target_dir="$(resolve_path "$target_dir")"

[[ -f "$source_dir/SKILL.md" ]] || { echo "ERROR | Source is not a skill directory: $source_dir" >&2; exit 2; }
home_skills="$(resolve_path "${HOME%/}/.codex/skills")"
case "$target_dir" in
    "$home_skills"/*) ;;
    *) echo "ERROR | Target must be under $home_skills: $target_dir" >&2; exit 2 ;;
esac
[[ "$source_dir" != "$target_dir" ]] || { echo "ERROR | Source and target are identical; refusing to sync" >&2; exit 2; }
case "$target_dir/" in "$source_dir/"*) echo "ERROR | Target must not be inside source" >&2; exit 2 ;; esac
case "$source_dir/" in "$target_dir/"*) echo "ERROR | Source must not be inside target" >&2; exit 2 ;; esac
[[ ! -L "$source_dir/SKILL.md" ]] || { echo "ERROR | Source SKILL.md must not be a symlink" >&2; exit 2; }
if [[ -L "$target_dir/SKILL.md" || ( -e "$target_dir/SKILL.md" && ! -f "$target_dir/SKILL.md" ) ]]; then
    echo "ERROR | Target SKILL.md must be a regular file when present" >&2
    exit 2
fi
for payload_dir in references scripts assets agents; do
    if [[ ! -d "$source_dir/$payload_dir" || -L "$source_dir/$payload_dir" ]]; then
        echo "ERROR | Source payload directory missing or unsafe: $payload_dir" >&2
        exit 2
    fi
    if [[ -L "$target_dir/$payload_dir" || ( -e "$target_dir/$payload_dir" && ! -d "$target_dir/$payload_dir" ) ]]; then
        echo "ERROR | Target payload directory is unsafe: $payload_dir" >&2
        exit 2
    fi
done

validator="${HOME%/}/.codex/skills/.system/skill-creator/scripts/quick_validate.py"

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

run_validate() {
    local path="$1"
    [[ "$skip_validate" -eq 0 ]] || return 0
    # Multi-user: the skill-creator validator lives under each user's own ~/.codex.
    # If it is absent (e.g. a non-Codex install), warn and skip rather than fail.
    [[ -r "$validator" ]] || { echo "WARN   | quick_validate.py not found, skipping validation: $validator" >&2; return 0; }
    "$python_bin" "$validator" "$path"
}

# Only a validating run needs a PyYAML Python. If validation is skipped or the
# validator is absent (multi-user / non-Codex install), do not hard-require one.
if [[ "$skip_validate" -eq 0 && -r "$validator" ]]; then
    python_bin="$(choose_python)"
fi

rsync_args=(
    -a
    --checksum
    --itemize-changes
    --omit-dir-times
    --exclude '/.git/'
    --exclude '/.claude/'
    --exclude '/.codex/'
    --exclude '/.agents/'
    --exclude '/tmp/'
    --exclude '/生物信息学分析与论文写作_GitHub协同指导手册.md'
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
    echo "CHECK  | current source payload only; target-only files are retained"
    remaining="$(rsync -n "${rsync_args[@]}" "$source_dir/" "$target_dir/")"
    if [[ -n "$remaining" ]]; then
        printf '%s\n' "$remaining" >&2
        echo "ERROR | Managed runtime payload still differs after sync" >&2
        exit 1
    fi
    echo "PASS   | current source payload synchronized; target extras retained (not a strict mirror)"
fi
