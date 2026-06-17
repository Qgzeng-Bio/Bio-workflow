#!/usr/bin/env python3
"""Look up bio-workflow program cards by program name or alias."""

from __future__ import annotations

import argparse
import csv
import shlex
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY = REPO_ROOT / "references" / "program-cards" / "registry.tsv"
ONBOARDING = "references/program-cards/program-onboarding.md"
ONBOARDING_TOOL = "scripts/program_onboard.py"


def normalize(text: str) -> str:
    return " ".join(text.strip().lower().replace("_", "-").split())


def load_registry(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return list(reader)


def aliases_for(row: dict[str, str]) -> set[str]:
    values = {row["Program_Key"], row["Display_Name"]}
    values.update(alias.strip() for alias in row["Aliases"].split(",") if alias.strip())
    return {normalize(value) for value in values if value.strip()}


def find_matches(query: str, rows: list[dict[str, str]]) -> list[dict[str, str]]:
    needle = normalize(query)
    matches = []
    for row in rows:
        aliases = aliases_for(row)
        if needle in aliases or any(needle and needle in alias for alias in aliases):
            matches.append(row)
    return matches


def print_match(row: dict[str, str]) -> None:
    print(f"Status\tMATCH")
    print(f"Program_Key\t{row['Program_Key']}")
    print(f"Display_Name\t{row['Display_Name']}")
    print(f"Card_Path\t{row['Card_Path']}")
    print(f"Modes\t{row['Modes']}")
    print(f"Aliases\t{row['Aliases']}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Look up a bio-workflow program card by program name or alias."
    )
    parser.add_argument("program", help="Program name or alias, for example BUSCO or syri")
    parser.add_argument(
        "--registry",
        default=str(REGISTRY),
        help="Path to program-card registry TSV",
    )
    args = parser.parse_args()

    registry = Path(args.registry)
    if not registry.exists():
        print(f"Status\tERROR")
        print(f"Reason\tRegistry not found: {registry}", file=sys.stderr)
        return 2

    rows = load_registry(registry)
    matches = find_matches(args.program, rows)
    if len(matches) == 1:
        print_match(matches[0])
        return 0
    if len(matches) > 1:
        print("Status\tAMBIGUOUS")
        for row in matches:
            print(f"Candidate\t{row['Program_Key']}\t{row['Card_Path']}\t{row['Modes']}")
        return 1

    print("Status\tUNKNOWN")
    print(f"Program\t{args.program}")
    print(f"Next\tpython3 {ONBOARDING_TOOL} probe {shlex.quote(args.program)}")
    print(f"Reference\tRead {ONBOARDING}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
