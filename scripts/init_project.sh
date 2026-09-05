#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage:
  scripts/init_project.sh --project <dir> [--workspace-steward] [--layout-v2|--legacy-layout] [--yes]

Preview or create a Bioflow project. A new or empty project defaults to layout v2:
config/rawdata/scripts/logs/tmp/results/docs/manuscripts. A non-empty project
without config/Project_Layout.tsv remains legacy (data/reports) and is never
rearranged. --layout-v2 explicitly opts an existing reviewed root into v2;
--legacy-layout explicitly requests the old seven-root skeleton.

Dry-run is the default. --yes creates missing directories/files only; existing
files are never overwritten. --workspace-steward explicitly installs Draft
workspace contracts. Broad and protected ~/data or ~/tools roots are refused.
USAGE
}

project=""
write=0
workspace_steward=0
force_v2=0
force_legacy=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --project)
            [[ $# -ge 2 ]] || { echo "FAIL | --project requires a value" >&2; exit 2; }
            project="$2"; shift 2 ;;
        --workspace-steward) workspace_steward=1; shift ;;
        --layout-v2) force_v2=1; shift ;;
        --legacy-layout) force_legacy=1; shift ;;
        --yes) write=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "FAIL | Unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

[[ -n "$project" ]] || { echo "FAIL | --project is required" >&2; exit 2; }
[[ "$force_v2" -eq 0 || "$force_legacy" -eq 0 ]] || { echo "FAIL | --layout-v2 and --legacy-layout are mutually exclusive" >&2; exit 2; }
command -v realpath >/dev/null 2>&1 || { echo "FAIL | realpath is required" >&2; exit 2; }

project_abs="$(realpath -m -- "$project")"
home_abs="$(realpath -m -- "${HOME:-/nonexistent}")"
case "$project_abs" in
    /|/data9|/data9/home|"$home_abs"|"${home_abs%/}/projects")
        echo "FAIL | Refusing broad project root: $project_abs" >&2; exit 2 ;;
esac
if [[ "$project_abs" =~ ^/data9/home/[^/]+/(data|tools)(/|$) ]] \
    || [[ "$project_abs" == "${home_abs%/}/data" || "$project_abs" == "${home_abs%/}/data/"* ]] \
    || [[ "$project_abs" == "${home_abs%/}/tools" || "$project_abs" == "${home_abs%/}/tools/"* ]]; then
    echo "FAIL | Refusing protected project path: $project_abs" >&2; exit 2
fi

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
templates="$root/assets/project-templates"
[[ -d "$templates" ]] || { echo "FAIL | Missing templates: $templates" >&2; exit 2; }

layout="v2"
marker="$project_abs/config/Project_Layout.tsv"
[[ ! -L "$marker" ]] || { echo "FAIL | Unsafe layout marker symlink: $marker" >&2; exit 2; }
if [[ "$force_v2" -eq 1 ]]; then
    for legacy_root in data reports; do
        if [[ -e "$project_abs/$legacy_root" || -L "$project_abs/$legacy_root" ]]; then
            echo "FAIL | --layout-v2 refuses an existing legacy root: $project_abs/$legacy_root" >&2
            echo "FAIL | Generate and review a migration plan; direct mixed-layout opt-in is forbidden." >&2
            exit 2
        fi
    done
    layout="v2"
elif [[ "$force_legacy" -eq 1 ]]; then
    [[ ! -e "$marker" ]] || { echo "FAIL | --legacy-layout conflicts with existing v2 marker: $marker" >&2; exit 2; }
    layout="legacy"
elif [[ -e "$marker" ]]; then
    [[ -f "$marker" ]] || { echo "FAIL | Unsafe layout marker: $marker" >&2; exit 2; }
    expected="$(cat "$templates/Project_Layout.tsv")"
    observed="$(cat "$marker")"
    [[ "$observed" == "$expected" ]] || { echo "FAIL | Unsupported or modified layout marker: $marker" >&2; exit 2; }
elif [[ -d "$project_abs" ]] && find "$project_abs" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null | grep -q .; then
    layout="legacy"
fi

