#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage:
  scripts/project_state_audit.sh [--project <dir>] [--max-depth 3] [--max-files 1000] [--check-queue]

Read-only project state audit for qgzeng bio-workflow resume protocol.
Default project is the current directory. It never walks upward to parent roots.
It performs a bounded scan of project-local directories only:
config/ data/ scripts/ logs/ results/ reports/ tmp/

The script prints state candidates and a suggested workflow_status.tsv row.
It does not write files, submit jobs, cancel jobs, resubmit jobs, or repair outputs.
Broad roots such as /, /data9, /data9/home, your home directory, and your
home/projects directory are refused; ask the user for a narrower project directory.
USAGE
}

project="."
max_depth=3
max_files=1000
check_queue=0
scan_warnings=()
declare -A limit_warned=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --project)
            [[ $# -ge 2 ]] || { echo "FAIL | --project requires a value" >&2; exit 1; }
            project="$2"
            shift 2
            ;;
        --max-depth)
            [[ $# -ge 2 ]] || { echo "FAIL | --max-depth requires a value" >&2; exit 1; }
            max_depth="$2"
            shift 2
            ;;
        --max-files)
            [[ $# -ge 2 ]] || { echo "FAIL | --max-files requires a value" >&2; exit 1; }
            max_files="$2"
            shift 2
            ;;
        --check-queue)
            check_queue=1
            shift
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

if [[ ! "$max_depth" =~ ^[0-9]+$ || "$max_depth" -lt 1 || "$max_depth" -gt 6 ]]; then
    echo "FAIL | --max-depth must be an integer from 1 to 6" >&2
    exit 1
fi

if [[ ! "$max_files" =~ ^[0-9]+$ || "$max_files" -lt 50 || "$max_files" -gt 10000 ]]; then
    echo "FAIL | --max-files must be an integer from 50 to 10000" >&2
    exit 1
fi

if [[ ! -d "$project" ]]; then
    echo "FAIL | Project directory does not exist: $project" >&2
    exit 1
fi

project_abs="$(cd "$project" && pwd -P)"

# Refuse broad roots. Keep the cluster-wide literals, and also refuse the current
# user's own home and home/projects so a multi-user install protects every account.
_home_abs="$(cd "${HOME:-/nonexistent}" 2>/dev/null && pwd -P || echo "${HOME%/}")"
case "$project_abs" in
    /|/data9|/data9/home|"$_home_abs"|"${_home_abs%/}/projects")
        echo "FAIL | Refusing broad root audit: $project_abs" >&2
        echo "FAIL | Provide a narrower project directory; full-disk or account-wide scans require explicit confirmation." >&2
        exit 1
        ;;
esac
# Also refuse ANY account's home or home/projects on this cluster, not just the
# current user's, so a multi-user install never account-wide-scans a peer's tree.
if [[ "$project_abs" =~ ^/data9/home/[^/]+(/projects)?$ ]]; then
    echo "FAIL | Refusing broad account-root audit: $project_abs" >&2
    echo "FAIL | Provide a narrower project directory; account-wide scans require explicit confirmation." >&2
    exit 1
fi

cd "$project_abs"

scan_dirs=(config data scripts logs results reports tmp)

bounded_find_files() {
    local dir="$1"
    local count=0
    local file
    [[ -d "$dir" ]] || return 0
    while IFS= read -r file; do
        printf '%s\n' "$file"
        count=$((count + 1))
        if [[ "$count" -ge "$max_files" ]]; then
            if [[ -z "${limit_warned[$dir]:-}" ]]; then
                scan_warnings+=("$dir reached --max-files=$max_files; evidence may be incomplete.")
                limit_warned[$dir]=1
            fi
            break
        fi
    done < <(find "$dir" -maxdepth "$max_depth" \( -type f -o -type l \) -print 2>/dev/null || true)
}

list_files() {
    local dir
    for dir in "$@"; do
        bounded_find_files "$dir"
    done
}

recent_files() {
    local limit="$1"
    shift
    local file
    while IFS= read -r file; do
        [[ -n "$file" && -e "$file" ]] || continue
        printf '%s\t%s\n' "$(stat -c '%Y' "$file" 2>/dev/null || printf '0')" "$file"
    done < <(list_files "$@") | sort -nr | head -n "$limit" | cut -f2- || true
}

count_lines() {
    sed '/^$/d' | wc -l | tr -d ' '
}

first_nonempty() {
    sed -n '/./{p;q;}'
}

evidence_file_mtime() {
    local line="$1"
    local file="${line%%:*}"
    if [[ -e "$file" || -L "$file" ]]; then
        stat -c '%Y' "$file" 2>/dev/null || printf '0'
    else
        printf '0'
    fi
}

evidence_lines_max_mtime() {
    local lines="$1"
    local max=0
    local line
    local mtime
    while IFS= read -r line; do
        [[ -n "$line" ]] || continue
        mtime="$(evidence_file_mtime "$line")"
        [[ "$mtime" =~ ^[0-9]+$ ]] || mtime=0
        if [[ "$mtime" -gt "$max" ]]; then
            max="$mtime"
        fi
    done <<< "$lines"
    printf '%s\n' "$max"
}

filter_evidence_after_mtime() {
    local cutoff="$1"
    local lines="$2"
    local line
    local mtime
    while IFS= read -r line; do
        [[ -n "$line" ]] || continue
        mtime="$(evidence_file_mtime "$line")"
        [[ "$mtime" =~ ^[0-9]+$ ]] || mtime=0
        if [[ "$mtime" -gt 0 && "$mtime" -lt "$cutoff" ]]; then
            continue
        fi
        printf '%s\n' "$line"
    done <<< "$lines" | head -n 8 || true
}

print_block() {
    local title="$1"
    local body="$2"
    printf '[INFO] %s\n' "$title"
    if [[ -n "$body" ]]; then
        printf '%s\n' "$body" | sed 's/^/  - /'
    else
        printf '  - NA\n'
    fi
}

check_scan_limits() {
    local dir
    local count
    local file
    for dir in "$@"; do
        [[ -d "$dir" ]] || continue
        [[ -z "${limit_warned[$dir]:-}" ]] || continue
        count=0
        while IFS= read -r file; do
            count=$((count + 1))
            if [[ "$count" -gt "$max_files" ]]; then
                scan_warnings+=("$dir has more than --max-files=$max_files files; evidence was truncated.")
                limit_warned[$dir]=1
                break
            fi
        done < <(find "$dir" -maxdepth "$max_depth" \( -type f -o -type l \) -print 2>/dev/null || true)
    done
}

input_files="$(list_files config data | grep -Ei '(^|/)(manifest|sample|samples|config|params|input|inputs)|\.(tsv|csv|txt|yaml|yml|json|fa|fasta|fna|fq|fastq|gz|bam|cram|vcf|bcf|gff|gtf|bed)$' | head -n 80 || true)"
script_files="$(list_files scripts | grep -Ei '\.(sh|bash|slurm|sbatch)$|(^|/)(run|submit|workflow|pipeline)[^/]*$' | head -n 80 || true)"
log_files="$(list_files logs reports | grep -Ei '\.(out|err|log)$' | head -n 120 || true)"
err_files="$(printf '%s\n' "$log_files" | grep -Ei '\.err$' || true)"
out_log_files="$(printf '%s\n' "$log_files" | grep -Ei '\.(out|log)$' || true)"
result_files="$(list_files results reports | grep -Ev '^reports/workflow_status\.tsv$' | head -n 120 || true)"

input_count="$(printf '%s\n' "$input_files" | count_lines)"
script_count="$(printf '%s\n' "$script_files" | count_lines)"
log_count="$(printf '%s\n' "$log_files" | count_lines)"
result_count="$(printf '%s\n' "$result_files" | count_lines)"

slurm_script_files="$(
    while IFS= read -r file; do
        [[ -n "$file" && -r "$file" ]] || continue
        if [[ "$file" =~ \.(slurm|sbatch)$ ]] || head -n 80 "$file" | grep -Eq '^[[:space:]]*#SBATCH'; then
            printf '%s\n' "$file"
        fi
    done <<< "$script_files"
)"
slurm_script_count="$(printf '%s\n' "$slurm_script_files" | count_lines)"

failure_pattern='(OUT_OF_MEMORY|Out Of Memory|oom-kill|oom_kill|Cannot allocate memory|DUE TO TIME LIMIT|TIMEOUT|No such file or directory|cannot stat|command not found|ModuleNotFoundError|ImportError|Permission denied|Operation not permitted|Segmentation fault|core dumped|No space left on device|Disk quota exceeded|format error|invalid format|chromosome.*not found|contig.*not found|Traceback|FAILED|CANCELLED)'
install_failure_pattern='(Could not solve for environment specs|UnsatisfiableError|ResolvePackageNotFound|critical libmamba|Conda.*(failed|error)|conda.*(failed|error)|micromamba.*(failed|error)|singularity.*(FATAL|ERROR)|FATAL:|No space left on device|Disk quota exceeded|Status[[:space:]]+(FAILED|FAIL)|exit[ _-]?code([=:]|[[:space:]])+[1-9][0-9]*|Traceback|command not found)'
completion_pattern='(Job completed|Job finished|Finished successfully|normal completion|All done|Done\.?$|PILOT DONE|WORKFLOW DONE|Pipeline completed|Analysis completed)'
start_pattern='(Job started|Submitted batch job|SLURM_JOB_ID|Job ID:|host=.*job=[0-9]+|(^|[[:space:]])job=[0-9]+)'
status_file="reports/workflow_status.tsv"
status_file_mtime=0
status_job_ids=""

if [[ -r "$status_file" ]]; then
    status_file_mtime="$(stat -c '%Y' "$status_file" 2>/dev/null || printf '0')"
    status_job_ids="$(
        awk -F '\t' '
            NR == 1 {
                for (i = 1; i <= NF; i++) idx[tolower($i)] = i
                next
            }
            {
                job = (("job_id" in idx) ? $(idx["job_id"]) : "")
                if (job ~ /^[0-9]+$/) print job
            }
        ' "$status_file" | sort -u || true
    )"
