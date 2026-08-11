#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
init="$root/scripts/init_project.sh"
steward="$root/scripts/workspace_steward.py"
gen="$root/scripts/gen_sbatch.sh"
prepare="$root/scripts/prepare_submission.sh"
submit="$root/scripts/submit_and_log.sh"
tmp="$(mktemp -d /tmp/bioflow-workspace-integration.XXXXXX)"
trap 'rm -rf "$tmp"' EXIT
project="$tmp/project"

"$init" --project "$project" --workspace-steward --yes >/dev/null
for contract in Workspace_Policy.tsv Workspace_Modules.tsv Workspace_Routes.tsv; do
    [[ -s "$project/config/$contract" ]] || { echo "FAIL | missing $contract" >&2; exit 1; }
done
printf 'PASS | init explicitly installs workspace contracts\n'

cat > "$project/config/Workspace_Modules.tsv" <<'TSV'
Module_ID	Parent_Module	Stage	Short_Name	Module_Kind	Depends_On	Purpose	Owner	Compatibility	Notes
M001	ROOT	01	core	analysis		Core fixture	tester	Managed	NA
TSV
cat > "$project/config/Workspace_Routes.tsv" <<'TSV'
Route_ID	Module_ID	Path_Type	Path_Role	Relative_Path	Producer_Tasks	Consumer_Tasks	Retention	Required	Compatibility	Purpose	Notes
R001	M001	Directory	Script	scripts/01_core	T001		Working	Yes	Managed	Core scripts	NA
R002	M001	Directory	Log	logs/01_core	T001		Working	Yes	Managed	Core logs	NA
R003	M001	Directory	Temporary	tmp/01_core	T001		Disposable	Yes	Managed	Core temporary	NA
R004	M001	Directory	Result	results/01_core	T001		Retained	Yes	Managed	Core results	NA
TSV
cat > "$project/reports/Task_Status.tsv" <<'TSV'
Task_ID	Stage	Sample_ID	Status	Job_ID	Dependency	Script_Path	Log_Path	Output_Path	Acceptance_Path	Retry_Count	Updated_Time
T001	M001	NA	Ready	NA	NA	scripts/01_core/job.slurm	logs/01_core/job.out	results/01_core	NA	0	2026-08-10T00:00:00+08:00
TSV
python3 "$steward" apply --project "$project" --yes >/dev/null

script="$project/scripts/01_core/job.slurm"
"$gen" \
    --job-name ws_gate --cpus 1 --mem 4G \
    --log-dir "$project/logs/01_core" \
    --out "$script" --cmd 'echo done' \
    --project "$project" --module M001 --task-id T001 \
    --output-dir "$project/results/01_core" --tmp-dir "$project/tmp/01_core" \
    >/dev/null
[[ -s "$script" ]] || { echo 'FAIL | steward-aware sbatch script was not generated' >&2; exit 1; }
wrong_script="$project/scripts/01_core/other.slurm"
set +e
wrong_gen_out="$("$gen" \
    --job-name ws_wrong --cpus 1 --mem 4G \
    --log-dir "$project/logs/01_core" \
    --out "$wrong_script" --cmd 'echo wrong' \
    --project "$project" --module M001 --task-id T001 \
    --output-dir "$project/results/01_core" --tmp-dir "$project/tmp/01_core" 2>&1)"
wrong_gen_rc=$?
set -e
[[ "$wrong_gen_rc" -eq 1 && ! -e "$wrong_script" ]] \
    || { printf 'FAIL | unregistered script path was generated\n%s\n' "$wrong_gen_out" >&2; exit 1; }
grep -Fq 'does not match Task_Status.Script_Path' <<< "$wrong_gen_out"
printf 'PASS | gen_sbatch validates routes and binds the registered script path\n'

prepare_out="$(cd "$project" && "$prepare" \
    --script "$script" --output "$project/results/01_core" \
    --project "$project" --module M001 --task-id T001 --tmp "$project/tmp/01_core")"
grep -Fq '[工作区] PASS | module=M001 task=T001' <<< "$prepare_out"
grep -Fq 'VERDICT: 🟢 GO' <<< "$prepare_out"
printf 'PASS | prepare_submission includes Workspace Steward GO/NO-GO layer\n'

set +e
wrong_out="$(cd "$project" && "$prepare" \
    --script "$script" --output "$project/reports" \
    --project "$project" --module M001 --task-id T001 --tmp "$project/tmp/01_core" 2>&1)"
wrong_rc=$?
set -e
[[ "$wrong_rc" -eq 1 ]] || { printf 'FAIL | wrong route was not blocked\n%s\n' "$wrong_out" >&2; exit 1; }
grep -Fq 'Workspace Steward 路由闸门 BLOCK' <<< "$wrong_out"
printf 'PASS | prepare_submission blocks a managed output-route mismatch\n'

mkdir "$project/results/01_core/unplanned_dir"
set +e
drift_out="$(cd "$project" && "$prepare" \
    --script "$script" --output "$project/results/01_core" \
    --project "$project" --module M001 --task-id T001 --tmp "$project/tmp/01_core" 2>&1)"
drift_rc=$?
set -e
[[ "$drift_rc" -eq 1 ]] || { printf 'FAIL | workspace audit drift did not block submission\n%s\n' "$drift_out" >&2; exit 1; }
grep -Fq $'WS006\tWorkspace_Audit\tresults/01_core/unplanned_dir' <<< "$drift_out"
rmdir "$project/results/01_core/unplanned_dir"
printf 'PASS | prepare_submission propagates full workspace audit blockers\n'

submit_out="$(cd "$project" && "$submit" \
    --script "$script" --output "$project/results/01_core" \
    --project "$project" --module M001 --task-id T001 --tmp "$project/tmp/01_core")"
grep -Fq '闸门 GO (dry-run)' <<< "$submit_out"
[[ ! -e "$project/reports/run_record.tsv" ]] || { echo 'FAIL | submit dry-run wrote run record' >&2; exit 1; }
printf 'PASS | submit_and_log forwards workspace arguments without sbatch or writes\n'

printf 'PASS | workspace execution-gate integration fixtures\n'
