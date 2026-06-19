# Validation checklists

Use these checklists as a compact acceptance gate for qgzeng bioinformatics
workflows. Keep evidence concrete: paths, counts, job IDs, versions, and short log
snippets. Do not treat a zero exit code as enough.

## Core bioinformatics closure checklist

- Confirm input paths, sample IDs, genome/reference versions, coordinate systems,
  and chromosome naming before interpreting results.
- Avoid heavy compute on login/admin nodes; use SLURM or a confirmed compute node
  for real workloads.
- Validate key intermediate files are non-empty and have expected columns, formats,
  record counts, coordinate ranges, and indexes.
- Record commands, parameters, environments, versions, manifests, and output
  locations in a handoff or report.
- Check representative outputs manually or with summary statistics before claiming
  biological conclusions.
- Report failures, skipped steps, accepted warnings, and remaining uncertainty
  explicitly.

## Resume checklist

- First classify the project with `references/resume-protocol.md` before planning
  new work.
- Prefer the read-only audit:
  `scripts/project_state_audit.sh --project <dir> --max-depth 3 --max-files 1000`.
- Default to the current project directory. Do not audit `/`, `/data9`,
  `/data9/home/qgzeng`, or `/data9/home/qgzeng/projects` without explicit
  confirmation and a bounded plan.
- Use `--check-queue` only when job IDs or SLURM log clues exist.
- Assign one primary state: `Input_ready`, `Script_ready`, `Queued_or_running`,
  `Failed`, `Complete_unvalidated`, or `Analysis_ready`.
- For `Script_ready`, run `scripts/prepare_submission.sh --script <file>` with
  known manifest/input/output paths before proposing `sbatch`; use
  `scripts/slurm_preflight.sh --script <file>` only as a fallback.
- For `Queued_or_running`, monitor with `squeue`/`sacct`; do not edit active-run
  scripts or resubmit without confirmation.
- If `squeue`/`sacct` are unavailable but the newest log has a job ID/start line
  without a terminal marker, keep the state at `Queued_or_running`/unknown instead
  of validating older outputs.
- For `Failed`, run `scripts/slurm_failure_triage.sh --jobid <id>` or `--err <file>`
  before changing resources.
- For `Complete_unvalidated`, run result acceptance checks before any biological
  interpretation, figure generation, or downstream analysis.
- For `Analysis_ready`, cite the validation evidence path before interpreting
  biology or plotting.
- Do not write `reports/workflow_status.tsv` automatically; write it only after
  user confirmation, using the standard columns from `references/resume-protocol.md`.

## Input checklist

- Research question, organism, reference version, sample design, and expected outputs
  are stated.
- Input paths are explicit and scoped to the project or user-provided locations.
- Required files exist, are readable, and are non-empty.
- File types match the planned tools: FASTA/FASTQ/BAM/VCF/GFF/GTF/BED/TSV.
- Indexes are present when required: `.fai`, `.bai/.crai`, `.tbi/.csi`, sequence
  dictionary, or tool-specific indexes.
- Sample count, group labels, and paired-end naming match the manifest.
- Chromosome/scaffold names are compatible across FASTA, BAM, VCF, and annotation.
- Raw data under `/data9/home/qgzeng/data/` are treated as protected read-only input
  unless the user explicitly confirms otherwise.

## Lightweight environment checklist

- Current host is identified; compute-heavy work is not run on `admin2` or login nodes.
- Tool discovery is cheap: `command -v`, `--version`, known env path, or explicit
  Singularity image.
- No installation, upgrade, or environment mutation is attempted without confirmation.
- Proxy variables or `proxychains` are not used for raw-data downloads without
  explicit user confirmation.
- Broad scans such as `find /data9` or unbounded `du` are avoided.

## Resource-estimation checklist

- Tool mode is identified, not just the tool name.
- For generated workflows, generator warnings are reviewed before the generated
  stage scripts are executed.
- For KMERIA/k-mer GWAS, count output format is confirmed to be compatible with the
  matrix-construction stage before scaling beyond a pilot.
- Input scale evidence is recorded: file sizes, `.fai`, sample count, database size,
  or previous `sacct`.
- Parallelism is classified: single-threaded, moderate, strong, memory-bound, or
  I/O-bound.
- Memory estimate names the main driver and includes headroom.
- CPU request explains why more CPUs would or would not help.
- Pilot `/usr/bin/time -v` logs have `Exit status: 0` before they are used for CPU
  or memory down-tuning.
- Partition follows estimated memory: usually `normal` below 200G; consider `fat` or
  `fat2` at or above 200G after confirmation.
- Array concurrency has a `%N` cap chosen from memory, disk I/O, and queue pressure.
- Array manifests for bundled templates are headerless; remove `Sample_ID`/`Chunk_ID`
  headers or adjust task-line indexing before submission.
