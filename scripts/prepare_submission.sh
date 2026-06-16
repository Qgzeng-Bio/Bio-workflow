#!/usr/bin/env bash
# prepare_submission.sh — 提交前一键体检 + 绿灯包生成 (只读, 绝不提交)
#
# 它编排已有的只读 helper, 把 SKILL.md 第 7 节 "Preflight before submitting" 和
# "Before sbatch, show the user" 那两段散文编译成一个可执行件:
#   输入层  -> check_inputs.sh         (输入是否齐全/完整)
#   脚本层  -> slurm_preflight.sh      (SBATCH 规则 PASS/WARN/FAIL)
#   任务层  -> parallelization_audit.sh(array 任务数 + manifest 表头)
#   配额层  -> check_quota.sh          (会不会撞 200/100/600 上限, 尽力而为)
#   输出层  -> 覆盖检查 (输出目录是否已有结果)
# 最后汇成 GO / NO-GO 裁决, 并打印"待执行但尚未提交"的确切 sbatch 命令。
#
# 它从不 sbatch/scancel/重提/写状态文件/改用户脚本。按提交键仍是用户确认后的动作。
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage:
  scripts/prepare_submission.sh --script <slurm_script> \
      [--manifest <manifest.tsv>] [--input-list <filelist.txt>] \
      [--output <output_dir>] [--mode normal|debug|fat|fat2|high] [--conc <N>]

Read-only pre-submission gate for qgzeng bio-workflow. It runs the existing
read-only helpers, prints a single GO/NO-GO "green-light package", and prints the
exact sbatch command WITHOUT submitting it.

Options:
  --script       sbatch script to check (required)
  --manifest     manifest for array task counting + header detection (optional)
  --input-list   file with one input path per line, checked via check_inputs.sh (optional)
  --output       output directory; warns if it already contains files (optional)
  --mode         partition mode forwarded to slurm_preflight.sh (optional)
  --conc         array concurrency cap %N used in the suggested command + quota dry-run
                 (optional; default taken from parallelization_audit, else 4)

Exit codes: 0=GO (maybe with warnings to acknowledge)  1=NO-GO (hard blocker)  2=usage error
USAGE
}

