#!/usr/bin/env bash
# submit_and_log.sh — 确认后提交 + 记账 (后端 executor)
#
# 它把 prepare_submission.sh 当最终闸门复用 (不重造检查逻辑):
#   1. 跑 prepare_submission.sh; NO-GO 就拒绝提交。
#   2. 默认 dry-run: 只打印待提交命令, 不 sbatch。
#   3. 只有显式 --yes 才真正 sbatch, 并把 Job_ID/参数/时间追加进 run record TSV。
# 它绝不自动重提 (no auto-resubmit), 不循环, 不改既有脚本。
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage:
  scripts/submit_and_log.sh --script <slurm_script> [gate options] [--record FILE] [--yes]

Confirmed-submit wrapper. Runs prepare_submission.sh as the final GO/NO-GO gate, then:
  - without --yes : DRY-RUN — prints the exact sbatch command, submits nothing.
  - with    --yes : if the gate says GO, submits via sbatch and appends a run-record row.

Options:
  --script FILE     sbatch script to submit (required). The array, if any, must be
                    declared in the script itself so the gate inspects exactly what is
                    submitted (no --array override here, by design).
  --manifest FILE   forwarded to the gate (array task count + header)
  --claim-manifest FILE
                    Optional result_manifest.yaml. If given and the file exists at
                    submit time, run scripts/log_claim_audit.sh --manifest <path>
                    --job-id <Job_ID> after a successful sbatch and record the
                    checker status into the run record's Checker_Status_AtSubmit
                    column.
  --input-list FILE forwarded to the gate (input existence/integrity)
  --output DIR      forwarded to the gate (protected-path + overwrite check)
  --mode P          forwarded to the gate (partition for preflight)
  --conc N          forwarded to the gate (array %N cap for quota dry-run)
  --record FILE     run-record TSV to append (default: reports/run_record.tsv)
  --yes             actually submit (without it, dry-run only)
  -h, --help        show this help

Exit codes: 0=GO (dry-run shown, or submitted)  1=NO-GO / blocked  2=usage error
USAGE
}

