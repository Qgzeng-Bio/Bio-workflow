#!/usr/bin/env bash
# check_quota.sh — 检查 SLURM 配额占用，对照 user_qgzeng 上限
set -euo pipefail

usage() {
  cat <<'EOF'
check_quota.sh — 检查 SLURM 配额占用 (默认用户=当前用户)
  本机 user_qgzeng 上限: 已提交(排队+运行) ≤ 200 | 运行中 ≤ 100 | 运行CPU总和 ≤ 600
用法:
  check_quota.sh                     仅显示当前占用与余量
  check_quota.sh -n 150 -c 8         预演: 再提交150个作业、每个8核 是否超限
  check_quota.sh -n 150 -c 8 -j 50   同上, 块内并发上限50 (更贴近真实峰值CPU)
选项:
  -n 作业数   -c 每作业核数   -j 块内并发上限   -u 指定用户名
退出码: 0=OK  1=预演会超提交上限  2=参数错误
EOF
}

USER_NAME="$(whoami)"
MAX_SUBMIT=200; MAX_RUNNING=100; MAX_CPU=600
ADD_JOBS=0; ADD_CPUS=0; CONC=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    -n|--add-jobs) ADD_JOBS="$2"; shift 2;;
    -c|--cpus)     ADD_CPUS="$2"; shift 2;;
    -j|--conc)     CONC="$2"; shift 2;;
    -u|--user)     USER_NAME="$2"; shift 2;;
    -h|--help)     usage; exit 0;;
    *) echo "未知参数: $1" >&2; usage; exit 2;;
  esac
done

command -v squeue >/dev/null || { echo "找不到 squeue" >&2; exit 2; }

# -r 展开 array 元素为独立行，才能得到真实作业数 (对应 MaxSubmitJobs 的计数方式)
n_running=$(squeue -u "$USER_NAME" -h -r -t running -o "%i" | wc -l | tr -d ' ')
n_pending=$(squeue -u "$USER_NAME" -h -r -t pending -o "%i" | wc -l | tr -d ' ')
cpu_running=$(squeue -u "$USER_NAME" -h -r -t running -o "%C" | awk '{s+=$1} END{print s+0}')
n_submit=$(( n_running + n_pending ))

echo "== 当前 SLURM 占用 (user=$USER_NAME) =="
printf "  已提交(排队+运行): %4d / %-4d  余 %d\n" "$n_submit"    "$MAX_SUBMIT"  "$(( MAX_SUBMIT  - n_submit  ))"
printf "  运行中:            %4d / %-4d  余 %d\n" "$n_running"   "$MAX_RUNNING" "$(( MAX_RUNNING - n_running ))"
printf "  运行中CPU:         %4d / %-4d  余 %d\n" "$cpu_running" "$MAX_CPU"     "$(( MAX_CPU     - cpu_running ))"
[[ "$n_pending" -gt 0 ]] && printf "  (排队中: %d)\n" "$n_pending"

status=0
if [[ "$ADD_JOBS" -gt 0 ]]; then
  echo "== 预演: 再提交 $ADD_JOBS 个作业, 每个 ${ADD_CPUS} 核 =="
  proj_submit=$(( n_submit + ADD_JOBS ))
  run_at_once="$ADD_JOBS"
  [[ "$CONC" -gt 0 && "$CONC" -lt "$ADD_JOBS" ]] && run_at_once="$CONC"
  proj_cpu=$(( cpu_running + run_at_once * ADD_CPUS ))
  if [[ "$proj_submit" -gt "$MAX_SUBMIT" ]]; then
    printf "  预计已提交: %d / %d  ✗ 超限 → 必须分块 (scripts/submit_chunked.sh)\n" "$proj_submit" "$MAX_SUBMIT"; status=1
  else
    printf "  预计已提交: %d / %d  ✓\n" "$proj_submit" "$MAX_SUBMIT"
  fi
  if [[ "$proj_cpu" -gt "$MAX_CPU" ]]; then
    printf "  预计峰值CPU: %d / %d  ✗ 超限 (多余任务会自动排队, 不会被拒, 但变慢)\n" "$proj_cpu" "$MAX_CPU"
  else
    printf "  预计峰值CPU: %d / %d  ✓\n" "$proj_cpu" "$MAX_CPU"
  fi
  # 机器可读状态 (供 prepare_submission.sh 等调用方稳定解析, 不依赖中文文案)
  if [[ "$status" -eq 1 ]]; then echo "STATUS=SUBMIT_LIMIT_EXCEEDED"; else echo "STATUS=OK"; fi
fi
exit "$status"
