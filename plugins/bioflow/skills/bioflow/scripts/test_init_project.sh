#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
init="$root/scripts/init_project.sh"
tmp="$(mktemp -d /tmp/bioflow-init-test.XXXXXX)"
trap 'rm -rf "$tmp"' EXIT
project="$tmp/project"

output="$($init --project "$project")"
grep -Fq 'MODE    | dry-run' <<< "$output"
[[ ! -e "$project" ]] || { echo 'FAIL | dry-run wrote project paths' >&2; exit 1; }
printf 'PASS | dry-run is read-only\n'

$init --project "$project" --yes >/dev/null
for path in config data scripts logs tmp results reports; do
    [[ -d "$project/$path" ]] || { echo "FAIL | missing directory: $path" >&2; exit 1; }
done
for path in config/Input_Manifest.tsv config/result_manifest.yaml config/Directory_Index.tsv reports/Analysis_Plan.md reports/workflow_status.tsv reports/Task_Status.tsv reports/Acceptance_Report.md reports/Methods_Summary.md reports/Delivery_Index.md; do
    [[ -s "$project/$path" ]] || { echo "FAIL | missing template: $path" >&2; exit 1; }
done
[[ ! -e "$project/config/Workspace_Policy.tsv" ]] \
    || { echo 'FAIL | legacy init unexpectedly enabled Workspace Steward' >&2; exit 1; }
printf 'PASS | project skeleton created without implicit steward enablement\n'

workspace_dry="$($init --project "$project" --workspace-steward)"
grep -Fq 'WORKSPACE_STEWARD | enabled' <<< "$workspace_dry"
grep -Fq 'WOULD_CREATE_FILE' <<< "$workspace_dry"
[[ ! -e "$project/config/Workspace_Policy.tsv" ]] \
    || { echo 'FAIL | workspace dry-run wrote contracts' >&2; exit 1; }
$init --project "$project" --workspace-steward --yes >/dev/null
for path in config/Workspace_Policy.tsv config/Workspace_Modules.tsv config/Workspace_Routes.tsv; do
    [[ -s "$project/$path" ]] || { echo "FAIL | missing workspace template: $path" >&2; exit 1; }
done
printf 'PASS | explicit workspace steward templates created\n'

printf '\nSENTINEL\n' >> "$project/reports/Analysis_Plan.md"
printf '\n# MANIFEST_SENTINEL\n' >> "$project/config/result_manifest.yaml"
printf 'D999\tresults/SENTINEL\tlegacy\t\tSENTINEL\tSentinel row\ttest\tExternal\tDo not overwrite\n' >> "$project/config/Directory_Index.tsv"
printf 'M999\tROOT\t\tlegacy\tlegacy\t\tSentinel module\ttest\tLegacy\tDo not overwrite\n' >> "$project/config/Workspace_Modules.tsv"
$init --project "$project" --workspace-steward --yes >/dev/null
[[ "$(tail -n 1 "$project/reports/Analysis_Plan.md")" == 'SENTINEL' ]] \
    || { echo 'FAIL | existing plan was overwritten' >&2; exit 1; }
[[ "$(tail -n 1 "$project/config/result_manifest.yaml")" == '# MANIFEST_SENTINEL' ]] \
    || { echo 'FAIL | existing result manifest was overwritten' >&2; exit 1; }
grep -Fq $'D999\tresults/SENTINEL\tlegacy' "$project/config/Directory_Index.tsv" \
    || { echo 'FAIL | existing directory index was overwritten' >&2; exit 1; }
grep -Fq $'M999\tROOT\t\tlegacy' "$project/config/Workspace_Modules.tsv" \
    || { echo 'FAIL | existing workspace modules were overwritten' >&2; exit 1; }
printf 'PASS | rerun preserves existing files\n'

if $init --project "${HOME%/}/data/bioflow-init-test" >/dev/null 2>&1; then
    echo 'FAIL | protected path was accepted' >&2
    exit 1
fi
printf 'PASS | protected path refused\n'
