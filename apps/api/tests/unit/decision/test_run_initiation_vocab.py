"""Tests for the RunInitiation Decision vocabulary.

Covers the DECISION_CONTEXT_RUN_INITIATION context constant, the closed
RUN_INITIATION_CHOICES set, and its parity with the RunInitiationChoice
Literal. The RunInitiator agent writes one Decision(context=RunInitiation,
choice=Start) per Run it autonomously starts.
"""

from typing import get_args

import pytest

from cora.decision.aggregates.decision import (
    DECISION_CONTEXT_RUN_INITIATION,
    RUN_INITIATION_CHOICES,
    RunInitiationChoice,
)


@pytest.mark.unit
def test_decision_context_run_initiation_constant() -> None:
    assert DECISION_CONTEXT_RUN_INITIATION == "RunInitiation"


@pytest.mark.unit
def test_run_initiation_choices_closed_set() -> None:
    assert frozenset({"Start"}) == RUN_INITIATION_CHOICES


@pytest.mark.unit
def test_run_initiation_choices_match_literal() -> None:
    """The frozenset and the Literal stay in lockstep."""
    assert frozenset(get_args(RunInitiationChoice)) == RUN_INITIATION_CHOICES


@pytest.mark.unit
def test_start_choice_mirrors_the_start_run_command_verb() -> None:
    """`Start` mirrors the StartRun command verb, as RunSupervision's Hold /
    Resume mirror HoldRun / ResumeRun."""
    assert "Start" in RUN_INITIATION_CHOICES
