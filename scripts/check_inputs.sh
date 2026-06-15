#!/usr/bin/env bash
# check_inputs.sh — 输入文件清单与完整性检查 (登录节点安全, 默认不做重IO)
set -euo pipefail

usage() {
  cat <<'EOF'
check_inputs.sh — 输入文件清单与完整性检查 (登录节点安全)
用法:
  check_inputs.sh f1 f2 ...                直接给文件
  check_inputs.sh -l filelist.txt          从清单读取(每行一个路径)
  check_inputs.sh -d DIR -p '*.fastq.gz'   在目录中按通配匹配 (注意给通配加引号)
选项:
  --paired      检查 R1/R2 (或 _1/_2) 是否成对 (需用分隔符, 如 samp_R1.fastq.gz)
  --gzip-test   对 .gz 做完整性测试 (gzip -t 会读全文件, 大文件请在计算节点跑)
检查项: 存在 / 可读 / 非空 / gz魔数 / 格式首字符(fastq=@ fasta=> vcf=#)
退出码: 0=全部通过  1=发现问题  2=参数错误
EOF
}

FILES=(); PAIRED=0; GZTEST=0; DIR=""; PAT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -l) mapfile -t _f < "$2"; FILES+=("${_f[@]}"); shift 2;;
    -d) DIR="$2"; shift 2;;
    -p) PAT="$2"; shift 2;;
    --paired)    PAIRED=1; shift;;
    --gzip-test) GZTEST=1; shift;;
    -h|--help)   usage; exit 0;;
    -*) echo "未知参数: $1" >&2; usage; exit 2;;
    *)  FILES+=("$1"); shift;;
  esac
done

if [[ -n "$DIR" ]]; then
  [[ -n "$PAT" ]] || { echo "-d 需配合 -p 通配" >&2; exit 2; }
  while IFS= read -r f; do FILES+=("$f"); done < <(find "$DIR" -maxdepth 1 -type f -name "$PAT" | sort)
fi
[[ "${#FILES[@]}" -gt 0 ]] || { echo "没有要检查的文件" >&2; exit 2; }

sniff() { # 只读少量内容判断格式, 不解压全文件 (head 关闭管道即停)
  local f="$1" c
  case "$f" in
    *.gz) c=$(zcat -- "$f" 2>/dev/null | head -c 1 || true);;
    *)    c=$(head -c 1 -- "$f" 2>/dev/null || true);;
  esac
  case "$c" in
    @) echo "fastq";; ">") echo "fasta";; "#") echo "vcf/hdr";; *) echo "?";;
  esac
}

problems=0; total_bytes=0
printf "%-46s %10s %5s %-8s %s\n" "FILE" "SIZE" "GZ" "FORMAT" "STATUS"
for f in "${FILES[@]}"; do
  st="OK"; gz="-"; fmt="-"; sz=0
  if   [[ ! -e "$f" ]]; then st="缺失";   problems=$((problems+1))
  elif [[ ! -r "$f" ]]; then st="不可读"; problems=$((problems+1))
  else
    sz=$(stat -c %s -- "$f" 2>/dev/null || echo 0); total_bytes=$((total_bytes+sz))
    [[ "$sz" -eq 0 ]] && { st="空文件"; problems=$((problems+1)); }
    if [[ "$f" == *.gz ]]; then
      if [[ "$(od -An -N2 -tx1 -- "$f" 2>/dev/null | tr -d ' ')" == "1f8b" ]]; then gz="ok"
      else gz="坏"; st="非gzip"; problems=$((problems+1)); fi
      if [[ "$GZTEST" -eq 1 && "$gz" == "ok" ]]; then
        gzip -t -- "$f" 2>/dev/null || { gz="CRC坏"; st="gzip损坏"; problems=$((problems+1)); }
      fi
    fi
    [[ "$st" == "OK" || "$st" == "空文件" ]] && fmt=$(sniff "$f")
  fi
  printf "%-46s %10s %5s %-8s %s\n" "$(basename "$f")" "$sz" "$gz" "$fmt" "$st"
done

echo "---"
printf "文件数: %d  总大小: %s  问题: %d\n" "${#FILES[@]}" \
  "$(awk -v b=$total_bytes 'BEGIN{printf "%.2f GB", b/1073741824}')" "$problems"

if [[ "$PAIRED" -eq 1 ]]; then
  echo "== 配对检查 (按去除 _R1/_R2/_1/_2 归组) =="
  declare -A cnt
  for f in "${FILES[@]}"; do
    key=$(basename "$f" | sed -E 's/[._-]R?[12]([._-]|$)/\1/')
    cnt["$key"]=$(( ${cnt["$key"]:-0} + 1 ))
  done
  for k in "${!cnt[@]}"; do
    [[ "${cnt[$k]}" -ne 2 ]] && { echo "  配对异常(${cnt[$k]}): $k"; problems=$((problems+1)); }
  done
  echo "  样本组数: ${#cnt[@]}"
fi

if [[ "$problems" -eq 0 ]]; then echo "✓ 全部通过"; exit 0
else echo "✗ 发现 $problems 个问题"; exit 1; fi
