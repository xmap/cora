"""Tests for the AuthorityRevocationHold Decision vocabulary (kill-switch K3).

Covers the DECISION_CONTEXT_AUTHORITY_REVOCATION_HOLD context constant, the
closed AUTHORITY_REVOCATION_HOLD_CHOICES set, its parity with the
AuthorityRevocationHoldChoice Literal, and a naming guard that the audit-fallback
value stays work-noun-qualified (no bare Deferred) so it does not collide in the
shared, globally-filtered DecisionChoice projection.
"""

from typing import get_args

import pytest

from cora.decision.aggregates.decision import (
    AUTHORITY_REVOCATION_HOLD_CHOICES,
    DECISION_CONTEXT_AUTHORITY_REVOCATION_HOLD,
    AuthorityRevocationHoldChoice,
)


@pytest.mark.unit
def test_decision_context_authority_revocation_hold_constant() -> None:
    assert DECISION_CONTEXT_AUTHORITY_REVOCATION_HOLD == "AuthorityRevocationHold"


@pytest.mark.unit
def test_authority_revocation_hold_choices_closed_set() -> None:
    assert frozenset({"Held", "HoldDeferred"}) == AUTHORITY_REVOCATION_HOLD_CHOICES


@pytest.mark.unit
def test_authority_revocation_hold_choices_match_literal() -> None:
    """The frozenset and the Literal stay in lockstep."""
    assert frozenset(get_args(AuthorityRevocationHoldChoice)) == AUTHORITY_REVOCATION_HOLD_CHOICES


@pytest.mark.unit
def test_audit_fallback_choice_is_work_noun_qualified() -> None:
    """A bare `Deferred` would collide in the shared DecisionChoice namespace; the
    audit-fallback value must carry the Hold work-noun (parallel to
    PromotionDeferred / SupervisionDeferred)."""
    assert "Deferred" not in AUTHORITY_REVOCATION_HOLD_CHOICES
    assert "HoldDeferred" in AUTHORITY_REVOCATION_HOLD_CHOICES
