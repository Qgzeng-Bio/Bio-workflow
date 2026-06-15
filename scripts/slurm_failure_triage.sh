#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage:
  scripts/slurm_failure_triage.sh (--jobid <id> | --err <file>) [--out <file>] [--logs-dir <dir>]

Read-only SLURM failure triage for qgzeng bio-workflow rules.
It may read sacct, .err, and .out evidence, then classify the failure and print the
smallest next fix. It never edits scripts, deletes outputs, or resubmits jobs.

Exit code:
  1  recognized failure type found
  2  failure evidence found but not classified
  0  WARN/no failure evidence only
USAGE
}

jobid=""
err_file=""
out_file=""
logs_dir=""
err_given=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --jobid)
            [[ $# -ge 2 ]] || { echo "FAIL | --jobid requires a value" >&2; exit 1; }
            jobid="$2"
            shift 2
            ;;
        --err)
            [[ $# -ge 2 ]] || { echo "FAIL | --err requires a value" >&2; exit 1; }
            err_file="$2"
            err_given=1
            shift 2
            ;;
        --out)
            [[ $# -ge 2 ]] || { echo "FAIL | --out requires a value" >&2; exit 1; }
            out_file="$2"
            shift 2
            ;;
        --logs-dir)
            [[ $# -ge 2 ]] || { echo "FAIL | --logs-dir requires a value" >&2; exit 1; }
            logs_dir="$2"
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

if [[ -z "$jobid" && "$err_given" -eq 0 ]]; then
    echo "FAIL | Provide exactly one of --jobid <id> or --err <file>" >&2
    usage >&2
    exit 1
fi

if [[ -n "$jobid" && "$err_given" -eq 1 ]]; then
    echo "FAIL | Use --jobid or --err, not both" >&2
    exit 1
fi

if [[ -n "$jobid" && ! "$jobid" =~ ^[0-9]+([_.][0-9]+)?$ ]]; then
    echo "FAIL | --jobid should look like a SLURM job ID: $jobid" >&2
    exit 1
fi

if [[ "$err_given" -eq 1 ]]; then
    [[ -e "$err_file" ]] || { echo "FAIL | .err file does not exist: $err_file" >&2; exit 1; }
    [[ -r "$err_file" ]] || { echo "FAIL | .err file is not readable: $err_file" >&2; exit 1; }
fi

if [[ -n "$out_file" ]]; then
    [[ -e "$out_file" ]] || { echo "FAIL | .out file does not exist: $out_file" >&2; exit 1; }
    [[ -r "$out_file" ]] || { echo "FAIL | .out file is not readable: $out_file" >&2; exit 1; }
fi

if [[ -n "$logs_dir" ]]; then
    [[ -d "$logs_dir" ]] || { echo "FAIL | --logs-dir does not exist: $logs_dir" >&2; exit 1; }
fi

sacct_output=""
if [[ -n "$jobid" ]]; then
    if command -v sacct >/dev/null 2>&1; then
        sacct_output="$(sacct -j "$jobid" --format=JobID,State,ExitCode,MaxRSS,Elapsed -P 2>&1 || true)"
    else
        sacct_output="WARN | sacct not found in PATH"
    fi
fi

if [[ -n "$jobid" && -n "$logs_dir" ]]; then
    if [[ -z "$err_file" ]]; then
        err_file="$(find "$logs_dir" -maxdepth 3 -type f \( -name "${jobid}_*.err" -o -name "*${jobid}*.err" \) -print 2>/dev/null | sort | tail -n 1 || true)"
    fi
    if [[ -z "$out_file" ]]; then
        out_file="$(find "$logs_dir" -maxdepth 3 -type f \( -name "${jobid}_*.out" -o -name "*${jobid}*.out" -o -name "*${jobid}*.log" \) -print 2>/dev/null | sort | tail -n 1 || true)"
    fi
fi

err_tail=""
out_tail=""
if [[ -n "$err_file" && -r "$err_file" ]]; then
    err_tail="$(tail -n 320 "$err_file" 2>/dev/null || true)"
fi
if [[ -n "$out_file" && -r "$out_file" ]]; then
    out_tail="$(tail -n 320 "$out_file" 2>/dev/null || true)"
fi

combined="$(
    printf '[sacct]\n%s\n' "$sacct_output"
    printf '[err:%s]\n%s\n' "${err_file:-NA}" "$err_tail"
    printf '[out:%s]\n%s\n' "${out_file:-NA}" "$out_tail"
)"
classification_text="$(
    printf '%s\n' "$sacct_output"
    printf '%s\n' "$err_tail"
    printf '%s\n' "$out_tail"
)"

failure_type="UNKNOWN"
severity="UNKNOWN"
evidence="No matching failure pattern found"
minimal_fix="Read the full .err/.out and script context; classify manually before changing resources or resubmitting."
unknown_failure=0

classify_if_match() {
    local type="$1"
    local pattern="$2"
    local fix="$3"
    local match
    if [[ "$failure_type" != "UNKNOWN" ]]; then
        return 0
    fi
    match="$(printf '%s\n' "$classification_text" | grep -Eim 1 -- "$pattern" || true)"
    if [[ -n "$match" ]]; then
        failure_type="$type"
        severity="FAIL"
        evidence="$match"
        minimal_fix="$fix"
    fi
}

classify_if_match "OOM" \
    '(OUT_OF_MEMORY|Out Of Memory|oom-kill|oom_kill|Killed process|Cannot allocate memory|exceeded memory)' \
    "Compare MaxRSS to requested memory, reduce array concurrency if needed, and ask before increasing --mem or resubmitting."

classify_if_match "TIMEOUT" \
    '(TIMEOUT|DUE TO TIME LIMIT|time limit)' \
    "Treat walltime as a script/resource-policy issue; remove or adjust #SBATCH --time only with justification and do not wrap long bioinformatics commands with shell timeout."

classify_if_match "DISK_FULL" \
    '(No space left on device|Disk quota exceeded|quota exceeded|write failed|Input/output error)' \
    "Check project filesystem and tmp/output locations; ask before deleting, moving, or overwriting outputs."

classify_if_match "PERMISSION" \
    '(Permission denied|Operation not permitted|Read-only file system|cannot create.*Permission)' \
    "Check write target, protected directories, and executable permissions; do not write into protected raw-data/tool paths without confirmation."

classify_if_match "ENV_TOOL" \
    '(command not found|No module named|ModuleNotFoundError|ImportError|cannot open shared object file|library .*not found|conda: command not found|singularity: command not found|Rscript: command not found|exit code 127)' \
    "Fix environment activation, module/container path, or tool discovery; record command -v and tool version before rerun."

classify_if_match "MISSING_INPUT" \
    '(No such file or directory|cannot stat|cannot access|failed to open|No input|Input file .*not found|No such file$)' \
    "Validate the manifest and exact input paths with small read-only checks; add fail-fast path checks before rerun."

classify_if_match "SEGFAULT" \
    '(Segmentation fault|segfault|core dumped|SIGSEGV|Bus error)' \
    "Check input integrity, tool version, and resource pressure; run a small explicit subset or version-specific diagnostic before full rerun."

classify_if_match "FORMAT_CHROMOSOME_MISMATCH" \
    '(chromosome .*not found|contig .*not found|sequence .*not found|different.*chrom|incompatible.*contig|Malformed|parse error|invalid.*format|format error|not bgzip|truncated|corrupt)' \
    "Validate file format, indexes, and chromosome names on a small explicit subset before rerunning."

classify_if_match "NETWORK_PROXY" \
    '(Could not resolve host|Name or service not known|Temporary failure in name resolution|Connection timed out|Connection refused|SSL|TLS|proxy|HTTP[^0-9]*(403|404|429|500|502|503))' \
    "Check network/source availability and avoid external proxies for raw-data downloads unless the user explicitly confirms."

if [[ "$failure_type" == "UNKNOWN" ]]; then
    unknown_match="$(printf '%s\n' "$classification_text" | grep -Eim 1 '(FAILED|CANCELLED|NonZeroExitCode|ExitCode=[1-9]|[|][1-9][0-9]*:)' || true)"
    if [[ -n "$unknown_match" ]]; then
        severity="UNKNOWN"
        unknown_failure=1
        evidence="$unknown_match"
        minimal_fix="Failure is evident but not classified by this heuristic; inspect the full logs before changing resources or resubmitting."
    else
        warn_match="$(printf '%s\n' "$classification_text" | grep -Eim 1 '(WARN|WARNING|Warning)' || true)"
        if [[ -n "$warn_match" ]]; then
            failure_type="WARN"
            severity="WARN"
            evidence="$warn_match"
            minimal_fix="Review warning context and validate outputs; do not treat warnings as success without result checks."
        fi
    fi
fi

printf '[INFO] SLURM failure triage\n'
printf '[INFO] Job_ID: %s\n' "${jobid:-NA}"
printf '[INFO] Err_File: %s\n' "${err_file:-NA}"
printf '[INFO] Out_File: %s\n' "${out_file:-NA}"
printf '[INFO] Logs_Dir: %s\n' "${logs_dir:-NA}"

if [[ -n "$sacct_output" ]]; then
    printf '[INFO] sacct\n'
    printf '%s\n' "$sacct_output" | sed 's/^/  /'
fi

if [[ -n "$err_file" && ! -r "$err_file" ]]; then
    printf '[WARN] Discovered .err is not readable: %s\n' "$err_file"
fi
if [[ -n "$out_file" && ! -r "$out_file" ]]; then
    printf '[WARN] Discovered .out is not readable: %s\n' "$out_file"
fi

printf '[RESULT] Failure_Type: %s\n' "$failure_type"
printf '[RESULT] Severity: %s\n' "$severity"
printf '[RESULT] Evidence: %s\n' "$evidence"
printf '[RESULT] Minimal_Fix: %s\n' "$minimal_fix"
printf '[NOTE] Read-only triage only; no script edits, cleanup, cancellation, or resubmission were attempted.\n'

if [[ "$severity" == "FAIL" ]]; then
    exit 1
fi
if [[ "$unknown_failure" -eq 1 ]]; then
    exit 2
fi
exit 0