fi

failure_evidence="$(
    while IFS= read -r file; do
        [[ -n "$file" && -r "$file" ]] || continue
        match="$(tail -n 240 "$file" 2>/dev/null | grep -Eim 1 -- "$failure_pattern" || true)"
        [[ -n "$match" ]] && printf '%s: %s\n' "$file" "$match"
    done <<< "$err_files" | head -n 8 || true
)"

install_log_files="$(printf '%s\n' "$log_files" | grep -Ei '(^|/)(codex_)?install|program-onboarding|onboard|conda|micromamba|singularity|nextflow' || true)"
install_failure_evidence="$(
    while IFS= read -r file; do
        [[ -n "$file" && -r "$file" ]] || continue
        match="$(tail -n 320 "$file" 2>/dev/null | grep -Eim 1 -- "$install_failure_pattern" || true)"
        [[ -n "$match" ]] && printf '%s: %s\n' "$file" "$match"
    done <<< "$install_log_files" | head -n 8 || true
)"

completion_evidence="$(
    while IFS= read -r file; do
        [[ -n "$file" && -r "$file" ]] || continue
        match="$(tail -n 240 "$file" 2>/dev/null | grep -Eim 1 -- "$completion_pattern" || true)"
        [[ -n "$match" ]] && printf '%s: %s\n' "$file" "$match"
    done <<< "$out_log_files" | head -n 8 || true
)"

