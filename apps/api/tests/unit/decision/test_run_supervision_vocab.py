"""Tests for the RunSupervision Decision vocabulary.

Covers the DECISION_CONTEXT_RUN_SUPERVISION context constant, the
closed RUN_SUPERVISION_CHOICES set, its parity with the
RunSupervisionChoice Literal, and a naming guard that the audit-fallback
values stay work-noun-qualified (no bare Deferred / Conflicted) so they
do not collide in the shared, globally-filtered DecisionChoice
projection.
"""

from typing import get_args

import pytest

from cora.decision.aggregates.decision import (
    DECISION_CONTEXT_RUN_SUPERVISION,
    RUN_SUPERVISION_CHOICES,
    RunSupervisionChoice,
)


@pytest.mark.unit
def test_decision_context_run_supervision_constant() -> None:
    assert DECISION_CONTEXT_RUN_SUPERVISION == "RunSupervision"


@pytest.mark.unit
def test_run_supervision_choices_closed_set() -> None:
    assert (
        frozenset(
            {
                "Continue",
                "Hold",
                "Resume",
                "Stop",
                "Abort",
                "SupervisionDeferred",
                "SupervisionConflicted",
                "SupervisionQuieted",
                "SupervisionStalled",
                "SupervisionBreached",
                "Truncate",
            }
        )
        == RUN_SUPERVISION_CHOICES
    )


@pytest.mark.unit
def test_run_supervision_choices_match_literal() -> None:
    """The frozenset and the Literal stay in lockstep."""
    assert frozenset(get_args(RunSupervisionChoice)) == RUN_SUPERVISION_CHOICES


@pytest.mark.unit
def test_audit_fallback_choices_are_work_noun_qualified() -> None:
    """Bare `Deferred` / `Conflicted` would collide in the shared
    DecisionChoice namespace; the audit-fallback values must carry the
    Supervision work-noun (parallel to DebriefDeferred / DebriefConflicted)."""
    assert "Deferred" not in RUN_SUPERVISION_CHOICES
    assert "Conflicted" not in RUN_SUPERVISION_CHOICES
    assert "SupervisionDeferred" in RUN_SUPERVISION_CHOICES
    assert "SupervisionConflicted" in RUN_SUPERVISION_CHOICES


@pytest.mark.unit
def test_advise_rung_choices_are_work_noun_qualified() -> None:
    """The three advise-rung dispositions carry the Supervision work-noun
    (no bare Quieted / Stalled / Breached) for the same namespace-collision
    reason, and read as objective edges (naming-r3: Breached, not Doubted)."""
    assert "Quieted" not in RUN_SUPERVISION_CHOICES
    assert "Stalled" not in RUN_SUPERVISION_CHOICES
    assert "Breached" not in RUN_SUPERVISION_CHOICES
    assert "Doubted" not in RUN_SUPERVISION_CHOICES  # renamed away by naming-r3
    assert {"SupervisionQuieted", "SupervisionStalled", "SupervisionBreached"} <= (
        RUN_SUPERVISION_CHOICES
    )
