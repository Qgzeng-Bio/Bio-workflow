# KMERIA program card

Use this card when the user asks to run KMERIA for reference-free k-mer GWAS
on resequencing data. KMERIA tests every distinct k-mer in the population for
phenotype association — captures SV/CNV/PAV signal that SNP-only GWAS misses.

The pipeline is `count → kctm → filter → m2b → asso → (downstream: merge →
threshold → sig k-mers → genome-coord mapping → Manhattan)`. The wrapper
`kmeria_wrapper.pl` covers the first five steps; downstream is project-script
territory because the official documentation leaves it as a TODO.

For the validated quinoa pilot/full-run, see project history at
`/data9/home/qgzeng/projects/2-C_quinoa/10-population_structure/4-kmer-GWAS`.

## Supported modes

- `pilot_kmer_gwas`: 4–10 sample end-to-end pilot to validate the
  count→kctm→filter→m2b→asso→postgwas chain before committing to a full run.
- `full_population_kmer_gwas`: full population (100s of samples). Requires
  bounded count batching, separate matrix step, per-trait `asso` array, and
  project-scripted downstream because of asso's exit-code quirk and the
  missing official Manhattan recipe.
- `kmer_to_genome_mapping`: post-GWAS step that places significant k-mers on
  reference coordinates (KMERIA `addp`/`kbam`, BLAST short, or `bwa aln`)
  to produce the real Manhattan plot.

## Environment preflight

- Check `command -v kmeria`, `command -v kmeria_wrapper.pl`, `command -v kmc`,
  and `command -v gemma`. The wrapper lives in `KMERIA/scripts/`, not `bin/`,
  so `KMERIA/scripts` must be on PATH (the README's PATH line does not
  include it).
- README's `chmod 755 bin/* external_tools/* bimbamAsso/*` is mandatory; files
  come out of git read-only. Add `scripts/*.pl` to that chmod.
- Source the install's activate script that sets
  `LD_LIBRARY_PATH=<env>/lib:<install>/lib:...` and the four PATH entries
  (`bin`, `scripts`, `bimbamAsso`, `external_tools`). Without `<env>/lib`
  first, the prebuilt `kmeria` cannot find a new enough `libstdc++.so.6`
  (needs `GLIBCXX_3.4.32` / `CXXABI_1.3.13`).
- Capture `kmeria --version`, `kmeria --help`, and `kmeria_wrapper.pl --help`
  evidence. Capture `kmc` banner version (no `--version` flag).
- Reuse an existing Conda env if it already supplies `libhts.so.3`,
  `libbz2.so.1.0`, and a `libstdc++.so.6` with `GLIBCXX_3.4.32`. Building a
  new env is rarely necessary — many existing bioinformatics envs already
  satisfy these. Do not use the upstream `kmeria_env.yaml` blindly: it is a
  build environment (GCC 15 + dev tools), and the project history records it
  as "INSUFFICIENT — lacks curl/ssl/lzma that bundled libhts needs".
- Do not clone, install, or mutate Conda envs without explicit confirmation.

## Required inputs by mode

- `pilot_kmer_gwas`: a small samples list (one sample ID per line, canonical
  order), per-sample paired FASTQ files renamed to `<sample>_1.fq.gz` /
  `<sample>_2.fq.gz`, sample depth file (`<sample>\t<depth>` from
  `samtools idxstats`), at least one phenotype file
  (`<sample>\t<value>` per line; same order as samples list).
- `full_population_kmer_gwas`: same shape at full size; canonical
  `samples.list` sorted, plus a `traits.list` for per-trait array.
- `kmer_to_genome_mapping`: per-trait `<trait>.sig.fasta` from postgwas, plus
  a reference FASTA. Optional: existing SNP-GWAS peaks for cross-checking.

## Input preparation

- FASTQ rename: KMERIA's count regex is
  `^<sample>(_R?[12])?\.(fq|fastq|fa|fasta)(\.gz)?$`. Project FASTQ named like
  `<sample>_clean_1.fq.gz` will fail to be discovered; symlink or rename to
  `<sample>_1.fq.gz` / `_2.fq.gz` first.
- Depth file: `samtools idxstats` (~0.3 s/sample), not `samtools coverage`
  (~150 s/sample). Use `view | head` only with `|| true` (SIGPIPE under
  `set -e`). Computed depth = `mapped_reads × read_len / genome_len`.
- Phenotype: one column per trait, one row per sample, sample order
  identical to `samples.list`. KMERIA's `--pheno-col` is a 1-based phenotype
  *index* (1 = first trait), not a file column number.
- Sample order: keep `samples.list` canonical and pass the same order to
  every step. `kctm` order must equal count order — verify with `diff` after
  generating the kctm sample-order file.

