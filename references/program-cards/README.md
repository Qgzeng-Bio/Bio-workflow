# Program cards

Program cards handle requests where the user names a single program before giving
a full workflow, for example "run BUSCO" or "run SyRI". They are not replacements
for playbooks. A playbook starts from a biological objective; a program card starts
from a tool and forces the missing mode, inputs, parameters, resources, and
acceptance checks into the conversation.

## How to use

1. Match the program name to a card with `registry.tsv` or:

   ```bash
   python3 scripts/program_card_lookup.py <program_name>
   ```

2. If a card exists, read it before writing commands.
3. If no card exists, use `program-onboarding.md` and start with:

   ```bash
   python3 scripts/program_onboard.py choose <program_name>
   python3 scripts/program_onboard.py probe <program_name>
   ```

   `choose` records install/source/pilot choices under `config/program-onboarding/`
   and does not install or download anything. Generate install proposals with
   `plan-install`; execute only with
   `install --proposal <json> --yes` after confirmation; then run `capture` and
   `draft-card` before any registry promotion. Choice and evidence outputs stay
   project-local by default; draft cards stay under `references/program-cards/drafts/`
   unless `--output-card` is supplied, and draft generation will not overwrite an
   existing draft unless `--force` is supplied.
4. Always select a supported mode before deciding inputs or resources.
5. Ask for explicit input paths, a manifest, or a bounded search root plus pattern
   and maxdepth. Do not scan broad data or project roots.
6. Generate an auditable script and run the SLURM safety layer before submission:
   `gen_sbatch.sh`, `slurm_preflight.sh`, `prepare_submission.sh`, and only after
   confirmation `submit_and_log.sh`.
7. Validate outputs with the card-specific acceptance checks plus
   `../validation-checklists.md`.

## Card index

The authoritative card index is `registry.tsv`. Keep aliases, modes, and card
paths there so lookup can be checked mechanically.

Current cards:

- `busco.md`
- `minimap2-samtools.md`
- `syri.md`
- `biser.md`
- `kmeria.md`

After adding or editing a card, run:

```bash
python3 scripts/validate_program_cards.py
python3 scripts/validate_program_cards.py --check-drafts
```

## Evidence grades

- `project_history`: Proven by this server or a real project run.
- `local_help`: Verified from local `--help`, `-h`, or `--version`.
- `local_run`: Verified by a local pilot or completed run.
- `official_doc`: Taken from official documentation or manual.
- `github_readme`: Taken from a GitHub README or release note.
- `inferred`: Reasoned from input type, resource behavior, or domain experience.
  Mark this explicitly and upgrade it after a local proof.

## Mode-driven rule

Do not treat a program name as a runnable plan. A program may have several modes
with different input contracts and resource shapes. Confirm the mode, then narrow:

```text
program -> mode -> input type -> parameters -> resources -> script -> preflight -> run -> acceptance
```

If the user cannot identify the input location, ask for one of:

- exact file paths
- a manifest
- a bounded search root, filename pattern, and maxdepth

Do not install software, download databases, mutate Conda environments, or write
under `/data9/home/qgzeng/tools/` without user confirmation.
