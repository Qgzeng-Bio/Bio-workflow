#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage:
  scripts/parallelization_audit.sh --script <file> [--manifest <file>] [--mode auto|sample|chromosome|file]

Read-only parallelization audit for qgzeng bio-workflow rules.
It detects serial independent-task bottlenecks and CPU requests that are not
passed to tools, then prints TSV suggestions. It never rewrites scripts, writes
manifests, submits jobs, cancels jobs, or resubmits jobs.
USAGE
}

script=""
manifest=""
mode="auto"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --script)
            [[ $# -ge 2 ]] || { echo "FAIL | --script requires a value" >&2; exit 1; }
            script="$2"
            shift 2
            ;;
        --manifest)
            [[ $# -ge 2 ]] || { echo "FAIL | --manifest requires a value" >&2; exit 1; }
            manifest="$2"
            shift 2
            ;;
        --mode)
            [[ $# -ge 2 ]] || { echo "FAIL | --mode requires a value" >&2; exit 1; }
            mode="$2"
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

if [[ -z "$script" ]]; then
    echo "FAIL | Missing --script <file>" >&2
    usage >&2
    exit 1
fi

case "$mode" in
    auto|sample|chromosome|file) ;;
    *)
        echo "FAIL | Unsupported --mode: $mode" >&2
        exit 1
        ;;
esac

[[ -e "$script" ]] || { echo "FAIL | Script does not exist: $script" >&2; exit 1; }
[[ -r "$script" ]] || { echo "FAIL | Script is not readable: $script" >&2; exit 1; }

if [[ -n "$manifest" ]]; then
    [[ -e "$manifest" ]] || { echo "FAIL | Manifest does not exist: $manifest" >&2; exit 1; }
    [[ -r "$manifest" ]] || { echo "FAIL | Manifest is not readable: $manifest" >&2; exit 1; }
fi

big_command_pattern='(^|[[:space:]/])(kmeria|fastp|bwa|minimap2|hisat2|STAR|samtools[[:space:]]+sort|hifiasm|orthofinder|braker[.]pl|braker|maker|EDTA[.]pl|RepeatModeler|RepeatMasker|syri|plotsr|nucmer|delta-filter|show-coords|juicer|3d-dna|run-asm-pipeline|busco|quast|gatk|bcftools|featureCounts|diamond|blastn|blastp|hmmsearch|hmmscan|cmscan|PanGenie)([[:space:]]|$)'

active_text="$(
    awk '/^[[:space:]]*#/ { next } /^[[:space:]]*$/ { next } { print }' "$script"
)"

sbatch_text="$(
    awk '/^[[:space:]]*#SBATCH[[:space:]]+/ { print }' "$script"
)"

get_sbatch_value() {
    local long="$1"
    local short="$2"
    local line rest token next value=""
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

requested_cpus="$(get_sbatch_value "--cpus-per-task" "-c" || true)"
requested_cpus="${requested_cpus:-NA}"
requested_mem_gb="NA"
mem_value="$(get_sbatch_value "--mem" "" || true)"
if [[ -n "$mem_value" ]]; then
    requested_mem_gb="$(mem_to_gb "$mem_value")"
fi

has_array=0
has_parallel=0
cpu_passed=0

if printf '%s\n' "$sbatch_text" | grep -Eq -- '--array(=|[[:space:]])'; then
    has_array=1
fi
if printf '%s\n' "$active_text" | grep -Eiq 'xargs[[:space:]].*-P|(^|[[:space:];|])parallel([[:space:]]|$)|(^|[[:space:];])wait([[:space:]]|$)|[[:space:]]&([[:space:]]*(#.*)?)?$'; then
    has_parallel=1
fi
if printf '%s\n' "$active_text" | grep -Eiq '\$SLURM_CPUS_PER_TASK|\$\{SLURM_CPUS_PER_TASK(:-[0-9]+)?\}|--threads(=|[[:space:]])|--thread(=|[[:space:]])|--cpus(=|[[:space:]])|--cpu(=|[[:space:]])|--cores(=|[[:space:]])|--jobs(=|[[:space:]])|--workers(=|[[:space:]])|(^|[[:space:]])-[tp@][[:space:]]+[0-9$]'; then
    cpu_passed=1
fi

repeated_summary="$(
    printf '%s\n' "$active_text" \
        | awk '
            BEGIN { IGNORECASE = 1 }
            function key_for(line, lower) {
                lower = tolower(line)
                if (lower ~ /kmeria[[:space:]]+count/) return "kmeria count"
                if (lower ~ /bwa[[:space:]]+mem/) return "bwa mem"
                if (lower ~ /samtools[[:space:]]+sort/) return "samtools sort"
                if (lower ~ /featurecounts/) return "featureCounts"
                if (lower ~ /repeatmodeler/) return "RepeatModeler"
                if (lower ~ /repeatmasker/) return "RepeatMasker"
                if (lower ~ /edta[.]pl/) return "EDTA.pl"
                if (match(lower, /(^|[[:space:]\/])(fastp|minimap2|hisat2|star|hifiasm|orthofinder|braker[.]pl|braker|maker|syri|plotsr|nucmer|busco|quast|gatk|bcftools|diamond|blastn|blastp|hmmsearch|hmmscan|cmscan|pangenie)([[:space:]]|$)/, a)) return a[2]
                return ""
            }
            {
                k = key_for($0)
                if (k != "") {
                    count[k]++
                    if (!(k in first)) first[k] = $0
                }
            }
            END {
                best = ""
                best_count = 0
                for (k in count) {
                    if (count[k] > best_count) {
                        best = k
                        best_count = count[k]
                    }
                }
                if (best_count > 0) print best "\t" best_count "\t" first[best]
            }
        '
)"