start_evidence="$(
    while IFS= read -r file; do
        [[ -n "$file" && -r "$file" ]] || continue
        match="$(tail -n 120 "$file" 2>/dev/null | grep -Eim 1 -- "$start_pattern" || true)"
        [[ -n "$match" ]] && printf '%s: %s\n' "$file" "$match"
    done <<< "$log_files" | head -n 8 || true
)"

job_ids="$(
    while IFS= read -r file; do
        [[ -n "$file" ]] || continue
        base="$(basename "$file")"
        if [[ "$base" =~ ^([0-9]{4,})([_\.-]|$) ]]; then
            printf '%s\n' "${BASH_REMATCH[1]}"
        elif [[ "$base" =~ (^|[^[:alnum:]])(job|slurm)[_-]?([0-9]{4,})([^0-9]|$) ]]; then
            printf '%s\n' "${BASH_REMATCH[3]}"
        fi
        [[ -r "$file" ]] || continue
        tail -n 120 "$file" 2>/dev/null \
            | grep -Eio 'Job ID: *[0-9]+|Submitted batch job [0-9]+|SLURM_JOB_ID[=: ]+[0-9]+' \
            | grep -Eo '[0-9]{4,}' || true
    done <<< "$log_files" | sort -u
)"
job_ids="$(printf '%s\n%s\n' "$job_ids" "$status_job_ids" | sed '/^$/d' | sort -u)"

