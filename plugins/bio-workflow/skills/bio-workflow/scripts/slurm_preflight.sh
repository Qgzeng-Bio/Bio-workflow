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

value_is_protected() {
    # Protected = the current user's own data/tools, plus any /data9/home/<user>/data|tools.
    local p="${1%/}" home="${HOME%/}"
    [[ "$p" == "$home/data" || "$p" == "$home/data"/* \
       || "$p" == "$home/tools" || "$p" == "$home/tools"/* ]] && return 0
    [[ "$p" =~ ^/data9/home/[^/]+/(data|tools)(/.*)?$ ]] && return 0
    return 1
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

mem_gb_from_script() {
    local cpus mem_value mem_per_cpu mem_per_cpu_gb
    cpus="$(get_sbatch_value "--cpus-per-task" "-c" || true)"
    [[ -n "$cpus" ]] || cpus="$(get_sbatch_value "--ntasks" "-n" || true)"
    mem_value="$(get_sbatch_value "--mem" "" || true)"
    mem_per_cpu="$(get_sbatch_value "--mem-per-cpu" "" || true)"
    if [[ -n "$mem_value" ]]; then
        mem_to_gb "$mem_value"
    elif [[ -n "$mem_per_cpu" && "$cpus" =~ ^[0-9]+$ ]]; then
        mem_per_cpu_gb="$(mem_to_gb "$mem_per_cpu")"
        awk -v m="$mem_per_cpu_gb" -v c="$cpus" 'BEGIN { if (m == "NA") print "NA"; else printf "%.2f\n", m * c }'
    else
        printf 'NA\n'
    fi
}

check_log_path() {
    local label="$1"
    local value="$2"
    local clean_value
    if [[ -z "$value" ]]; then
        fail "Missing #SBATCH $label directive"
        return
    fi
    clean_value="${value%\"}"
    clean_value="${clean_value#\"}"
    clean_value="${clean_value%\'}"
    clean_value="${clean_value#\'}"
    if value_is_protected "$clean_value"; then
        fail "#SBATCH $label writes to protected path: $clean_value"
    elif [[ "$clean_value" == /* ]]; then
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

check_sbatch_chdir() {
    local value clean_value
    value="$(get_sbatch_value "--chdir" "-D" || true)"
    if [[ -z "$value" ]]; then
        pass "No #SBATCH --chdir directive"
        return
    fi
    clean_value="${value%\"}"
    clean_value="${clean_value#\"}"
    clean_value="${clean_value%\'}"
    clean_value="${clean_value#\'}"
    if value_is_protected "$clean_value"; then
        fail "#SBATCH --chdir targets protected path: $clean_value"
    else
        pass "#SBATCH --chdir does not target a protected path: $clean_value"
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
    local refs home_esc unexp core cb write_target
    home_esc="$(printf '%s' "${HOME%/}" | sed -E 's/[][(){}.^$*+?|\\]/\\&/g')"
    # A protected data/tools dir = the current user's ~/data|tools, ANY account's
    # /data9/home/<user>/data|tools, or the unexpanded ~ / $HOME / ${HOME...} forms
    # (the shell expands those only at run time). ${HOME[^}]*} covers ${HOME},
    # ${HOME%/}, ${HOME:-x}. Static scan: indirect expansion via another variable
    # cannot be caught here — slurm_preflight is a heuristic, not a sandbox.
    # ~user (named tilde, e.g. ~alice/data -> /data9/home/alice/data) as well as bare
    # ~. A quote may sit between HOME and the path, e.g. "$HOME"/data or "${HOME}"/tools.
    unexp="(~[a-zA-Z0-9_.-]*|[\$]HOME|[\$][{]HOME[^}]*[}])[\"']?/(data|tools)"
    core="(/data9/home/[^/]+/(data|tools)|${home_esc}/(data|tools)|${unexp})"
    # core + a name boundary (end or a non-name char). Excludes alnum _ . - so
    # ".../datax", ".../data-backup", "~/tools-v2" do NOT match value_is_protected.
    cb="${core}(\$|[^[:alnum:]_.-])"
    # FAIL only when a protected path is itself the WRITE/DELETE target; a protected
    # path used as a read-only INPUT (e.g. --input ~/data/ref.fa --output results/x)
    # stays a WARN. This is a line-level heuristic — the authoritative blocks on
    # protected OUTPUT targets are the structured gates on #SBATCH
    # --output/--error/--chdir, prepare_submission --output and submit_and_log
    # --record. Write-target signals:
    #   - redirection or a write-option (-o/--output/--prefix/...) pointing AT it
    #   - a create/modify/delete/download/compress command naming it as an argument
    #     (rm/rmdir/shred/unlink/mv/mkdir/touch/tee/wget/curl/pigz/gzip/bgzip/bzip2/xz)
    #   - cp/rsync/install/ln whose final (target) argument is it
    write_target="(>>?[[:space:]]*[\"']?${cb}|(-o|-O|-t|--output|--out|--target-directory|--prefix|--dir|--tmp|--temp)(=|[[:space:]]+)[\"']?${cb}|(^|[[:space:];|&])[[:space:]]*(rm|rmdir|shred|unlink|mv|mkdir|touch|tee|wget|curl|pigz|gzip|bgzip|bzip2|xz)([[:space:]][^;|&]*)?[[:space:]][\"']?${cb}|(^|[[:space:];|&])[[:space:]]*(cp|rsync|install|ln)[[:space:]][^;|&]*[[:space:]][\"']?${core}(/[^[:space:]\"';|&]*)?[\"']?([[:space:]]+-[^[:space:]]+)*[[:space:]]*(\$|[;|&]))"
    # consider EVERY active reference; strip an inline " # comment" tail first so a
    # protected write target sitting right before a comment is not hidden from the
    # scan. The " +#" guard leaves ${HOME#...}/URL-fragment '#' (no leading space) intact.
    refs="$(awk '/^[[:space:]]*#/ { next } { sub(/[[:space:]]+#.*$/, ""); print }' "$script" | grep -E -- "$cb" || true)"
    if [[ -z "$refs" ]]; then
        pass "No active reference to a protected data/tools path (own or any /data9/home/*/data|tools)"
        return
    fi
    if printf '%s\n' "$refs" | grep -Eq -- "$write_target"; then
        fail "Protected data/tools path is a write/delete target (own or another account)"
    else
        warn "Protected data/tools path is referenced as a read-only input; verify it is not a write target"
    fi
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

check_conda_activation() {
    # Only the in-shell `... activate <env>` form is risky. `conda run -n` /
    # `micromamba run -n` resolve the env themselves and do not rely on PATH.
    if ! grep_active '(^|[[:space:];&|])(conda|micromamba|mamba)[[:space:]]+activate([[:space:]]|$)'; then
        pass "No in-shell conda/micromamba activate detected"
        return
    fi

    # Explicit waiver, aligned with ALLOW_TIME_DIRECTIVE: still emit a downgraded
    # WARN so the bypass leaves an auditable trace instead of a silent pass.
    if grep -Eq '^[[:space:]]*#.*ALLOW_NO_PATH_GUARD' "$script"; then
        warn "conda activate present with ALLOW_NO_PATH_GUARD marker; verify PATH cannot be shadowed by an externally exported env bin (sbatch --export=ALL pollution)"
        return
    fi

    # Per-activation, ORDER-SENSITIVE analysis (codex review P2). The risk is real
    # only when, inside the block opened by a `conda activate` (until the next
    # activation or EOF), a PATH-resolved python runs BEFORE the env bin is pinned
    # to the front of PATH. So an earlier guarded env must not mask a later
    # unguarded one (P2-A), and a guard written after the first python is too late
    # (P2-B). Absolute-path python and `conda run -n` do not rely on PATH and are
    # ignored. Worst block wins: BAD > UNGUARDED > NOSELF > OK.
    local verdict
    verdict="$(awk '
        BEGIN { IGNORECASE = 1 }
        function close_block() {
            if (!inblk) return
            if (!guard) unguarded = 1
            else if (!self) noself = 1
        }
        /^[[:space:]]*#/ { next }
        {
            if ($0 ~ /(^|[;&|]|[[:space:]])(conda|micromamba|mamba)[[:space:]]+activate([[:space:]]|$)/) {
                close_block(); any = 1; inblk = 1; guard = 0; self = 0; next
            }
            if (!inblk) next
            if ($0 ~ /export[[:space:]]+PATH=["'\'']?[$][{]?CONDA_PREFIX[}]?\/bin:[$][{]?PATH[}]?/) guard = 1
            if ($0 ~ /export[[:space:]]+PATH=["'\'']?[^"'\'' ]*\/envs\/[^\/"'\'' ]+\/bin:[$][{]?PATH[}]?/) guard = 1
            if ($0 ~ /command[[:space:]]+-v[[:space:]]+python[0-9.]*/) self = 1
            if ($0 ~ /(^|[;&|]|[[:space:]])(which[[:space:]]+python[0-9.]*|python[0-9.]*[[:space:]]+-c[[:space:]].*import)/) self = 1
            isbare = ($0 ~ /(^|[;&|`(]|[[:space:]])(\/usr\/bin\/time[[:space:]]+-v[[:space:]]+)?python[0-9.]*([[:space:]]|$)/)
            isabs  = ($0 ~ /\/(bin|envs\/[^\/ ]+\/bin)\/python[0-9.]*([[:space:]]|$)/)
            if (isbare && !isabs && !guard) bad = 1
        }
        END {
            close_block()
            if (!any) print "NONE"
            else if (bad) print "BAD"
            else if (unguarded) print "UNGUARDED"
            else if (noself) print "NOSELF"
            else print "OK"
        }
    ' "$script")"

    case "$verdict" in
        NONE)
            pass "No in-shell conda/micromamba activate detected" ;;
        OK)
            pass "every conda activate pins \$CONDA_PREFIX/bin to PATH before any python, with a self-check" ;;
        NOSELF)
            warn "conda activate has a PATH guard but no activation self-check; add a command -v python landing assertion or a fail-fast import so a bad env fails in ~1s, not mid-run" ;;
        BAD)
            warn "a PATH-resolved python runs after a conda activate BEFORE its PATH guard; a polluted PATH (sbatch --export=ALL from an env-exporting parent) runs the wrong python and crashes on import. Put export PATH=\"\$CONDA_PREFIX/bin:\$PATH\" (and a command -v python assertion) right after each activate, ahead of any python, or mark # ALLOW_NO_PATH_GUARD if python is unused/absolute" ;;
        *)
            warn "conda activate without an explicit PATH guard; if this job resolves python/tools via PATH it can pick a foreign env's bin (sbatch --export=ALL pollution). Add export PATH=\"\$CONDA_PREFIX/bin:\$PATH\" after each activate, or mark # ALLOW_NO_PATH_GUARD" ;;
    esac
}

big_command_pattern='(^|[[:space:]/])(minimap2|bwa|hisat2|STAR|samtools[[:space:]]+sort|hifiasm|orthofinder|braker[.]pl|braker|maker|EDTA[.]pl|RepeatModeler|RepeatMasker|syri|plotsr|nucmer|delta-filter|show-coords|juicer|3d-dna|run-asm-pipeline|busco|quast|gatk|bcftools|fastp|featureCounts|diamond|blastn|blastp|hmmsearch|hmmscan|cmscan|PanGenie|kmeria)([[:space:]]|$)'
hite_command_pattern='(panHiTE[.]nf|panHiTE[.]py|HiTE[/][^[:space:]]*main[.]py|--use_HybridLTR|--use_NeuralTE|--is_denovo_nonltr)'
hite_invocation_pattern='^[[:space:]]*((/usr/bin/time[[:space:]]+-v[[:space:]]+)?python[0-9.]*[[:space:]][^#;|&]*(main[.]py|panHiTE[.]py)|nextflow[[:space:]]+run[[:space:]].*(panHiTE[.]nf|[$][{]?HITE_DIR[}]?[/]panHiTE[.]nf))'
nextflow_driver_pattern='(^|[[:space:]/])nextflow[[:space:]]+run([[:space:]]|$)'

check_cpu_forwarding() {
    local cpus
    cpus="$(get_sbatch_value "--cpus-per-task" "-c" || true)"
    if [[ -z "$cpus" ]]; then
        pass "No #SBATCH --cpus-per-task directive requiring CPU forwarding check"
        return
    fi
    if [[ ! "$cpus" =~ ^[0-9]+$ ]]; then
        warn "Cannot parse #SBATCH --cpus-per-task value for CPU forwarding check: $cpus"
        return
    fi
    if [[ "$cpus" -le 4 ]]; then
        pass "#SBATCH --cpus-per-task=$cpus is conservative; CPU forwarding warning not needed"
        return
    fi

    if grep_active '\$SLURM_CPUS_PER_TASK|\$\{SLURM_CPUS_PER_TASK(:-[0-9]+)?\}|--threads(=|[[:space:]])|--thread(=|[[:space:]])|--cpus(=|[[:space:]])|--cpu(=|[[:space:]])|--cores(=|[[:space:]])|--jobs(=|[[:space:]])|--workers(=|[[:space:]])|(^|[[:space:]])-[tp@][[:space:]]+[0-9$]'; then
        pass "High CPU request appears to be passed to a tool or SLURM_CPUS_PER_TASK"
    else
        warn "#SBATCH --cpus-per-task=$cpus but no obvious --threads/-t/-p/-@/--cpus or SLURM_CPUS_PER_TASK use; CPU may be over-requested"
    fi
}

check_serial_parallelization_hint() {
    local has_array=0
    local has_parallel=0
    local repeated_summary loop_big_count repeat_key repeat_count repeat_example

    if has_sbatch_value "--array" "-a"; then
        has_array=1
    fi
    if grep_active 'xargs[[:space:]].*-P|(^|[[:space:];|])parallel([[:space:]]|$)|(^|[[:space:];])wait([[:space:]]|$)|[[:space:]]&([[:space:]]*(#.*)?)?$'; then
        has_parallel=1
    fi

    repeated_summary="$(
        awk '
            BEGIN { IGNORECASE = 1 }
            /^[[:space:]]*#/ { next }
            function key_for(line, lower) {
                lower = tolower(line)
                if (lower ~ /^[[:space:]]*(echo|printf)[[:space:]]/) return ""
                if (lower ~ /^[[:space:]]*(if|elif|for|while|case|do|done|then|else|fi|esac|\[)([[:space:]]|$)/) return ""
                if (lower ~ /kmeria[[:space:]]+count/) return "kmeria count"
                if (lower ~ /bwa[[:space:]]+mem/) return "bwa mem"
                if (lower ~ /samtools[[:space:]]+sort/) return "samtools sort"
                if (lower ~ /featurecounts/) return "featureCounts"
                if (lower ~ /repeatmodeler/) return "RepeatModeler"
                if (lower ~ /repeatmasker/) return "RepeatMasker"
                if (lower ~ /edta[.]pl/) return "EDTA.pl"
                if (lower ~ /^[[:space:]]*nextflow[[:space:]]+run([[:space:]]|$)/) return "Nextflow run"
                if (lower ~ /^[[:space:]]*(\/usr\/bin\/time[[:space:]]+-v[[:space:]]+)?python[0-9.]*[[:space:]][^#;|&]*panhite[.]py/) return "panHiTE"
                if (lower ~ /^[[:space:]]*(\/usr\/bin\/time[[:space:]]+-v[[:space:]]+)?python[0-9.]*[[:space:]][^#;|&]*main[.]py/) return "HiTE"
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
        ' "$script"
    )"

    loop_big_count="$(
        awk -v pattern="${big_command_pattern}|${hite_invocation_pattern}" '
            BEGIN { IGNORECASE = 1; in_loop = 0; found = 0 }
            /^[[:space:]]*#/ { next }
            /^[[:space:]]*(for[[:space:]].*[[:space:]]in[[:space:]]|while[[:space:]]+read)(.*)$/ { in_loop = 1 }
            in_loop && $0 ~ pattern { found++ }
            /^[[:space:]]*done([[:space:]]|$)/ { in_loop = 0 }
            END { print found + 0 }
        ' "$script"
    )"

    if [[ "$has_array" -eq 0 && "$has_parallel" -eq 0 && -n "$repeated_summary" ]]; then
        IFS=$'\t' read -r repeat_key repeat_count repeat_example <<< "$repeated_summary"
        if [[ "$repeat_count" -ge 3 ]]; then
            warn "Repeated independent-looking $repeat_key commands run serially ($repeat_count copies); consider scripts/parallelization_audit.sh --script $script"
            return
        fi
    fi

    if [[ "$has_array" -eq 0 && "$has_parallel" -eq 0 && "$loop_big_count" -gt 0 ]]; then
        warn "Large-compute command appears inside a serial loop; consider scripts/parallelization_audit.sh --script $script"
    else
        pass "No obvious serial independent-task bottleneck detected"
    fi
}

check_resource_sanity() {
    local cpus mem_gb partition first_tool sort_m sort_m_gb sort_total_gb
    local warned=0

    cpus="$(get_sbatch_value "--cpus-per-task" "-c" || true)"
    [[ -n "$cpus" ]] || cpus="$(get_sbatch_value "--ntasks" "-n" || true)"
    cpus="${cpus:-NA}"
    mem_gb="$(mem_gb_from_script)"
    partition="$mode"

    if [[ "$cpus" =~ ^[0-9]+$ ]]; then
        if [[ "$cpus" -gt 32 ]]; then
            warn "Resource sanity: --cpus-per-task=$cpus exceeds the usual 16-32 CPU bioinformatics range; require benchmark or project-history evidence"
            warned=1
        elif [[ "$partition" == "normal" && "$cpus" -gt 16 ]]; then
            warn "Resource sanity: normal partition with $cpus CPUs is above the usual normal-node starting point; justify with scaling evidence or reduce"
            warned=1
        fi
    else
        warn "Resource sanity: cannot parse requested CPU count; resource estimate is incomplete"
        warned=1
    fi

    if [[ "$mem_gb" != "NA" ]]; then
        if awk -v m="$mem_gb" 'BEGIN { exit !(m >= 200) }'; then
            if [[ "$partition" == "normal" ]]; then
                warn "Resource sanity: requested memory is ${mem_gb}G on normal; consider fat/fat2 or justify normal-node availability"
                warned=1
            fi
        elif [[ "$partition" == "fat" || "$partition" == "fat2" ]]; then
            warn "Resource sanity: requested memory is ${mem_gb}G on $partition (<200G); justify fat/fat2 use or prefer normal"
            warned=1
        fi
    else
        warn "Resource sanity: cannot parse requested memory; resource estimate is incomplete"
        warned=1
    fi

    if grep_active '(^|[[:space:]/])(syri)([[:space:]]|$)' && [[ "$cpus" =~ ^[0-9]+$ && "$cpus" -gt 8 ]]; then
        warn "Resource sanity: SyRI has limited CPU scaling; >8 CPUs needs evidence"
        warned=1
    fi
    if grep_active '(^|[[:space:]/])(featureCounts|plotsr|quast|fastp)([[:space:]]|$)' && [[ "$cpus" =~ ^[0-9]+$ && "$cpus" -gt 16 ]]; then
        warn "Resource sanity: detected a modest-scaling tool with $cpus CPUs; check software-resource-cards.md or reduce"
        warned=1
    fi
    if grep_active '(^|[[:space:]/])(bcftools)([[:space:]]|$)' && [[ "$cpus" =~ ^[0-9]+$ && "$cpus" -gt 8 ]]; then
        warn "Resource sanity: bcftools stages are often low-to-moderate parallel; >8 CPUs needs stage-specific evidence"
        warned=1
    fi
    if grep_active "$nextflow_driver_pattern"; then
        warn "Resource sanity: Nextflow driver resources cover only the launcher; review process cpus/memory/queueSize in the -c config before submission"
        warned=1
    fi
    if grep_active '(^|[[:space:]/])(hifiasm|orthofinder|braker[.]pl|braker|maker|EDTA[.]pl|RepeatModeler|RepeatMasker|juicer|3d-dna|run-asm-pipeline|PanGenie)([[:space:]]|$)' || { grep_active "$hite_command_pattern" && ! grep_active "$nextflow_driver_pattern"; }; then
        if [[ "$mem_gb" != "NA" ]] && awk -v m="$mem_gb" 'BEGIN { exit !(m < 64) }'; then
            first_tool="$(first_active_match '(^|[[:space:]/])(hifiasm|orthofinder|braker[.]pl|braker|maker|EDTA[.]pl|RepeatModeler|RepeatMasker|juicer|3d-dna|run-asm-pipeline|PanGenie)([[:space:]]|$)' || true)"
            [[ -n "$first_tool" ]] || first_tool="$(first_active_match "$hite_command_pattern" || true)"
            warn "Resource sanity: memory-heavy workflow has only ${mem_gb}G; confirm this is a pilot/small input or increase memory: $first_tool"
            warned=1
        fi
    fi

    if grep_active 'samtools[[:space:]]+sort'; then
        sort_m="$(
            awk '
                BEGIN { IGNORECASE = 1 }
                /^[[:space:]]*#/ { next }
                /samtools[[:space:]]+sort/ {
                    for (i = 1; i <= NF; i++) {
                        if ($i == "-m" && (i + 1) <= NF) { print $(i + 1); exit }
                        if ($i ~ /^-m[0-9.]+[KMGTP]?B?$/) { sub(/^-m/, "", $i); print $i; exit }
                    }
                }
            ' "$script"
        )"
        if [[ -z "$sort_m" ]]; then
            warn "Resource sanity: samtools sort detected without explicit -m; set per-thread sort memory and match it to --mem"
            warned=1
        elif [[ "$cpus" =~ ^[0-9]+$ && "$mem_gb" != "NA" ]]; then
            sort_m_gb="$(mem_to_gb "$sort_m")"
            if [[ "$sort_m_gb" != "NA" ]]; then
                sort_total_gb="$(awk -v m="$sort_m_gb" -v c="$cpus" 'BEGIN { printf "%.2f\n", m * c }')"
                if awk -v s="$sort_total_gb" -v r="$mem_gb" 'BEGIN { exit !(s > r * 0.9) }'; then
                    warn "Resource sanity: samtools sort -m * CPUs is about ${sort_total_gb}G, leaving little headroom under --mem=${mem_gb}G"
                    warned=1
                fi
            fi
        fi
    fi

    if ! grep_active "$big_command_pattern" && ! grep_active "$hite_command_pattern" && ! grep_active "$nextflow_driver_pattern" && [[ "$cpus" =~ ^[0-9]+$ ]] && [[ "$mem_gb" != "NA" ]]; then
        if [[ "$cpus" -gt 4 ]] || awk -v m="$mem_gb" 'BEGIN { exit !(m > 32) }'; then
            warn "Resource sanity: no known large-compute tool detected but resources are cpus=$cpus mem=${mem_gb}G; justify or reduce for wrapper/summary scripts"
            warned=1
        fi
    fi

    if [[ "$warned" -eq 0 ]]; then
        pass "Resource sanity: no obvious CPU/memory/partition mismatch detected; still verify input-size and tool-specific estimates"
    fi
}

if [[ -z "$mode" ]]; then
    mode="$(infer_partition || true)"
    [[ -n "$mode" ]] || mode="normal"
fi

printf '[INFO] SLURM preflight\n'
printf '[INFO] Script: %s\n' "$script"
printf '[INFO] Mode: %s\n' "$mode"

if grep -Eiq '^[[:space:]]*#SBATCH[[:space:]]+.*(--time(=|[[:space:]])|-t([[:space:]=]|$))' "$script"; then
    if grep -Eq '^[[:space:]]*#.*ALLOW_TIME_DIRECTIVE' "$script"; then
        warn "#SBATCH --time is present with ALLOW_TIME_DIRECTIVE marker; verify explicit user confirmation and cluster-policy reason before submitting"
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
check_sbatch_chdir

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

# Catch a recursive+force rm whether the flags are combined (-rf/-fr), separated
# (-r -f), or long (--recursive --force) — the combined-only regex used to miss them.
rm_hit="$(awk '
    /^[[:space:]]*#/ { next }
    {
        cl = $0
        sub(/[[:space:]]#.*/, "", cl)   # drop an inline comment (space-#) to avoid false hits
        if (cl !~ /(^|[[:space:];&|(\/])rm([[:space:]]|$)/) next
        rec = 0; force = 0
        n = split(cl, toks, /[[:space:]]+/)
        for (i = 1; i <= n; i++) {
            t = toks[i]
            if (t == "--recursive" || t == "-r" || t == "-R") rec = 1
            else if (t == "--force" || t == "-f") force = 1
            else if (t ~ /^-[a-zA-Z]+$/) { if (t ~ /[rR]/) rec = 1; if (t ~ /f/) force = 1 }
        }
        if (rec && force) { print; exit }
    }
' "$script")"
if [[ -n "$rm_hit" ]]; then
    fail "Destructive recursive+force rm found (combined or separated flags)"
else
    pass "No active recursive+force rm pattern"
fi

check_protected_paths
check_kmeria_static
check_conda_activation

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

check_cpu_forwarding
check_serial_parallelization_hint
check_resource_sanity

if grep_active "$nextflow_driver_pattern"; then
    pass "Known Nextflow workflow driver detected; child process resources must be reviewed in the Nextflow config"
elif grep_active "$big_command_pattern" || grep_active "$hite_command_pattern"; then
    big_match="$(first_active_match "$big_command_pattern" || true)"
    [[ -n "$big_match" ]] || big_match="$(first_active_match "$hite_command_pattern" || true)"
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
