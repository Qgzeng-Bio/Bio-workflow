#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
tmp="$(mktemp -d /tmp/bioflow-layout-v2-integration.XXXXXX)"
trap 'rm -rf "$tmp"' EXIT
project="$tmp/project"

"$root/scripts/init_project.sh" --project "$project" --yes >/dev/null
mkdir -p "$project/scripts/01-assembly" "$project/logs/01-assembly" "$project/tmp/01-assembly" "$project/results/01-assembly"
script="$project/scripts/01-assembly/job.slurm"
"$root/scripts/gen_sbatch.sh" --job-name layout_v2 --cpus 1 --mem 4G \
    --log-dir "$project/logs/01-assembly" --out "$script" --cmd 'echo done' >/dev/null

clean="$(cd "$project" && "$root/scripts/prepare_submission.sh" \
    --script "$script" --project "$project" --output "$project/results/01-assembly")"
grep -Fq '[目录结构] PASS | layout v2' <<< "$clean"
grep -Fq 'VERDICT: 🟢 GO' <<< "$clean"
printf 'PASS | layout-v2 structure gate accepts one clean result module\n'

set +e
tmp_output="$(cd "$project" && "$root/scripts/prepare_submission.sh" \
    --script "$script" --project "$project" --output "$project/tmp/01-assembly" 2>&1)"
tmp_rc=$?
set -e
[[ "$tmp_rc" -eq 1 ]] || { printf 'FAIL | tmp output was not blocked\n%s\n' "$tmp_output" >&2; exit 1; }
grep -Fq '不得位于 tmp/' <<< "$tmp_output"
printf 'PASS | layout-v2 formal output under tmp is blocked\n'

outside="$tmp/outside"
mkdir "$outside"
set +e
outside_output="$(cd "$outside" && "$root/scripts/prepare_submission.sh" \
    --script "$script" --output "$project/tmp/01-assembly" 2>&1)"
outside_rc=$?
set -e
[[ "$outside_rc" -eq 1 ]] || { printf 'FAIL | outside-project invocation bypassed tmp gate\n%s\n' "$outside_output" >&2; exit 1; }
grep -Fq '不得位于 tmp/' <<< "$outside_output"
set +e
outside_submit="$(cd "$outside" && "$root/scripts/submit_and_log.sh" \
    --script "$script" --output "$project/tmp/01-assembly" 2>&1)"
outside_submit_rc=$?
set -e
[[ "$outside_submit_rc" -eq 1 ]] || { printf 'FAIL | submit backend outside-project invocation bypassed tmp gate\n%s\n' "$outside_submit" >&2; exit 1; }
grep -Fq '闸门 NO-GO' <<< "$outside_submit"
printf 'PASS | script-root inference blocks outside-project submission bypass\n'

set +e
raw_output="$(cd "$project" && "$root/scripts/prepare_submission.sh" \
    --script "$script" --project "$project" --output "$project/rawdata" 2>&1)"
raw_rc=$?
set -e
[[ "$raw_rc" -eq 1 ]] || { printf 'FAIL | rawdata output was not blocked\n%s\n' "$raw_output" >&2; exit 1; }
grep -Fq '不得位于 rawdata/' <<< "$raw_output"
printf 'PASS | layout-v2 write target under rawdata is blocked\n'

mkdir "$project/results/02-assembly-v2-final"
set +e
rogue_output="$(cd "$project" && "$root/scripts/prepare_submission.sh" \
    --script "$script" --project "$project" --output "$project/results/01-assembly" 2>&1)"
rogue_rc=$?
set -e
[[ "$rogue_rc" -eq 1 ]] || { printf 'FAIL | duplicate/versioned module was not blocked\n%s\n' "$rogue_output" >&2; exit 1; }
grep -Fq 'STRUCT_MODULE_VERSION' <<< "$rogue_output"
printf 'PASS | layout-v2 duplicate/version-suffixed result module blocks preflight\n'