script=""; manifest=""; claim_manifest=""; input_list=""; output_dir=""; mode=""; conc=""
record="reports/run_record.tsv"; do_submit=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --script)     [[ $# -ge 2 ]] || { echo "ERROR | --script requires a value" >&2; exit 2; }; script="$2"; shift 2 ;;
        --manifest)   [[ $# -ge 2 ]] || { echo "ERROR | --manifest requires a value" >&2; exit 2; }; manifest="$2"; shift 2 ;;
        --claim-manifest) [[ $# -ge 2 ]] || { echo "ERROR | --claim-manifest requires a value" >&2; exit 2; }; claim_manifest="$2"; shift 2 ;;
        --input-list) [[ $# -ge 2 ]] || { echo "ERROR | --input-list requires a value" >&2; exit 2; }; input_list="$2"; shift 2 ;;
        --output)     [[ $# -ge 2 ]] || { echo "ERROR | --output requires a value" >&2; exit 2; }; output_dir="$2"; shift 2 ;;
        --mode)       [[ $# -ge 2 ]] || { echo "ERROR | --mode requires a value" >&2; exit 2; }; mode="$2"; shift 2 ;;
        --conc)       [[ $# -ge 2 ]] || { echo "ERROR | --conc requires a value" >&2; exit 2; }; conc="$2"; shift 2 ;;
        --record)     [[ $# -ge 2 ]] || { echo "ERROR | --record requires a value" >&2; exit 2; }; record="$2"; shift 2 ;;
        --yes)        do_submit=1; shift ;;
        -h|--help)    usage; exit 0 ;;
        *)            echo "ERROR | Unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

[[ -n "$script" ]] || { echo "ERROR | Missing --script" >&2; exit 2; }
[[ -e "$script" && -r "$script" ]] || { echo "ERROR | Script missing or unreadable: $script" >&2; exit 2; }

resolve_safe() {  # echo a clean absolute path; FAIL (return 1, no output) if it cannot
    # be safely resolved (realpath missing/failing, non-absolute, or residual "..").
    local p="$1" n
    command -v realpath >/dev/null 2>&1 || return 1
    n="$(realpath -m -- "$p" 2>/dev/null)" || return 1
    [[ "$n" == /* ]] || return 1
    case "$n" in */../*|*/.. ) return 1 ;; esac
    printf '%s\n' "$n"
}
is_protected() {
    local p="${1%/}"
    [[ "$p" == /data9/home/qgzeng/data || "$p" == /data9/home/qgzeng/data/* \
       || "$p" == /data9/home/qgzeng/tools || "$p" == /data9/home/qgzeng/tools/* ]]
}
_rec_norm="$(resolve_safe "$record")" || { echo "ERROR | --record 无法安全规范化 (realpath 不可用或路径含 ..): $record" >&2; exit 2; }
is_protected "$_rec_norm" && { echo "ERROR | --record is under a protected path: $record" >&2; exit 2; }
record="$_rec_norm"  # use the normalized absolute path everywhere downstream

# --- locate prepare_submission.sh (the gate) ----------------------------------
self_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
proj_root="$(cd "$self_dir/.." && pwd)"
gate=""
[[ -x "$self_dir/prepare_submission.sh" ]] && gate="$self_dir/prepare_submission.sh"
[[ -n "$gate" ]] || { echo "ERROR | prepare_submission.sh not found; refusing to submit without the gate" >&2; exit 1; }

# --- minimal #SBATCH parser (for the run record) ------------------------------
get_sbatch_value() {
    local long="$1" short="$2" line rest token next value=""
    local -a fields
    while IFS= read -r line; do
        [[ "$line" =~ ^[[:space:]]*#SBATCH[[:space:]]+ ]] || continue
        rest="${line#*#SBATCH}"
        # shellcheck disable=SC2206
        fields=($rest)
        for ((i = 0; i < ${#fields[@]}; i++)); do
            token="${fields[$i]}"; next="${fields[$((i + 1))]:-}"
            if   [[ "$token" == "$long="* ]]; then value="${token#"$long="}"
            elif [[ "$token" == "$long" && -n "$next" ]]; then value="$next"
            elif [[ -n "$short" && "$token" == "$short" && -n "$next" ]]; then value="$next"
            elif [[ -n "$short" && "$token" == "$short"* && "$token" != "$short" ]]; then value="${token#"$short"}"
            fi
        done
    done < "$script"
    [[ -n "$value" ]] && printf '%s\n' "$value"
}

file_fp() {  # fingerprint to detect the script changing between gate and submit (TOCTOU);
    # echoes NA when it cannot be computed so the caller can fail closed.
    local fp=""
    if command -v sha256sum >/dev/null 2>&1; then fp="$(sha256sum "$script" 2>/dev/null | cut -d' ' -f1)"
    elif command -v stat >/dev/null 2>&1; then fp="$(stat -c '%Y:%s' "$script" 2>/dev/null)"; fi
    printf '%s\n' "${fp:-NA}"
}
script_fp_before="$(file_fp)"

# --- build the (unexecuted) sbatch command (array, if any, lives in the script) -
sbatch_cmd=(sbatch "$script")
cmd_str="${sbatch_cmd[*]}"

# --- run the gate -------------------------------------------------------------
gate_args=(--script "$script")
[[ -n "$manifest" ]]   && gate_args+=(--manifest "$manifest")
[[ -n "$input_list" ]] && gate_args+=(--input-list "$input_list")
[[ -n "$output_dir" ]] && gate_args+=(--output "$output_dir")
[[ -n "$mode" ]]       && gate_args+=(--mode "$mode")
[[ -n "$conc" ]]       && gate_args+=(--conc "$conc")

echo "[INFO] 最终闸门: $gate"
set +e
gate_out="$("$gate" "${gate_args[@]}")"
gate_rc=$?
set -e
printf '%s\n' "$gate_out"
echo "----------------------------------------------------------------------"

if [[ "$gate_rc" -ne 0 ]]; then
    echo "🔴 闸门 NO-GO (exit $gate_rc); 拒绝提交。修复硬阻断后重试。" >&2
    exit 1
fi

# --- GO ----------------------------------------------------------------------
if [[ "$do_submit" -ne 1 ]]; then
    echo "🟢 闸门 GO (dry-run)。待提交命令 (尚未提交):"
    echo "    $cmd_str"
    echo "确认无误后加 --yes 才会真正提交。"
    exit 0
fi

command -v sbatch >/dev/null 2>&1 || { echo "ERROR | sbatch not found; cannot submit" >&2; exit 1; }

# TOCTOU: refuse to submit if the script changed since the gate inspected it, or if the
# fingerprint cannot be confirmed (fail closed rather than trust an unverifiable script).
fp_now="$(file_fp)"
if [[ "$script_fp_before" == "NA" || "$fp_now" == "NA" || "$fp_now" != "$script_fp_before" ]]; then
    echo "ERROR | 脚本指纹无法确认或已变化, 拒绝提交 (请重跑闸门): $script" >&2
    exit 1
fi

# Pre-validate the run record is writable BEFORE submitting, so a submitted job is never
# left unrecorded by a late mkdir/permission failure.
legacy_record_header=$'Job_ID\tJob_Name\tScript\tPartition\tCPUs\tMem\tArray\tSubmit_Time\tUser'
current_record_header=$'Job_ID\tJob_Name\tScript\tPartition\tCPUs\tMem\tArray\tSubmit_Time\tUser\tChecker_Status_AtSubmit'

migrate_or_create_record() {
    # Migration is single-writer by assumption; if two submit_and_log.sh calls
    # race against the same run-record TSV, the fixed ${record}.tmp can collide.
    # The caller's working model is one human/one submit at a time, so we keep
    # this simple. Concurrent submitters should serialize externally (flock).
    local header field_count tmp
    if [[ ! -e "$record" ]]; then
        printf '%s\n' "$current_record_header" > "$record"
        return 0
    fi

    IFS= read -r header < "$record" || header=""
    field_count="$(awk -F '\t' 'NR==1 {print NF; found=1; exit} END {if (!found) print 0}' "$record")"

    if [[ "$field_count" == "10" && "$header" == "$current_record_header" ]]; then
        return 0
    fi

    if [[ "$field_count" == "9" && "$header" == "$legacy_record_header" ]]; then
        tmp="${record}.tmp"
        {
            printf '%s\n' "$current_record_header"
            awk 'NR > 1 {print $0 "\tNA"}' "$record"
        } > "$tmp" || { echo "ERROR | failed to write migrated record temp file: $tmp" >&2; exit 1; }
        mv "$tmp" "$record" || { echo "ERROR | failed to replace run record after migration: $record" >&2; exit 1; }
        echo "[INFO] migrated run record schema to add Checker_Status_AtSubmit: $record"
        return 0
    fi

    echo "ERROR | unknown run-record header schema; refusing to submit: $record" >&2
    echo "ERROR | first line: $header" >&2
    exit 1
}

rec_dir="$(dirname "$record")"
[[ -d "$rec_dir" ]] || mkdir -p "$rec_dir" || { echo "ERROR | 无法创建 record 目录: $rec_dir" >&2; exit 1; }
if [[ -e "$record" ]]; then
    [[ -w "$record" ]] || { echo "ERROR | record 文件不可写: $record" >&2; exit 1; }
else
    [[ -w "$rec_dir" ]] || { echo "ERROR | record 目录不可写: $rec_dir" >&2; exit 1; }
fi
migrate_or_create_record

# Pre-validate the claim manifest BEFORE submitting, so a job that promised
# claim auditing never ends up with MANIFEST_MISSING. If the operator
# specified --claim-manifest, the file must exist now or we refuse.
if [[ -n "$claim_manifest" ]]; then
    audit_manifest_pre="$claim_manifest"
    [[ "$audit_manifest_pre" == /* ]] || audit_manifest_pre="$proj_root/$audit_manifest_pre"
    if [[ ! -f "$audit_manifest_pre" ]]; then
        echo "ERROR | --claim-manifest given but file does not exist: $claim_manifest" >&2
        echo "ERROR | refusing to submit; either fix the path or omit --claim-manifest" >&2
        exit 1
    fi
    if [[ ! -r "$audit_manifest_pre" ]]; then
        echo "ERROR | --claim-manifest exists but is not readable: $audit_manifest_pre" >&2
        exit 1
    fi
    if [[ ! -x "$proj_root/scripts/log_claim_audit.sh" ]]; then
        echo "ERROR | scripts/log_claim_audit.sh missing or not executable; cannot audit" >&2
        exit 1
    fi
fi

echo "🟢 闸门 GO + --yes; 正在提交..."
set +e
jid="$(sbatch --parsable "${sbatch_cmd[@]:1}")"
sub_rc=$?
set -e
if [[ "$sub_rc" -ne 0 || -z "$jid" ]]; then
    echo "ERROR | sbatch 提交失败 (exit $sub_rc): $jid" >&2
    exit 1
fi

# --- append the run record ----------------------------------------------------
job_name="$(get_sbatch_value '--job-name' '-J' || true)"; [[ -n "$job_name" ]] || job_name="$(basename "$script")"
r_part="$(get_sbatch_value '--partition' '-p' || true)"; [[ -n "$r_part" ]] || r_part="NA"
r_cpus="$(get_sbatch_value '--cpus-per-task' '-c' || true)"; [[ -n "$r_cpus" ]] || r_cpus="NA"
r_mem="$(get_sbatch_value '--mem' '' || true)"; [[ -n "$r_mem" ]] || r_mem="NA"
r_array="$(get_sbatch_value '--array' '-a' || true)"; [[ -n "$r_array" ]] || r_array="NA"
sub_time="$(date '+%F %T')"
sub_user="$(whoami 2>/dev/null || echo "${USER:-unknown}")"
checker_status="NA"

if [[ -n "$claim_manifest" ]]; then
    # We pre-validated existence above, but re-resolve here in case a TOCTOU
    # rename happened between gate and submit; treat any race as MANIFEST_MISSING.
    audit_manifest="$claim_manifest"
    [[ "$audit_manifest" == /* ]] || audit_manifest="$proj_root/$audit_manifest"
    if [[ -f "$audit_manifest" ]]; then
        set +e
        audit_out="$(bash "$proj_root/scripts/log_claim_audit.sh" --manifest "$audit_manifest" --job-id "$jid" 2>&1)"
        audit_rc=$?
        set -e
        # log_claim_audit.sh exit codes (machine-readable, see its --help):
        #   0 PASS  1 WARN  2 BLOCK  3 PARSE_ERROR  4 INFRA_ERROR
        case "$audit_rc" in
            0) checker_status="PASS" ;;
            1) checker_status="WARN" ;;
            2) checker_status="BLOCK" ;;
            3) checker_status="PARSE_ERROR" ;;
            4) checker_status="INFRA_ERROR" ;;
            *) checker_status="AUDIT_ERROR" ;;
        esac
        if [[ "$audit_rc" -ge 3 ]]; then
            echo "ERROR | claim audit reported $checker_status (exit $audit_rc); job was not cancelled: $jid" >&2
            printf '%s\n' "$audit_out" >&2
        fi
        [[ -n "$audit_out" ]] && printf '%s\n' "$audit_out"
    else
        checker_status="MANIFEST_MISSING"
        echo "WARN | --claim-manifest disappeared between prevalidation and submit: $claim_manifest" >&2
    fi
fi
printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$jid" "$job_name" "$script" "$r_part" "$r_cpus" "$r_mem" "$r_array" "$sub_time" "$sub_user" "$checker_status" >> "$record"

echo "✅ 已提交 Job_ID=$jid; 已记账到 $record"
echo "   监控: squeue -j $jid   |   sacct -j $jid --format=JobID,State,ExitCode,MaxRSS,Elapsed"
exit 0