queue_evidence=""
sacct_evidence=""
if [[ "$check_queue" -eq 1 && -n "$job_ids" ]]; then
    ids_csv="$(printf '%s\n' "$job_ids" | paste -sd, -)"
    if command -v squeue >/dev/null 2>&1; then
        queue_evidence="$(squeue -j "$ids_csv" -h -o '%i|%T|%M|%R' 2>/dev/null || true)"
    fi
    if command -v sacct >/dev/null 2>&1; then
        sacct_evidence="$(
            while IFS= read -r jid; do
                [[ -n "$jid" ]] || continue
                sacct -j "$jid" --format=JobID,State,ExitCode,MaxRSS,Elapsed -n -P 2>/dev/null || true
            done <<< "$job_ids"
        )"
    fi
fi

sacct_failed_evidence="$(printf '%s\n' "$sacct_evidence" | grep -Ei '(^|[|])(FAILED|TIMEOUT|OUT_OF_MEMORY|NODE_FAIL|CANCELLED)([|]|$)' | head -n 5 || true)"
queue_active_evidence="$(printf '%s\n' "$queue_evidence" | grep -Ei '[|](PENDING|RUNNING|CONFIGURING|COMPLETING)[|]' | head -n 5 || true)"

incomplete_run_evidence="$(
    while IFS= read -r file; do
        [[ -n "$file" && -r "$file" ]] || continue
        [[ "$file" =~ \.(out|log)$ ]] || continue
        tail_block="$(tail -n 240 "$file" 2>/dev/null || true)"
        printf '%s\n' "$tail_block" | grep -Eiq -- "$completion_pattern|$failure_pattern" && continue
        match="$(printf '%s\n' "$tail_block" | grep -Eim 1 -- "$start_pattern" || true)"
        [[ -n "$match" ]] && { printf '%s: %s\n' "$file" "$match"; break; }
    done < <(recent_files 12 logs reports)
)"

