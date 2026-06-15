#!/bin/bash
#SBATCH --partition=normal
#SBATCH --job-name=per_chunk_array
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --array=1-N%2
#SBATCH --output=/absolute/project/path/logs/%A_%a_%x.out
#SBATCH --error=/absolute/project/path/logs/%A_%a_%x.err

set -euo pipefail

PROJECT_DIR="/absolute/project/path"
CHUNK_MANIFEST="${PROJECT_DIR}/config/chunk_manifest.tsv"
OUT_ROOT="${PROJECT_DIR}/results/per_chunk"
TMP_ROOT="${PROJECT_DIR}/tmp/per_chunk"

echo "[INFO] Job started | Host: $(hostname) | Time: $(date)"
echo "[INFO] Job ID: ${SLURM_JOB_ID:-NA} | Array task: ${SLURM_ARRAY_TASK_ID:-NA}"
echo "[INFO] Partition: ${SLURM_JOB_PARTITION:-NA} | CPUs: ${SLURM_CPUS_PER_TASK:-NA}"
echo "[INFO] Workdir: $(pwd)"

[[ -r "$CHUNK_MANIFEST" ]] || { echo "[ERROR] Chunk manifest not readable: $CHUNK_MANIFEST" >&2; exit 1; }

TASK_LINE="$(sed -n "${SLURM_ARRAY_TASK_ID}p" "$CHUNK_MANIFEST")"
[[ -n "$TASK_LINE" ]] || { echo "[ERROR] Empty manifest line for task ${SLURM_ARRAY_TASK_ID}" >&2; exit 1; }
if printf '%s\n' "$TASK_LINE" | grep -Eiq '^(Chunk_ID|Chunk[[:space:]_-]*ID|Item_List_File)([[:space:]]|$)'; then
    echo "[ERROR] Chunk manifest appears to contain a header. Default array templates expect no header; remove it or adjust task-line indexing." >&2
    exit 1
fi

# Expected TSV columns: Chunk_ID  Item_List_File
# Item_List_File is a text/TSV file containing one sample/chromosome/file per line.
IFS=$'\t' read -r Chunk_ID Item_List_File <<< "$TASK_LINE"
[[ -n "${Chunk_ID:-}" ]] || { echo "[ERROR] Missing Chunk_ID on task ${SLURM_ARRAY_TASK_ID}" >&2; exit 1; }
[[ -r "$Item_List_File" ]] || { echo "[ERROR] Item_List_File not readable: $Item_List_File" >&2; exit 1; }

CHUNK_OUT="${OUT_ROOT}/${Chunk_ID}"
CHUNK_TMP="${TMP_ROOT}/${Chunk_ID}"
mkdir -p "$CHUNK_OUT" "$CHUNK_TMP"

echo "[INFO] Chunk_ID: $Chunk_ID"
echo "[INFO] Item list: $Item_List_File"
echo "[INFO] Output: $CHUNK_OUT"
echo "[INFO] Temp: $CHUNK_TMP"

while IFS= read -r Item_ID; do
    [[ -n "$Item_ID" ]] || continue
    [[ "$Item_ID" =~ ^# ]] && continue
    echo "[INFO] Processing item: $Item_ID"
    # Replace this block with the project command. Pass CPUs explicitly when supported.
    # /usr/bin/time -v tool --threads "${SLURM_CPUS_PER_TASK:-4}" \
    #     --input "$Item_ID" \
    #     --output "${CHUNK_OUT}/${Item_ID}.tsv" \
    #     2> "${CHUNK_OUT}/${Item_ID}.time.log"
done < "$Item_List_File"

echo "[INFO] TODO: replace template command for ${Chunk_ID}"
echo "[INFO] Job finished | Time: $(date)"