## Parameter negotiation

- Must ask: ploidy, k-mer length, max-abundance, missing-rate, traits to test,
  sample list, depth file source, partition/QOS, threads-per-task, how many
  traits to run concurrently in the asso array.
- Project-validated defaults (quinoa 418-sample full run, `config/params.conf`):
  `k = 31`, `max-abund = 1000`, `missing = 0.6`, `--ploidy 2`. Confirm with the
  user before reusing on a different organism / cohort.
- KMERIA k-mer length is GWAS-bounded: `kmeria count` v2.0.4 accepts
  `k = 2..63`, but k > 31 is not recommended for GWAS. Default `k = 31`.
- Ploidy: KMERIA expects effective ploidy. Quinoa is allotetraploid but
  *disomic* — use `--ploidy 2`, not 4. Confirm before assuming auto-polyploid.
- Threads scale poorly for `count`: 4→16 threads gives ~1.03× speedup
  because `count` caps at ~3 cores. Default to `--threads 4` per sample.
- For `asso` (the long pole), threads scale better — 32 cores per trait is
  the project-validated default.
- Concurrency: full-run `count` array should batch ~50 samples with `%4`
  parallel (=16 CPU/batch); `asso` array runs traits with `%3` (3 traits ×
  32 cores = 96 CPU). All within the user_qgzeng QOS budget
  (≤200 submitted, ≤100 running, ≤600 CPU).
- Must record: KMERIA version + commit, k, ploidy, max-abund, missing-rate,
  pheno-col convention used, exact threads/concurrency, and depth-file
  provenance.

## Resource model

For shared resource patterns (SLURM partition selection, QOS budgeting, array
concurrency), follow `../software-resource-cards.md`. The KMERIA-specific
numbers below extend that with project-history figures.

Pilot resource table (8 quinoa samples, validated 2026-06-15):

| stage  | wall          | peak RAM        | output disk      | partition        |
| ------ | ------------- | --------------- | ---------------- | ---------------- |
| count  | ~6 min/sample | 19.3 G/sample   | 3.25 G/sample    | normal, 4 cores  |
| kctm   | 20 min        | streaming (~0)  | 13 G             | normal, low-mem  |
| filter | 2 min         | streaming (~0)  | 5.8 G            | normal, low-mem  |
| m2b    | 15 min        | 0.6 G           | 6.9 G BIMBAM     | normal, low-mem  |
| asso   | hours/trait   | 1.9 G           | per-chunk assoc  | normal, 32 cores |

Full-run extrapolation (418 samples, project history):
- Count: ~1.4 TB binary k-mer files total (3.25 G/sample × 418).
- kctm/filter/m2b: streaming, low memory; `normal` partition is correct, not
  `fat` despite naive intuition.
- Matrix step disk peaks ~1–3 TB during kctm + filter + m2b chains.
- Asso is the long pole: hours-to-days per trait. Test set scales with
  `n_samples` — 8 samples already produce ~370 M k-mers; full run produces
  far more.

Project memory caps recorded:
- count: 24 G / 4 cores / `--time 01:00:00` (short walltime backfills better).
- matrix: 200 G / 32 cores / `--time 48:00:00`.
- asso: 120 G / 32 cores / `--time 72:00:00`.

## Script generation notes

- Always source the activate script first; never assume PATH or
  LD_LIBRARY_PATH inherits correctly across job nodes.
- Use the BINARY (`kmeria <step>`) when the wrapper's Getopt collision is a
  risk — see "Wrapper short-flag collision" below. Prefer long flags
  (`--threads`, not `-t`) when calling `kmeria_wrapper.pl`.
- `count`: write to `<sample>.bin.tmp` and `mv` on success so partial writes
  cannot pass the resume check.
- Resume safety: count, matrix, and asso are all resume-safe by output
  presence. Re-running a count array skips samples whose `.bin` is non-empty.
- `count` output must be BINARY (`.bin`); never pass `-T` (text). The wrapper
  has a long-flag-only contract because of the collision; the binary's `-t`
  is fine.
- Logs: absolute path with `%x_%A_%a` so array log files don't collide. Keep
  asso `--time` generous (project uses 72 h) but count `--time` short
  (≤01:00:00) for backfill.
- Do not trust `kmeria asso`'s exit code. Verify chunk coverage by counting
  `*.assoc.txt` against the bimbam chunk count; only fail when actual
  coverage is short.
- Wrapper SLURM headers omit `--account/--qos/--mem`; if calling the
  wrapper's scheduler mode, patch headers via project gen_sbatch first.

## Acceptance checks

