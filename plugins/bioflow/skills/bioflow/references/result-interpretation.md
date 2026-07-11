# Result interpretation contract

Use this contract after technical acceptance and before biological narrative,
figures, downstream decisions, or manuscript claims.

## Evidence ladder

1. **Run evidence:** job/program ended as expected; logs and job IDs are complete.
2. **Data evidence:** expected files, samples, formats, counts, coordinates, and
   reference versions are correct.
3. **Analysis evidence:** tool-specific QC and acceptance gates pass.
4. **Biological evidence:** the result is robust to relevant confounders and is
   biologically interpretable within the design.
5. **Claim evidence:** every statement cites specific accepted outputs and carries
   the caveats required by `check_result_contract.py`.

Passing a lower layer never proves a higher one. In particular, exit code zero and
non-empty files do not prove biological validity.

## Statement categories

- **Observation:** a direct, reproducible description of accepted data, including
  metric, unit, sample/reference, method, and evidence path.
- **Interpretation:** a reasoned explanation supported by observations and an
  applicable method or rule. State alternatives and relevant confounders.
- **Hypothesis:** a testable biological possibility that exceeds current evidence.
  State what additional experiment or analysis would support or reject it.
- **Limitation:** a known boundary caused by design, sampling, method, reference,
  mapping, batch, coordinate, or rule-coverage constraints.

Do not rewrite an Interpretation or Hypothesis as an Observation. Do not describe
association, overlap, enrichment, or prediction as causation without an explicit
causal design and evidence.

## Claim record

For important claims, add a `claims` entry to `result_manifest.yaml`:

```yaml
analysis_types: [assembly_evaluation]
claims:
  - claim_id: ASM_001
    category: Observation
    statement: "Cqu_final contig N50 is 70,111,769 bp."
    analysis_type: assembly_evaluation
    evidence_paths:
      - results/QUAST_Summary.tsv
    status: supported
    caveats: []
```

Use `status: uncertain` when evidence, provenance, applicability, or rule coverage
is incomplete. Use `status: blocked` when a `BLOCK` rule fires. Evidence paths must
resolve to readable accepted artifacts; a status row alone is not evidence.

## Checker statuses

- `PASS`: active rules cover every declared/inferred analysis type and no gate
  fired. This permits only claims supported by cited local evidence.
- `WARN`: proceed only with every warning carried into the narrative.
- `BLOCK`: do not make the constrained claim; state the rule and lifting evidence.
- `UNCERTAIN`: rule coverage or required analysis evidence is missing. Report
  observations descriptively, label interpretation uncertain, and do not claim
  publication-grade validation.

Never convert `UNCERTAIN` to `PASS` by omitting `analysis_types`. The checker
infers known types from supported manifest blocks and returns `UNCERTAIN` when it
cannot establish coverage.

## Interpretation output

For each important result, report:

```text
Observation: <direct result with metric/unit/context>
Evidence: <accepted path(s), tool/version, reference/coordinates>
Interpretation: <supported explanation or UNCERTAIN>
Hypothesis: <optional testable extension>
Limitations: <design/method/provenance/rule caveats>
Next validation: <smallest test that would change confidence>
```

Keep prose proportional to evidence. When multiple explanations fit, list them
instead of choosing the most biologically attractive story.
