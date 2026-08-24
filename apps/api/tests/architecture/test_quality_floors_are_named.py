"""A quality floor is chosen by name, never by comparing to a literal.

`Quality` is a trichotomy, and a consumer reading one is picking between
two different questions: can I BELIEVE this value (`Bad` alone
disqualifies) or can I ACT on it (only `Good` will do). Both are
legitimate, so neither is a default, so every use site has to choose.

The choice used to be spelled as a raw comparison, and spelled that way
it is nearly unreadable: `!= "Good"` and `== "Bad"` look like the same
kind of defensive check, and which one is correct depends on whether the
consumer records or acts, and on which state the facility decided to
alarm. Three independently written consumers got it wrong the same way,
each answering the believe question with the act test:

  - the hutch permit (fixed 2026-08-09),
  - the BLEPS interlock flags (fixed 2026-08-23),
  - the beam-availability gate (fixed 2026-08-24, and that one could not
    pass in any state of the beamline).

`cora.shared.quality.believable` / `actionable` give the two questions
names. This test is what stops a fourth consumer from re-deriving the
answer instead of picking one: a raw comparison against a quality
literal, anywhere outside the modules that legitimately handle the
strings, fails here.

`ALLOWED` holds exactly one module, the one that DEFINES the floors, and
should stay that size. The substrate adapters were in it at first, on
the assumption that translating a native severity enum into ours needs
the literals. It does, but never as a COMPARISON: they map with a dict
and return a constant, so the check does not see them and the entries
were exemptions granted against nothing. Removing them is not tidying,
it is the difference between an allowlist that describes the guard and
one that quietly widens it.

A consumer never belongs here. If a new module seems to need an entry,
the thing it wants is almost certainly `believable` or `actionable`.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path

_QUALITY_LITERALS = frozenset({"Good", "Uncertain", "Bad"})

ALLOWED = frozenset({"cora/shared/quality.py"})


def _relative(path: Path) -> str:
    return path.as_posix().rsplit("apps/api/", 1)[-1].removeprefix("src/")


def _comparisons_against_a_quality_literal(path: Path) -> list[str]:
    """Every `x == "Good"` / `x != "Bad"` style comparison in one file.

    AST-based rather than textual so that the strings appearing in
    docstrings, log payloads and error messages (which are describing a
    floor, not applying one) do not register.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        if not any(isinstance(op, (ast.Eq, ast.NotEq, ast.In, ast.NotIn)) for op in node.ops):
            continue
        for operand in (node.left, *node.comparators):
            for literal in ast.walk(operand):
                if isinstance(literal, ast.Constant) and literal.value in _QUALITY_LITERALS:
                    found.append(f"line {node.lineno}: compares against {literal.value!r}")
    return found


@pytest.mark.architecture
@pytest.mark.parametrize("path", sorted(tracked_python_files()), ids=_relative)
def test_no_module_compares_a_quality_against_a_literal(path: Path) -> None:
    rel = _relative(path)
    if rel in ALLOWED:
        return
    violations = _comparisons_against_a_quality_literal(path)
    assert not violations, (
        f"{rel} picks a quality floor by comparing to a literal:\n  "
        + "\n  ".join(violations)
        + "\nUse cora.shared.quality.believable (can I trust this value: "
        "everything but Bad) or actionable (can I act on it: Good only). "
        "Which one is right depends on whether this consumer records or "
        "acts; that module's docstring has the three times it was got "
        "wrong."
    )


@pytest.mark.architecture
def test_every_allowed_module_still_exists() -> None:
    """A stale allowlist entry silently un-guards nothing, but it does rot.

    Renaming an adapter without updating `ALLOWED` leaves a dead entry
    that reads like a granted exemption. Cheap to catch here.
    """
    tracked = {_relative(p) for p in tracked_python_files()}
    assert tracked >= ALLOWED, f"ALLOWED names modules that no longer exist: {ALLOWED - tracked}"