validation_evidence=""
latest_status_row=""
status_running_evidence=""
status_install_resolved_evidence=""
if [[ -r "$status_file" ]]; then
    latest_status_row="$(awk -F '\t' 'NR > 1 && NF >= 9 && $1 != "" { row=$0 } END { print row }' "$status_file" 2>/dev/null || true)"
    if [[ -n "$latest_status_row" ]]; then
        IFS=$'\t' read -r status_stage status_value status_evidence_path status_job_id status_exit_code status_input_path status_output_path status_next_action status_updated_time status_extra <<< "$latest_status_row"
        stage_lc="$(printf '%s\n' "$status_stage" | tr '[:upper:]' '[:lower:]')"
        status_lc="$(printf '%s\n' "$status_value" | tr '[:upper:]' '[:lower:]')"
        evidence_ok=0
        if [[ "$status_evidence_path" != "NA" && -e "$status_evidence_path" ]]; then
            evidence_ok=1
        fi
        if [[ "$status_output_path" != "NA" && -e "$status_output_path" ]]; then
            evidence_ok=1
        fi
        if [[ "$stage_lc" == "analysis_ready" && "$status_lc" =~ ^(validated|accepted|pass|passed|analysis_ready)$ && "$evidence_ok" -eq 1 ]]; then
            validation_evidence="$latest_status_row"
        fi
    fi

    status_running_evidence="$(
        awk -F '\t' '
            NR == 1 {
                for (i = 1; i <= NF; i++) idx[tolower($i)] = i
                next
            }
            {
                stage = (("stage" in idx) ? $(idx["stage"]) : "")
                status = (("status" in idx) ? $(idx["status"]) : "")
                job = (("job_id" in idx) ? $(idx["job_id"]) : "")
                finished = (("finished" in idx) ? $(idx["finished"]) : "")
                st = tolower(stage)
                ss = tolower(status)
                ff = tolower(finished)
                if (job ~ /^[0-9]+$/ && (ss ~ /(pending|running|queued|submitted)/ || st ~ /(queued_or_running|pilot|run)/) && (ff == "" || ff == "-" || ss ~ /(pending|running|queued|submitted)/)) {
                    print "reports/workflow_status.tsv: " $0
                    exit
                }
            }
        ' "$status_file" 2>/dev/null || true
    )"

    status_install_resolved_evidence="$(
        awk -F '\t' '
            NR == 1 {
                for (i = 1; i <= NF; i++) idx[tolower($i)] = i
                next
            }
            {
                stage = (("stage" in idx) ? $(idx["stage"]) : "")
                status = (("status" in idx) ? $(idx["status"]) : "")
                st = tolower(stage)
                ss = tolower(status)
                if (st ~ /(install|configure)/ && ss ~ /(completed|done|success|abandoned)/) {
                    print "reports/workflow_status.tsv: " $0
                }
            }
        ' "$status_file" 2>/dev/null | head -n 5 || true
    )"
fi

if [[ -n "$install_failure_evidence" && -n "$status_install_resolved_evidence" && "$status_file_mtime" -gt 0 ]]; then
    install_failure_evidence="$(
        while IFS= read -r line; do
            [[ -n "$line" ]] || continue
            evidence_file="${line%%:*}"
            if [[ -e "$evidence_file" ]]; then
                evidence_mtime="$(stat -c '%Y' "$evidence_file" 2>/dev/null || printf '0')"
                if [[ "$evidence_mtime" =~ ^[0-9]+$ && "$evidence_mtime" -lt "$status_file_mtime" ]]; then
                    continue
                fi
            fi
            printf '%s\n' "$line"
        done <<< "$install_failure_evidence" | head -n 8 || true
    )"
fi

completion_mtime="$(evidence_lines_max_mtime "$completion_evidence")"
success_cutoff=0
if [[ "$completion_mtime" =~ ^[0-9]+$ && "$completion_mtime" -gt "$success_cutoff" ]]; then
    success_cutoff="$completion_mtime"
fi
if [[ -n "$validation_evidence" && "$status_file_mtime" =~ ^[0-9]+$ && "$status_file_mtime" -gt "$success_cutoff" ]]; then
    success_cutoff="$status_file_mtime"
fi
if [[ "$success_cutoff" -gt 0 ]]; then
    failure_evidence="$(filter_evidence_after_mtime "$success_cutoff" "$failure_evidence")"
    install_failure_evidence="$(filter_evidence_after_mtime "$success_cutoff" "$install_failure_evidence")"
fi

candidate_stage=()
candidate_status=()
candidate_evidence=()
candidate_next=()

add_candidate() {
    candidate_stage+=("$1")
    candidate_status+=("$2")
    candidate_evidence+=("$3")
    candidate_next+=("$4")
}

