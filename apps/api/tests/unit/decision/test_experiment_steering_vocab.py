"""Tests for the ExperimentSteering Decision vocabulary.

Covers the DECISION_CONTEXT_EXPERIMENT_STEERING context constant, the closed
EXPERIMENT_STEERING_CHOICES set, its parity with the ExperimentSteeringChoice
Literal, and a naming guard that the audit-fallback values stay work-noun-
qualified (no bare Deferred / Conflicted) so they do not collide in the shared,
globally-filtered DecisionChoice projection.
"""

from typing import get_args

import pytest

from cora.decision.aggregates.decision import (
    DECISION_CONTEXT_EXPERIMENT_STEERING,
    EXPERIMENT_STEERING_CHOICES,
    ExperimentSteeringChoice,
)


@pytest.mark.unit
def test_decision_context_experiment_steering_constant() -> None:
    assert DECISION_CONTEXT_EXPERIMENT_STEERING == "ExperimentSteering"


@pytest.mark.unit
def test_experiment_steering_choices_closed_set() -> None:
    assert (
        frozenset(
            {
                "Continue",
                "Conclude",
                "Hold",
                "SteeringDeferred",
                "SteeringConflicted",
            }
        )
        == EXPERIMENT_STEERING_CHOICES
    )


@pytest.mark.unit
def test_experiment_steering_choices_match_literal() -> None:
    """The frozenset and the Literal stay in lockstep."""
    assert frozenset(get_args(ExperimentSteeringChoice)) == EXPERIMENT_STEERING_CHOICES


@pytest.mark.unit
def test_audit_fallback_choices_are_work_noun_qualified() -> None:
    """Bare `Deferred` / `Conflicted` would collide in the shared DecisionChoice
    namespace; the audit-fallback values must carry the Steering work-noun
    (parallel to SupervisionDeferred / DebriefDeferred)."""
    assert "Deferred" not in EXPERIMENT_STEERING_CHOICES
    assert "Conflicted" not in EXPERIMENT_STEERING_CHOICES
    assert "SteeringDeferred" in EXPERIMENT_STEERING_CHOICES
    assert "SteeringConflicted" in EXPERIMENT_STEERING_CHOICES