loop_big_count="$(
    awk -v pattern="$big_command_pattern" '
        BEGIN { IGNORECASE = 1; in_loop = 0; found = 0 }
        /^[[:space:]]*#/ { next }
        /^[[:space:]]*(for[[:space:]].*[[:space:]]in[[:space:]]|while[[:space:]]+read)(.*)$/ { in_loop = 1 }
        in_loop && $0 ~ pattern { found++ }
        /^[[:space:]]*done([[:space:]]|$)/ { in_loop = 0 }
        END { print found + 0 }
    ' "$script"
)"

manifest_tasks="NA"
manifest_header=0
if [[ -n "$manifest" ]]; then
    manifest_total="$(awk 'NF && $0 !~ /^[[:space:]]*#/ { n++ } END { print n + 0 }' "$manifest")"
    first_manifest_line="$(awk 'NF && $0 !~ /^[[:space:]]*#/ { print; exit }' "$manifest")"
    if printf '%s\n' "$first_manifest_line" | grep -Eiq '^(Sample_ID|Sample[[:space:]_-]*ID|Input_1|Read1|Chunk_ID|Item_List_File)([[:space:]]|$)'; then
        manifest_header=1
        manifest_tasks="$(awk -v n="$manifest_total" 'BEGIN { if (n > 0) print n - 1; else print 0 }')"
    else
        manifest_tasks="$manifest_total"
    fi
fi

audit_mode="$mode"
if [[ "$audit_mode" == "auto" ]]; then
    if [[ -n "$manifest" ]] && head -n 5 "$manifest" | grep -Eiq '(^|[[:space:]_])(sample|accession|fastq|fq|read)([[:space:]_]|$)'; then
        audit_mode="sample"
    elif printf '%s\n' "$active_text" | grep -Eiq 'chromosome|chrom|chr[0-9A-Za-z]+'; then
        audit_mode="chromosome"
    elif printf '%s\n' "$active_text" | grep -Eiq 'sample|fastq|fq\.gz|read1|read2|accession|kmeria[[:space:]]+count|fastp|bwa[[:space:]]+mem'; then
        audit_mode="sample"
    else
        audit_mode="file"
    fi
fi

candidate_unit="$audit_mode"
estimated_tasks="$manifest_tasks"
serial_bottleneck="NONE"
first_example="NA"

if [[ -n "$repeated_summary" ]]; then
    IFS=$'\t' read -r repeat_key repeat_count repeat_example <<< "$repeated_summary"
    if [[ "$repeat_count" -ge 3 && "$has_array" -eq 0 && "$has_parallel" -eq 0 ]]; then
        serial_bottleneck="Repeated $repeat_key commands appear to run serially ($repeat_count copies)"
        estimated_tasks="$repeat_count"
        first_example="$repeat_example"
    fi
fi

