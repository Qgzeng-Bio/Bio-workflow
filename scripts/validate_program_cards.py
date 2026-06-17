#!/usr/bin/env python3
"""Validate bio-workflow program-card registry and card structure."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CARD_DIR = REPO_ROOT / "references" / "program-cards"
DRAFT_DIR = CARD_DIR / "drafts"
REGISTRY = CARD_DIR / "registry.tsv"
REQUIRED_FILES = [
    CARD_DIR / "README.md",
    CARD_DIR / "template.md",
    CARD_DIR / "program-onboarding.md",
    CARD_DIR / "install-proposal-template.md",
    CARD_DIR / "evidence-bundle-schema.md",
    REGISTRY,
]
NON_CARD_MARKDOWN = {
    "README.md",
    "template.md",
    "program-onboarding.md",
    "install-proposal-template.md",
    "evidence-bundle-schema.md",
}
REQUIRED_HEADINGS = [
    "Supported modes",
    "Environment preflight",
    "Required inputs by mode",
    "Input preparation",
    "Parameter negotiation",
    "Resource model",
    "Script generation notes",
    "Acceptance checks",
    "Common failures and recovery",
    "Evidence grade",
]
EVIDENCE_GRADES = {
    "project_history",
    "local_help",
    "local_run",
    "official_doc",
    "github_readme",
    "inferred",
}


def fail(message: str, errors: list[str]) -> None:
    errors.append(message)


def read_registry(errors: list[str]) -> list[dict[str, str]]:
    if not REGISTRY.exists():
        fail(f"missing registry: {REGISTRY}", errors)
        return []
    with REGISTRY.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        required = ["Program_Key", "Display_Name", "Aliases", "Card_Path", "Modes", "Status"]
        if reader.fieldnames != required:
            fail(f"registry header must be: {required}", errors)
            return []
        return list(reader)


def headings(markdown: str) -> set[str]:
    found = set()
    for line in markdown.splitlines():
        match = re.match(r"^##\s+(.+?)\s*$", line)
        if match:
            found.add(match.group(1))
    return found


def list_values(cell: str) -> list[str]:
    return [item.strip() for item in cell.split(",") if item.strip()]


def validate_card(row: dict[str, str], errors: list[str]) -> None:
    rel_path = row["Card_Path"]
    card_path = REPO_ROOT / rel_path
    if not card_path.exists():
        fail(f"{row['Program_Key']}: missing card {rel_path}", errors)
        return

    text = card_path.read_text(encoding="utf-8")
    found = headings(text)
    for heading in REQUIRED_HEADINGS:
        if heading not in found:
            fail(f"{rel_path}: missing heading '## {heading}'", errors)

    grades_present = {grade for grade in EVIDENCE_GRADES if grade in text}
    if not grades_present:
        fail(f"{rel_path}: no recognized evidence grade labels found", errors)

    for mode in list_values(row["Modes"]):
        if mode not in text:
            fail(f"{rel_path}: registry mode '{mode}' not mentioned in card", errors)

    if "../software-resource-cards.md" not in text:
        fail(f"{rel_path}: does not reference ../software-resource-cards.md", errors)


def validate_draft(path: Path, errors: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    lower_text = text.lower()
    found = headings(text)
    rel_path = str(path.relative_to(REPO_ROOT))
    for heading in REQUIRED_HEADINGS:
        if heading not in found:
            fail(f"{rel_path}: missing heading '## {heading}'", errors)

    grades_present = {grade for grade in EVIDENCE_GRADES if grade in text}
    if not grades_present:
        fail(f"{rel_path}: no recognized evidence grade labels found", errors)

    if "local_run" in text or "project_history" in text:
        fail(f"{rel_path}: draft must not claim local_run or project_history evidence", errors)

    if "not registered" not in lower_text or "registry.tsv" not in text:
        fail(f"{rel_path}: draft does not state registry review/registration status", errors)

    if "Evidence bundle:" not in text:
        fail(f"{rel_path}: draft does not reference an evidence bundle", errors)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate program-card registry, active cards, and optional drafts.")
    parser.add_argument(
        "--check-drafts",
        action="store_true",
        help="Also validate draft cards under references/program-cards/drafts.",
    )
    args = parser.parse_args()

    errors: list[str] = []

    for path in REQUIRED_FILES:
        if not path.exists():
            fail(f"missing required file: {path.relative_to(REPO_ROOT)}", errors)

    rows = read_registry(errors)
    seen_keys: set[str] = set()
    seen_aliases: dict[str, str] = {}

    for row in rows:
        key = row["Program_Key"]
        if key in seen_keys:
            fail(f"duplicate Program_Key: {key}", errors)
        seen_keys.add(key)

        if row["Status"] != "active":
            fail(f"{key}: unsupported Status '{row['Status']}'", errors)

        aliases = [key, row["Display_Name"], *list_values(row["Aliases"])]
        for alias in aliases:
            norm = alias.strip().lower()
            if not norm:
                continue
            owner = seen_aliases.get(norm)
            if owner and owner != key:
                fail(f"alias '{alias}' used by both {owner} and {key}", errors)
            seen_aliases[norm] = key

        validate_card(row, errors)

    card_files = {
        str(path.relative_to(REPO_ROOT))
        for path in CARD_DIR.glob("*.md")
        if path.name not in NON_CARD_MARKDOWN
    }
    registered = {row["Card_Path"] for row in rows}
    for extra in sorted(card_files - registered):
        fail(f"card not registered: {extra}", errors)

    draft_count = 0
    if args.check_drafts and DRAFT_DIR.exists():
        for draft in sorted(DRAFT_DIR.glob("*.md")):
            draft_count += 1
            validate_draft(draft, errors)

    if errors:
        print("Program card validation: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    if args.check_drafts:
        print(f"Program card validation: PASS ({len(rows)} active cards, {draft_count} draft cards)")
    else:
        print(f"Program card validation: PASS ({len(rows)} active cards)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
