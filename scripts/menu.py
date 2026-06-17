#!/usr/bin/env python3
"""Generic up/down arrow chooser for bio-workflow scripts.

Two public entry points:

- ``ask(title, options, default=0)`` — show a single up/down menu, return the
  selected index. The user can also press ``q`` or ``Esc`` to cancel, which
  raises ``KeyboardInterrupt`` so the caller can decide what to do.

- ``ask_question(question)`` — same behaviour, but driven by a structured
  ``Question`` dataclass that supports per-option descriptions and an optional
  free-text prompt (the canonical "Type something" / "Custom" option). Returns
  ``(option, text)``. This is the shape ``program_onboard.py`` needs.

Design choices that match the rest of the project:

- Pure stdlib (``curses`` is in the Python standard library). No pip install,
  no extra package to track in onboarding.
- Plain-text fallback when stdin/stdout is not a TTY, or when ``curses`` errors
  out (some terminals refuse ``curs_set(0)`` or lack a TERM definition). This
  is essential because bio-workflow scripts get piped, ``< /dev/null``-fed by
  CI, and run under SLURM where there is no terminal at all.
- ``KeyboardInterrupt`` on cancel so the caller can wrap a single ``try``
  around a whole flow rather than checking sentinel return codes.

Demo: ``python3 scripts/menu.py``
"""

from __future__ import annotations

import curses
import sys
from dataclasses import dataclass, field
from typing import Sequence


@dataclass(frozen=True)
class Option:
    """One row in a menu.

    - ``label`` — what the user sees on the highlighted line.
    - ``description`` — optional second line shown indented under the label.
    - ``value`` — opaque identifier the caller wants back. Defaults to ``label``.
    - ``needs_text`` — if True, after the user picks this option the chooser
      switches to a free-text input prompt (``text_prompt``) and returns what
      they typed.
    - ``text_prompt`` — what to print/show when collecting the free-text input.
    """

    label: str
    description: str = ""
    value: str = ""
    needs_text: bool = False
    text_prompt: str = "Enter value: "

    def resolved_value(self) -> str:
        return self.value or self.label


@dataclass(frozen=True)
class Question:
    """A titled set of options with a default."""

    title: str
    options: tuple[Option, ...]
    default_index: int = 0
    help_line: str = "Up/Down to choose, Enter to confirm, q to quit"

    def normalized_default(self) -> int:
        if not self.options:
            raise ValueError("Question has no options")
        if 0 <= self.default_index < len(self.options):
            return self.default_index
        return 0


# ---------------------------------------------------------------------------
# Low-level: simple ask() over plain string options
# ---------------------------------------------------------------------------


def ask(
    title: str,
    options: Sequence[str],
    default: int = 0,
    help_line: str = "Up/Down to choose, Enter to confirm, q to quit",
) -> int:
    """Show an up/down menu with string options. Return the chosen index.

    Raises ``KeyboardInterrupt`` if the user presses ``q`` or ``Esc``.
    """
    if not options:
        raise ValueError("ask() needs at least one option")
    default = default if 0 <= default < len(options) else 0
    question = Question(
        title=title,
        options=tuple(Option(label=str(o)) for o in options),
        default_index=default,
        help_line=help_line,
    )
    chosen, _ = ask_question(question)
    return question.options.index(chosen)


# ---------------------------------------------------------------------------
# Structured: ask_question() over a Question/Option tree
# ---------------------------------------------------------------------------


def ask_question(question: Question) -> tuple[Option, str]:
    """Show a Question. Return (chosen Option, free-text or '').

    The chooser prefers a curses up/down menu when both stdin and stdout are
    TTYs. Otherwise — or when curses fails to initialize — it falls back to a
    numbered prompt, so the same call works under pipes, CI, and SLURM.
    """
    if _interactive() and _curses_supported():
        try:
            return _curses_choose(question)
        except curses.error:
            # Fall back if the terminal can't honor a curses primitive.
            return _plain_choose(question)
    return _plain_choose(question)


# ---------------------------------------------------------------------------
# TTY detection + curses backend
# ---------------------------------------------------------------------------


def _interactive() -> bool:
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except (AttributeError, ValueError):
        return False


