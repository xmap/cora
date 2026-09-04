"""Guard against HTML comments reaching a published Slidev deck.

Slidev compiles slide-end HTML comments in slides.md into the deck's JavaScript
bundle and serves them from the presenter routes, so anything written there is
readable by anyone who opens the deployed deck. Delivery notes therefore belong
in the private talks repository, and the copy under talks/ carries only what
renders on screen.

Nothing enforced that. The docs workflow builds every talks/<slug>/ it finds,
and neither the pre-commit hooks nor the suite looked at deck content, so a deck
could carry notes indefinitely without anything objecting.

Scope is slides.md, which is where Slidev reads notes from. Vue components under
components/ can also carry template comments; they are not covered here because
notes are not authored in them, and widening the rule to files nobody writes
notes in would cost more in false failures than it buys.

Decks are discovered from git-tracked files rather than a filesystem scan, so an
unstaged draft stays invisible during pre-commit hook runs, mirroring
tests/architecture/conftest.py's tracked_python_files().
"""

from __future__ import annotations

import os
import re
import subprocess
from functools import cache
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_REPO_ROOT = Path(__file__).resolve().parents[5]

# Slidev reads a note from a comment block at the end of a slide. Match any HTML
# comment rather than only that position: a comment anywhere in slides.md is
# compiled into the bundle just the same.
_COMMENT = re.compile(r"<!--.*?-->", re.S)


@cache
def _tracked_deck_sources() -> list[Path]:
    # Strip pre-commit's GIT_DIR / GIT_INDEX_FILE so the worktree's real tracked
    # set shows through, same rationale as the research candidate guard.
    env = {k: v for k, v in os.environ.items() if k not in {"GIT_DIR", "GIT_INDEX_FILE"}}
    result = subprocess.run(
        ["git", "ls-files", "talks"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    return sorted(
        _REPO_ROOT / line for line in result.stdout.splitlines() if line.endswith("/slides.md")
    )


def test_at_least_one_tracked_deck_source_found() -> None:
    # The comment check below is parametrized over discovered decks. An empty
    # list would make it vanish and report green over nothing at all, which is
    # the failure mode this guard exists to prevent.
    assert _tracked_deck_sources(), "no talks/*/slides.md found in git-tracked files"


@pytest.mark.parametrize(
    "deck_source",
    _tracked_deck_sources(),
    ids=lambda p: p.parent.name,
)
def test_tracked_deck_source_carries_no_html_comment(deck_source: Path) -> None:
    comments = _COMMENT.findall(deck_source.read_text(encoding="utf-8"))
    rel = deck_source.relative_to(_REPO_ROOT)
    assert not comments, (
        f"{rel}: {len(comments)} HTML comment(s) in a published deck source. "
        f"Slidev compiles these into the deployed bundle and serves them from the "
        f"presenter routes. Move delivery notes to the private talks repository "
        f"and keep this copy free of them. First match: {comments[0][:80]!r}"
    )
