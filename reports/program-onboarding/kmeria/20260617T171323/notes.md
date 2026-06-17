# KMERIA v2.0.4 install notes (commit 7c891be)

## Surprises encountered

1. **GitHub has no `v2.0.4` source tag.** README claims v2.0.4 (2026-06-12)
   but `git ls-remote --tags` only returns up to `v2.0.1-new`. Newer tags
   in the repo are binary-only releases (`KMERIA_Linux64_Binary-v2.0.x`).
   Workaround: pin `main` HEAD commit `7c891be`.

2. **`kmeria_env.yaml` defaults to `name: kmeriaenv`.** Override with `-n`
   to avoid colliding with an existing env. Used `bio_kmeria_v2_0_4`.

3. **README PATH instructions miss `scripts/`.** `kmeria_wrapper.pl` lives
   in `scripts/`, not `bin/` or `external_tools/`. Adding `scripts/` to PATH
   is required for the documented entry point to be callable by name.

4. **Pre-built `bin/kmeria` needs GCC 12+ libstdc++.** It links against
   GLIBCXX_3.4.32 / CXXABI_1.3.13 which the system `/lib64/libstdc++.so.6`
   does not provide. The conda env (GCC 15) supplies a newer one — set
   `LD_LIBRARY_PATH=<env>/lib:<install>/lib:...` so the env's libstdc++
   is found before the system one.

5. **README step 4 (`chmod 755 bin/* external_tools/* bimbamAsso/*`) is
   not optional.** Files come out of git read-only by default; without
   chmod, `kmc` and `gemma` cannot be executed.

6. **Wrapper version (v2.0.1) lags main version (v2.0.4).** Author has not
   bumped `kmeria_wrapper.pl`'s self-reported version. Cosmetic only;
   workflow steps (count/kctm/filter/m2b/asso) still work.

## Next step (L4)

To pilot this install on real data, the user must provide:
- A samples list (one sample ID per line) — see wrapper `--samples`
- Per-sample FASTQ paths
- Optional: phenotype/covariate files for the `asso` step

Then: `. activate.sh && kmeria_wrapper.pl --step count --samples … --threads 16`
in a controlled pilot directory before any SLURM submission.