first_input="$(printf '%s\n' "$input_files" | first_nonempty)"
first_output="$(printf '%s\n' "$result_files" | first_nonempty)"
first_job_id="$(printf '%s\n' "$job_ids" | first_nonempty)"
first_exit_code="$(printf '%s\n' "$sacct_evidence" | awk -F '|' 'NF >= 3 && $3 != "" { print $3; exit }')"
[[ -n "$first_job_id" ]] || first_job_id="NA"
[[ -n "$first_exit_code" ]] || first_exit_code="NA"
[[ -n "$first_input" ]] || first_input="NA"
[[ -n "$first_output" ]] || first_output="NA"

check_scan_limits "${scan_dirs[@]}"

active_candidate_added=0
if [[ -n "$queue_active_evidence" ]]; then
    evidence="$(printf '%s\n' "$queue_active_evidence" | first_nonempty)"
    add_candidate "Queued_or_running" "Running" "$evidence" "Monitor with squeue/sacct and bounded log tails; do not edit or resubmit active work."
    active_candidate_added=1
elif [[ -n "$status_running_evidence" ]]; then
    evidence="$(printf '%s\n' "$status_running_evidence" | first_nonempty)"
    add_candidate "Queued_or_running" "Needs_monitoring" "$evidence" "Monitor the recorded job with squeue/sacct and bounded log tails; do not edit or resubmit active work."
    active_candidate_added=1
elif [[ -n "$incomplete_run_evidence" && -n "$job_ids" ]]; then
    if [[ "$check_queue" -eq 1 && -z "$queue_evidence" && -z "$sacct_evidence" ]]; then
        add_candidate "Queued_or_running" "Queue_state_unknown" "$incomplete_run_evidence" "Queue/accounting evidence is unavailable; retry squeue/sacct or inspect the newest log before validation or edits."
    else
        add_candidate "Queued_or_running" "Needs_monitoring" "$incomplete_run_evidence" "Check squeue/sacct for the discovered job ID before changing scripts."
    fi
    active_candidate_added=1
elif [[ -n "$start_evidence" && -z "$completion_evidence" && -z "$failure_evidence" && -z "$install_failure_evidence" && -n "$job_ids" ]]; then
    evidence="$(printf '%s\n' "$start_evidence" | first_nonempty)"
    add_candidate "Queued_or_running" "Needs_monitoring" "$evidence" "Check squeue/sacct for the discovered job ID before changing scripts."
    active_candidate_added=1
fi

if [[ -n "$failure_evidence" || -n "$sacct_failed_evidence" || -n "$install_failure_evidence" ]]; then
    evidence="$(printf '%s\n%s\n%s\n' "$sacct_failed_evidence" "$failure_evidence" "$install_failure_evidence" | first_nonempty)"
    if [[ -n "$install_failure_evidence" && -z "$failure_evidence" && -z "$sacct_failed_evidence" ]]; then
        if [[ "$active_candidate_added" -eq 0 ]]; then
            add_candidate "Failed" "Needs_install_triage" "$evidence" "Triage install/onboarding log; record updated install status before running downstream scripts."
        fi
    else
        add_candidate "Failed" "Needs_triage" "$evidence" "Run scripts/slurm_failure_triage.sh on the job ID or .err log; ask before resubmission."
    fi
fi

if [[ "$result_count" -gt 0 && -n "$validation_evidence" ]]; then
    add_candidate "Analysis_ready" "Validated" "$status_file" "Proceed to plotting, reporting, or biological interpretation using validated evidence."
elif [[ "$result_count" -gt 0 && -n "$completion_evidence" && -z "$incomplete_run_evidence" ]]; then
    evidence="$(printf '%s\n' "$completion_evidence" | first_nonempty)"
    add_candidate "Complete_unvalidated" "Needs_validation" "$evidence" "Run result acceptance checks before biological interpretation."
fi