- Expected runtime and disk growth are stated when they may be material.
- `#SBATCH --time` is absent by default, or its presence is explicitly justified.

## SLURM pre-submit checklist

- Run `scripts/prepare_submission.sh --script <file>` before proposing
  `sbatch` whenever manifest/input/output context is available; use
  `scripts/slurm_preflight.sh --script <file>` only as a fallback.
- Include a `🧮 资源判断` for CPU, memory, partition, array concurrency, and
  whether the request fits the tool/input scale.
- Script uses strict mode: `set -euo pipefail` or equivalent.
- Log paths are absolute and include `%j` or `%x`.
- `#SBATCH --output`, `#SBATCH --error`, and `#SBATCH --chdir` do not target protected
  raw-data or tool directories.
- Output directories are explicit and overwrite behavior is known.
- Temporary directories are project-local and sized for the tool.
- Inputs, outputs, tools, and versions are echoed or logged.
- Job name, partition, CPU, memory, array range, and array concurrency are reported.
- No active `rm -rf` pattern is present unless the user explicitly approved it.
- No unguarded display-only pipe to `head` is present under `set -euo pipefail`.
- Stage wrappers keep full stderr/time logs, not only filtered `error` lines.
- No write-like command targets `/data9/home/qgzeng/data/` or
  `/data9/home/qgzeng/tools/`.
- User confirmation is obtained before `sbatch`, resubmission, `scancel`, high-memory,
  long-running, or large-download actions.

## Failure-diagnosis checklist

- Record job ID, script path, submit time, and log paths.
- Query `sacct -j <jobid> --format=JobID,State,ExitCode,MaxRSS,Elapsed`.
- Read the matching `.err` and relevant `.out` before changing resources.
- Classify the failure: missing input, permission, env/tool, OOM, TIMEOUT, segfault,
  disk full, software bug, or biological/data issue.
- Treat `TIMEOUT` as a script/resource-policy problem; do not add shell `timeout` to
  force long bioinformatics work to stop.
- For OOM, compare `MaxRSS` to requested memory and adjust only with evidence.
- For format or naming errors, validate a small explicit subset before rerunning.
- For exit code 13/141, empty `.err`, or logs ending at a harmless preview command,
  inspect unguarded `| head`/pipefail patterns before changing resources.
- For KMERIA failures, distinguish count-stage input/tool failures from `count` to
  `kctm` format incompatibility; do not resubmit the same stage order when the
  wrapper already warned about incompatible formats.
- Ask before resubmitting or changing concurrency.

## Result acceptance checklist

- Run layer: expected files exist, are non-empty, and logs show normal completion.
- Data layer: sample count, record count, format, coordinate system, and chromosome
  names match expectations.
- Analysis layer: QC metrics, filters, controls, and parameter choices are documented.
- Reproducibility layer: exact commands, tool versions, scripts, configs, and manifests
  are saved.
- Biological layer: conclusions answer the research question and separate evidence
  from speculative hypotheses.
- For quinoa, interpretation considers stress tolerance, salinity, drought response,
  mineral accumulation, subgenome differentiation, structural variation, and
  pangenome variability when relevant.

## Centromere and CENH3 checklist

- IP/Input pairing, genome size source, mapping branch, dedup status, and MAPQ
  policy are recorded.
- CENH3 domains are called from log2(IP/Input) signal, not from MACS2 peaks alone;
  MACS2 is treated as auxiliary support.
- TRASH/CEN40 density, HOR-like blocks, CENH3 domains, final BED intervals, and
  `.fai` chromosome lengths use the same coordinate convention and chromosome names.
- Final boundary changes are reviewed on genome-wide plots and labeled as confident,
  curated, rescue, discordant, or no-clear-signal.
- HOR scoring is rerun after final BED boundary changes; old BED-filtered monomer
  and HOR tables are not reused silently.

## Synteny checklist

- GFF feature IDs, CDS FASTA record IDs, BED column 4 IDs, and selected isoform
  policy are compatible.
- Prepared `.bed`, `.uniq.bed`, and `.cds` files are non-empty and have expected
  record counts before JCVI ortholog calls.
- Anchor, screened anchor, lifted anchor, and block counts are recorded, including
  the chosen `--cscore`, `--minspan`, and working directory.
- `seqids`, `layout`, `plot.bed`, and microsynteny `layout.txt` are checked against
  generated prefixes and anchors rather than invented from memory.
- Karyotype or microsynteny figures are non-empty and visually checked for swapped
  genomes, missing chromosomes, or label/layout mismatches.

## Repeat annotation checklist

- Genome FASTA, `.fai`, EDTA, RepeatModeler, RepeatMasker, solo-LTR, TEsorter, and
  downstream BED/GFF files use the same assembly version and chromosome names.
