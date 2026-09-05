# Research Log

Create one Markdown record for each important analysis, interpretation change, sample/reference change, result-selection change, or figure-generation decision.

File naming:

```text
YYYYMMDD_Short_Name.md
```

Examples: `20260811_Assembly_QC.md`, `20260812_Gene_Family_Filter.md`.

Requirements:

1. Copy `TEMPLATE.md` for a new record.
2. Keep `Research_Log_ID` stable and unique (`R001`, `R002`, ...).
3. Make the `Date` field match the filename date.
4. Register every record in `Log_Index.tsv`.
5. Use `Result_Maturity` honestly:
   - `Exploratory`: first look; not citable as stable evidence;
   - `Provisional`: output is stable enough to discuss but not independently reviewed;
   - `Verified`: inputs, commands, outputs, checks, and interpretation were reviewed;
   - `Frozen`: part of an accepted manuscript/publication baseline.
6. A `Verified` or `Frozen` record must not contain `UNKNOWN` placeholders or cite disposable `tmp/` paths as formal output/evidence.
7. Keep exact commands here, not from memory; scheduler-generated diagnostics remain under `logs/`.

`Log_Index.tsv` is the index. Individual Markdown files hold the detailed scientific narrative.
