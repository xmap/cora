"""Fitness guard: a deployment's Open questions stay aligned with its assets.md placeholders.

The Open questions page (`docs/deployments/<id>/questions.md`) is a
delete-on-answer queue: every modelling value a beamline must confirm
carries an `unknown-pending-confirmation` token in `assets.md`, tagged
with the id of the question that will resolve it (for example
`` `unknown-pending-confirmation` (DRIVE-1) ``). This guard keeps the two
from drifting:

  - completeness: every `unknown-pending-confirmation` placeholder in a
    deployment's `assets.md` table is tagged with a `(QUESTION-ID)`.
    A new placeholder cannot land untracked.
  - no orphan / no dead tag: every tagged id is a live question on that
    deployment's `questions.md`. A question cannot be deleted while its
    placeholder still carries the token.

Scope: the invariant covers the explicit value-placeholder token only.
Assertion questions (where the doc makes a model CHOICE rather than
leaving a blank, e.g. `DET-1` "is the lens turret rotating?") do not map
to a token and are intentionally out. Non-goal: the test does NOT catch a
question left on the page after its placeholder was filled (a stale open
question is low-stakes and human-visible); enforcing that would need a
token-vs-assertion classification the data shows is not mechanical.

Only markdown table rows count as placeholders; prose mentions of the
token (paragraphs discussing it) are ignored. The test discovers every
`docs/deployments/<id>/` that has BOTH `questions.md` and `assets.md`, so
a new beamline is guarded automatically.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_REPO_ROOT = Path(__file__).resolve().parents[5]
_DEPLOYMENTS = _REPO_ROOT / "docs" / "deployments"

_PLACEHOLDER = "unknown-pending-confirmation"
_QUESTION_ROW = re.compile(r"^\|\s*([A-Z]+-\d+)\s*\|")
_TAG = re.compile(r"\(([A-Z]+-\d+)\)")


def _deployments_with_questions() -> list[Path]:
    if not _DEPLOYMENTS.is_dir():
        return []
    return sorted(
        d
        for d in _DEPLOYMENTS.iterdir()
        if (d / "questions.md").is_file() and (d / "assets.md").is_file()
    )


def _live_question_ids(questions_md: Path) -> list[str]:
    ids: list[str] = []
    for line in questions_md.read_text(encoding="utf-8").splitlines():
        match = _QUESTION_ROW.match(line)
        if match:
            ids.append(match.group(1))
    return ids


def test_at_least_one_deployment_has_a_questions_page() -> None:
    # Guards against the discovery silently finding nothing (a moved path
    # would make every parametrized test below vanish and pass vacuously).
    assert _deployments_with_questions(), (
        "no docs/deployments/<id>/ with both questions.md and assets.md found"
    )


@pytest.mark.parametrize("deployment", _deployments_with_questions(), ids=lambda d: d.name)
def test_question_ids_are_unique_and_well_formed(deployment: Path) -> None:
    ids = _live_question_ids(deployment / "questions.md")
    assert ids, f"{deployment.name}: no question ids parsed from questions.md"
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    assert not duplicates, f"{deployment.name}: duplicate question ids {duplicates}"


@pytest.mark.parametrize("deployment", _deployments_with_questions(), ids=lambda d: d.name)
def test_every_placeholder_is_tagged_with_a_live_question(deployment: Path) -> None:
    live = set(_live_question_ids(deployment / "questions.md"))
    untagged: list[str] = []
    dangling: list[str] = []
    checked = 0
    for number, line in enumerate(
        (deployment / "assets.md").read_text(encoding="utf-8").splitlines(), start=1
    ):
        # Only value-placeholders count: the token inside a markdown table
        # row. Prose mentions of the token are not placeholders to tag.
        if not line.lstrip().startswith("|") or _PLACEHOLDER not in line:
            continue
        checked += 1
        tags = _TAG.findall(line)
        if not tags:
            untagged.append(f"  assets.md:{number}: {line.strip()}")
            continue
        dangling.extend(
            f"  assets.md:{number}: ({tag}) is not a live question"
            for tag in tags
            if tag not in live
        )
    assert checked, f"{deployment.name}: no placeholder rows found in assets.md (parser drift?)"
    assert not untagged, (
        f"{deployment.name}: `{_PLACEHOLDER}` placeholder(s) with no (QUESTION-ID) tag. "
        f"Add the tracking question id so the answer has a home:\n" + "\n".join(untagged)
    )
    assert not dangling, (
        f"{deployment.name}: placeholder tag(s) point at a question not on questions.md. "
        f"Add the question, or fix the tag:\n" + "\n".join(dangling)
    )