- For every repeat tool mode used, official GitHub/docs or local installed source
  were checked for the exact command boundary; record source URL/path, check date,
  local version/container, and whether the command is discovery, masking,
  classification, summarization, alignment, or tree building.
- Repeat workflow deliverables are separated: TRF tandem repeats, RepeatModeler
  libraries, EDTA structural TE annotation, RepeatMasker softmasked FASTA, solo-LTR
  ratios, TE density, and TEsorter/RT phylogeny are not treated as one evidence type.
- Each result has a declared use: TRF for tandem repeats, EDTA GFF3/sum for TE
  composition, EDTA TElib/RepeatModeler libraries for masking/library reuse,
  RepeatMasker `.masked` for gene-prediction softmasking, solo/intact ratios for
  LTR turnover, density/metagene profiles for spatial enrichment, and TEsorter/RT
  trees for domain-containing LTR classification/phylogeny.
- TRF records the full seven numeric parameters and labels `.mask` as tandem-repeat
  masking evidence only.
- RepeatModeler records whether `-LTRStruct` was deliberately used, keeps the log,
  uses one intended assembly/haplotype per database, and does not split a genome into
  arbitrary chunks for later naive merging.
- EDTA runs record version/container, genome, `--species`, `--step`, `--sensitive`,
  `--anno`, `--evaluate`, `--force`, `--overwrite`, `--threads`, and `--cds`.
- EDTA FASTA headers are short/simple and stable; `--overwrite 0/1`, `--force`,
  `--curatedlib`, and `--rmlib` decisions are explicit and not hidden defaults.
- EDTA final TElib, TEanno GFF3, TEanno sum, RM out/GFF, intact GFF3/FASTA, and
  `TE.fa.stat*` summaries are non-empty before interpretation.
- RepeatModeler outputs include deliberate database prefix, family library, `.stk`,
  log, and genome version; requested CPUs match the real `-threads`/`-pa` setting.
- RepeatMasker outputs include `.masked`, `.out`, `.out.gff`, `.tbl`, `.cat.gz`,
  library checksum/source, backend, and `-xsmall`/hardmask policy.
- RepeatMasker custom library headers preserve useful `#class/subclass` labels when
  class-level summaries matter, and `-pa` is translated into actual backend CPU use
  before SLURM resources are chosen.
- Merged/deduplicated repeat libraries record raw inputs, sequence type, command
  (`cd-hit-est` for nucleotide TE libraries, `cd-hit` for protein FASTA), `-c`,
  `-n`, coverage thresholds such as `-aS`, `.clstr`, counts before/after, and
  checksums.
- DeepTE refinement of EDTA `LTR/unknown` has backups, non-empty ID lists,
  `LTR_unknown.fa`, `LTR_known.fa`, DeepTE output, normalized `LTR_unknown_DeepTE.fa`,
  updated TElib checksum, and a recorded EDTA re-annotation decision.
- DeepTE records species mode/model directory, family mode, output directory, and
  probability threshold; it is used here for unknown TE classification, not primary
  repeat discovery.
- solo/intact LTR ratios are tied to the exact TElib and EDTA/RepeatMasker `.out`
  file; large sorted joins have disk estimates and are not run on admin/login nodes.
- TE density and flanking-gene/metagene profiles use 0-based half-open BED
  coordinates, validated feature-type names, explicit window/bin sizes, and saved
  TSV plus figure outputs.
- TEsorter output has non-empty intact-LTR FASTA, class table, domain table, domain
  FASTA/GFF, database name, coverage, e-value, and command name (`TEsorter` or
  `tesorter`) recorded.
- TEsorter element mode versus genome mode is explicit; for plant intact LTRs use
  extracted TE/LTR sequences with a plant database such as `rexdb-plant`, and state
  the expected bias against no-domain/non-autonomous or highly divergent elements.
- RT-domain trees record target superfamily/domain, extracted sequence count,
  domain naming scheme, MAFFT alignment, IQ-TREE2 model/bootstrap settings, and ID
  mapping back to LTR coordinates or insertion-time records.
- Any `--overwrite 1`, TElib replacement, rerun into non-empty directories, external
  model download, or write into protected paths has explicit user confirmation.

## Genome annotation checklist

- Genome FASTA, `.fai`, repeat annotation, masked FASTA, gene GFF3, CDS, protein,
  transcript FASTA, and functional tables all use the same assembly version and
  chromosome names.
- Repeat annotation source is explicit: EDTA, RepeatModeler/RepeatMasker, or both with
  separate purposes; partial repeat outputs are not treated as final.
- RNA/protein evidence provenance is recorded, including species, tissue/stage,
  strandedness, database/source version, and filtering policy.
