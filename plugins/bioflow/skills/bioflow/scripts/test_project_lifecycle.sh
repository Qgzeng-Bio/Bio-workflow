#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
audit="$root/scripts/project_state_audit.sh"
tmp="$(mktemp -d /tmp/bioflow-lifecycle-test.XXXXXX)"
trap 'rm -rf "$tmp"' EXIT

make_project() {
    local name="$1"
    mkdir -p "$tmp/$name"/{config,data,scripts,logs,results,reports,tmp}
    printf '%s\n' "$tmp/$name"
}

assert_primary() {
    local expected="$1"
    local project="$2"
    local output
    output="$($audit --project "$project" --max-depth 3 --max-files 1000)"
    if ! grep -Fq "Primary_stage: $expected" <<< "$output"; then
        printf 'FAIL | expected %s for %s\n%s\n' "$expected" "$project" "$output" >&2
        exit 1
    fi
    printf 'PASS | %s\n' "$expected"
}

project="$(make_project intake)"
assert_primary Project_intake "$project"

project="$(make_project initialized_skeleton)"
cp "$root/assets/project-templates/Input_Manifest.tsv" "$project/config/Input_Manifest.tsv"
cp "$root/assets/project-templates/Analysis_Plan.md" "$project/reports/Analysis_Plan.md"
cp "$root/assets/project-templates/Acceptance_Report.md" "$project/reports/Acceptance_Report.md"
cp "$root/assets/project-templates/Methods_Summary.md" "$project/reports/Methods_Summary.md"
cp "$root/assets/project-templates/Delivery_Index.md" "$project/reports/Delivery_Index.md"
assert_primary Project_intake "$project"

project="$(make_project plan_without_inputs)"
printf 'Plan_Status: Reviewed\n' > "$project/reports/Analysis_Plan.md"
assert_primary Project_intake "$project"

project="$(make_project plan_status_pointer_only)"
printf 'Sample_ID\tInput_Path\nS1\t/data/example.fastq.gz\n' > "$project/config/samples.tsv"
printf 'Stage\tStatus\tEvidence_Path\tJob_ID\tExit_Code\tInput_Path\tOutput_Path\tNext_Action\tUpdated_Time\n' > "$project/reports/workflow_status.tsv"
printf 'Plan_ready\tReviewed\tconfig/samples.tsv\tNA\tNA\tconfig/samples.tsv\tNA\tWrite script\t2026-07-11T00:00:00+0800\n' >> "$project/reports/workflow_status.tsv"
assert_primary Input_ready "$project"

project="$(make_project external_plan_status_pointer)"
printf 'Sample_ID\tInput_Path\nS1\t/data/example.fastq.gz\n' > "$project/config/samples.tsv"
printf 'Plan_Status: Reviewed\n' > "$tmp/outside_plan.md"
printf 'Stage\tStatus\tEvidence_Path\tJob_ID\tExit_Code\tInput_Path\tOutput_Path\tNext_Action\tUpdated_Time\n' > "$project/reports/workflow_status.tsv"
printf 'Plan_ready\tReviewed\t../outside_plan.md\tNA\tNA\tconfig/samples.tsv\tNA\tWrite script\t2026-07-11T00:00:00+0800\n' >> "$project/reports/workflow_status.tsv"
assert_primary Input_ready "$project"

project="$(make_project inputs)"
printf 'Sample_ID\tInput_Path\nS1\t/data/example.fastq.gz\n' > "$project/config/samples.tsv"
assert_primary Input_ready "$project"

project="$(make_project draft_plan)"
printf 'Sample_ID\tInput_Path\nS1\t/data/example.fastq.gz\n' > "$project/config/samples.tsv"
printf 'Plan_Status: Draft\n' > "$project/reports/Analysis_Plan.md"
assert_primary Input_ready "$project"

project="$(make_project reviewed_plan)"
printf 'Sample_ID\tInput_Path\nS1\t/data/example.fastq.gz\n' > "$project/config/samples.tsv"
printf 'Plan_Status: Reviewed\n' > "$project/reports/Analysis_Plan.md"
assert_primary Plan_ready "$project"

project="$(make_project script_ready)"
printf 'Sample_ID\tInput_Path\nS1\t/data/example.fastq.gz\n' > "$project/config/samples.tsv"
printf 'Plan_Status: Reviewed\n' > "$project/reports/Analysis_Plan.md"
printf '#!/usr/bin/env bash\n#SBATCH --cpus-per-task=1\n' > "$project/scripts/10_run.slurm"
assert_primary Script_ready "$project"

