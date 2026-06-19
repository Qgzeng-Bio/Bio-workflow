#!/usr/bin/env bash
# submit_chunked.sh — safe chunked array submitter for large task sets.
#
# This script never calls sbatch directly.  It materializes one checked sbatch
# copy per chunk, with the real #SBATCH --array range embedded in that copy, and
# delegates submission to submit_and_log.sh so the normal prepare_submission.sh
# gate, dry-run behavior, TOCTOU check, and run record still apply.
set -euo pipefail

usage() {
    cat <<'EOF'
submit_chunked.sh — split a large array into QOS-safe chunks

Usage:
  submit_chunked.sh -s job.sbatch -N 850 [-k 150] [-j 50] [-m 180] [-w 60] [-o 1] \
      [--manifest FILE] [--input-list FILE] [--output DIR] [--mode P] \
      [--record FILE] [--claim-manifest FILE] [--yes]

Options:
  -s FILE       source sbatch script. Its #SBATCH --array, if present, is
                replaced in each chunk copy.
  -N INT        total task count. Chunks cover START..N.
  -k INT        chunk size (default 150).
  -j INT        per-chunk array concurrency cap, written as %INT (default 50).
  -m INT        maximum submitted/running jobs allowed before each chunk
                submission (default 180, leaving room under the 200 cap).
  -w INT        seconds to wait between queue checks when over the cap (default 60).
  -o INT        first array index (default 1).
  --manifest FILE        forwarded to submit_and_log.sh / prepare_submission.sh.
  --input-list FILE      forwarded to submit_and_log.sh / prepare_submission.sh.
  --output DIR           forwarded to submit_and_log.sh / prepare_submission.sh.
  --chunk-dir DIR        directory for materialized chunk scripts (default:
                         ./reports/submitted_scripts/chunked/<run>_<script>).
  --mode P               forwarded to submit_and_log.sh / prepare_submission.sh.
  --record FILE          forwarded to submit_and_log.sh (default there:
                         reports/run_record.tsv).
  --claim-manifest FILE  forwarded to submit_and_log.sh.
  --yes                  actually submit. Without --yes this is a dry-run and
                         writes no chunk scripts.
  -h, --help             show this help.

No arbitrary sbatch passthrough is supported. Put submission-relevant settings in
the sbatch script so the gate inspects exactly what will run.
EOF
}

