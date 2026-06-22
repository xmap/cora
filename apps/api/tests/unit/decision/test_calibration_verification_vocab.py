"""Tests for the CalibrationVerification Decision vocabulary.

Covers the DECISION_CONTEXT_CALIBRATION_VERIFICATION context constant, the closed
CALIBRATION_VERIFICATION_CHOICES set, its parity with the
CalibrationVerificationChoice Literal, and that `Stale` does not collide in the
shared, globally-filtered DecisionChoice projection column. The CalibrationWatcher
agent is flag-only (one Decision per stale-calibration episode); the context noun
is `CalibrationVerification` (the lifecycle dimension) while the agent kind is
`CalibrationWatcher` (a deliberate context-noun-vs-doer asymmetry, not drift).
"""

from typing import get_args

import pytest

from cora.decision.aggregates.decision import (
    CALIBRATION_VERIFICATION_CHOICES,
    CAUTION_PROMOTION_CHOICES,
    CAUTION_PROPOSAL_CHOICES,
    CLEARANCE_EXPIRY_CHOICES,
    CLEARANCE_PROGRESS_CHOICES,
    DECISION_CONTEXT_CALIBRATION_VERIFICATION,
    RUN_DEBRIEF_CHOICES,
    RUN_SUPERVISION_CHOICES,
    CalibrationVerificationChoice,
)


@pytest.mark.unit
def test_decision_context_calibration_verification_constant() -> None:
    assert DECISION_CONTEXT_CALIBRATION_VERIFICATION == "CalibrationVerification"


@pytest.mark.unit
def test_calibration_verification_choices_closed_set() -> None:
    assert frozenset({"Stale"}) == CALIBRATION_VERIFICATION_CHOICES


@pytest.mark.unit
def test_calibration_verification_choices_match_literal() -> None:
    """The frozenset and the Literal stay in lockstep."""
    assert frozenset(get_args(CalibrationVerificationChoice)) == CALIBRATION_VERIFICATION_CHOICES


@pytest.mark.unit
def test_calibration_verification_choice_is_unique_in_shared_namespace() -> None:
    """`Stale` does not collide with any sibling context's choice values in the
    globally-filtered DecisionChoice projection column (Flag / Expire / Promote /
    Continue / ...). naming-r3 chose `Stale` precisely because `Flag` was taken."""
    siblings = (
        CAUTION_PROMOTION_CHOICES
        | CAUTION_PROPOSAL_CHOICES
        | CLEARANCE_EXPIRY_CHOICES
        | CLEARANCE_PROGRESS_CHOICES
        | RUN_DEBRIEF_CHOICES
        | RUN_SUPERVISION_CHOICES
    )
    assert CALIBRATION_VERIFICATION_CHOICES.isdisjoint(siblings)
    assert "Stale" in CALIBRATION_VERIFICATION_CHOICES