project="$(make_project queued)"
printf 'Job started | SLURM_JOB_ID=12345\n' > "$project/logs/12345_run.out"
assert_primary Queued_or_running "$project"

project="$(make_project failed)"
printf 'Traceback: analysis failed\n' > "$project/logs/run.err"
assert_primary Failed "$project"

project="$(make_project complete)"
printf 'result\n' > "$project/results/Summary.tsv"
printf 'Job completed\n' > "$project/logs/run.out"
assert_primary Complete_unvalidated "$project"

project="$(make_project analysis_ready)"
printf 'result\n' > "$project/results/Summary.tsv"
printf 'Acceptance_Status: Accepted\n' > "$project/reports/Acceptance_Report.md"
printf 'Stage\tStatus\tEvidence_Path\tJob_ID\tExit_Code\tInput_Path\tOutput_Path\tNext_Action\tUpdated_Time\n' > "$project/reports/workflow_status.tsv"
printf 'Analysis_ready\tValidated\treports/Acceptance_Report.md\tNA\t0:0\tNA\tresults/Summary.tsv\tInterpret results\t2026-07-11T00:00:00+0800\n' >> "$project/reports/workflow_status.tsv"
assert_primary Analysis_ready "$project"

project="$(make_project analysis_status_pointer_only)"
printf 'result\n' > "$project/results/Summary.tsv"
printf 'Job completed\n' > "$project/logs/run.out"
printf 'Acceptance_Status: Draft\n' > "$project/reports/Acceptance_Report.md"
printf 'Stage\tStatus\tEvidence_Path\tJob_ID\tExit_Code\tInput_Path\tOutput_Path\tNext_Action\tUpdated_Time\n' > "$project/reports/workflow_status.tsv"
printf 'Analysis_ready\tValidated\tresults/Summary.tsv\tNA\t0:0\tNA\tresults/Summary.tsv\tInterpret results\t2026-07-11T00:00:00+0800\n' >> "$project/reports/workflow_status.tsv"
assert_primary Complete_unvalidated "$project"

project="$(make_project delivered)"
printf 'result\n' > "$project/results/Summary.tsv"
printf 'Acceptance_Status: Accepted\n' > "$project/reports/Acceptance_Report.md"
printf 'Delivery_Status: Delivered\n' > "$project/reports/Delivery_Index.md"
assert_primary Delivered "$project"

project="$(make_project delivered_after_failure)"
printf 'result\n' > "$project/results/Summary.tsv"
printf 'Acceptance_Status: Accepted\n' > "$project/reports/Acceptance_Report.md"
printf 'analysis failed\n' > "$project/logs/run.err"
printf 'Delivery_Status: Delivered\n' > "$project/reports/Delivery_Index.md"
touch -t 202607110101 "$project/reports/Acceptance_Report.md"
touch -t 202607110102 "$project/logs/run.err"
touch -t 202607110103 "$project/reports/Delivery_Index.md"
assert_primary Delivered "$project"

project="$(make_project unaccepted_delivery_after_failure)"
printf 'result\n' > "$project/results/Summary.tsv"
printf 'Acceptance_Status: Draft\n' > "$project/reports/Acceptance_Report.md"
printf 'analysis failed\n' > "$project/logs/run.err"
printf 'Delivery_Status: Delivered\n' > "$project/reports/Delivery_Index.md"
touch -t 202607110101 "$project/logs/run.err"
touch -t 202607110102 "$project/reports/Delivery_Index.md"
assert_primary Failed "$project"

project="$(make_project delivery_status_pointer_only)"
printf 'result\n' > "$project/results/Summary.tsv"
printf 'Job completed\n' > "$project/logs/run.out"
printf 'Acceptance_Status: Draft\n' > "$project/reports/Acceptance_Report.md"
printf 'Delivery_Status: Draft\n' > "$project/reports/Delivery_Index.md"
printf 'Stage\tStatus\tEvidence_Path\tJob_ID\tExit_Code\tInput_Path\tOutput_Path\tNext_Action\tUpdated_Time\n' > "$project/reports/workflow_status.tsv"
printf 'Delivered\tDelivered\tresults/Summary.tsv\tNA\t0:0\tNA\tresults/Summary.tsv\tPreserve\t2026-07-11T00:00:00+0800\n' >> "$project/reports/workflow_status.tsv"
assert_primary Complete_unvalidated "$project"

printf 'PASS | project lifecycle regression fixtures\n'
