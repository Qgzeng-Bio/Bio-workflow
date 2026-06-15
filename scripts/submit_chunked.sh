#!/usr/bin/env bash
# submit_chunked.sh — 分块提交大规模 array 作业, 始终保持"已提交数"低于 QOS 上限
set -euo pipefail

usage() {
  cat <<'EOF'
submit_chunked.sh — 分块提交大规模 array 作业 (遵守 user_qgzeng: 已提交 ≤ 200)
用法:
  submit_chunked.sh -s job.sbatch -N 850 [-k 150] [-j 50] [-m 180] [-w 60] [-o 1] [-- 透传给sbatch...]
参数:
  -s  要提交的 sbatch 脚本 (脚本内用 $SLURM_ARRAY_TASK_ID 索引样本;
      脚本里的 #SBATCH --array 会被命令行覆盖)
  -N  样本/任务 总数 (array 索引范围 1..N)
  -k  每块大小            (默认 150)
  -j  块内并发 %N         (默认 50)
  -m  允许的最大已提交数  (默认 180, 给 200 留余量)
  -w  轮询间隔秒          (默认 60)
  -o  array 起始索引      (默认 1)
  --  其后参数原样透传给 sbatch (放在脚本名之前的 sbatch 选项)
说明: 顺序提交连续块; 每块提交前等待直到 已提交 + 块大小 ≤ m。
建议后台运行: nohup submit_chunked.sh ... > submit.log 2>&1 &
EOF
}

SCRIPT=""; N=0; CHUNK=150; CONC=50; MAXSUB=180; WAIT=60; START=1
USER_NAME="$(whoami)"; PASS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    -s) SCRIPT="$2"; shift 2;;
    -N) N="$2"; shift 2;;
    -k) CHUNK="$2"; shift 2;;
    -j) CONC="$2"; shift 2;;
    -m) MAXSUB="$2"; shift 2;;
    -w) WAIT="$2"; shift 2;;
    -o) START="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    --) shift; PASS=("$@"); break;;
    *) echo "未知参数: $1" >&2; usage; exit 2;;
  esac
done

[[ -n "$SCRIPT" && "$N" -gt 0 ]] || { echo "必须指定 -s 脚本 和 -N 总数" >&2; usage; exit 2; }
[[ -f "$SCRIPT" ]] || { echo "找不到脚本: $SCRIPT" >&2; exit 2; }
command -v sbatch >/dev/null || { echo "找不到 sbatch" >&2; exit 2; }

submitted_count() { squeue -u "$USER_NAME" -h -r -t pending,running -o "%i" | wc -l | tr -d ' '; }

echo "[$(date '+%F %T')] 分块提交开始: 脚本=$SCRIPT 总数=$N 块=$CHUNK 并发=%$CONC 提交上限=$MAXSUB"
start="$START"
while [[ "$start" -le "$N" ]]; do
  end=$(( start + CHUNK - 1 )); [[ "$end" -gt "$N" ]] && end="$N"
  size=$(( end - start + 1 ))

  while :; do
    cur=$(submitted_count)
    [[ $(( cur + size )) -le "$MAXSUB" ]] && break
    echo "[$(date '+%F %T')] 已提交 $cur, 再加 $size 会超 $MAXSUB, 等待 ${WAIT}s ..."
    sleep "$WAIT"
  done

  jid=$(sbatch --parsable --array="${start}-${end}%${CONC}" "${PASS[@]+"${PASS[@]}"}" "$SCRIPT")
  echo "[$(date '+%F %T')] 提交块 ${start}-${end} (${size}个) -> JobID ${jid}  [当前已提交≈$(submitted_count)]"
  start=$(( end + 1 ))
done
echo "[$(date '+%F %T')] 全部 $N 个任务提交完成。"
