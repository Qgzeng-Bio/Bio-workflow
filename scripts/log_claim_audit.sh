#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage:
  log_claim_audit.sh --manifest <path> [--job-id <id>] [--note "<text>"]
                     [--audit <tsv>] [--rules <tsv>] [--anchors <yaml>]
                     [--checker <py>]

Defaults:
  --audit   reports/claim_audit.tsv
  --rules   references/interpretation-rules.tsv
  --anchors references/project-anchors.yaml
  --checker scripts/check_result_contract.py
  --job-id  NA
  --note    ""

Path safety: --audit / --rules / --anchors / --checker accept absolute paths
without restriction (operator-trust boundary). The default --audit lives under
the project's reports/ dir. If you point --audit elsewhere, you own the side
effects (mkdir -p of parents, header creation).

Audit TSV schema:
  Timestamp
  Job_ID
  Manifest_Path
  Manifest_SHA256
  Status
  Block_Rules
  Warn_Rules
  Note
  Outcome

Exit codes (machine-readable):
  0  PASS  — checker reported PASS
  1  WARN  — checker reported WARN
  2  BLOCK — checker reported BLOCK
  3  PARSE_ERROR — checker output could not be parsed (status/rc mismatch)
  4  INFRA_ERROR — usage/path/yaml/header problem; nothing was checked
USAGE
}

proj_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