script=""
manifest=""
input_list=""
output_dir=""
mode=""
conc=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --script)      [[ $# -ge 2 ]] || { echo "ERROR | --script requires a value" >&2; exit 2; }; script="$2"; shift 2 ;;
        --manifest)    [[ $# -ge 2 ]] || { echo "ERROR | --manifest requires a value" >&2; exit 2; }; manifest="$2"; shift 2 ;;
        --input-list)  [[ $# -ge 2 ]] || { echo "ERROR | --input-list requires a value" >&2; exit 2; }; input_list="$2"; shift 2 ;;
        --output)      [[ $# -ge 2 ]] || { echo "ERROR | --output requires a value" >&2; exit 2; }; output_dir="$2"; shift 2 ;;
        --mode)        [[ $# -ge 2 ]] || { echo "ERROR | --mode requires a value" >&2; exit 2; }; mode="$2"; shift 2 ;;
        --conc)        [[ $# -ge 2 ]] || { echo "ERROR | --conc requires a value" >&2; exit 2; }; conc="$2"; shift 2 ;;
        -h|--help)     usage; exit 0 ;;
        *)             echo "ERROR | Unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if [[ -z "$script" ]]; then
    echo "ERROR | Missing --script <slurm_script>" >&2
    usage >&2
    exit 2
fi
[[ -e "$script" ]] || { echo "ERROR | Script does not exist: $script" >&2; exit 2; }
[[ -r "$script" ]] || { echo "ERROR | Script is not readable: $script" >&2; exit 2; }
if [[ -n "$manifest" ]]; then
    [[ -e "$manifest" ]] || { echo "ERROR | Manifest does not exist: $manifest" >&2; exit 2; }
    [[ -r "$manifest" ]] || { echo "ERROR | Manifest is not readable: $manifest" >&2; exit 2; }
fi
if [[ -n "$input_list" ]]; then
    [[ -e "$input_list" ]] || { echo "ERROR | Input list does not exist: $input_list" >&2; exit 2; }
    [[ -r "$input_list" ]] || { echo "ERROR | Input list is not readable: $input_list" >&2; exit 2; }
fi
case "$mode" in
    ""|normal|debug|fat|fat2|high) ;;
    *) echo "ERROR | Unsupported --mode: $mode" >&2; exit 2 ;;
esac
if [[ -n "$conc" && ! "$conc" =~ ^[1-9][0-9]*$ ]]; then
    echo "ERROR | --conc must be an integer >= 1 (a %N cap of 0 is invalid): $conc" >&2
    exit 2
fi

# --- locate sibling helpers across the project dir and the global skill dir ----
self_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
helper_dirs=("$self_dir" "$HOME/.claude/skills/bioinformatics-analysis-workflow/scripts")

find_helper() {
    local name="$1" d
    for d in "${helper_dirs[@]}"; do
        if [[ -x "$d/$name" ]]; then
            printf '%s\n' "$d/$name"
            return 0
        fi
    done
    return 1
}

# --- minimal #SBATCH parser (matches the local idiom in the other scripts) -----
get_sbatch_value() {
    local long="$1" short="$2" line rest token next value=""
    local -a fields
    while IFS= read -r line; do
        [[ "$line" =~ ^[[:space:]]*#SBATCH[[:space:]]+ ]] || continue
        rest="${line#*#SBATCH}"
        # shellcheck disable=SC2206
        fields=($rest)
        for ((i = 0; i < ${#fields[@]}; i++)); do
            token="${fields[$i]}"
            next="${fields[$((i + 1))]:-}"
            if [[ "$token" == "$long="* ]]; then
                value="${token#"$long="}"
            elif [[ "$token" == "$long" && -n "$next" ]]; then
                value="$next"
            elif [[ -n "$short" && "$token" == "$short" && -n "$next" ]]; then
                value="$next"
            elif [[ -n "$short" && "$token" == "$short"* && "$token" != "$short" ]]; then
                value="${token#"$short"}"
            fi
        done
    done < "$script"
    [[ -n "$value" ]] && printf '%s\n' "$value"
}

# Count tasks in a SLURM --array spec. Handles single (N), range (A-B),
# stepped range (A-B:S) and comma lists (combinations of the above), and
# strips a trailing %cap. Prints the integer count, or returns 1 (no output)
# when the spec cannot be parsed reliably.
array_task_count() {
    local spec="$1" seg a b step total=0
    local -a segs
    spec="${spec%%\%*}"  # strip trailing %cap (e.g. 1-20%4 -> 1-20)
    spec="${spec// /}"   # strip spaces
    [[ -n "$spec" ]] || return 1
    IFS=',' read -ra segs <<< "$spec"
    for seg in "${segs[@]}"; do
        if [[ "$seg" =~ ^([0-9]+)-([0-9]+):([0-9]+)$ ]]; then
            # force base-10 so leading-zero indices (e.g. 001-010, 08-10) are not
            # mis-parsed as octal by bash arithmetic. (round-2 NEW-2)
            a=$((10#${BASH_REMATCH[1]})); b=$((10#${BASH_REMATCH[2]})); step=$((10#${BASH_REMATCH[3]}))
            { [[ "$step" -ge 1 && "$b" -ge "$a" ]]; } || return 1
            total=$(( total + (b - a) / step + 1 ))
        elif [[ "$seg" =~ ^([0-9]+)-([0-9]+)$ ]]; then
            a=$((10#${BASH_REMATCH[1]})); b=$((10#${BASH_REMATCH[2]}))
            [[ "$b" -ge "$a" ]] || return 1
            total=$(( total + b - a + 1 ))
        elif [[ "$seg" =~ ^[0-9]+$ ]]; then
            total=$(( total + 1 ))
        else
            return 1
        fi
    done
    printf '%s\n' "$total"
}

# Read one column from parallelization_audit.sh TSV output by HEADER NAME
# (robust to column-order changes). $1 = full audit stdout, $2 = column name.
audit_col() {
    awk -F'\t' -v col="$2" '
        NR==1 { for (i = 1; i <= NF; i++) if ($i == col) idx = i; next }
        NR==2 { if (idx) print $idx; exit }
    ' <<< "$1"
}

job_name="$(get_sbatch_value '--job-name' '-J' || true)"
[[ -n "$job_name" ]] || job_name="$(basename "$script")"
req_cpus="$(get_sbatch_value '--cpus-per-task' '-c' || true)"
req_mem="$(get_sbatch_value '--mem' '' || true)"
req_part="$(get_sbatch_value '--partition' '-p' || true)"
script_array="$(get_sbatch_value '--array' '-a' || true)"

# verdict accumulators
blockers=()
warnings=()
input_line="(跳过 / skipped — 未提供 --input-list)"
preflight_line="(未运行)"
task_line="(无 manifest / array)"
quota_line="(未运行)"
output_line="(未指定 --output)"

# === 1. 输入层 / input layer ===================================================
if [[ -n "$input_list" ]]; then
    ci="$(find_helper check_inputs.sh || true)"
    if [[ -z "$ci" ]]; then
        input_line="check_inputs.sh 未找到, 输入未校验"
        warnings+=("输入未校验: check_inputs.sh 未随项目打包 (只在全局 skill 目录)")
    else
        set +e
        ci_out="$("$ci" -l "$input_list" 2>&1)"
        ci_rc=$?
        set -e
        if [[ "$ci_rc" -eq 0 ]]; then
            input_line="$(printf '%s' "$ci_out" | tail -n 1) (来自 check_inputs.sh)"
        else
            input_line="$(printf '%s' "$ci_out" | tail -n 1)"
            blockers+=("输入检查未通过 (check_inputs.sh exit $ci_rc): 见 --input-list $input_list")
        fi
    fi
fi

# === 2. 脚本层 / preflight =====================================================
pf="$(find_helper slurm_preflight.sh || true)"
if [[ -z "$pf" ]]; then
    preflight_line="slurm_preflight.sh 未找到"
    blockers+=("无法运行 slurm_preflight.sh (核心闸门缺失)")
else
    pf_args=(--script "$script")
    [[ -n "$mode" ]] && pf_args+=(--mode "$mode")
    set +e
    pf_out="$("$pf" "${pf_args[@]}" 2>&1)"
    pf_rc=$?
    set -e
    pf_summary="$(printf '%s\n' "$pf_out" | grep -E '^\[INFO\] Summary:' | tail -n 1 || true)"
    [[ -n "$pf_summary" ]] || pf_summary="(无 summary 行; 见完整输出)"
    preflight_line="${pf_summary#\[INFO\] Summary: }"
    pf_warn="$(printf '%s\n' "$preflight_line" | sed -nE 's/.*WARN=([0-9]+).*/\1/p')"
    [[ -n "$pf_warn" ]] || pf_warn=0
    if [[ "$pf_rc" -ne 0 ]]; then
        blockers+=("preflight 报 FAIL (硬阻断): $preflight_line")
    elif [[ "$pf_warn" -gt 0 ]]; then
        warnings+=("preflight 有 $pf_warn 个 WARN, 提交前需逐条解释")
    fi
fi

# === 3. 任务层 / array task count + manifest header ============================
est_tasks="NA"
manifest_header="0"
audit_cap=""
pa="$(find_helper parallelization_audit.sh || true)"
if [[ -n "$pa" ]]; then
    pa_args=(--script "$script")
    [[ -n "$manifest" ]] && pa_args+=(--manifest "$manifest")
    set +e
    pa_out="$("$pa" "${pa_args[@]}" 2>/dev/null)"
    pa_rc=$?
    set -e
    if [[ "$pa_rc" -eq 0 ]]; then
        est_tasks="$(audit_col "$pa_out" "Estimated_Tasks")"
        manifest_header="$(audit_col "$pa_out" "Manifest_Header")"
        audit_cap="$(audit_col "$pa_out" "Suggested_Array_Cap")"
        [[ -n "$est_tasks" ]] || est_tasks="NA"
        # round-2 NEW-3: an absent Manifest_Header column must not be silently read
        # as "0" (no header). If a manifest was given but the flag is missing, mark
        # it unknown and handle conservatively below.
        if [[ -z "$manifest_header" ]]; then
            if [[ -n "$manifest" ]]; then manifest_header="unknown"; else manifest_header="0"; fi
        fi
    fi
fi

# resolve the array concurrency cap to use in the suggested command
cap_num=""
if [[ -n "$conc" ]]; then
    cap_num="$conc"
elif [[ -n "$audit_cap" && "$audit_cap" =~ ^%([0-9]+)$ ]]; then
    cap_num="${BASH_REMATCH[1]}"
fi

# Manifest header is judged INDEPENDENTLY of where the array lives. Bundled templates
# read the manifest 1-indexed (sed -n "${TASK_ID}p"), so a header row runs as task 1
# and the last sample is dropped — this is true whether the array directive is already
# in the script or is suggested here. (P1-b, and round-2 NEW-1: must not be bypassed by
# the script-array branch below.) An "unknown" header flag is warned, not silently OK.
header_note=""
if [[ "$manifest_header" == "1" ]]; then
    header_note=" [含表头→阻断]"
    blockers+=("manifest 第一行是表头, 默认模板会把表头当作任务 1 并漏掉末样本; 移除表头或改任务索引后再提交")
elif [[ "$manifest_header" == "unknown" ]]; then
    header_note=" [表头未知→需确认]"
    warnings+=("无法判定 manifest 是否含表头 (审计输出缺 Manifest_Header 列); 请手动确认无表头后再提交")
fi

# decide whether the suggested command needs an --array override. Only auto-suggest a
# range when there is definitively no header (manifest_header == 0).
needs_array=0
array_range=""
if [[ -n "$script_array" ]]; then
    sa_cnt="$(array_task_count "$script_array" || true)"
    if [[ -n "$sa_cnt" ]]; then
        task_line="脚本自带 array: $script_array (≈$sa_cnt 个任务)$header_note"
    else
        task_line="脚本自带 array: $script_array (任务数无法可靠解析, 手动确认)$header_note"
        warnings+=("脚本自带 array 范围无法可靠解析 ($script_array); 任务数与配额需手动确认")
    fi
elif [[ -n "$manifest" && "$est_tasks" =~ ^[0-9]+$ && "$est_tasks" -ge 1 && "$manifest_header" == "0" ]]; then
    needs_array=1
    [[ -n "$cap_num" ]] || cap_num=4
    array_range="1-${est_tasks}%${cap_num}"
    task_line="manifest 任务数=$est_tasks, 表头=0, 建议 --array=$array_range"
elif [[ -n "$manifest" ]]; then
    # header==1 / header==unknown / unparseable tasks: do not auto-suggest a command
    task_line="manifest: 任务数=$est_tasks 表头=$manifest_header$header_note; 提交前手动确认"
    [[ "$est_tasks" =~ ^[0-9]+$ ]] || warnings+=("无法从 manifest 解析任务数, array 范围需手动确认")
fi

# === 4. 配额层 / quota dry-run (best effort) ===================================
quota_jobs=""
if [[ -n "$script_array" ]]; then
    quota_jobs="$(array_task_count "$script_array" || true)"
elif [[ "$est_tasks" =~ ^[0-9]+$ ]]; then
    quota_jobs="$est_tasks"
fi
cq="$(find_helper check_quota.sh || true)"
if [[ -z "$cq" ]]; then
    quota_line="check_quota.sh 未找到, 配额未核对"
    warnings+=("配额未核对: check_quota.sh 未随项目打包 (只在全局 skill 目录)")
elif [[ -z "$quota_jobs" ]]; then
    quota_line="无可解析的 array 任务数, 跳过配额预演 (单作业或范围未知)"
else
    cq_args=(-n "$quota_jobs")
    [[ "$req_cpus" =~ ^[0-9]+$ ]] && cq_args+=(-c "$req_cpus")
    [[ -n "$cap_num" ]] && cq_args+=(-j "$cap_num")
    set +e
    cq_out="$("$cq" "${cq_args[@]}" 2>&1)"
    cq_rc=$?
    set -e
    quota_line="$(printf '%s\n' "$cq_out" | grep -E '已提交\(排队\+运行\)' | head -n 1 | sed -E 's/^[[:space:]]*//' || true)"
    # Decide on the stable machine-readable STATUS marker, not exit code or wording:
    # squeue socket errors abort check_quota before any STATUS prints -> fall through to WARN.
    if printf '%s\n' "$cq_out" | grep -q '^STATUS=SUBMIT_LIMIT_EXCEEDED'; then
        blockers+=("直接提交会超 QOS 已提交上限 (200); 改用 scripts/submit_chunked.sh 分块提交")
        [[ -n "$quota_line" ]] || quota_line="预计已提交超 200 上限"
        quota_line="$quota_line  [✗ 超提交上限, 需分块]"
    elif printf '%s\n' "$cq_out" | grep -q '^STATUS=OK'; then
        [[ -n "$quota_line" ]] || quota_line="(配额预演通过)"
    elif [[ "$cq_rc" -eq 1 ]]; then
        # No STATUS= marker, but check_quota.sh's documented contract is exit 1 = over
        # submit limit. Honour the exit code so an OUTDATED check_quota.sh copy (one that
        # never prints STATUS=) cannot silently turn a real over-limit into a soft WARN.
        # A squeue failure mid-run can also exit 1; in that ambiguous case a safety gate
        # must fail closed (block), not proceed.
        blockers+=("配额预演退出码=1 (check_quota.sh 契约: =超提交上限) 但缺 STATUS= 标记; 可能是旧版 check_quota.sh 或 squeue 中途失败。保守阻断: 先同步 scripts/check_quota.sh 或在可访问 SLURM 的会话手动核对配额, 超限时用 scripts/submit_chunked.sh 分块")
        [[ -n "$quota_line" ]] || quota_line="配额预演 exit=1 (疑似超限或 check_quota.sh 过旧)"
        quota_line="$quota_line  [✗ exit=1, 保守阻断]"
    else
        # exit 2 / other with no STATUS -> squeue/sacct genuinely unavailable; per design
        # this stays a WARN (the box's squeue is intermittently flaky), never a hard blocker.
        warnings+=("配额检查不可用 (check_quota.sh exit $cq_rc; 本机 squeue/sacct 偶发权限问题), 提交前请在可访问 SLURM 的会话复核")
        quota_line="配额检查不可用 (exit $cq_rc), 需手动复核"
    fi
fi

# === 5. 输出层 / protected-path + overwrite check ==============================
if [[ -n "$output_dir" ]]; then
    if command -v realpath >/dev/null 2>&1; then
        out_norm="$(realpath -m -- "$output_dir" 2>/dev/null || printf '%s' "$output_dir")"
    else
        out_norm="$output_dir"
    fi
    out_norm="${out_norm%/}"
    if [[ "$out_norm" != /* ]]; then
        # round-2 NEW-4: could not normalize to an absolute path (realpath missing and a
        # relative/.. path). We cannot prove it is outside protected trees, so fail closed.
        output_line="$output_dir 无法规范化为绝对路径 (realpath 不可用?), 保守拒绝"
        blockers+=("--output 无法规范化为绝对路径, 无法证明不在保护目录; 请改用绝对路径: $output_dir")
    elif [[ "$out_norm" == /data9/home/qgzeng/data || "$out_norm" == /data9/home/qgzeng/data/* \
       || "$out_norm" == /data9/home/qgzeng/tools || "$out_norm" == /data9/home/qgzeng/tools/* ]]; then
        # P1-a: protected raw-data/tools tree is never a valid output target.
        output_line="$out_norm → 保护目录, 禁止写入"
        blockers+=("--output 落在保护目录 (/data9/home/qgzeng/data 或 /tools), 禁止写入: $out_norm")
    elif [[ ! -e "$output_dir" ]]; then
        output_line="$output_dir 不存在 (将新建)"
    elif [[ ! -d "$output_dir" ]]; then
        output_line="$output_dir 存在但不是目录"
        warnings+=("--output 不是目录: $output_dir")
    else
        n_out="$(find "$output_dir" -mindepth 1 -maxdepth 1 2>/dev/null | head -n 50 | wc -l | tr -d ' ')"
        if [[ "$n_out" -gt 0 ]]; then
            output_line="$output_dir 已有内容 (顶层 ≥$n_out 项), 提交可能覆盖已有结果"
            warnings+=("输出目录非空, 确认不会覆盖既有结果: $output_dir")
        else
            output_line="$output_dir 为空"
        fi
    fi
fi

# === assemble the suggested (UNEXECUTED) sbatch command ========================
sbatch_cmd="sbatch"
[[ -n "$mode" && -z "$req_part" ]] && sbatch_cmd+=" --partition=$mode"
[[ "$needs_array" -eq 1 ]] && sbatch_cmd+=" --array=$array_range"
sbatch_cmd+=" $script"

# === green-light package =======================================================
printf '=== 提交绿灯包 / Submission gate: %s ===\n' "$job_name"
printf '[输入]   %s\n' "$input_line"
printf '[脚本]   preflight %s\n' "$preflight_line"
printf '[任务]   %s\n' "$task_line"
printf '[资源]   partition=%s  cpus-per-task=%s  mem=%s\n' \
    "${req_part:-NA}" "${req_cpus:-NA}" "${req_mem:-NA}"
printf '[配额]   %s\n' "$quota_line"
printf '[输出]   %s\n' "$output_line"
printf '[时间]   %s\n' "$(get_sbatch_value '--time' '-t' >/dev/null 2>&1 && echo '⚠️ 含 #SBATCH --time, 确认是否需要' || echo '无 #SBATCH --time')"
printf -- '----------------------------------------------------------------------\n'

if [[ "${#blockers[@]}" -gt 0 ]]; then
    printf '裁决 / VERDICT: 🔴 NO-GO  (%d 个硬阻断)\n' "${#blockers[@]}"
    for b in "${blockers[@]}"; do printf '  ✗ %s\n' "$b"; done
    [[ "${#warnings[@]}" -gt 0 ]] && for w in "${warnings[@]}"; do printf '  ⚠️ %s\n' "$w"; done
    printf '修复硬阻断后重跑本脚本; 未通过前不要提交。\n'
    exit 1
fi

printf '裁决 / VERDICT: 🟢 GO'
if [[ "${#warnings[@]}" -gt 0 ]]; then
    printf '  (%d 个 WARN 需你确认)\n' "${#warnings[@]}"
    for w in "${warnings[@]}"; do printf '  ⚠️ %s\n' "$w"; done
else
    printf '\n'
fi
printf '待执行命令 (尚未提交 / NOT submitted):\n'
printf '  %s\n' "$sbatch_cmd"
printf '确认无误后再提交; 本脚本只读, 不会自动 sbatch。\n'
exit 0
