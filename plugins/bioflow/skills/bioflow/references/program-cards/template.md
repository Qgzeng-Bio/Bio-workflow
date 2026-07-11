# Program card template

Use this template when adding a new program card. Keep the card focused on
program-specific behavior; shared resource and validation rules stay in
`../software-resource-cards.md` and `../validation-checklists.md`.

After creating a card, add it to `registry.tsv` and run:

```bash
python3 scripts/validate_program_cards.py
```

## Supported modes

- `mode_name`: one-line purpose and output type.

## Environment preflight

- Check `command -v <program>` before assuming availability.
- Record `<program> --version` or the closest supported version command.
- Record `<program> --help`/`-h` evidence when syntax matters.
- Check only explicit Conda envs, modules, containers, or tool paths.
- Do not install or download without user confirmation.

## Required inputs by mode

- `mode_name`: required files, indexes, manifests, and compatibility constraints.

## Input preparation

- Required indexes or converted files.
- Naming, coordinate, or format constraints.
- Output directory and overwrite rules.

## Parameter negotiation

- Must ask: parameters that change biological interpretation or large resource use.
- Can infer: parameters safely derived from file type, mode, or manifest.
- Must record: defaults that affect reproducibility.

## Resource model

- Link to `../software-resource-cards.md` when the tool is covered.
- Summarize only tool-specific resource traps not covered there.
- Prefer a pilot for unknown memory, disk, or scaling behavior.

## Script generation notes

- Environment activation or absolute binary paths.
- Thread variable handling.
- Log, temp, and output path conventions.
- Rerun and overwrite behavior.

## Acceptance checks

- Required outputs and non-empty checks.
- Summary metrics to parse.
- Format, coordinate, ID, or sample-count consistency checks.
- Logs/version/provenance required for reproducibility.

## Common failures and recovery

- Failure symptom.
- Minimal diagnosis.
- Minimal safe recovery.
- When rerun is required.

## Evidence grade

Use these labels on critical parameters or operational claims:

- `project_history`
- `local_help`
- `local_run`
- `official_doc`
- `github_readme`
- `inferred`
