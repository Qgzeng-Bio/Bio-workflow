#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage:
  scripts/slurm_preflight.sh --script <slurm_script> [--mode normal|debug|fat|fat2|high]

Read-only SLURM script preflight for qgzeng bio-workflow rules.
Reports PASS/WARN/FAIL and exits 1 when any FAIL is found.
USAGE
}

script=""
mode=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --script)
            [[ $# -ge 2 ]] || { echo "FAIL | --script requires a value" >&2; exit 1; }
            script="$2"
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
    echo "FAIL | Missing --script <slurm_script>" >&2
    usage >&2
    exit 1
fi

case "$mode" in
    ""|normal|debug|fat|fat2|high) ;;
    *)
        echo "FAIL | Unsupported --mode: $mode" >&2
        exit 1
        ;;
esac

if [[ ! -e "$script" ]]; then
    echo "FAIL | Script does not exist: $script" >&2
    exit 1
fi

if [[ ! -r "$script" ]]; then
    echo "FAIL | Script is not readable: $script" >&2
    exit 1
fi

pass_count=0
warn_count=0
fail_count=0

pass() {
    printf 'PASS | %s\n' "$1"
    pass_count=$((pass_count + 1))
}

warn() {
    printf 'WARN | %s\n' "$1"
    warn_count=$((warn_count + 1))
}

fail() {
    printf 'FAIL | %s\n' "$1"
    fail_count=$((fail_count + 1))
}

strip_inline_comment() {
    local line="$1"
    printf '%s\n' "${line%%#*}"
}

grep_active() {
    local pattern="$1"
    awk 'BEGIN { IGNORECASE=1 } /^[[:space:]]*#/ { next } { print }' "$script" \
        | grep -Eiq -- "$pattern"
}

first_active_match() {
    local pattern="$1"
    awk '/^[[:space:]]*#/ { next } { print }' "$script" | grep -Ei -m 1 -- "$pattern" || true
}

sbatch_has() {
    local pattern="$1"
    grep -Eiq "^[[:space:]]*#SBATCH[[:space:]].*$pattern" "$script"
}

