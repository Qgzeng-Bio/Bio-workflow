# Result manifest schema

`scripts/check_result_contract.py` consumes a `result_manifest.yaml` that
captures a single evaluation/finishing run. The schema is intentionally
narrow: every metric must carry the provenance fields its rule set requires
in `references/interpretation-rules.tsv`. Missing fields are reported as
`MISSING` (treated as a soft block on publication-grade claims).

The fields below are derived from the **real** quinoa V2 evaluation outputs
under `/data9/home/qgzeng/projects/2-C_quinoa/7-Genome-evalution/`, not
invented. See "Real output anchoring" below for the source files.

## Top-level shape

```yaml
schema_version: result_manifest.v1
analysis_id: <str>             # e.g. "quinoa_v2_post_finishing"
project: <str>                 # used to look up matching anchors
created_at: <ISO-8601>
created_by: <str>              # tool that produced this manifest

assemblies:
  - key: <str>                 # short identifier, e.g. Cqu_final / hap1 / hap2
    role: primary | phased_haplotype | scaffolded | other
    fasta: <path>              # absolute or project-relative
    contig_N50: <int?>         # bp, if known
    scaffold_N50: <int?>       # bp, only if scaffolding ran
    total_length: <int>
    n_contigs: <int?>
    gaps: <int?>

busco:                          # one entry per (assembly, lineage) pair
  - assembly_key: <str>
    lineage: <str>              # e.g. embryophyta_odb12  -- REQUIRED
    mode: genome | protein | transcriptome   # REQUIRED
    db_version: <str>           # e.g. "2025-07-01" -- REQUIRED
    busco_version: <str>        # e.g. "6.0.0"
    n_busco: <int>              # total markers in the lineage
    C: <float>  S: <float>  D: <float>  F: <float>  M: <float>
    short_summary: <path?>      # path to short_summary.specific.*.txt or .json

merqury:
  - assembly_key: <str>
    k: <int>                    # REQUIRED -- different k cannot be ranked
    read_db_type: illumina_pcrfree | illumina_other | hifi | hybrid | unknown   # REQUIRED
    read_db_path: <path?>       # the read.meryl directory
    coverage: <float?>          # x-coverage of the read database, if recorded
    independence: <bool?>       # false if read_db built from same reads as assembly input
    QV: <float>                 # aggregate QV
    error_rate: <float?>
    qv_file: <path?>            # path to result_<key>.qv

lai:
  - assembly_key: <str>
    LAI: <float>                # whole_genome value (first row of *.out.LAI)
    raw_LAI: <float?>
    intact_LTR_RT_pct: <float>  # REQUIRED for ASM_LAI_001 applicability check
    total_LTR_RT_pct: <float>   # REQUIRED for ASM_LAI_001 applicability check
    lai_file: <path?>           # path to <asm>.fa.out.LAI

quast:
  source: <path?>               # path to report.tsv
  per_assembly: {<assembly_key>: {N50: <int>, total: <int>, ...}}

mapping:
  - assembly_key: <str>
    read_type: hifi | ont | illumina
    rate_pct: <float>
    flagstat: <path?>

telomere:
  - assembly_key: <str>
    repeats: <int>              # tidk telomere count
    expected: <int?>            # 2 * n_chromosomes if all ends complete

anchors_compared: [<anchor_name>, ...]   # e.g. ["quinoa_v2_reference_frame"]
```

## Required-field minima per metric

The checker treats the following as MISSING (soft-block) when absent.
"Required" here means "needed before a publication-grade claim is allowed",
not "needed to load the manifest".

| Block | Required fields |
| --- | --- |
| `busco[*]` | `lineage`, `mode`, `db_version`, `C`, `D`, `F`, `M` |
| `merqury[*]` | `k`, `read_db_type`, `QV` |
| `lai[*]` | `LAI`, `total_LTR_RT_pct`, `intact_LTR_RT_pct` |
| `assemblies[*]` | `key`, `fasta`, `total_length`, at least one of `contig_N50` / `scaffold_N50` (labeled) |

## Rule wiring

The checker dispatches one Python function per `rule_id` in
`references/interpretation-rules.tsv`. Each function reads the manifest plus
the anchors file and returns one of:

- `("OK", "")`
- `("WARN", "<one-line caveat with the relevant provenance values inline>")`
- `("BLOCK", "<one-line claim constraint with the offending field values>")`
- `("MISSING", "<dotted.path.to.field>")`

Output is the short, machine-parseable `Field\tValue` style used by
`program_card_lookup.py` so a downstream LLM can parse it without a heavy
template.

## Real output anchoring (do not edit unless the source files change)

| Tool | Real file | Format | Source-of-truth field on disk |
| --- | --- | --- | --- |
| BUSCO v6 | `busco_<lineage>/short_summary.specific.<lineage>.<run>.txt` (and `.json`) | KEY: VALUE / JSON | `results.{Complete,Duplicated,Fragmented,Missing}` + lineage metadata |
| Merqury | `result_<key>.qv` (aggregate) | 5-col TSV no header | `assembly  n_mismatch  total_bp  QV  error_rate` |
| Merqury per-contig | `result_<key>.<asm>.qv` | 5-col TSV no header | one row per chromosome |
| LAI | `<asm>.fa.out.LAI` | 7-col TSV with header | first row `whole_genome` carries the genome-wide `LAI`; per-1Mb windows below |
| QUAST | `quast/report.tsv` | 2-col TSV | metric / value pairs |
| FAI | `<asm>.fa.fai` | 5-col TSV | `name length offset linebases linewidth` |

`scripts/collect_metrics.py` (Phase 3, not in this commit) will populate the
manifest from these files. Until then, manifests are hand-authored or
filled by an upstream pipeline.