manifest=""
job_id="NA"
note=""
audit_tsv="reports/claim_audit.tsv"
rules="references/interpretation-rules.tsv"
anchors="references/project-anchors.yaml"
checker="scripts/check_result_contract.py"
python_bin=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --manifest) [[ $# -ge 2 ]] || { echo "ERROR | --manifest requires a value" >&2; exit 4; }; manifest="$2"; shift 2 ;;
        --job-id)   [[ $# -ge 2 ]] || { echo "ERROR | --job-id requires a value" >&2; exit 4; }; job_id="$2"; shift 2 ;;
        --note)     [[ $# -ge 2 ]] || { echo "ERROR | --note requires a value" >&2; exit 4; }; note="$2"; shift 2 ;;
        --audit)    [[ $# -ge 2 ]] || { echo "ERROR | --audit requires a value" >&2; exit 4; }; audit_tsv="$2"; shift 2 ;;
        --rules)    [[ $# -ge 2 ]] || { echo "ERROR | --rules requires a value" >&2; exit 4; }; rules="$2"; shift 2 ;;
        --anchors)  [[ $# -ge 2 ]] || { echo "ERROR | --anchors requires a value" >&2; exit 4; }; anchors="$2"; shift 2 ;;
        --checker)  [[ $# -ge 2 ]] || { echo "ERROR | --checker requires a value" >&2; exit 4; }; checker="$2"; shift 2 ;;
        --python)   [[ $# -ge 2 ]] || { echo "ERROR | --python requires a value" >&2; exit 4; }; python_bin="$2"; shift 2 ;;
        -h|--help)  usage; exit 0 ;;
        *)          echo "ERROR | Unknown argument: $1" >&2; usage >&2; exit 4 ;;
    esac
done

# Find a python interpreter that has PyYAML; check_result_contract.py imports yaml
# unconditionally and exits 2 with a confusing message if not present. Project
# convention (HANDOFF) is the anaconda3 interpreter. Caller may force one with --python.
if [[ -z "$python_bin" ]]; then
    for cand in /data9/home/qgzeng/anaconda3/bin/python3 python3; do
        if command -v "$cand" >/dev/null 2>&1 && "$cand" -c 'import yaml' >/dev/null 2>&1; then
            python_bin="$cand"
            break
        fi
    done
fi
if [[ -z "$python_bin" ]]; then
    echo "ERROR | no python3 with PyYAML found; pass --python /path or install pyyaml" >&2
    exit 4
fi

resolve_path() {
    local path="$1"
    if [[ "$path" == /* ]]; then
        printf '%s\n' "$path"
    else
        printf '%s/%s\n' "$proj_root" "$path"
    fi
}

[[ -n "$manifest" ]] || { echo "ERROR | --manifest is required" >&2; exit 4; }

manifest="$(resolve_path "$manifest")"
audit_tsv="$(resolve_path "$audit_tsv")"
rules="$(resolve_path "$rules")"
anchors="$(resolve_path "$anchors")"
checker="$(resolve_path "$checker")"

[[ -r "$manifest" ]] || { echo "ERROR | manifest missing or unreadable: $manifest" >&2; exit 4; }
if [[ "$job_id" != "NA" && ! "$job_id" =~ ^[0-9]+(_[0-9]+)?$ ]]; then
    echo "ERROR | --job-id must be NA, a numeric JobID, or an array task id: $job_id" >&2
    exit 4
fi

manifest_sha256="NA"
if command -v sha256sum >/dev/null 2>&1; then
    read -r manifest_sha256 _ < <(sha256sum "$manifest")
elif command -v stat >/dev/null 2>&1; then
    manifest_sha256="$(stat -c '%Y:%s' "$manifest" 2>/dev/null || true)"
    [[ -n "$manifest_sha256" ]] || manifest_sha256="NA"
fi

set +e
checker_out="$("$python_bin" "$checker" --manifest "$manifest" --rules "$rules" --anchors "$anchors")"
checker_rc=$?
set -e

first_line="${checker_out%%$'\n'*}"
status_prefix=$'STATUS\t'
parsed_status=""
if [[ "$first_line" == "$status_prefix"* ]]; then
    parsed_status="${first_line#"$status_prefix"}"
fi

expected_rc=""
case "$parsed_status" in
    PASS)  expected_rc=0 ;;
    WARN)  expected_rc=1 ;;
    BLOCK) expected_rc=2 ;;
esac

extract_rules() {
    local label="$1"
    local found
    found="$(
        printf '%s\n' "$checker_out" |
            awk -v label="$label:" '
                $0 == label {in_section=1; next}
                in_section && ($0 == "" || $0 ~ /^[A-Z_]+:/) {exit}
                in_section && $0 ~ /^[[:space:]]+/ {
                    line=$0
                    sub(/^[[:space:]]+/, "", line)
                    split(line, fields, /[[:space:]\t]+/)
                    if (fields[1] != "") print fields[1]
                }
            ' |
            sort -u |
            awk 'BEGIN {out=""} {out = (out == "" ? $1 : out "," $1)} END {print out}'
    )"
    if [[ -n "$found" ]]; then
        printf '%s\n' "$found"
    else
        printf 'NONE\n'
    fi
}

ensure_audit_header() {
    # Concurrency note: noclobber + read-back is intentionally simple, not flock-based.
    # The expected caller is one human / one SLURM submit at a time on a shared FS;
    # heavy parallel writes to the same audit TSV would need an external lock and
    # are out of scope for this skill. If two processes race, one writes the header
    # and the other's noclobber attempt fails silently — both then read it back.
    local audit_dir header field_count
    audit_dir="$(dirname "$audit_tsv")"
    if [[ ! -e "$audit_tsv" ]]; then
        mkdir -p "$audit_dir"
        if ! ( set -o noclobber; printf 'Timestamp\tJob_ID\tManifest_Path\tManifest_SHA256\tStatus\tBlock_Rules\tWarn_Rules\tNote\tOutcome\n' > "$audit_tsv" ) 2>/dev/null; then
            [[ -e "$audit_tsv" ]] || { echo "ERROR | failed to create audit TSV: $audit_tsv" >&2; exit 4; }
        fi
    fi

    IFS= read -r header < "$audit_tsv" || header=""
    field_count="$(awk -F '\t' 'NR==1 {print NF; found=1; exit} END {if (!found) print 0}' "$audit_tsv")"
    if [[ "$field_count" != "9" ]]; then
        echo "ERROR | audit TSV has unexpected header column count ($field_count != 9): $audit_tsv" >&2
        echo "ERROR | first line: $header" >&2
        exit 4
    fi
}

append_row() {
    local status="$1"
    local block_rules="$2"
    local warn_rules="$3"
    local clean_note timestamp
    clean_note="${note//$'\t'/ }"
    clean_note="${clean_note//$'\n'/ }"
    clean_note="${clean_note//$'\r'/ }"
    timestamp="$(date '+%F %T')"
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\tTBD\n' \
        "$timestamp" "$job_id" "$manifest" "$manifest_sha256" "$status" \
        "$block_rules" "$warn_rules" "$clean_note" >> "$audit_tsv"
}

if [[ -z "$expected_rc" || "$checker_rc" -ne "$expected_rc" ]]; then
    ensure_audit_header
    append_row "PARSE_ERROR" "NONE" "NONE"
    echo "ERROR | checker STATUS/exit-code mismatch or unparseable STATUS (status=${parsed_status:-NA}, exit=$checker_rc)" >&2
    exit 3
fi

block_rules="$(extract_rules "BLOCKED")"
warn_rules="$(extract_rules "WARNINGS")"

ensure_audit_header
append_row "$parsed_status" "$block_rules" "$warn_rules"

echo "✅ claim audit appended: STATUS=$parsed_status rules_block=$block_rules rules_warn=$warn_rules -> $audit_tsv"
exit "$checker_rc"