script=""
total=0
chunk=150
conc=50
max_submit=180
wait_s=60
start_index=1
manifest=""
input_list=""
output_dir=""
chunk_dir_arg=""
mode=""
record=""
claim_manifest=""
do_submit=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        -s) [[ $# -ge 2 ]] || { echo "ERROR | -s requires a value" >&2; exit 2; }; script="$2"; shift 2 ;;
        -N) [[ $# -ge 2 ]] || { echo "ERROR | -N requires a value" >&2; exit 2; }; total="$2"; shift 2 ;;
        -k) [[ $# -ge 2 ]] || { echo "ERROR | -k requires a value" >&2; exit 2; }; chunk="$2"; shift 2 ;;
        -j) [[ $# -ge 2 ]] || { echo "ERROR | -j requires a value" >&2; exit 2; }; conc="$2"; shift 2 ;;
        -m) [[ $# -ge 2 ]] || { echo "ERROR | -m requires a value" >&2; exit 2; }; max_submit="$2"; shift 2 ;;
        -w) [[ $# -ge 2 ]] || { echo "ERROR | -w requires a value" >&2; exit 2; }; wait_s="$2"; shift 2 ;;
        -o) [[ $# -ge 2 ]] || { echo "ERROR | -o requires a value" >&2; exit 2; }; start_index="$2"; shift 2 ;;
        --manifest) [[ $# -ge 2 ]] || { echo "ERROR | --manifest requires a value" >&2; exit 2; }; manifest="$2"; shift 2 ;;
        --input-list) [[ $# -ge 2 ]] || { echo "ERROR | --input-list requires a value" >&2; exit 2; }; input_list="$2"; shift 2 ;;
        --output) [[ $# -ge 2 ]] || { echo "ERROR | --output requires a value" >&2; exit 2; }; output_dir="$2"; shift 2 ;;
        --chunk-dir) [[ $# -ge 2 ]] || { echo "ERROR | --chunk-dir requires a value" >&2; exit 2; }; chunk_dir_arg="$2"; shift 2 ;;
        --mode) [[ $# -ge 2 ]] || { echo "ERROR | --mode requires a value" >&2; exit 2; }; mode="$2"; shift 2 ;;
        --record) [[ $# -ge 2 ]] || { echo "ERROR | --record requires a value" >&2; exit 2; }; record="$2"; shift 2 ;;
        --claim-manifest) [[ $# -ge 2 ]] || { echo "ERROR | --claim-manifest requires a value" >&2; exit 2; }; claim_manifest="$2"; shift 2 ;;
        --yes) do_submit=1; shift ;;
        -h|--help) usage; exit 0 ;;
        --) echo "ERROR | arbitrary sbatch passthrough is disabled; encode options in the script and rerun the gate" >&2; exit 2 ;;
        *) echo "ERROR | unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

[[ -n "$script" ]] || { echo "ERROR | missing -s <script>" >&2; usage >&2; exit 2; }
[[ -e "$script" && -r "$script" ]] || { echo "ERROR | source script missing or unreadable: $script" >&2; exit 2; }
[[ "$total" =~ ^[1-9][0-9]*$ ]] || { echo "ERROR | -N must be an integer >= 1: $total" >&2; exit 2; }
[[ "$chunk" =~ ^[1-9][0-9]*$ ]] || { echo "ERROR | -k must be an integer >= 1: $chunk" >&2; exit 2; }
[[ "$conc" =~ ^[1-9][0-9]*$ ]] || { echo "ERROR | -j must be an integer >= 1: $conc" >&2; exit 2; }
[[ "$max_submit" =~ ^[1-9][0-9]*$ ]] || { echo "ERROR | -m must be an integer >= 1: $max_submit" >&2; exit 2; }
[[ "$wait_s" =~ ^[0-9]+$ ]] || { echo "ERROR | -w must be an integer >= 0: $wait_s" >&2; exit 2; }
[[ "$start_index" =~ ^[1-9][0-9]*$ ]] || { echo "ERROR | -o must be an integer >= 1: $start_index" >&2; exit 2; }
[[ "$start_index" -le "$total" ]] || { echo "ERROR | -o start index cannot exceed -N total: $start_index > $total" >&2; exit 2; }
grep -Eq '^[[:space:]]*#SBATCH[[:space:]]+' "$script" || {
    echo "ERROR | source script has no #SBATCH directives; chunk copies would not be inspectable" >&2
    exit 2
}

self_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
submitter="$self_dir/submit_and_log.sh"
[[ -x "$submitter" ]] || { echo "ERROR | submit_and_log.sh missing or not executable: $submitter" >&2; exit 1; }
work_root="$(pwd -P)"

resolve_safe() {
    local p="$1" n
    command -v realpath >/dev/null 2>&1 || return 1
    n="$(realpath -m -- "$p" 2>/dev/null)" || return 1
    [[ "$n" == /* ]] || return 1
    case "$n" in */../*|*/.. ) return 1 ;; esac
    printf '%s\n' "$n"
}

protected_write_path() {
    case "$1" in
        /data9/home/qgzeng/data|/data9/home/qgzeng/data/*|/data9/home/qgzeng/tools|/data9/home/qgzeng/tools/*)
            return 0
            ;;
    esac
    return 1
}

script_abs="$(resolve_safe "$script")" || { echo "ERROR | cannot safely resolve source script: $script" >&2; exit 2; }
script_base="$(basename "$script_abs")"
safe_base="${script_base//[^A-Za-z0-9._-]/_}"
safe_base="${safe_base%.*}"
[[ -n "$safe_base" ]] || safe_base="chunked_job"
run_id="$(date '+%Y%m%dT%H%M%S')"
if [[ -n "$chunk_dir_arg" ]]; then
    chunk_dir="$(resolve_safe "$chunk_dir_arg")" || { echo "ERROR | cannot safely resolve --chunk-dir: $chunk_dir_arg" >&2; exit 2; }
else
    chunk_dir="$(resolve_safe "$work_root/reports/submitted_scripts/chunked/${run_id}_${safe_base}")" || {
        echo "ERROR | cannot safely resolve default chunk dir under: $work_root" >&2
        exit 2
    }
fi
if protected_write_path "$chunk_dir"; then
    echo "ERROR | refusing to write chunk scripts under protected data/tools root: $chunk_dir" >&2
    exit 2
fi
queue_user="${SLURM_USER:-${USER:-}}"
if [[ -z "$queue_user" ]]; then
    queue_user="$(whoami 2>/dev/null || true)"
fi
[[ -n "$queue_user" ]] || { echo "ERROR | cannot determine queue user; set USER or SLURM_USER" >&2; exit 2; }

submitted_count() {
    local count
    count="$(squeue -u "$queue_user" -h -r -t pending,running -o "%i" 2>/dev/null | wc -l | tr -d ' ')" || return 1
    [[ "$count" =~ ^[0-9]+$ ]] || return 1
    printf '%s\n' "$count"
}

shell_join() {
    local arg
    for arg in "$@"; do
        printf '%q ' "$arg"
    done
}

write_chunk_script() {
    local src="$1" dst="$2" range="$3" tmp
    tmp="${dst}.tmp"
    awk -v array_line="#SBATCH --array=${range}" '
        BEGIN { inserted = 0; saw_sbatch = 0 }
        /^[[:space:]]*#SBATCH[[:space:]]+/ {
            saw_sbatch = 1
            if ($0 ~ /^[[:space:]]*#SBATCH[[:space:]]+--array([=[:space:]]|$)/) {
                if (!inserted) {
                    print array_line
                    inserted = 1
                }
                next
            }
            print
            next
        }
        {
            if (!inserted && saw_sbatch) {
                print array_line
                inserted = 1
            }
            print
        }
        END {
            if (!inserted) print array_line
        }
    ' "$src" > "$tmp"
    mv "$tmp" "$dst"
}

submit_args_base=()
[[ -n "$record" ]] && submit_args_base+=(--record "$record")
[[ -n "$manifest" ]] && submit_args_base+=(--manifest "$manifest")
[[ -n "$input_list" ]] && submit_args_base+=(--input-list "$input_list")
[[ -n "$output_dir" ]] && submit_args_base+=(--output "$output_dir")
[[ -n "$mode" ]] && submit_args_base+=(--mode "$mode")
[[ -n "$claim_manifest" ]] && submit_args_base+=(--claim-manifest "$claim_manifest")

printf '[INFO] chunked submit plan\n'
printf '[INFO] Source script: %s\n' "$script_abs"
printf '[INFO] Task range: %s-%s  chunk=%s  concurrency=%%%s  submit-cap=%s\n' \
    "$start_index" "$total" "$chunk" "$conc" "$max_submit"
printf '[INFO] Mode: %s\n' "$([[ "$do_submit" -eq 1 ]] && echo "SUBMIT (--yes)" || echo "DRY-RUN (no writes, no sbatch)")"
printf '[INFO] Chunk script dir: %s\n' "$chunk_dir"

if [[ "$do_submit" -eq 1 ]]; then
    mkdir -p "$chunk_dir"
fi

idx="$start_index"
chunk_no=0
while [[ "$idx" -le "$total" ]]; do
    end=$(( idx + chunk - 1 ))
    [[ "$end" -gt "$total" ]] && end="$total"
    size=$(( end - idx + 1 ))
    range="${idx}-${end}%${conc}"
    chunk_no=$(( chunk_no + 1 ))
    chunk_script="$chunk_dir/${safe_base}.chunk${chunk_no}.${idx}-${end}.sbatch"
    submit_cmd=("$submitter" --script "$chunk_script" "${submit_args_base[@]}" --conc "$conc")

    if [[ "$do_submit" -ne 1 ]]; then
        printf '[DRY-RUN] chunk %03d: array=%s size=%s script=%s\n' "$chunk_no" "$range" "$size" "$chunk_script"
        printf '          would run: '
        shell_join "${submit_cmd[@]}" --yes
        printf '\n'
        idx=$(( end + 1 ))
        continue
    fi

    while :; do
        cur="$(submitted_count)" || {
            echo "ERROR | cannot read current squeue count; refusing chunk submission until quota can be checked" >&2
            exit 1
        }
        [[ $(( cur + size )) -le "$max_submit" ]] && break
        printf '[INFO] submitted=%s; adding %s would exceed %s; sleeping %ss\n' \
            "$cur" "$size" "$max_submit" "$wait_s"
        sleep "$wait_s"
    done

    write_chunk_script "$script_abs" "$chunk_script" "$range"
    printf '[INFO] submitting chunk %03d: array=%s script=%s\n' "$chunk_no" "$range" "$chunk_script"
    "${submit_cmd[@]}" --yes
    idx=$(( end + 1 ))
done

printf '[INFO] chunked submitter finished: %s chunks planned%s\n' \
    "$chunk_no" "$([[ "$do_submit" -eq 1 ]] && echo " and submitted through submit_and_log.sh" || echo " (dry-run only)")"