def _curses_supported() -> bool:
    # On Linux curses is always importable from the stdlib, but a missing
    # /usr/share/terminfo or TERM=dumb still breaks it. We treat the import
    # check as a cheap probe and let _curses_choose() fall back on errors.
    try:
        import curses  # noqa: F401
    except Exception:
        return False
    return True


def _curses_choose(question: Question) -> tuple[Option, str]:
    def run(stdscr: "curses._CursesWindow") -> tuple[Option, str]:
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        index = question.normalized_default()
        options = question.options
        while True:
            stdscr.clear()
            stdscr.addstr(0, 0, question.title, curses.A_BOLD)
            stdscr.addstr(1, 0, question.help_line)
            width = max(20, curses.COLS - 6)
            row = 3
            positions: list[int] = []
            for i, opt in enumerate(options):
                positions.append(row)
                marker = "> " if i == index else "  "
                attr = curses.A_REVERSE if i == index else curses.A_NORMAL
                stdscr.addstr(row, 0, (marker + opt.label)[: curses.COLS - 1], attr)
                row += 1
                if opt.description:
                    stdscr.addstr(row, 4, opt.description[:width])
                    row += 1
                row += 0  # keep reserved if we later want a blank line
            stdscr.refresh()
            key = stdscr.getch()
            if key in (curses.KEY_UP, ord("k")):
                index = (index - 1) % len(options)
            elif key in (curses.KEY_DOWN, ord("j")):
                index = (index + 1) % len(options)
            elif key in (10, 13, curses.KEY_ENTER):
                option = options[index]
                text = ""
                if option.needs_text:
                    text = _curses_read_text(stdscr, option.text_prompt)
                return option, text
            elif key in (ord("q"), 27):
                raise KeyboardInterrupt

    return curses.wrapper(run)


def _curses_read_text(stdscr: "curses._CursesWindow", prompt: str) -> str:
    curses.echo()
    try:
        try:
            curses.curs_set(1)
        except curses.error:
            pass
        stdscr.clear()
        stdscr.addstr(0, 0, prompt)
        stdscr.refresh()
        raw = stdscr.getstr(1, 0, 4096)
    finally:
        curses.noecho()
        try:
            curses.curs_set(0)
        except curses.error:
            pass
    return raw.decode(errors="replace").strip()


# ---------------------------------------------------------------------------
# Plain-text fallback
# ---------------------------------------------------------------------------


def _plain_choose(question: Question) -> tuple[Option, str]:
    print(f"\n{question.title}")
    default = question.normalized_default()
    for i, opt in enumerate(question.options, start=1):
        tag = " [default]" if i - 1 == default else ""
        print(f"  {i}. {opt.label}{tag}")
        if opt.description:
            print(f"     {opt.description}")
    raw = input("Choose a number and press Enter: ").strip()
    if not raw:
        index = default
    else:
        try:
            index = int(raw) - 1
        except ValueError as exc:
            raise SystemExit(f"invalid choice: {raw}") from exc
    if index < 0 or index >= len(question.options):
        raise SystemExit(f"invalid choice: {raw}")
    option = question.options[index]
    text = input(option.text_prompt).strip() if option.needs_text else ""
    return option, text


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------


def _demo() -> int:
    install_question = Question(
        title="Where should we install the new program?",
        options=(
            Option(
                label="Project-local (./tools/<program>)",
                description="Recommended for first contact; easy to inspect and remove.",
                value="project_local",
            ),
            Option(
                label="User tools (~/tools/<program>)",
                description="Long-term install for repeated use across projects.",
                value="user_tools",
            ),
            Option(
                label="Type a custom directory",
                description="Free-text path; will be confirmed before any write.",
                value="custom",
                needs_text=True,
                text_prompt="Custom install directory: ",
            ),
            Option(
                label="Do not install yet",
                description="Keep discovery/proposal only; no clone, no env, no writes.",
                value="no_install",
            ),
        ),
        default_index=0,
    )

    try:
        chosen, text = ask_question(install_question)
    except KeyboardInterrupt:
        print("\n[cancelled]")
        return 130

    print()
    print(f"Selected value : {chosen.resolved_value()}")
    print(f"Selected label : {chosen.label}")
    if text:
        print(f"Custom text    : {text}")
    return 0


if __name__ == "__main__":
    sys.exit(_demo())
