#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
gen="$root/scripts/gen_sbatch.sh"
preflight="$root/scripts/slurm_preflight.sh"
tmp="$(mktemp -d /tmp/bioflow-preflight-test.XXXXXX)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/logs"

assert_clean() {
    local script="$1"
    local output
    output="$($preflight --script "$script")"
    grep -Eq 'Summary: PASS=[0-9]+ WARN=0 FAIL=0$' <<< "$output" \
        || { printf 'FAIL | expected clean PASS\n%s\n' "$output" >&2; exit 1; }
    printf 'PASS | clean preflight\n'
}

$gen --job-name pass --cpus 1 --mem 4G --log-dir "$tmp/logs" \
    --cmd 'echo done' --out "$tmp/pass.slurm" >/dev/null
assert_clean "$tmp/pass.slurm"

$gen --job-name warn --cpus 1 --mem 4G --log-dir "$tmp/logs" \
    --time 01:00:00 --allow-time --cmd 'echo done' --out "$tmp/warn.slurm" >/dev/null
warn_output="$($preflight --script "$tmp/warn.slurm")"
grep -Eq 'Summary: PASS=[0-9]+ WARN=[1-9][0-9]* FAIL=0$' <<< "$warn_output" \
    || { printf 'FAIL | expected WARN without FAIL\n%s\n' "$warn_output" >&2; exit 1; }
printf 'PASS | warning preflight\n'

cp "$tmp/pass.slurm" "$tmp/fail.slurm"
sed -i '/#SBATCH --cpus-per-task/a #SBATCH --array=1-10' "$tmp/fail.slurm"
set +e
fail_output="$($preflight --script "$tmp/fail.slurm" 2>&1)"
fail_rc=$?
set -e
[[ "$fail_rc" -eq 1 ]] || { printf 'FAIL | expected preflight exit 1\n%s\n' "$fail_output" >&2; exit 1; }
grep -Eq 'Summary: PASS=[0-9]+ WARN=[0-9]+ FAIL=[1-9][0-9]*$' <<< "$fail_output" \
    || { printf 'FAIL | expected FAIL count\n%s\n' "$fail_output" >&2; exit 1; }
grep -Fq 'Array directive lacks a %N concurrency cap' <<< "$fail_output" \
    || { printf 'FAIL | expected array-cap failure\n%s\n' "$fail_output" >&2; exit 1; }
printf 'PASS | failing preflight\n'

$gen --job-name negative --cpus 1 --mem 4G --log-dir "$tmp/logs" \
    --cmd '# rm -rf /tmp/comment-only' --out "$tmp/negative.slurm" >/dev/null
negative_output="$($preflight --script "$tmp/negative.slurm")"
grep -Fq 'No active recursive+force rm pattern' <<< "$negative_output" \
    || { printf 'FAIL | comment-only rm caused a false positive\n%s\n' "$negative_output" >&2; exit 1; }
grep -Eq 'Summary: PASS=[0-9]+ WARN=0 FAIL=0$' <<< "$negative_output" \
    || { printf 'FAIL | negative fixture was not clean\n%s\n' "$negative_output" >&2; exit 1; }
printf 'PASS | commented destructive command ignored\n'
