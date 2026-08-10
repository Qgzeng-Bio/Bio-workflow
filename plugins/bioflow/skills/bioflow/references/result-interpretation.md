# Result interpretation contract

Use this contract after technical acceptance and before biological narrative,
figures, downstream decisions, or manuscript claims.

## Evidence ladder

1. **Run evidence:** program/job ended as expected and logs are complete.
2. **Data evidence:** expected files, samples, formats, coordinates, and references
   are correct.
3. **Analysis evidence:** method-specific QC and acceptance gates pass.
4. **Biological evidence:** the result is robust to relevant design confounders.
5. **Claim evidence:** each statement cites accepted outputs and passes its own
   subject/protocol gate in `result_manifest.v2`.

Passing a lower layer never proves a higher one. Exit code zero and non-empty files
do not establish a biological claim.

## Statement categories

- **Observation:** direct accepted result with metric, unit, subject/reference,
  method/protocol, and evidence path.
- **Interpretation:** explanation supported by observations and an applicable
  method; retain alternatives and confounders.
- **Hypothesis:** testable extension beyond current evidence; state the next test.
- **Limitation:** boundary caused by design, sampling, method, reference, mapping,
  batch, coordinate, or rule coverage.

Do not rewrite interpretation or hypothesis as observation. Association, overlap,
enrichment, and prediction are not causation.

## Claim records

Important statements use the v2 claim interface. For example, a local N50
observation needs only the N50 axis:

```yaml
schema_version: result_manifest.v2
analysis_types: [assembly_evaluation]
claims:
  - claim_id: ASM_N50_OBS_001
    claim_type: metric_observation
    metric: N50
    subjects: [Cqu_final]
    protocol:
      n50_type: contig_N50
    evidence_paths:
      - ../results/QUAST_Summary.tsv
    status: supported
    caveats: []
```

A comparative or overview claim must separately name all subjects and protocol
selectors. Relative evidence paths resolve from the manifest directory. The
checker tests only those paths and never searches for substitute evidence.

Use `status: uncertain` when scope, applicability, or evidence is unresolved. Use
`status: blocked` when a blocking gate is known. Do not label a claim `supported`
merely because a metric block exists; checker warnings/blocks are reported as a
status inconsistency.

## Checker statuses

- `PASS`: every declared v2 claim has complete schema, matching subject/protocol
  records, readable evidence, and no warning/block.
- `WARN`: not publication-grade PASS. Carry every warning into prose; typical
  causes include no explicit claim, incomplete provenance, or non-independent QV.
- `BLOCK`: do not make the constrained claim. State the rule and evidence needed
  to lift it.
- `UNCERTAIN`: active rules cannot decide the claim scope, or the claim itself is
  declared uncertain. Report accepted observations only.

Overall precedence is `BLOCK > UNCERTAIN > WARN > PASS`. Legacy v1 or unversioned
manifests remain readable but cannot receive claim-grade PASS without a manual v2
claim. Never obtain PASS by deleting `analysis_types` or evidence blocks.

## Narrative output

For each important result, report:

```text
Observation: <direct result with unit, subject, and protocol>
Evidence: <manifest claim_id and readable accepted path(s)>
Interpretation: <supported explanation or UNCERTAIN>
Hypothesis: <optional testable extension>
Limitations: <design/method/provenance/rule caveats>
Next validation: <smallest evidence that changes confidence>
```

An `assembly_quality_overview` requires contiguity, BUSCO, QV, LAI, mapping, and
telomere evidence for every subject. This does not prevent an independently
supported single-axis N50/BUSCO/QV observation from being reported at its proper
scope.
