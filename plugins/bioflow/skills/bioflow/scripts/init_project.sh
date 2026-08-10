#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage:
  scripts/init_project.sh --project <dir> [--yes]

Preview or create the minimal bioflow project layout and templates.
Dry-run is the default. --yes creates missing directories/files only; existing
files are never overwritten. Broad roots and protected ~/data or ~/tools paths
(including /data9/home/<user>/data|tools) are refused.
USAGE
}

project=""
write=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --project)
            [[ $# -ge 2 ]] || { echo "FAIL | --project requires a value" >&2; exit 2; }
            project="$2"
            shift 2
            ;;
        --yes)
            write=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "FAIL | Unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

[[ -n "$project" ]] || { echo "FAIL | --project is required" >&2; exit 2; }
command -v realpath >/dev/null 2>&1 || { echo "FAIL | realpath is required" >&2; exit 2; }

project_abs="$(realpath -m -- "$project")"
home_abs="$(realpath -m -- "${HOME:-/nonexistent}")"
case "$project_abs" in
    /|/data9|/data9/home|"$home_abs"|"${home_abs%/}/projects")
        echo "FAIL | Refusing broad project root: $project_abs" >&2
        exit 2
        ;;
esac
if [[ "$project_abs" =~ ^/data9/home/[^/]+/(data|tools)(/|$) ]] \
    || [[ "$project_abs" == "${home_abs%/}/data" || "$project_abs" == "${home_abs%/}/data/"* ]] \
    || [[ "$project_abs" == "${home_abs%/}/tools" || "$project_abs" == "${home_abs%/}/tools/"* ]]; then
    echo "FAIL | Refusing protected project path: $project_abs" >&2
    exit 2
fi

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
templates="$root/assets/project-templates"
[[ -d "$templates" ]] || { echo "FAIL | Missing templates: $templates" >&2; exit 2; }

dirs=(config data scripts logs tmp results reports)
sources=(
    "$templates/Input_Manifest.tsv"
    "$templates/Analysis_Plan.md"
    "$templates/workflow_status.tsv"
    "$templates/Task_Status.tsv"
    "$templates/Acceptance_Report.md"
    "$templates/Methods_Summary.md"
    "$templates/Delivery_Index.md"
)
targets=(
    "$project_abs/config/Input_Manifest.tsv"
    "$project_abs/reports/Analysis_Plan.md"
    "$project_abs/reports/workflow_status.tsv"
    "$project_abs/reports/Task_Status.tsv"
    "$project_abs/reports/Acceptance_Report.md"
    "$project_abs/reports/Methods_Summary.md"
    "$project_abs/reports/Delivery_Index.md"
)

printf 'PROJECT | %s\n' "$project_abs"
if [[ "$write" -eq 0 ]]; then
    printf 'MODE    | dry-run; add --yes to create missing paths\n'
else
    printf 'MODE    | write missing paths; never overwrite\n'
fi

for dir in "${dirs[@]}"; do
    path="$project_abs/$dir"
    if [[ -d "$path" ]]; then
        printf 'EXISTS  | %s\n' "$path"
    elif [[ "$write" -eq 1 ]]; then
        mkdir -p -- "$path"
        printf 'CREATED | %s\n' "$path"
    else
        printf 'WOULD_CREATE_DIR | %s\n' "$path"
    fi
done

for i in "${!sources[@]}"; do
    source="${sources[$i]}"
    target="${targets[$i]}"
    [[ -f "$source" ]] || { echo "FAIL | Missing template: $source" >&2; exit 2; }
    if [[ -e "$target" ]]; then
        printf 'EXISTS  | %s\n' "$target"
    elif [[ "$write" -eq 1 ]]; then
        install -m 0644 -- "$source" "$target"
        printf 'CREATED | %s\n' "$target"
    else
        printf 'WOULD_CREATE_FILE | %s\n' "$target"
    fi
done