- For each predictor or evidence wrapper, official docs/GitHub or local installed
  source were checked for the exact mode used; record source URL/path, check date,
  tool version/container, and command-line mode.
- Protein homology evidence uses a target-appropriate taxonomic scope, such as
  same genus/family/order/clade depending on the organism and data availability; do
  not reuse quinoa's Caryophyllales library for unrelated taxa.
- EviAnn/BRAKER3 shared protein libraries have a manifest with taxon rationale,
  source databases/species, build date, sequence counts before/after filtering,
  header-cleaning rule, deduplication rule, and checksum.
- Protein evidence is large and diverse enough to represent many protein families
  with multiple related-species representatives, not a tiny hand-picked convenience
  set or an uncontrolled duplicate/isoform dump.
- Predictor work directories are unique per run or array task; no concurrent tasks
  write into the same BRAKER/MAKER/AUGUSTUS/GeneMark output directory.
- HISAT2/StringTie RNA evidence is mode-compatible: HISAT2 `--dta` is used for
  downstream transcript assembly, BAMs are coordinate-sorted and indexed, STAR
  alternatives carry transcript-strand tags when needed, and StringTie `--mix` input
  order is recorded if short and long reads are combined.
- BRAKER3 evidence mode is explicit: softmasked genome, RNA BAM source, protein
  library scope, unique species/work directory, container/version, and any
  BUSCO/compleasm-assisted prediction mode are recorded.
- AUGUSTUS training is reproducible: source GFF3/FASTA, GenBank conversion route,
  raw/filtered locus counts, random train/test split, species name, project-local
  `AUGUSTUS_CONFIG_PATH`, and `optimize_augustus.pl` decision are recorded.
- TransDecoder outputs are tied to transcript evidence, not treated as standalone
  genome gene predictions; LongOrfs/Predict or wrapper mode, homology-retention
  settings, `--single_best_only` policy, and genome-projection route are recorded.
- SPALN/miniprot-style protein-to-genome evidence records database/index mode,
  output GFF3 mode, species/table or intron settings, version, and sorted
  evidence-GFF output path.
- GFF3 validates structurally: required feature types exist, `ID`/`Parent` links are
  consistent, CDS phases are valid, and coordinates are within contig lengths.
- Gene, transcript, exon, CDS, protein length, isoform-per-gene, and gene-density
  summaries are generated and checked for repeat-driven inflation or truncation.
- Released protein FASTA has protein-mode BUSCO with lineage, mode, version, and
  database identity reported.
- Functional annotation keeps raw hits, filtered hits, final merged gene-function
  table, database versions, thresholds, and merge priority separate and reproducible.
- Final release includes ID mapping if any gene/transcript IDs were renamed after
  prediction.
- Annotation conclusions separate structure quality, expression evidence, homology
  evidence, and functional labels; weak single-hit labels are not overclaimed.
- For multi-accession batches, the intended sample manifest or regex is checked
  against observed summary rows; non-sample directories are not allowed in sample
  summaries.
- Batch GFF3/BUSCO summaries include a `status` column, and any non-`ok` value such
  as `ambiguous_gff`, `no_gff`, `missing_pep`, `busco_failed`, `no_short_summary`,
  or `parse_failed` blocks cross-sample interpretation until resolved.
- EviAnn-style outputs report evidence composition (`complete`, `transcript_only`,
  `protein_only`, and other evidence classes) rather than only total gene counts.
- BRAKER3 batch outputs use unique per-task working directories and species names;
  shared BRAKER/AUGUSTUS working directories are treated as collision risks.
- Protein BUSCO summaries use protein mode, exact lineage path/version, marker count,
  and intended sample set; high duplicated BUSCOs are interpreted with ploidy and
  subgenome context.

## Figure acceptance checklist

- Arial or acceptable sans-serif font is used consistently.
- Background is pure white; major and minor grids are removed.
- Top and right spines are removed unless the plot type requires them.
- Tick marks point outward and axis linewidth is 0.5-0.75 pt.
- Palette is colorblind-aware and avoids pure red/pure blue as dominant colors.
- Legend does not hide data and repeated groups keep the same colors across panels.
- Axis labels include units where relevant, such as Mb, FPKM, or `-log10(P)`.
- PDF is exported first; PNG/JPEG is at least 300 dpi when raster output is needed.
- Plotting data, code, and parameters are saved with the figure.
- English figure legend draft states design, data source, and statistical method.

## Skill-maintenance checklist

- Keep `SKILL.md` as the single official entry point (the skill loader reads only this file).
- Run quick validation:
  `python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py /data9/home/qgzeng/.codex/skills/<skill-folder>`.
- For script changes, run `bash -n` and at least one representative positive and
  negative test.
