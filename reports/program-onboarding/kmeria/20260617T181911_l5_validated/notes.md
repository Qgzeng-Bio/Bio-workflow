# KMERIA — L5 validation evidence (auto-imported from project history)

This bundle was created by reading a user-named set of files in the live
project — not by scanning. The four files read:

- `reports/RUN_FULL.md`   — runbook with submit order + tuning knobs
- `reports/HANDOFF.md`    — pilot resource table + gotcha list
- `scripts/20_count.sbatch`, `30_matrix.sbatch`, `40_asso.sbatch`

Plus `sacct` results from the bounded `project_state_audit.sh` run, which
proved 50/50 array tasks COMPLETED for full-run count batch (job 846422)
and the 8-sample pilot Manhattan PNG already exists on disk.

## What promoted KMERIA to active card

The project demonstrates KMERIA running end-to-end:
- Pilot 845807 (job exit 0): count → kctm → filter → m2b → asso → merge →
  threshold → pseudo-Manhattan, all stages produced expected outputs.
- Full-run count 846422: 50/50 array tasks COMPLETED, ~10–15 min/task,
  ~13–18 GB/task RAM.
- Threshold file proves merge+threshold scripts work:
  PH 8 samples → 369,534,602 total k-mers, 11.9 M effective, Bonferroni 1.35e-10.

This crosses the L5 bar in the project's L0–L6 ladder. The card was
promoted directly from draft to active and added to registry.tsv with
modes `pilot_kmer_gwas`, `full_population_kmer_gwas`, `kmer_to_genome_mapping`.

## What was NOT done in this session

- Did not modify any file under the live KMERIA project.
- Did not scan the project filesystem (only read four named files plus
  the bounded audit output).
- Did not run KMERIA against project data (the local install at
  `/data9/home/qgzeng/tools/kmeria/v2.0.4_7c891be/` was already verified
  in bundle 20260617T171323).