sources=()
targets=()
if [[ "$layout" == "v2" ]]; then
    dirs=(config rawdata scripts logs tmp results docs manuscripts .github .github/ISSUE_TEMPLATE \
          config/parameters config/environments \
          docs/status docs/research-log docs/decisions docs/methods docs/validation docs/delivery)
    sources=(
        "$templates/Project_Layout.tsv" "$templates/Project_README.md"
        "$templates/PROJECT_STATUS.md" "$templates/CHANGELOG.md" "$templates/Gitignore"
        "$templates/Rawdata_README.md" "$templates/Input_Manifest.tsv"
        "$templates/Sample_Metadata.tsv" "$templates/Reference_Manifest.tsv"
        "$templates/Tool_Versions.tsv" "$templates/Analysis_Plan.md"
        "$templates/workflow_status.tsv" "$templates/Task_Status.tsv"
        "$templates/Acceptance_Report.md" "$templates/Methods_Summary.md"
        "$templates/Delivery_Index.md" "$templates/Decision_Log.md"
        "$templates/Research_Log_README.md" "$templates/Research_Log_Entry.md" "$templates/Manuscripts_README.md"
        "$templates/Pull_Request_Template.md" "$templates/Analysis_Issue_Template.md"
        "$templates/result_manifest.yaml" "$templates/Directory_Index.tsv"
        "$templates/Log_Index.tsv" "$templates/Decision_Index.tsv"
    )
    targets=(
        "$project_abs/config/Project_Layout.tsv" "$project_abs/README.md"
        "$project_abs/PROJECT_STATUS.md" "$project_abs/CHANGELOG.md" "$project_abs/.gitignore"
        "$project_abs/rawdata/README.md" "$project_abs/config/Input_Manifest.tsv"
        "$project_abs/config/Sample_Metadata.tsv" "$project_abs/config/Reference_Manifest.tsv"
        "$project_abs/config/Tool_Versions.tsv" "$project_abs/docs/Analysis_Plan.md"
        "$project_abs/docs/status/workflow_status.tsv" "$project_abs/docs/status/Task_Status.tsv"
        "$project_abs/docs/validation/Acceptance_Report.md" "$project_abs/docs/methods/Methods_Summary.md"
        "$project_abs/docs/delivery/Delivery_Index.md" "$project_abs/docs/decisions/Decision_Log.md"
        "$project_abs/docs/research-log/README.md" "$project_abs/docs/research-log/TEMPLATE.md" "$project_abs/manuscripts/README.md"
        "$project_abs/.github/PULL_REQUEST_TEMPLATE.md" "$project_abs/.github/ISSUE_TEMPLATE/analysis.md"
        "$project_abs/config/result_manifest.yaml" "$project_abs/config/Directory_Index.tsv"
        "$project_abs/docs/research-log/Log_Index.tsv" "$project_abs/docs/decisions/Decision_Index.tsv"
    )
else
    dirs=(config data scripts logs tmp results reports)
    sources=(
        "$templates/Input_Manifest.tsv" "$templates/Analysis_Plan.md"
        "$templates/workflow_status.tsv" "$templates/Task_Status.tsv"
        "$templates/Acceptance_Report.md" "$templates/Methods_Summary.md"
        "$templates/Delivery_Index.md" "$templates/result_manifest.yaml"
        "$templates/Directory_Index.tsv"
    )
    targets=(
        "$project_abs/config/Input_Manifest.tsv" "$project_abs/reports/Analysis_Plan.md"
        "$project_abs/reports/workflow_status.tsv" "$project_abs/reports/Task_Status.tsv"
        "$project_abs/reports/Acceptance_Report.md" "$project_abs/reports/Methods_Summary.md"
        "$project_abs/reports/Delivery_Index.md" "$project_abs/config/result_manifest.yaml"
        "$project_abs/config/Directory_Index.tsv"
    )
fi

if [[ "$workspace_steward" -eq 1 ]]; then
    if [[ "$layout" == "v2" ]]; then
        sources+=("$templates/Workspace_Policy_v2.tsv" "$templates/Workspace_Modules_v2.tsv" "$templates/Workspace_Routes.tsv")
    else
        sources+=("$templates/Workspace_Policy.tsv" "$templates/Workspace_Modules.tsv" "$templates/Workspace_Routes.tsv")
    fi
    targets+=("$project_abs/config/Workspace_Policy.tsv" "$project_abs/config/Workspace_Modules.tsv" "$project_abs/config/Workspace_Routes.tsv")
fi

# Validate every controlled path before the first write. Never follow a symlink
# root, parent, or controlled target outside the project.
for dir in "${dirs[@]}"; do
    path="$project_abs/$dir"
    [[ ! -L "$path" ]] || { echo "FAIL | Project directory must not be a symlink: $path" >&2; exit 2; }
    [[ ! -e "$path" || -d "$path" ]] || { echo "FAIL | Project directory collides with a non-directory: $path" >&2; exit 2; }
done
for target in "${targets[@]}"; do
    [[ ! -L "$target" ]] || { echo "FAIL | Controlled template target must not be a symlink: $target" >&2; exit 2; }
    [[ ! -e "$target" || -f "$target" ]] || { echo "FAIL | Controlled template target collides with a non-file: $target" >&2; exit 2; }
done

printf 'PROJECT | %s\n' "$project_abs"
printf 'LAYOUT | %s\n' "$layout"
printf 'WORKSPACE_STEWARD | %s\n' "$([[ "$workspace_steward" -eq 1 ]] && printf enabled || printf disabled)"
printf 'MODE    | %s\n' "$([[ "$write" -eq 1 ]] && printf 'write missing paths; never overwrite' || printf 'dry-run; add --yes to create missing paths')"

for dir in "${dirs[@]}"; do
    path="$project_abs/$dir"
    if [[ -d "$path" ]]; then
        printf 'EXISTS | %s\n' "$path"
    elif [[ "$write" -eq 1 ]]; then
        mkdir -p -- "$path"; printf 'CREATED | %s\n' "$path"
    else
        printf 'WOULD_CREATE_DIR | %s\n' "$path"
    fi
done

for i in "${!sources[@]}"; do
    source="${sources[$i]}"; target="${targets[$i]}"
    [[ -f "$source" ]] || { echo "FAIL | Missing template: $source" >&2; exit 2; }
    if [[ -e "$target" ]]; then
        printf 'EXISTS | %s\n' "$target"
    elif [[ "$write" -eq 1 ]]; then
        install -m 0644 -- "$source" "$target"; printf 'CREATED | %s\n' "$target"
    else
        printf 'WOULD_CREATE_FILE | %s\n' "$target"
    fi
done
