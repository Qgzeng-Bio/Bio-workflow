#!/usr/bin/env bash
# gen_sbatch.sh — 生成 preflight-clean 的 SLURM 脚本 (前端 executor)
#
# 按参数拼出符合 qgzeng bio-workflow 规则的 sbatch 脚本骨架, 并在输出前自己跑一遍
# scripts/slurm_preflight.sh: 任何 FAIL 就拒绝输出。这样生成物在结构上不可能 preflight 不过。
# 它只生成脚本 (低风险动作), 绝不 sbatch / 提交 / 改既有脚本。
#
# 脚本骨架固定包含: 绝对日志路径 + %j_%x、set -euo pipefail、[INFO] 元信息、
# THREADS=${SLURM_CPUS_PER_TASK} 线程转发; normal/fat/fat2/high 默认不加 --time。
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage:
  scripts/gen_sbatch.sh --job-name NAME --cpus N --mem SIZE --log-dir ABS_DIR [options]

Generate a preflight-clean SLURM script. The generated script is validated with
slurm_preflight.sh before output; if preflight FAILs, nothing is emitted. Prints to
stdout by default, or to --out. Never submits.

Required:
  --job-name NAME      #SBATCH --job-name
  --cpus N             #SBATCH --cpus-per-task (integer)
  --mem SIZE           #SBATCH --mem (e.g. 16G, 64G, 4000M)
  --log-dir ABS_DIR    absolute, non-protected dir; logs go to ABS_DIR/%j_%x.out/.err

Options:
  --partition P        normal|debug|fat|fat2|high (default normal)
  --array RANGE        #SBATCH --array; MUST include a %N cap (e.g. 1-10%4)
  --manifest FILE      when --array is set, add a manifest read line (sed by task id)
  --cmd 'COMMAND'      the tool command line; use "$THREADS" for thread count
  --chdir DIR          #SBATCH --chdir (rejected if protected)
  --time WALLTIME      only with --partition debug, or together with --allow-time
  --allow-time         allow --time on non-debug partitions (adds ALLOW_TIME_DIRECTIVE)
  --out FILE           write here (non-protected); refuses to overwrite without --force
  --force              allow overwriting --out
  -h, --help           show this help

Exit codes: 0=generated (preflight passed)  1=generation/preflight blocked  2=usage error
USAGE
}