if [[ "$slurm_script_count" -gt 0 && -z "$completion_evidence" && -z "$failure_evidence" && -z "$install_failure_evidence" && -z "$incomplete_run_evidence" && -z "$status_running_evidence" && -z "$queue_active_evidence" ]]; then
    evidence="$(printf '%s\n' "$slurm_script_files" | first_nonempty)"
    add_candidate "Script_ready" "Needs_preflight" "$evidence" "Run scripts/prepare_submission.sh --script <file> with known manifest/input/output; include resource assessment; ask before sbatch."
fi

if [[ "$input_count" -gt 0 && "$script_count" -eq 0 && "$result_count" -eq 0 ]]; then
    add_candidate "Input_ready" "Needs_planning" "$first_input" "Define manifest, methods, outputs, and success criteria before writing scripts."
fi

printf '[INFO] Project: %s\n' "$project_abs"
printf '[INFO] Max_depth: %s\n' "$max_depth"
printf '[INFO] Max_files_per_dir: %s\n' "$max_files"
printf '[INFO] Check_queue: %s\n' "$check_queue"
printf '[INFO] Counts: inputs=%s scripts=%s slurm_scripts=%s logs=%s results=%s\n' \
    "$input_count" "$script_count" "$slurm_script_count" "$log_count" "$result_count"

if [[ "${#scan_warnings[@]}" -gt 0 ]]; then
    printf '[WARN] Bounded scan warnings\n'
    for warning in "${scan_warnings[@]}"; do
        printf '  - %s\n' "$warning"
    done
fi

print_block "Recent scripts" "$(recent_files 5 scripts)"
print_block "Recent logs" "$(recent_files 5 logs reports)"
print_block "Recent results/reports" "$(recent_files 5 results reports)"

if [[ "$check_queue" -eq 1 ]]; then
    print_block "Discovered job IDs" "$job_ids"
    print_block "squeue evidence" "$queue_evidence"
    print_block "sacct evidence" "$sacct_evidence"
fi

printf '[INFO] State candidates\n'
if [[ "${#candidate_stage[@]}" -eq 0 ]]; then
    printf '  - UNKNOWN | Evidence=No canonical resume state detected | Next_Action=Ask for explicit inputs, scripts, logs, or results.\n'
    primary_stage="UNKNOWN"
    primary_status="Unknown"
    primary_evidence="NA"
    primary_next="Ask for explicit inputs, scripts, logs, or results."
else
    for i in "${!candidate_stage[@]}"; do
        printf '  - %s | Status=%s | Evidence=%s | Next_Action=%s\n' \
            "${candidate_stage[$i]}" "${candidate_status[$i]}" "${candidate_evidence[$i]}" "${candidate_next[$i]}"
    done
    primary_stage="${candidate_stage[0]}"
    primary_status="${candidate_status[0]}"
    primary_evidence="${candidate_evidence[0]}"
    primary_next="${candidate_next[0]}"
fi

evidence_path="$primary_evidence"
if [[ "$evidence_path" == *:* && -e "${evidence_path%%:*}" ]]; then
    evidence_path="${evidence_path%%:*}"
fi
[[ -n "$evidence_path" ]] || evidence_path="NA"

row_job_id="$first_job_id"
if [[ "$row_job_id" == "NA" && "$primary_evidence" =~ (Job[[:space:]]ID:|Submitted[[:space:]]batch[[:space:]]job|SLURM_JOB_ID|job=)[^0-9]*([0-9]{4,}) ]]; then
    row_job_id="${BASH_REMATCH[2]}"
fi

printf '[INFO] Recommended_minimal_next_action: %s\n' "$primary_next"
printf '[INFO] Suggested reports/workflow_status.tsv row (not written)\n'
printf 'Stage\tStatus\tEvidence_Path\tJob_ID\tExit_Code\tInput_Path\tOutput_Path\tNext_Action\tUpdated_Time\n'
printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$primary_stage" "$primary_status" "$evidence_path" "$row_job_id" "$first_exit_code" \
    "$first_input" "$first_output" "$primary_next" "$(date +%Y-%m-%dT%H:%M:%S%z)"