if [[ "$serial_bottleneck" == "NONE" && "$loop_big_count" -gt 0 && "$has_array" -eq 0 && "$has_parallel" -eq 0 ]]; then
    serial_bottleneck="Loop contains large-compute command without SLURM array or explicit local parallelism"
    first_example="$(printf '%s\n' "$active_text" | grep -Ei -m 1 "$big_command_pattern" || true)"
fi

if [[ "$serial_bottleneck" == "NONE" && "$requested_cpus" =~ ^[0-9]+$ && "$requested_cpus" -gt 4 && "$cpu_passed" -eq 0 ]]; then
    serial_bottleneck="CPU_OVERREQUEST_RISK: --cpus-per-task=$requested_cpus but no obvious tool thread parameter or SLURM_CPUS_PER_TASK use"
fi

if [[ "$estimated_tasks" == "NA" ]]; then
    if [[ -n "$repeated_summary" ]]; then
        IFS=$'\t' read -r _ repeat_count _ <<< "$repeated_summary"
        estimated_tasks="$repeat_count"
    else
        estimated_tasks="NA"
    fi
fi

suggested_cpus="4"
if [[ "$requested_cpus" =~ ^[0-9]+$ ]]; then
    if [[ "$cpu_passed" -eq 1 && "$requested_cpus" -le 8 ]]; then
        suggested_cpus="$requested_cpus"
    elif [[ "$requested_cpus" -le 4 ]]; then
        suggested_cpus="$requested_cpus"
    else
        suggested_cpus="4"
    fi
fi

array_cap="%4"
if [[ "$requested_mem_gb" != "NA" ]]; then
    array_cap="$(
        awk -v mem="$requested_mem_gb" '
            BEGIN {
                if (mem >= 96) print "%1";
                else if (mem >= 64) print "%2";
                else if (mem >= 32) print "%3";
                else print "%4";
            }
        '
    )"
fi
if printf '%s\n' "$active_text" | grep -Eiq 'kmeria|fastq|fq\.gz|bwa|samtools[[:space:]]+sort|pigz|gzip'; then
    if [[ "$array_cap" == "%4" ]]; then
        array_cap="%2"
    fi
fi

template="assets/slurm-templates/per_sample_array.sbatch"
if [[ "$audit_mode" == "file" ]]; then
    template="assets/slurm-templates/per_chunk_array.sbatch"
fi

array_upper="$estimated_tasks"
if [[ "$array_upper" == "NA" || ! "$array_upper" =~ ^[0-9]+$ || "$array_upper" -lt 1 ]]; then
    array_upper="N"
fi
recommended_array="#SBATCH --array=1-${array_upper}${array_cap}"
manifest_read='TASK_LINE="$(sed -n "${SLURM_ARRAY_TASK_ID}p" "$MANIFEST")"'
recommended_action="Use a SLURM array with one independent ${audit_mode} per task; keep per-task CPUs conservative and rerun failed array indices individually."
if [[ "$audit_mode" == "file" ]]; then
    recommended_action="Build a chunk manifest first, then use a SLURM array with one chunk per task when single files are too light or too numerous."
fi
if [[ "$has_array" -eq 1 ]]; then
    recommended_action="Script already has a SLURM array; verify it has a %N cap and that each task reads one manifest row."
fi
if [[ "$manifest_header" -eq 1 ]]; then
    recommended_action="Manifest header detected; default bundled array templates expect no header. Remove the header or adjust task-line indexing before submitting. $recommended_action"
fi
if [[ "$serial_bottleneck" == "NONE" ]]; then
    serial_bottleneck="No serial independent-task bottleneck detected by heuristic"
fi

printf 'Script\tMode\tCandidate_Unit\tEstimated_Tasks\tManifest_Header\tCurrent_Bottleneck\tCPU_Passed\tRequested_CPUs\tSuggested_CPUs_Per_Task\tSuggested_Array_Cap\tRecommended_Array\tManifest_Row_Read\tTemplate\tRecommended_Action\n'
printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$script" "$audit_mode" "$candidate_unit" "$estimated_tasks" "$manifest_header" "$serial_bottleneck" \
    "$cpu_passed" "$requested_cpus" "$suggested_cpus" "$array_cap" "$recommended_array" \
    "$manifest_read" "$template" "$recommended_action"

if [[ "$first_example" != "NA" && -n "$first_example" ]]; then
    printf '[NOTE] Example_Bottleneck_Command: %s\n' "$first_example" >&2
fi
printf '[NOTE] Read-only audit only; original script was not rewritten.\n' >&2
