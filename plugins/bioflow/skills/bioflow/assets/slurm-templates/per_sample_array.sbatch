#!/bin/bash
#SBATCH --partition=normal
#SBATCH --job-name=per_sample_array
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --array=1-N%2
#SBATCH --output=/absolute/project/path/logs/%A_%a_%x.out
#SBATCH --error=/absolute/project/path/logs/%A_%a_%x.err

set -euo pipefail

PROJECT_DIR="/absolute/project/path"
MANIFEST="${PROJECT_DIR}/config/sample_manifest.tsv"
OUT_ROOT="${PROJECT_DIR}/results/per_sample"
TMP_ROOT="${PROJECT_DIR}/tmp/per_sample"

echo "[INFO] Job started | Host: $(hostname) | Time: $(date)"
echo "[INFO] Job ID: ${SLURM_JOB_ID:-NA} | Array task: ${SLURM_ARRAY_TASK_ID:-NA}"
echo "[INFO] Partition: ${SLURM_JOB_PARTITION:-NA} | CPUs: ${SLURM_CPUS_PER_TASK:-NA}"
echo "[INFO] Workdir: $(pwd)"

[[ -r "$MANIFEST" ]] || { echo "[ERROR] Manifest not readable: $MANIFEST" >&2; exit 1; }

TASK_LINE="$(sed -n "${SLURM_ARRAY_TASK_ID}p" "$MANIFEST")"
[[ -n "$TASK_LINE" ]] || { echo "[ERROR] Empty manifest line for task ${SLURM_ARRAY_TASK_ID}" >&2; exit 1; }
if printf '%s\n' "$TASK_LINE" | grep -Eiq '^(Sample_ID|Sample[[:space:]_-]*ID|Input_1|Read1)([[:space:]]|$)'; then
    echo "[ERROR] Manifest appears to contain a header. Default array templates expect no header; remove it or adjust task-line indexing." >&2
    exit 1
fi

# Expected TSV columns: Sample_ID  Input_1  Input_2
IFS=$'\t' read -r Sample_ID Input_1 Input_2 <<< "$TASK_LINE"
[[ -n "${Sample_ID:-}" ]] || { echo "[ERROR] Missing Sample_ID on task ${SLURM_ARRAY_TASK_ID}" >&2; exit 1; }
[[ -r "$Input_1" ]] || { echo "[ERROR] Input_1 not readable: $Input_1" >&2; exit 1; }
if [[ -n "${Input_2:-}" && "$Input_2" != "NA" ]]; then
    [[ -r "$Input_2" ]] || { echo "[ERROR] Input_2 not readable: $Input_2" >&2; exit 1; }
fi

SAMPLE_OUT="${OUT_ROOT}/${Sample_ID}"
SAMPLE_TMP="${TMP_ROOT}/${Sample_ID}"
mkdir -p "$SAMPLE_OUT" "$SAMPLE_TMP"

echo "[INFO] Sample_ID: $Sample_ID"
echo "[INFO] Output: $SAMPLE_OUT"
echo "[INFO] Temp: $SAMPLE_TMP"

# Replace this block with the project command. Pass CPUs explicitly when supported.
# /usr/bin/time -v tool --threads "${SLURM_CPUS_PER_TASK:-4}" \
#     --input "$Input_1" \
#     --mate "$Input_2" \
#     --output "$SAMPLE_OUT/result.tsv" \
#     2> "${SAMPLE_OUT}/${Sample_ID}.time.log"

echo "[INFO] TODO: replace template command for ${Sample_ID}"
echo "[INFO] Job finished | Time: $(date)"