- `count`: every sample listed has a non-empty `<sample>_k31.bin`. Total
  count file count equals samples list length. Use `21_post_count.sh`-style
  verification before moving on.
- `kctm`: `kctm_sample_order.txt` is byte-equal to the canonical
  `samples.list`. `diff -q` must return clean.
- `filter` / `m2b`: BIMBAM chunk count is non-zero; record disk size.
- `asso`: per trait, count of `*.assoc.txt` equals BIMBAM chunk count
  (excluding `sampling.bimbam.gz`). Exit code is unreliable.
- `merge → threshold`: `<trait>_thresholds.txt` lists `Total_Kmers`,
  `Effective_Tests`, `Bonferroni`, `Relaxed`. Pilot reference: PH 8 samples
  → 369,534,602 total k-mers, 11.9 M effective, Bonferroni 1.35e-10.
- Manhattan PNG must be tagged `pseudo` until k-mers are mapped to genome
  coords; only the post-mapping plot is the "real" Manhattan.
- Logs / version / provenance: KMERIA version + commit, env path,
  pheno-col=1 evidence in run log, sample count, ploidy, k.

## Common failures and recovery

- `kmeria: error while loading shared libraries: libbz2.so.1.0` →
  `LD_LIBRARY_PATH` is missing the conda env's `lib/`. Add `<env>/lib:` to
  the front of LD_LIBRARY_PATH; do not symlink the system libbz2.
- `GLIBCXX_3.4.32 not found` against `/lib64/libstdc++.so.6` →
  same fix (env `lib/` first); do not link against the system libstdc++.
- `kmc: command not found` or `gemma: command not found` while binaries
  exist in `external_tools/` → missing chmod or `external_tools` not on
  PATH. Re-run README chmod step and re-source activate.
- `kmeria_wrapper.pl: command not found` while the file exists → `scripts/`
  not on PATH or file missing executable bit. README PATH line omits
  `scripts/`; project activate scripts must include it.
- Wrapper short-flag collision: passing `-t <int>` to
  `kmeria_wrapper.pl count` folds onto `-T` (text output), producing
  ~13 GB of TEXT k-mer counts that `kctm` then rejects with
  "Invalid KMERIA magic header". Use `--threads` with the wrapper. The
  binary `kmeria count` `-t` is unaffected.
- `kmeria asso` exits non-zero with all `.assoc.txt` chunks present →
  cosmetic post-step quirk; verify chunk coverage and treat as success
  when full coverage is present.
- `Insufficient columns` in asso → `--pheno-col` was set to a file column
  rather than the 1-based trait index. Use `--pheno-col 1` for a
  single-column phenotype file.
- FASTQ regex miss → KMERIA `count` cannot discover `<sample>_clean_1.fq.gz`.
  Symlink to `<sample>_1.fq.gz` and rerun.
- `count` array stuck at "Reason=Priority" forever → walltime too long for
  backfill. Cut `--time` to one-sample wall + 30% margin and resubmit; the
  project saw a Sept-start estimate at `--time=04:00:00` that vanished
  after switching to `--time=01:00:00`.
- Author's `kmeria_env.yaml` env fails on htslib calls → it is a build env,
  not a runtime env; it lacks curl/ssl/lzma that bundled libhts dynamically
  loads. Use a project-validated runtime env (e.g. `kmeriaenv` augmented
  with htslib + libstdcxx-ng>=15) instead.

## Evidence grade

- count→kctm→filter→m2b→asso pipeline shape, wrapper-vs-binary call
  contract, pheno-col 1-based-index semantics, FASTQ regex, depth via
  idxstats, ploidy=2 disomic case, asso-exit-code-quirk, count thread cap
  ~3 cores, count `--time 01:00:00` backfill rule, project resource caps:
  `project_history` (validated end-to-end on 8-sample pilot job 845807 plus
  full-run count batch 846422 with 50/50 array tasks COMPLETED in
  `/data9/home/qgzeng/projects/2-C_quinoa/10-population_structure/4-kmer-GWAS`).
- `kmeria --help`, `kmeria_wrapper.pl --help`, `kmc` banner, `gemma --help`:
  `local_help` (captured 2026-06-17 in
  `reports/program-onboarding/kmeria/20260617T171323/`).
- Pre-built binary GLIBCXX requirement: `local_run` (ldd against the
  installed binary).
- README/PATH bug (missing `scripts/`), README chmod-required step,
  prebuilt-vs-source choice on this server: `local_run` plus
  `github_readme`.
- k-mer length recommendation, asso scaling, kctm/filter/m2b memory
  profile: `project_history`.
- Manhattan downstream method (KMERIA `addp` vs BLAST-short vs `bwa aln`):
  `inferred` plus `github_readme` until the project's full-run actually
  picks a path.
