#!/usr/bin/env bash
# Read-only Bioflow layout helpers. Source this file; it performs no writes.

_bioflow_layout_script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
_bioflow_layout_python="${BIOFLOW_LAYOUT_PYTHON:-python3}"

bioflow_layout_schema() {
    local project="${1:-.}"
    "$_bioflow_layout_python" "$_bioflow_layout_script_dir/project_layout.py" \
        --project "$project" --field schema
}

bioflow_control_path() {
    local project="${1:-.}" key="$2"
    "$_bioflow_layout_python" "$_bioflow_layout_script_dir/project_layout.py" \
        --project "$project" --path "$key"
}

bioflow_find_project_root() {
    local start="${1:-.}"
    "$_bioflow_layout_python" "$_bioflow_layout_script_dir/project_layout.py" \
        --find-root "$start"
}
