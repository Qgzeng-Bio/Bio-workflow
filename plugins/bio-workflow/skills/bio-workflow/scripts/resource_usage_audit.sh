#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage:
  scripts/resource_usage_audit.sh [--script <sbatch>] [--jobid <id>] [--time-log <file>]... [--logs-dir <dir>] [--stage <name>]

Read-only resource usage audit for qgzeng bio-workflow rules.
It parses requested SLURM resources, sacct evidence, and GNU /usr/bin/time -v logs,
then prints TSV recommendations. It never writes reports, edits scripts, submits
jobs, cancels jobs, or resubmits jobs.

Recommended use:
  1. Run a small pilot or 4/8/16 benchmark with /usr/bin/time -v.
  2. Run this script on the pilot logs and sbatch script.
  3. Use the recommendation to choose full-run CPUs, memory, and array cap.
USAGE
}

script=""
jobid=""
logs_dir=""
stage="NA"
time_logs=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --script)
            [[ $# -ge 2 ]] || { echo "FAIL | --script requires a value" >&2; exit 1; }
            script="$2"
            shift 2
            ;;
        --jobid)
            [[ $# -ge 2 ]] || { echo "FAIL | --jobid requires a value" >&2; exit 1; }
            jobid="$2"
            shift 2
            ;;
        --time-log)
            [[ $# -ge 2 ]] || { echo "FAIL | --time-log requires a value" >&2; exit 1; }
            time_logs+=("$2")
            shift 2
            ;;
        --logs-dir)
            [[ $# -ge 2 ]] || { echo "FAIL | --logs-dir requires a value" >&2; exit 1; }
            logs_dir="$2"
            shift 2
            ;;
        --stage)
            [[ $# -ge 2 ]] || { echo "FAIL | --stage requires a value" >&2; exit 1; }
            stage="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "FAIL | Unknown argument: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

if [[ -z "$script" && -z "$jobid" && "${#time_logs[@]}" -eq 0 && -z "$logs_dir" ]]; then
    echo "FAIL | Provide at least one of --script, --jobid, --time-log, or --logs-dir" >&2
    usage >&2
    exit 1
fi

if [[ -n "$script" ]]; then
    [[ -e "$script" ]] || { echo "FAIL | Script does not exist: $script" >&2; exit 1; }
    [[ -r "$script" ]] || { echo "FAIL | Script is not readable: $script" >&2; exit 1; }
fi

if [[ -n "$jobid" && ! "$jobid" =~ ^[0-9]+([_.][0-9]+)?$ ]]; then
    echo "FAIL | --jobid should look like a SLURM job ID: $jobid" >&2
    exit 1
fi

if [[ -n "$logs_dir" ]]; then
    [[ -d "$logs_dir" ]] || { echo "FAIL | --logs-dir does not exist: $logs_dir" >&2; exit 1; }
    if [[ "${#time_logs[@]}" -eq 0 ]]; then
        while IFS= read -r discovered; do
            [[ -n "$discovered" ]] && time_logs+=("$discovered")
        done < <(
            if [[ -n "$jobid" ]]; then
                find "$logs_dir" -maxdepth 3 -type f \( -name "*${jobid}*time*" -o -name "*${jobid}*.time" -o -name "*${jobid}*.time.log" \) -print 2>/dev/null || true
            else
                find "$logs_dir" -maxdepth 3 -type f \( -name "*.time" -o -name "*.time.log" -o -name "*time*.log" \) -print 2>/dev/null || true
            fi
        )
    fi
fi

for file in "${time_logs[@]}"; do
    [[ -e "$file" ]] || { echo "FAIL | Time log does not exist: $file" >&2; exit 1; }
    [[ -r "$file" ]] || { echo "FAIL | Time log is not readable: $file" >&2; exit 1; }
done

get_sbatch_value() {
    local long="$1"
    local short="$2"
    local line rest token next value=""
    local -a fields
    [[ -n "$script" ]] || return 1
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

mem_to_gb() {
    local raw="$1"
    awk -v raw="$raw" '
        BEGIN {
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", raw)
            if (raw == "" || raw == "NA") { print "NA"; exit }
            value = raw
            unit = raw
            gsub(/[^0-9.]/, "", value)
            gsub(/[0-9.]/, "", unit)
            unit = toupper(unit)
            if (value == "") { print "NA"; exit }
            if (unit == "" || unit == "M" || unit == "MB") gb = value / 1024
            else if (unit == "K" || unit == "KB") gb = value / 1024 / 1024
            else if (unit == "G" || unit == "GB") gb = value
            else if (unit == "T" || unit == "TB") gb = value * 1024
            else gb = value / 1024
            printf "%.2f\n", gb
        }
    '
}

kb_to_gb() {
    local kb="$1"
    awk -v kb="$kb" 'BEGIN { if (kb == "" || kb == "NA") print "NA"; else printf "%.2f\n", kb / 1024 / 1024 }'
}

elapsed_to_seconds() {
    local raw="$1"
    awk -v raw="$raw" '
        BEGIN {
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", raw)
            if (raw == "" || raw == "NA") { print "NA"; exit }
            days = 0
            if (raw ~ /-/) {
                split(raw, d, "-")
                days = d[1]
                raw = d[2]
            }
            n = split(raw, a, ":")
            if (n == 3) sec = a[1] * 3600 + a[2] * 60 + a[3]
            else if (n == 2) sec = a[1] * 60 + a[2]
            else sec = raw
            sec += days * 86400
            printf "%.2f\n", sec
        }
    '
}

ceil_float() {
    local value="$1"
    awk -v x="$value" 'BEGIN { if (x == "" || x == "NA") print "NA"; else { y = int(x); if (x > y) y++; if (y < 1) y = 1; print y } }'
}

fmt_percent() {
    local numerator="$1"
    local denominator="$2"
    awk -v n="$numerator" -v d="$denominator" 'BEGIN { if (n == "NA" || d == "NA" || d <= 0) print "NA"; else printf "%.1f", 100 * n / d }'
}

requested_cpus="$(get_sbatch_value "--cpus-per-task" "-c" || true)"
if [[ -z "$requested_cpus" ]]; then
    requested_cpus="$(get_sbatch_value "--ntasks" "-n" || true)"
fi
requested_cpus="${requested_cpus:-NA}"
requested_mem_gb="NA"

if [[ -n "$script" ]]; then
    mem_value="$(get_sbatch_value "--mem" "" || true)"
    mem_per_cpu="$(get_sbatch_value "--mem-per-cpu" "" || true)"
    if [[ -n "$mem_value" ]]; then
        requested_mem_gb="$(mem_to_gb "$mem_value")"
    elif [[ -n "$mem_per_cpu" && "$requested_cpus" =~ ^[0-9]+$ ]]; then
        mem_per_cpu_gb="$(mem_to_gb "$mem_per_cpu")"
        requested_mem_gb="$(awk -v m="$mem_per_cpu_gb" -v c="$requested_cpus" 'BEGIN { printf "%.2f\n", m * c }')"
    fi
fi

sacct_output=""
sacct_maxrss_gb="NA"
sacct_elapsed="NA"
sacct_state="NA"
sacct_exit_code="NA"
sacct_alloc_cpus="NA"

if [[ -n "$jobid" ]]; then
    if command -v sacct >/dev/null 2>&1; then
        sacct_output="$(sacct -j "$jobid" --format=JobID,State,ExitCode,MaxRSS,Elapsed,AllocCPUS -n -P 2>/dev/null || true)"
        if [[ -n "$sacct_output" ]]; then
            sacct_state="$(printf '%s\n' "$sacct_output" | awk -F'|' 'NF >= 2 && $2 != "" { print $2; exit }')"
            sacct_exit_code="$(printf '%s\n' "$sacct_output" | awk -F'|' 'NF >= 3 && $3 != "" { print $3; exit }')"
            sacct_elapsed="$(printf '%s\n' "$sacct_output" | awk -F'|' 'NF >= 5 && $5 != "" { print $5; exit }')"
            sacct_alloc_cpus="$(printf '%s\n' "$sacct_output" | awk -F'|' 'NF >= 6 && $6 ~ /^[0-9]+$/ { print $6; exit }')"
            sacct_maxrss_gb="$(
                printf '%s\n' "$sacct_output" \
                    | awk -F'|' '
                        function to_gb(x, value, unit) {
                            gsub(/^[[:space:]]+|[[:space:]]+$/, "", x)
                            if (x == "" || x == "0") return 0
                            value = x
                            unit = x
                            gsub(/[^0-9.]/, "", value)
                            gsub(/[0-9.]/, "", unit)
                            unit = toupper(unit)
                            if (value == "") return 0
                            if (unit == "" || unit == "K" || unit == "KB") return value / 1024 / 1024
                            if (unit == "M" || unit == "MB") return value / 1024
                            if (unit == "G" || unit == "GB") return value
                            if (unit == "T" || unit == "TB") return value * 1024
                            return value / 1024 / 1024
                        }
                        NF >= 4 { gb = to_gb($4); if (gb > max) max = gb }
                        END { if (max > 0) printf "%.2f\n", max; else print "NA" }
                    '
            )"
        fi
    else
        sacct_output="WARN | sacct not found in PATH"
    fi
fi

if [[ "$requested_cpus" == "NA" && "$sacct_alloc_cpus" =~ ^[0-9]+$ ]]; then
    requested_cpus="$sacct_alloc_cpus"
fi

infer_threads_from_text() {
    local file="$1"
    local base
    base="$(basename "$file")"
    awk -v base="$base" '
        function emit(x) {
            if (x ~ /^[0-9]+$/ && x > 0) { print x; exit 0 }
        }
        BEGIN {
            if (match(base, /(^|[^[:alnum:]])(threads?|cpus?|cpu|t)([_=-]?)([0-9]+)([^[:alnum:]]|$)/, b)) emit(b[4])
            if (match(base, /(^|[^[:alnum:]])([0-9]+)([_=-]?)(threads?|cpus?)([^[:alnum:]]|$)/, c)) emit(c[2])
        }
        /Command being timed:/ || /threads?[ =:]/ || /cpus?[ =:]/ || /SLURM_CPUS_PER_TASK/ || /--threads|--cpus|--cores|--jobs|-t[[:space:]]|-p[[:space:]]|-@[[:space:]]/ {
            line = $0
            if (match(line, /(threads?|cpus?|cores|jobs)[ =:]+([0-9]+)/, a)) emit(a[2])
            if (match(line, /--(threads?|cpus|cores|jobs)[= ]+([0-9]+)/, d)) emit(d[2])
            if (match(line, /(^|[[:space:]])-[@tp][[:space:]]+([0-9]+)/, e)) emit(e[2])
            if (match(line, /SLURM_CPUS_PER_TASK[^0-9]*([0-9]+)/, f)) emit(f[1])
        }
    ' "$file" 2>/dev/null || true
}

parse_time_log() {
    local file="$1"
    local percent elapsed maxrss_kb threads elapsed_seconds maxrss_gb exit_status
    percent="$(awk -F': ' '/Percent of CPU this job got/ { gsub(/%/, "", $2); print $2; exit }' "$file" 2>/dev/null || true)"
    elapsed="$(awk -F': ' '/Elapsed \(wall clock\) time/ { print $NF; exit }' "$file" 2>/dev/null || true)"
    maxrss_kb="$(awk -F': ' '/Maximum resident set size/ { print $2; exit }' "$file" 2>/dev/null || true)"
    exit_status="$(awk -F': ' '/Exit status/ { print $2; exit }' "$file" 2>/dev/null || true)"
    threads="$(infer_threads_from_text "$file")"
    [[ -n "$threads" ]] || threads="NA"
    [[ -n "$exit_status" ]] || exit_status="NA"
    elapsed_seconds="$(elapsed_to_seconds "${elapsed:-NA}")"
    maxrss_gb="$(kb_to_gb "${maxrss_kb:-NA}")"
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$file" "${percent:-NA}" "${elapsed_seconds:-NA}" "$maxrss_gb" "$threads" "${elapsed:-NA}" "$exit_status"
}

time_rows=()
if [[ "${#time_logs[@]}" -gt 0 ]]; then
    for file in "${time_logs[@]}"; do
        time_rows+=("$(parse_time_log "$file")")
    done
fi

benchmark_recommended="NA"
benchmark_classification=""
benchmark_note=""

if [[ "${#time_rows[@]}" -ge 2 ]]; then
    benchmark_recommended="$(
        printf '%s\n' "${time_rows[@]}" \
            | awk -F'\t' '
                $3 != "NA" && $5 ~ /^[0-9]+$/ {
                    n++
                    elapsed[n] = $3 + 0
                    threads[n] = $5 + 0
                    if (fastest == 0 || elapsed[n] < fastest) fastest = elapsed[n]
                }
                END {
                    if (n < 2) { print "NA"; exit }
                    threshold = fastest * 1.15
                    rec = 0
                    for (i = 1; i <= n; i++) {
                        if (elapsed[i] <= threshold && (rec == 0 || threads[i] < rec)) rec = threads[i]
                    }
                    if (rec > 0) print rec; else print "NA"
                }
            '
    )"
    if [[ "$benchmark_recommended" != "NA" ]]; then
        max_threads="$(
            printf '%s\n' "${time_rows[@]}" \
                | awk -F'\t' '$5 ~ /^[0-9]+$/ && $5 > max { max = $5 } END { if (max > 0) print max; else print "NA" }'
        )"
        if [[ "$max_threads" != "NA" && "$benchmark_recommended" =~ ^[0-9]+$ && "$max_threads" =~ ^[0-9]+$ && "$benchmark_recommended" -lt "$max_threads" ]]; then
            benchmark_classification="LOW_THREAD_SCALING"
            benchmark_note="Benchmark walltime shows weak high-thread scaling; choose the smallest thread count within 15% of the fastest run."
        fi
    fi
fi

classify_row() {
    local req_cpu="$1"
    local used_cpu="$2"
    local req_mem="$3"
    local maxrss="$4"
    local row_threads="$5"
    local exit_status="$6"
    local cpu_eff mem_eff class rec_cpu action benchmark_active
    cpu_eff="$(fmt_percent "$used_cpu" "$req_cpu")"
    mem_eff="$(fmt_percent "$maxrss" "$req_mem")"
    class=""
    rec_cpu="$req_cpu"
    benchmark_active=0
    action="Resource use matches the request; keep current resources unless queue pressure or output validation suggests otherwise."

    if [[ "$exit_status" != "NA" && "$exit_status" != "0" ]]; then
        printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
            "$used_cpu" "$cpu_eff" "$req_mem" "$maxrss" "$mem_eff" \
            "RUN_FAILED" "NA" "Timed command exited with status $exit_status; resource evidence is not valid for down-tuning. Run slurm_failure_triage.sh or inspect logs before changing CPU, memory, or array concurrency."
        return
    fi

    if [[ -n "$benchmark_classification" && "$row_threads" =~ ^[0-9]+$ ]]; then
        class="$benchmark_classification"
        rec_cpu="$benchmark_recommended"
        benchmark_active=1
        action="$benchmark_note"
    fi

    if [[ "$req_cpu" =~ ^[0-9]+$ && "$used_cpu" != "NA" ]]; then
        cpu_over="$(awk -v req="$req_cpu" -v eff="$cpu_eff" 'BEGIN { print (req > 4 && eff < 50) ? 1 : 0 }')"
        if [[ "$cpu_over" -eq 1 ]]; then
            class="${class:+$class;}CPU_OVERREQUEST"
            if [[ "$benchmark_active" -eq 1 ]]; then
                action="$action CPU use on this row is also below the request; keep the benchmark-derived CPU recommendation unless another pilot shows stronger scaling."
            else
                rec_cpu="$(ceil_float "$used_cpu")"
                action="CPU request is much higher than observed use; use a smaller pilot-derived --cpus-per-task before scaling, then prefer SLURM array over one oversized serial job."
            fi
        fi
    fi

    if [[ "$req_mem" != "NA" && "$maxrss" != "NA" ]]; then
        mem_over="$(awk -v eff="$mem_eff" 'BEGIN { print (eff < 35) ? 1 : 0 }')"
        if [[ "$mem_over" -eq 1 ]]; then
            class="${class:+$class;}MEM_OVERREQUEST"
            if [[ "$action" == "Resource use matches the request;"* ]]; then
                action="Memory use is far below the request; WARN only. Do not lower --mem automatically without another pilot or knowledge of input-size scaling."
            else
                action="$action Memory use is also far below the request; treat memory reduction as WARN-only."
            fi
        fi
    fi

    if [[ -z "$class" ]]; then
        class="RESOURCE_OK"
    fi

    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$used_cpu" "$cpu_eff" "$req_mem" "$maxrss" "$mem_eff" "$class" "$rec_cpu" "$action"
}

printf 'Stage\tSource\tJob_ID\tExit_Status\tRequested_CPUs\tEstimated_Used_CPUs\tCPU_Efficiency\tRequested_Mem_GB\tMaxRSS_GB\tMem_Efficiency\tClassification\tRecommended_CPUs\tRecommended_Action\n'

if [[ "${#time_rows[@]}" -gt 0 ]]; then
    for row in "${time_rows[@]}"; do
        IFS=$'\t' read -r file percent_cpu elapsed_sec maxrss_gb threads elapsed_raw exit_status <<< "$row"
        used_cpus="NA"
        if [[ "$percent_cpu" != "NA" ]]; then
            used_cpus="$(awk -v pct="$percent_cpu" 'BEGIN { printf "%.2f\n", pct / 100 }')"
        fi
        row_req_cpu="$requested_cpus"
        if [[ "$row_req_cpu" == "NA" && "$threads" =~ ^[0-9]+$ ]]; then
            row_req_cpu="$threads"
        fi
        row_maxrss="$maxrss_gb"
        if [[ "$row_maxrss" == "NA" ]]; then
            row_maxrss="$sacct_maxrss_gb"
        fi
        classification_fields="$(classify_row "$row_req_cpu" "$used_cpus" "$requested_mem_gb" "$row_maxrss" "$threads" "$exit_status")"
        printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$stage" "$file" "${jobid:-NA}" "$exit_status" "$row_req_cpu" "$classification_fields"
    done
else
    used_cpus="NA"
    maxrss_gb="$sacct_maxrss_gb"
    sacct_exit_status="NA"
    if [[ "$sacct_exit_code" != "NA" && -n "$sacct_exit_code" ]]; then
        sacct_exit_status="${sacct_exit_code%%:*}"
    fi
    classification_fields="$(classify_row "$requested_cpus" "$used_cpus" "$requested_mem_gb" "$maxrss_gb" "NA" "$sacct_exit_status")"
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$stage" "sacct" "${jobid:-NA}" "$sacct_exit_status" "$requested_cpus" "$classification_fields"
fi

if [[ -n "$sacct_output" ]]; then
    printf '[NOTE] sacct_State=%s ExitCode=%s Elapsed=%s AllocCPUS=%s\n' "${sacct_state:-NA}" "${sacct_exit_code:-NA}" "${sacct_elapsed:-NA}" "${sacct_alloc_cpus:-NA}" >&2
fi
printf '[NOTE] Read-only audit only; reports/resource_usage.tsv was not written.\n' >&2
