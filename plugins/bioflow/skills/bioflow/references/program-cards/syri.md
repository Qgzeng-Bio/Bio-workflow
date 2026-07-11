# SyRI program card

Use this card when the user asks to run SyRI directly. For full assembly SV
workflows, read `../playbook-variant-synteny-syri.md` first and use this card for
tool-level checks.

## Supported modes

- `pairwise_asm_sv`: one reference assembly versus one query assembly.
- `all_to_ref_batch`: multiple query assemblies compared to one reference.
- `chained_plotsr_input`: pairwise SyRI outputs prepared for plotsr/chained
  visualization.

## Environment preflight

- Check `command -v syri`.
- Check `command -v minimap2` because SyRI depends on a whole-genome alignment.
- Check `command -v samtools` if BAM/SAM inspection or indexing is needed.
- Record `syri --version` or `syri -h` when version output is unavailable.
- Record `minimap2 --version`.
- Use explicit Conda envs or binary paths already proven in the project when
  available.

## Required inputs by mode

- `pairwise_asm_sv`: reference FASTA, query FASTA, minimap2 SAM alignment, output
  directory, chromosome naming/orientation plan.
- `all_to_ref_batch`: reference FASTA, query FASTA manifest, per-sample output
  prefixes, array/concurrency plan.
- `chained_plotsr_input`: ordered pair list, SyRI outputs, genome/chromosome order,
  plotsr manifest target.

## Input preparation

- Confirm reference and query FASTA paths are explicit, readable, and non-empty.
- Use existing `.fai` files to compare chromosome IDs and lengths. State before
  creating missing indexes.
- Generate the alignment with minimap2 in the confirmed mode, usually
  `minimap2 -ax asm5 --eqx <ref.fa> <query.fa> > <pair.sam>` for close assemblies.
- Check chromosome orientation and naming before SyRI. Do not use SyRI output to
  compensate for obviously reversed or mismatched chromosome labels.
- Keep one output directory per pair.

## Parameter negotiation

- Must ask: reference assembly, query assembly or manifest, pair naming, topology
  (`pairwise_asm_sv`, `all_to_ref_batch`, or `chained_plotsr_input`), output root,
  and whether plotsr/VCF outputs are required.
- Must confirm: minimap2 preset/divergence expectation and `--eqx` use.
- Must ask for batch: array concurrency and whether failed pairs should block the
  whole batch.
- Can infer: `-F S` only when the input alignment is SAM and the local SyRI help
  confirms the syntax.
- Must record: SyRI version/help evidence, minimap2 command, reference/query FASTA
  versions, pair labels, and any VCF patch command.

## Resource model

Use `../software-resource-cards.md` under `SyRI` and `minimap2`. SyRI itself has
limited CPU scaling; clean alignments and memory headroom matter more than high
CPU. For many pairs, prefer a SLURM array with low concurrency.

## Script generation notes

- Generate or reference a per-pair minimap2 SAM first.
- Run SyRI from a pair-specific output directory or with explicit output paths.
- Preserve raw `syri.out`, `syri.summary`, logs, and command files.
- If VCF is used downstream, include the established SVLEN/SVTYPE patch step and
  save both raw and patched VCFs.
- Use `prepare_submission.sh` for each script or batch array before asking to
  submit.

## Acceptance checks

- `syri.out` exists and is non-empty.
- `syri.summary` exists and is non-empty.
- Logs show normal completion for minimap2 and SyRI.
- VCF, if requested, is patched/validated for `SVLEN` and `SVTYPE`.
- Pair labels, chromosome IDs, and reference/query orientation match the manifest.
- For plotsr/chained output, the plotsr input manifest exists and all referenced
  SyRI files exist.
- Do not interpret SV counts until naming/orientation and output completeness pass.

## Common failures and recovery

- SyRI rejects alignment format: confirm `-F` value and regenerate SAM if needed.
- Empty or tiny `syri.out`: inspect minimap2 alignment size and chromosome naming.
- Memory failure: reduce batch concurrency or move partition based on `sacct`
  evidence.
- Inverted/misoriented chromosomes: fix orientation/naming and regenerate alignment
  before rerunning SyRI.
- Missing VCF fields for downstream merging: apply the VCF SVLEN/SVTYPE patch and
  preserve the raw file.

## Evidence grade

- SyRI mode and local CLI flags: `local_help` when checked on this server.
- minimap2 `-ax asm5 --eqx` for close assembly-to-assembly SyRI input:
  `project_history` plus `official_doc`/`github_readme` when cited.
- VCF SVLEN/SVTYPE patch requirement: `project_history` for local workflows.
- Resource model: `project_history` plus `inferred` from
  `../software-resource-cards.md`.
- Acceptance checks: `local_run` after validated output exists.
