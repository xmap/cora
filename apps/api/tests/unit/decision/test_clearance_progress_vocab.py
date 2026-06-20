"""Tests for the ClearanceProgress Decision vocabulary.

Covers the DECISION_CONTEXT_CLEARANCE_PROGRESS context constant, the closed
CLEARANCE_PROGRESS_CHOICES set, and its parity with the ClearanceProgressChoice
Literal. The ClearanceWatcher agent is flag-only (it records a Decision only
when it surfaces a stalled front-of-lifecycle clearance), so the choice set is a
single value; the context noun is `ClearanceProgress` while the agent kind is
`ClearanceWatcher` (a deliberate context-noun-vs-doer asymmetry, not drift).
"""

from typing import get_args

import pytest

from cora.decision.aggregates.decision import (
    CLEARANCE_PROGRESS_CHOICES,
    DECISION_CONTEXT_CLEARANCE_PROGRESS,
    ClearanceProgressChoice,
)


@pytest.mark.unit
def test_decision_context_clearance_progress_constant() -> None:
    assert DECISION_CONTEXT_CLEARANCE_PROGRESS == "ClearanceProgress"


@pytest.mark.unit
def test_clearance_progress_choices_closed_set() -> None:
    assert frozenset({"Flag"}) == CLEARANCE_PROGRESS_CHOICES


@pytest.mark.unit
def test_clearance_progress_choices_match_literal() -> None:
    """The frozenset and the Literal stay in lockstep."""
    assert frozenset(get_args(ClearanceProgressChoice)) == CLEARANCE_PROGRESS_CHOICES


@pytest.mark.unit
def test_clearance_progress_choice_is_unique_in_shared_namespace() -> None:
    """`Flag` is unique in the globally-filtered DecisionChoice projection
    column (no collision with the sibling agents' Expire / Promote / Hold /
    Continue values)."""
    assert "Flag" in CLEARANCE_PROGRESS_CHOICES
    assert "Flagged" not in CLEARANCE_PROGRESS_CHOICES