infer_partition() {
    local line rest token next
    local -a fields
    while IFS= read -r line; do
        [[ "$line" =~ ^[[:space:]]*#SBATCH[[:space:]]+ ]] || continue
        rest="${line#*#SBATCH}"
        # shellcheck disable=SC2206
        fields=($rest)
        for ((i = 0; i < ${#fields[@]}; i++)); do
            token="${fields[$i]}"
            next="${fields[$((i + 1))]:-}"
            case "$token" in
                --partition=*) printf '%s\n' "${token#--partition=}"; return 0 ;;
                -p*) [[ "$token" != "-p" ]] && { printf '%s\n' "${token#-p}"; return 0; } ;;
                --partition|-p) [[ -n "$next" ]] && { printf '%s\n' "$next"; return 0; } ;;
            esac
        done
    done < "$script"
    return 1
}

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

has_sbatch_value() {
    local long="$1"
    local short="$2"
    [[ -n "$(get_sbatch_value "$long" "$short")" ]]
}

check_log_path() {
    local label="$1"
    local value="$2"
    if [[ -z "$value" ]]; then
        fail "Missing #SBATCH $label directive"
        return
    fi
    if [[ "$value" == /* ]]; then
        pass "#SBATCH $label uses an absolute path: $value"
    else
        fail "#SBATCH $label must use an absolute path, found: $value"
    fi
    if [[ "$value" == *"%j"* || "$value" == *"%x"* ]]; then
        pass "#SBATCH $label contains %j or %x"
    else
        fail "#SBATCH $label should include %j or %x to avoid log collisions: $value"
    fi
}

check_strict_mode() {
    local line clean has_e=0 has_u=0 has_pipe=0
    while IFS= read -r line; do
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        clean="$(strip_inline_comment "$line")"
        [[ "$clean" =~ (^|[[:space:];])set[[:space:]]+ ]] || continue
        printf '%s\n' "$clean" | grep -Eq -- '-[^[:space:];]*e' && has_e=1
        printf '%s\n' "$clean" | grep -Eq -- '-[^[:space:];]*u' && has_u=1
        case "$clean" in
            *pipefail*) has_pipe=1 ;;
        esac
    done < "$script"

    if [[ "$has_e" -eq 1 && "$has_u" -eq 1 && "$has_pipe" -eq 1 ]]; then
        pass "Strict shell mode is present: set -e, set -u, and pipefail"
    else
        fail "Strict shell mode missing or incomplete; use set -euo pipefail or equivalent"
    fi
}

check_pipefail_preview_pipelines() {
    local match
    match="$(
        awk '/^[[:space:]]*#/ { next } { print }' "$script" \
            | grep -Ei '\|[[:space:]]*head([[:space:]-]|$)' \
            | grep -Eiv '(\|\|[[:space:]]*true|ALLOW_PIPEFAIL_HEAD)' \
            | head -n 1 || true
    )"
    if [[ -n "$match" ]]; then
        fail "Unguarded pipe to head can fail under pipefail: $match"
    else
        pass "No unguarded pipe-to-head preview pattern"
    fi
}

check_protected_paths() {
    local path match write_pattern
    write_pattern='(^|[[:space:];|])(cp|mv|rsync|mkdir|touch|tee|wget|curl|ln|pigz|gzip|bgzip)([[:space:]]|$)|(^|[^<])>>?|--out([^[:alnum:]_-]|$)|--output([^[:alnum:]_-]|$)|--output=|-o[[:space:]]+|-O[[:space:]]+|--prefix|--dir|--tmp|--temp'
    for path in "/data9/home/qgzeng/data/" "/data9/home/qgzeng/tools/"; do
        match="$(first_active_match "$path" || true)"
        if [[ -z "$match" ]]; then
            pass "No active reference to protected path: $path"
            continue
        fi
        if printf '%s\n' "$match" | grep -Eiq -- "$write_pattern"; then
            fail "Protected path appears in a write-like command: $path"
        else
            warn "Protected path is referenced; verify it is read-only input: $path"
        fi
    done
}

check_kmeria_static() {
    if ! grep_active '(^|[[:space:]/])(kmeria|kmc|gemma|plink)([[:space:]]|$)|kmeria_wrapper\.pl|kctm_job\.sh'; then
        pass "No KMERIA-specific workflow pattern detected"
        return
    fi

    warn "KMERIA workflow detected; confirm count output format is compatible with matrix construction before scaling"
    if grep_active 'kmeria_wrapper\.pl' && grep_active '(^|[[:space:]])(--step[[:space:]]+all|--step=all)([[:space:]]|$)'; then
        warn "KMERIA wrapper --step all detected; inspect generation output and treat IMPORTANT NOTE format warnings as blockers"
    fi
    if grep_active 'kctm_job\.sh|run_stage[[:space:]]+kctm|(^|[[:space:]/])kctm([[:space:]]|$)'; then
        warn "KMERIA kctm/matrix stage detected; do not run it after incompatible count-output warnings"
    fi
}

big_command_pattern='(^|[[:space:]/])(minimap2|bwa|hisat2|STAR|samtools[[:space:]]+sort|hifiasm|orthofinder|braker\.pl|braker|maker|EDTA\.pl|RepeatModeler|RepeatMasker|syri|plotsr|nucmer|delta-filter|show-coords|juicer|3d-dna|run-asm-pipeline|busco|quast|gatk|bcftools|fastp|featureCounts|diamond|blastn|blastp|hmmsearch|hmmscan|cmscan|PanGenie|kmeria)([[:space:]]|$)'

if [[ -z "$mode" ]]; then
    mode="$(infer_partition || true)"
    [[ -n "$mode" ]] || mode="normal"
fi

printf '[INFO] SLURM preflight\n'
printf '[INFO] Script: %s\n' "$script"
printf '[INFO] Mode: %s\n' "$mode"

if grep -Eiq '^[[:space:]]*#SBATCH[[:space:]]+.*(--time(=|[[:space:]])|-t([[:space:]=]|$))' "$script"; then
    if grep -Eq '^[[:space:]]*#.*ALLOW_TIME_DIRECTIVE' "$script"; then
        pass "#SBATCH --time is present with ALLOW_TIME_DIRECTIVE comment"
    elif [[ "$mode" == "debug" ]]; then
        warn "#SBATCH --time is present in debug mode; acceptable only for tiny tests"
    else
        fail "#SBATCH --time is present in $mode mode; qgzeng rule is no default walltime"
    fi
else
    pass "No #SBATCH --time directive"
fi

check_log_path "--output" "$(get_sbatch_value "--output" "-o" || true)"
check_log_path "--error" "$(get_sbatch_value "--error" "-e" || true)"

array_value="$(get_sbatch_value "--array" "-a" || true)"
if [[ -z "$array_value" ]]; then
    pass "No #SBATCH --array directive"
elif [[ "$array_value" =~ %[0-9]+$ ]]; then
    pass "Array concurrency cap detected: $array_value"
else
    fail "Array directive lacks a %N concurrency cap: $array_value"
fi

check_strict_mode
check_pipefail_preview_pipelines

if grep_active '(^|[[:space:];])rm[[:space:]]+([^#;]*[[:space:]])?-[[:alnum:]]*r[[:alnum:]]*f|(^|[[:space:];])rm[[:space:]]+([^#;]*[[:space:]])?-[[:alnum:]]*f[[:alnum:]]*r'; then
    fail "Destructive rm -rf pattern found"
else
    pass "No active rm -rf pattern"
fi

check_protected_paths
check_kmeria_static

if grep_active '(^|[[:space:]])(proxychains|http_proxy|https_proxy|all_proxy|HTTP_PROXY|HTTPS_PROXY|ALL_PROXY)([[:space:]=]|$)'; then
    warn "External proxy pattern found; do not use proxies for raw-data downloads without confirmation"
else
    pass "No proxychains/http_proxy/https_proxy/all_proxy pattern"
fi

if sbatch_has 'admin2|--nodelist=admin2|--nodelist[[:space:]]+admin2'; then
    fail "SBATCH directive appears to target admin2/login node"
elif grep_active '(^|[[:space:];])ssh[[:space:]]+admin2([[:space:]]|$)'; then
    fail "Script contains ssh admin2; do not route compute through admin2"
elif grep_active 'admin2'; then
    warn "admin2 is mentioned in active script lines; verify no compute runs there"
else
    pass "No active admin2 compute target pattern"
fi

if grep_active "$big_command_pattern"; then
    big_match="$(first_active_match "$big_command_pattern" || true)"
    has_cpu=0
    has_mem=0
    if has_sbatch_value "--cpus-per-task" "-c" || has_sbatch_value "--ntasks" "-n"; then
        has_cpu=1
    fi
    if has_sbatch_value "--mem" "" || has_sbatch_value "--mem-per-cpu" ""; then
        has_mem=1
    fi
    if [[ "$has_cpu" -eq 1 && "$has_mem" -eq 1 ]]; then
        pass "Large-compute command has SLURM CPU and memory declarations"
    else
        fail "Large-compute command lacks SLURM CPU or memory declaration: $big_match"
    fi
else
    pass "No known large-compute command pattern detected"
fi

printf '[INFO] Summary: PASS=%d WARN=%d FAIL=%d\n' "$pass_count" "$warn_count" "$fail_count"

if [[ "$fail_count" -gt 0 ]]; then
    exit 1
fi
exit 0
