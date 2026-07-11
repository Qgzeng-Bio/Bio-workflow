#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
tmp="$(mktemp -d /tmp/bioflow-claim-audit-test.XXXXXX)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp"/{scripts,references,config,reports}

cp "$root/scripts/log_claim_audit.sh" "$root/scripts/check_result_contract.py" "$tmp/scripts/"
cp "$root/references/interpretation-rules.tsv" "$root/references/project-anchors.yaml" "$tmp/references/"
printf 'analysis_types:\n  - rnaseq\nrnaseq:\n  samples: 6\n' > "$tmp/config/result_manifest.yaml"

set +e
output="$(bash "$tmp/scripts/log_claim_audit.sh" --manifest config/result_manifest.yaml 2>&1)"
rc=$?
set -e

[[ "$rc" -eq 3 ]] || { printf 'FAIL | expected UNCERTAIN exit 3, got %s\n%s\n' "$rc" "$output" >&2; exit 1; }
grep -Fq 'STATUS=UNCERTAIN' <<< "$output" || { printf 'FAIL | status missing\n%s\n' "$output" >&2; exit 1; }
awk -F '\t' 'NR == 2 && $5 == "UNCERTAIN" && $7 ~ /COVERAGE/ {ok=1} END {exit !ok}' "$tmp/reports/claim_audit.tsv" \
    || { echo 'FAIL | UNCERTAIN audit row missing coverage evidence' >&2; exit 1; }

printf 'PASS | claim audit records UNCERTAIN coverage\n'
