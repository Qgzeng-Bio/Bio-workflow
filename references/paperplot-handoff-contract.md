# Bioflow → PaperPlot handoff contract

Bioflow validates biological readiness, provenance, units, sample ordering, and
key-sample selection. PaperPlot remains responsible for figure family, design
brief, plotting, export, rendered-image QA, and manuscript-readiness review.
Bioflow does not copy or modify PaperPlot templates.

For a multi-metric genome-quality figure, prepare the handoff before delegating:

```bash
python3 scripts/prepare_paperplot_handoff.py \
  --input Genome_Quality_Metrics.tsv \
  --output-tsv FigA_PaperPlot_Input.tsv \
  --output-json FigA_PaperPlot_Handoff.json \
  --figure-role publication \
  --max-key-samples 8
```

Outputs are refused when they already exist. `--force` is an overwrite action and
requires complete affected-path/risk disclosure plus `confirm_action` approval.
It cannot target an input, symlink, conflicting output, missing parent, or
`/data9/home/*/data|tools`.

## Input TSV

Required columns:

```text
Sample_ID\tMetric\tValue\tUnit\tDirection
```

Optional columns:

```text
Group\tWeight\tHighlight\tEvidence_Path\tClaim_Status
```

Rules:

- Input must be genuinely tab-delimited; CSV or a comma-packed single column is
  refused.
- `Value` and optional `Weight` must be finite numbers; weight must be positive.
- Every metric has one non-empty `Unit`, one normalized `Direction`, and one
  consistent weight. Units are never guessed from names such as N50 or genome
  size.
- Directions normalize to `Higher_better`, `Lower_better`, or `Neutral`.
- Each `Sample_ID + Metric` occurs once. Summarize repeated observations upstream
  under a declared statistical method; no plotting-layer silent mean is allowed.
- A sample has at most one `Group`. `Highlight` is an explicit boolean.
- `Claim_Status`, when present, is `supported`, `uncertain`, or `blocked`.
  Publication handoffs reject uncertain/blocked rows.
- A supplied `Evidence_Path` resolves relative to the input TSV directory.
  Publication handoffs reject missing/unreadable evidence and, in layout v2,
  any evidence under disposable `tmp/`.

TSV tables use English initial-capital underscore column names and retain atomic
sample/metric IDs exactly.

## Units

The default is no conversion: number and label remain exactly in the declared
unit (apart from canonical numeric formatting). Optional targets use:

```text
Metric\tSource_Unit\tTarget_Unit
```

```bash
python3 scripts/prepare_paperplot_handoff.py ... \
  --unit-targets Unit_Targets.tsv
```

Only audited linear length conversions among `bp`, `kb`, `Mb`, and `Gb` are
supported. The observed source must match exactly. Conversion changes both the
number and label and records the factor in JSON. Unknown conversions fail; the
script never relabels an unchanged number.

## Heterogeneous metric ranking

Raw N50, BUSCO%, QV, gap count, genome size, and other heterogeneous values are
never averaged together.

1. Calculate tie-aware fractional ranks **within each directional metric**.
2. Make `Higher_better` and `Lower_better` both score from 1 (best) to 0 (worst).
3. Exclude `Neutral` metrics from aggregate quality rank.
4. Combine available within-metric scores using the metric's consistent weight
   (default 1).
5. Report each sample's `Metric_Coverage`; missing metrics are also listed in JSON.

This is coverage-aware ordering, not a claim that metric scales are biologically
exchangeable. PaperPlot receives the rank and does not rerun a raw-value mean.

## Key samples

Selection is deterministic and bounded by `--max-key-samples`:

1. all explicit `Highlight=true` samples;
2. global best and worst aggregate ranks;
3. the best ranked sample in each non-empty group;
4. alternating high/low rank extremes until the limit.

If highlights alone exceed the limit, the script stops. Reasons are emitted in
`Key_Reason` and JSON. PaperPlot must use `Key_Sample` rather than selecting labels
from heterogeneous raw-value means.

## Outputs

The output TSV contains the normalized input plus:

```text
Rank_Score\tMetric_Coverage\tKey_Sample\tKey_Reason
```

The JSON records:

- input and optional unit-target SHA256;
- figure role and readiness;
- metric unit/direction/weight specs;
- conversion factors;
- ranking method and per-metric/sample ranks;
- missing metrics;
- key-sample reasons.

Both outputs are staged, flushed/fsynced, and replaced as a pair. Output ordering
and JSON serialization are deterministic for an unchanged input.

## PaperPlot delegation

Pass the handoff TSV and JSON to the installed `paperplot-skills`. Within qgzeng
projects, generated plotting code must read the handoff as TSV (`read.delim` or an
equivalent explicit tab reader) and preserve `Key_Sample`/sample order. Do not
copy a stock CSV path into the local script or silently convert the sidecar to
CSV. PaperPlot then performs its normal figure-selection, design, PDF/PNG export,
strict rendered-image QA, and old-vs-new review. A retained layout-v2 figure is
organized as `results/<module>/figures/FNNN_Name/`: formal PDF/PNG and README at
package root, exact plotting TSV under `source-data/`, generated MD/JSON checks
under `checks/`, and draft alternatives under the matching tmp route.
