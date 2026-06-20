"""Tests for the CautionPromotion Decision vocabulary.

Covers the DECISION_CONTEXT_CAUTION_PROMOTION context constant, the closed
CAUTION_PROMOTION_CHOICES set, its parity with the CautionPromotionChoice
Literal, and a naming guard that the audit-fallback values stay
work-noun-qualified (no bare Deferred / Conflicted) so they do not collide
in the shared, globally-filtered DecisionChoice projection.
"""

from typing import get_args

import pytest

from cora.decision.aggregates.decision import (
    CAUTION_PROMOTION_CHOICES,
    DECISION_CONTEXT_CAUTION_PROMOTION,
    CautionPromotionChoice,
)


@pytest.mark.unit
def test_decision_context_caution_promotion_constant() -> None:
    assert DECISION_CONTEXT_CAUTION_PROMOTION == "CautionPromotion"


@pytest.mark.unit
def test_caution_promotion_choices_closed_set() -> None:
    assert (
        frozenset({"Promote", "PromotionDeferred", "PromotionConflicted"})
        == CAUTION_PROMOTION_CHOICES
    )


@pytest.mark.unit
def test_caution_promotion_choices_match_literal() -> None:
    """The frozenset and the Literal stay in lockstep."""
    assert frozenset(get_args(CautionPromotionChoice)) == CAUTION_PROMOTION_CHOICES


@pytest.mark.unit
def test_audit_fallback_choices_are_work_noun_qualified() -> None:
    """Bare `Deferred` / `Conflicted` would collide in the shared DecisionChoice
    namespace; the audit-fallback values must carry the Promotion work-noun
    (parallel to SupervisionDeferred / DebriefDeferred)."""
    assert "Deferred" not in CAUTION_PROMOTION_CHOICES
    assert "Conflicted" not in CAUTION_PROMOTION_CHOICES
    assert "PromotionDeferred" in CAUTION_PROMOTION_CHOICES
    assert "PromotionConflicted" in CAUTION_PROMOTION_CHOICES
