# Install proposal

- Program key: `kmeria`
- Package name: `KMERIA`
- Version spec: `latest available`
- Source type: `github`
- Install method: `github_proposal_only`
- Target env: `bio_kmeria`
- Network required: `True`
- Created at: `2026-06-17T14:53:28+08:00`

## Channels

- `conda-forge`
- `bioconda`
- `defaults`

## Commands

No automatic install command is supported for this source type.

## Expected writes

- No automatic writes are defined by third-version onboarding.

## Risk notes

- This source type is proposal-only in program_onboard.py.
- Review official installation instructions and confirm target paths before any manual action.
- Do not write under /data9/home/qgzeng/tools/ without separate confirmation.

## Confirmation gate

Run only after review:

```bash
python3 scripts/program_onboard.py install --proposal reports/program-onboarding/kmeria/20260617T145326/install_proposal.json --yes
```
