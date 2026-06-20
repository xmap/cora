"""Tests for the ClearanceExpiry Decision vocabulary.

Covers the DECISION_CONTEXT_CLEARANCE_EXPIRY context constant, the closed
CLEARANCE_EXPIRY_CHOICES set, and its parity with the ClearanceExpiryChoice
Literal. The ClearanceExpirer agent is purely positive (it records a Decision
only when it expires a clearance), so the choice set is a single value; the
context noun is `ClearanceExpiry` while the agent kind is `ClearanceExpirer`
(a deliberate context-noun-vs-doer asymmetry, not drift).
"""

from typing import get_args

import pytest

from cora.decision.aggregates.decision import (
    CLEARANCE_EXPIRY_CHOICES,
    DECISION_CONTEXT_CLEARANCE_EXPIRY,
    ClearanceExpiryChoice,
)


@pytest.mark.unit
def test_decision_context_clearance_expiry_constant() -> None:
    assert DECISION_CONTEXT_CLEARANCE_EXPIRY == "ClearanceExpiry"


@pytest.mark.unit
def test_clearance_expiry_choices_closed_set() -> None:
    assert frozenset({"Expire"}) == CLEARANCE_EXPIRY_CHOICES


@pytest.mark.unit
def test_clearance_expiry_choices_match_literal() -> None:
    """The frozenset and the Literal stay in lockstep."""
    assert frozenset(get_args(ClearanceExpiryChoice)) == CLEARANCE_EXPIRY_CHOICES


@pytest.mark.unit
def test_clearance_expiry_choice_is_unique_in_shared_namespace() -> None:
    """`Expire` is a positive action verb, unique in the globally-filtered
    DecisionChoice projection column (no collision with the sibling agents'
    Promote / Hold / Continue values)."""
    assert "Expire" in CLEARANCE_EXPIRY_CHOICES
    assert "Expired" not in CLEARANCE_EXPIRY_CHOICES