job_name=""; cpus=""; mem=""; log_dir=""; partition="normal"
array=""; manifest=""; cmd=""; chdir=""; walltime=""; allow_time=0
out=""; force=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --job-name) [[ $# -ge 2 ]] || { echo "ERROR | --job-name requires a value" >&2; exit 2; }; job_name="$2"; shift 2 ;;
        --cpus)     [[ $# -ge 2 ]] || { echo "ERROR | --cpus requires a value" >&2; exit 2; }; cpus="$2"; shift 2 ;;
        --mem)      [[ $# -ge 2 ]] || { echo "ERROR | --mem requires a value" >&2; exit 2; }; mem="$2"; shift 2 ;;
        --log-dir)  [[ $# -ge 2 ]] || { echo "ERROR | --log-dir requires a value" >&2; exit 2; }; log_dir="$2"; shift 2 ;;
        --partition)[[ $# -ge 2 ]] || { echo "ERROR | --partition requires a value" >&2; exit 2; }; partition="$2"; shift 2 ;;
        --array)    [[ $# -ge 2 ]] || { echo "ERROR | --array requires a value" >&2; exit 2; }; array="$2"; shift 2 ;;
        --manifest) [[ $# -ge 2 ]] || { echo "ERROR | --manifest requires a value" >&2; exit 2; }; manifest="$2"; shift 2 ;;
        --cmd)      [[ $# -ge 2 ]] || { echo "ERROR | --cmd requires a value" >&2; exit 2; }; cmd="$2"; shift 2 ;;
        --chdir)    [[ $# -ge 2 ]] || { echo "ERROR | --chdir requires a value" >&2; exit 2; }; chdir="$2"; shift 2 ;;
        --time)     [[ $# -ge 2 ]] || { echo "ERROR | --time requires a value" >&2; exit 2; }; walltime="$2"; shift 2 ;;
        --allow-time) allow_time=1; shift ;;
        --out)      [[ $# -ge 2 ]] || { echo "ERROR | --out requires a value" >&2; exit 2; }; out="$2"; shift 2 ;;
        --force)    force=1; shift ;;
        -h|--help)  usage; exit 0 ;;
        *)          echo "ERROR | Unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

# --- validation ---------------------------------------------------------------
resolve_safe() {  # echo a clean absolute path; FAIL (return 1, no output) if it cannot
    # be safely resolved — realpath missing/failing, non-absolute, or a residual ".."
    # segment — so a broken realpath can never silently fail open.
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

[[ -n "$job_name" ]] || { echo "ERROR | Missing --job-name" >&2; exit 2; }
[[ -n "$cpus" ]]     || { echo "ERROR | Missing --cpus" >&2; exit 2; }
[[ -n "$mem" ]]      || { echo "ERROR | Missing --mem" >&2; exit 2; }
[[ -n "$log_dir" ]]  || { echo "ERROR | Missing --log-dir" >&2; exit 2; }

[[ "$cpus" =~ ^[1-9][0-9]*$ ]] || { echo "ERROR | --cpus must be a positive integer: $cpus" >&2; exit 2; }
[[ "$mem" =~ ^[1-9][0-9]*[KMGT]?B?$ ]] || { echo "ERROR | --mem looks invalid or zero (e.g. 16G, 4000M; --mem=0 is rejected): $mem" >&2; exit 2; }
case "$partition" in
    normal|debug|fat|fat2|high) ;;
    *) echo "ERROR | --partition must be normal|debug|fat|fat2|high: $partition" >&2; exit 2 ;;
esac

[[ "$log_dir" == /* ]] || { echo "ERROR | --log-dir must be an absolute path: $log_dir" >&2; exit 2; }
_ld="$(resolve_safe "${log_dir%/}")" || { echo "ERROR | --log-dir 无法安全规范化 (realpath 不可用或路径含 ..): $log_dir" >&2; exit 2; }
log_dir="$_ld"
is_protected "$log_dir" && { echo "ERROR | --log-dir is under a protected path: $log_dir" >&2; exit 2; }

if [[ -n "$array" ]]; then
    [[ "$array" =~ ^[0-9]+(-[0-9]+(:[1-9][0-9]*)?)?(,[0-9]+(-[0-9]+(:[1-9][0-9]*)?)?)*%[1-9][0-9]*$ ]] \
        || { echo "ERROR | --array must be a valid range/list with step>=1 and a %N cap >=1 (e.g. 1-10%4, 1-9:2%4, 1,3,5%2): $array" >&2; exit 2; }
fi
if [[ -n "$chdir" ]]; then
    _cd="$(resolve_safe "${chdir%/}")" || { echo "ERROR | --chdir 无法安全规范化 (realpath 不可用或路径含 ..): $chdir" >&2; exit 2; }
    chdir="$_cd"
    is_protected "$chdir" && { echo "ERROR | --chdir is under a protected path: $chdir" >&2; exit 2; }
fi
if [[ -n "$walltime" ]]; then
    if [[ "$partition" != "debug" && "$allow_time" -ne 1 ]]; then
        echo "ERROR | --time on '$partition' needs --allow-time (qgzeng rule: no default walltime except debug)" >&2
        exit 2
    fi
fi
if [[ -n "$out" ]]; then
    _out_norm="$(resolve_safe "$out")" || { echo "ERROR | --out 无法安全规范化 (realpath 不可用或路径含 ..): $out" >&2; exit 2; }
    is_protected "$_out_norm" && { echo "ERROR | --out is under a protected path: $out" >&2; exit 2; }
    [[ -e "$out" && "$force" -ne 1 ]] && { echo "ERROR | --out already exists (use --force to overwrite): $out" >&2; exit 2; }
fi

# --- locate slurm_preflight.sh ------------------------------------------------
self_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pf=""
for d in "$self_dir" "$HOME/.claude/skills/bioinformatics-analysis-workflow/scripts"; do
    [[ -x "$d/slurm_preflight.sh" ]] && { pf="$d/slurm_preflight.sh"; break; }
done
[[ -n "$pf" ]] || { echo "ERROR | slurm_preflight.sh not found; cannot guarantee preflight-clean output" >&2; exit 1; }

# --- build the script into a temp file ----------------------------------------
tmp="$(mktemp "${TMPDIR:-/tmp}/gen_sbatch.XXXXXX")"
trap 'rm -f "$tmp"' EXIT

{
    echo '#!/bin/bash'
    echo "#SBATCH --partition=$partition"
    echo "#SBATCH --job-name=$job_name"
    echo "#SBATCH --cpus-per-task=$cpus"
    echo "#SBATCH --mem=$mem"
    echo "#SBATCH --output=$log_dir/%j_%x.out"
    echo "#SBATCH --error=$log_dir/%j_%x.err"
    [[ -n "$array" ]] && echo "#SBATCH --array=$array"
    [[ -n "$chdir" ]] && echo "#SBATCH --chdir=${chdir%/}"
    if [[ -n "$walltime" ]]; then
        [[ "$partition" != "debug" ]] && echo "# ALLOW_TIME_DIRECTIVE (user-confirmed walltime on $partition)"
        echo "#SBATCH --time=$walltime"
    fi
    echo ''
    echo 'set -euo pipefail'
    echo ''
    echo 'echo "[INFO] Job started | Host: $(hostname) | Time: $(date)"'
    echo 'echo "[INFO] Job ID: ${SLURM_JOB_ID:-NA} | Partition: ${SLURM_JOB_PARTITION:-NA}"'
    echo 'echo "[INFO] CPUs: ${SLURM_CPUS_PER_TASK:-NA} | Workdir: $(pwd)"'
    echo ''
    echo '# Forward the SLURM CPU allocation to the tool via "$THREADS".'
    echo 'THREADS="${SLURM_CPUS_PER_TASK:-1}"'
    if [[ -n "$array" && -n "$manifest" ]]; then
        echo ''
        echo "MANIFEST=\"$manifest\""
        echo 'TASK_LINE="$(sed -n "${SLURM_ARRAY_TASK_ID}p" "$MANIFEST")"'
        echo '[[ -n "$TASK_LINE" ]] || { echo "[ERROR] empty manifest line for array task ${SLURM_ARRAY_TASK_ID}" >&2; exit 1; }'
        echo 'echo "[INFO] Array task ${SLURM_ARRAY_TASK_ID}: ${TASK_LINE}"'
    fi
    echo ''
    if [[ -n "$cmd" ]]; then
        echo "$cmd"
    else
        echo '# TODO: 填入实际命令; 用 "$THREADS" 作为线程数, 用 "$TASK_LINE" 取 array 行字段'
        echo 'echo "[WARN] gen_sbatch: no --cmd provided; fill in the command before submitting." >&2'
        echo 'exit 1'
    fi
} > "$tmp"

# --- shell syntax check: catch an unbalanced quote/newline from --cmd ----------
set +e
syn_out="$(bash -n "$tmp" 2>&1)"
syn_rc=$?
set -e
if [[ "$syn_rc" -ne 0 ]]; then
    echo "✗ 生成的脚本有 shell 语法错误 (常因 --cmd 引号未闭合), 不输出:" >&2
    printf '%s\n' "$syn_out" >&2
    exit 1
fi

# --- preflight-by-construction: refuse to emit if it would FAIL ---------------
set +e
pf_out="$("$pf" --script "$tmp" --mode "$partition" 2>&1)"
pf_rc=$?
set -e

if [[ "$pf_rc" -ne 0 ]]; then
    echo "✗ 生成的脚本未通过 preflight, 不输出。FAIL 项:" >&2
    printf '%s\n' "$pf_out" | grep '^FAIL' >&2 || true
    exit 1
fi

pf_summary="$(printf '%s\n' "$pf_out" | grep -E '^\[INFO\] Summary:' | tail -n 1 || true)"
warns="$(printf '%s\n' "$pf_out" | grep '^WARN' || true)"
if [[ -n "$warns" ]]; then
    echo "⚠️ 生成脚本 preflight 有 WARN (仍输出, 但请确认):" >&2
    printf '%s\n' "$warns" >&2
fi

# --- emit ---------------------------------------------------------------------
if [[ -n "$out" ]]; then
    cp "$tmp" "$out"
    echo "✓ 已生成 preflight-clean 脚本: $out  (${pf_summary#\[INFO\] Summary: })" >&2
    [[ -z "$cmd" ]] && echo "  提示: 未提供 --cmd, 脚本含 TODO 占位, 提交前必须补全命令。" >&2
else
    cat "$tmp"
fi
exit 0
