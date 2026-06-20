# Resource feedback and sizing

Use this reference when sizing CPU, memory, partition, and array concurrency, or
when a pilot/benchmark result should change the next resource request. Pair it
with `references/software-resource-cards.md` for tool-specific starting points and
`references/validation-checklists.md` for acceptance gates.

## Contents

- Resource model
- Feedback loop
- Server partition defaults

## Resource model

Do not request CPU or memory by habit. Estimate from:

- input size and record count
- algorithm memory model
- thread scalability
- temporary file expansion
- per-thread memory settings
- array concurrency
- current queue state
- previous job history when available

Prefer manifests, indexes, metadata, file sizes, and previous `sacct` or
`/usr/bin/time -v` records. Do not estimate resources by full recursive scans or
full streaming/decompression of FASTA, FASTQ, BAM/CRAM, VCF/BCF, or GFF/GTF
inputs on login/admin nodes. If metadata are missing and the estimate depends on
reading large files, propose a bounded SLURM precheck or ask the user for the
manifest/index path.

Use this reasoning pattern:

```text
Resource request = base memory for input/index/database
                 + per-thread memory * useful threads
                 + temporary/output headroom
```

Classify software before choosing CPU:

- mostly single-threaded: request 1-4 CPUs
- moderately parallel: request 4-16 CPUs
- strongly parallel and proven to scale: request 16-32 CPUs
- I/O-bound or memory-bound: keep CPUs conservative and protect disk bandwidth
- per-thread-memory tools such as sorting: calculate `threads * memory_per_thread`

Examples:

- `samtools sort`: total memory is approximately `-m * threads`.
- Aligners such as `minimap2`, `bwa`, `hisat2`, and `STAR`: CPU can help, but
  memory depends on reference/index size and mode.
- `blast`, `diamond`, and HMM searches: database size and output volume often
  dominate memory and disk.
- Assemblers, repeat annotation, pangenome construction, and orthology clustering
  can be memory-heavy; require explicit sizing or a pilot.
- R/Python plotting and summarization usually need 1-4 CPUs unless using real
  parallel code.
- Use `pigz` only when parallel I/O is helpful.

When uncertain, propose a small pilot or benchmark before the full run.

For repeat annotation, genome annotation, pangenome workflows, unknown tools,
multi-sample/multi-file pipelines, and workflow engines such as Nextflow,
Snakemake, or WDL, do not scale directly from a template to a full run unless
there is relevant historical `sacct` or `/usr/bin/time -v` evidence. Require a
pilot or explicitly state why existing evidence is sufficient.

For workflow engines, separate the resource model:

- driver resources: launcher CPU/memory, logs, executor overhead, and whether it
  performs real compute or only schedules jobs
- process resources: per-process `cpus`, `memory`, threads, Java heap, container
  overhead, and temporary expansion
- concurrency: job arrays, `queueSize`, simultaneous processes, shared database
  pressure, and total concurrent memory (`per_task_memory * concurrency`)
- outputs: `workDir`, publish directory, trace/report files, cleanup policy, and
  temporary disk growth

## Minimum SLURM script review

When reviewing an existing SLURM script, always give a short resource verdict. Do
not treat the presence of `#SBATCH --cpus-per-task` and `#SBATCH --mem` as enough.

Check at minimum:

- requested CPUs vs tool scalability and whether threads are passed to the tool
- requested memory vs the main memory driver: input, index/database, per-thread
  buffers, Java heap, sorting memory, temporary expansion, or output volume
- partition vs memory: `<200G` usually `normal`; `>=200G` consider `fat/fat2`
- array concurrency vs combined memory, disk I/O, and shared database pressure
- previous `sacct`/`/usr/bin/time -v` evidence when a related job already ran

If any part cannot be estimated from the script and explicit inputs, say so and
recommend a bounded pilot rather than silently accepting the template resources.

## Feedback loop

Unknown or poorly characterized tools must go through a feedback loop before the
full run:

1. Run a small pilot or benchmark with `/usr/bin/time -v` and preserved stderr.
2. After completion, parse SLURM accounting and time logs:

   ```bash
   scripts/resource_usage_audit.sh --script <slurm_script> --jobid <jobid> --time-log <stage.time.log> --stage <stage_name>
   ```

3. Use observed `Percent of CPU`, `MaxRSS`, and walltime to choose the next
   `--cpus-per-task`, `--mem`, and array `%N` cap.

Decision rules:

- If `Estimated_Used_CPUs ~= PercentCPU / 100` is far below requested CPUs, reduce
  the next request toward the measured effective CPU count.
- If `/usr/bin/time -v` reports non-zero `Exit status`, triage the failure before
  down-tuning resources.
- If requested CPUs are `> 4` and CPU efficiency is `< 50%`, treat the job as
  `CPU_OVERREQUEST` unless there is a known bursty or phased parallel step.
- If 4/8/16-thread benchmark walltime improves by `< 15%` at higher thread counts,
  choose the smallest thread count within 15% of the fastest run.
- If `MaxRSS / requested memory < 35%`, warn as `MEM_OVERREQUEST`, but do not
  lower memory without another pilot or input-size scaling evidence.
- For independent samples, chromosomes, or files, prefer a SLURM array with a
  concurrency cap over one oversized serial job.
- Bundled array templates expect headerless manifest files. If a manifest has
  `Sample_ID`, `Input_1`, `Chunk_ID`, or similar headers, remove the header or
  adjust task-line indexing before submission.

Use this read-only audit before rewriting real project scripts:

```bash
scripts/parallelization_audit.sh --script <slurm_script> --manifest <manifest.tsv> --mode auto
```

## Server partition defaults

- `< 200G` memory: prefer `normal`, usually up to about 16 CPUs.
- `>= 200G` memory: consider `fat` or `fat2`, often 16-32 CPUs, after checking
  queue state.
- `debug`: use only tiny tests, dry runs, and fast validation. A short `--time`
  is acceptable here when helpful or required.
- `high`: use only when user/project policy or queue state justifies it.
- Unknown memory: ask or run a bounded pilot; do not guess with maximum resources.

Do not add `#SBATCH --time` by default for `normal`, `fat`, `fat2`, or `high`.
If an existing script has a short walltime, warn that it may cause `TIMEOUT`.
