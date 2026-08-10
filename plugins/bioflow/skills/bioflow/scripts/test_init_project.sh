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
printf 'PASS | project skeleton created\n'

printf '\nSENTINEL\n' >> "$project/reports/Analysis_Plan.md"
printf '\n# MANIFEST_SENTINEL\n' >> "$project/config/result_manifest.yaml"
printf 'D999\tresults/SENTINEL\tlegacy\t\tSENTINEL\tSentinel row\ttest\tExternal\tDo not overwrite\n' >> "$project/config/Directory_Index.tsv"
$init --project "$project" --yes >/dev/null
[[ "$(tail -n 1 "$project/reports/Analysis_Plan.md")" == 'SENTINEL' ]] \
    || { echo 'FAIL | existing plan was overwritten' >&2; exit 1; }
[[ "$(tail -n 1 "$project/config/result_manifest.yaml")" == '# MANIFEST_SENTINEL' ]] \
    || { echo 'FAIL | existing result manifest was overwritten' >&2; exit 1; }
grep -Fq $'D999\tresults/SENTINEL\tlegacy' "$project/config/Directory_Index.tsv" \
    || { echo 'FAIL | existing directory index was overwritten' >&2; exit 1; }
printf 'PASS | rerun preserves existing files\n'

if $init --project "${HOME%/}/data/bioflow-init-test" >/dev/null 2>&1; then
    echo 'FAIL | protected path was accepted' >&2
    exit 1
fi
printf 'PASS | protected path refused\n'
