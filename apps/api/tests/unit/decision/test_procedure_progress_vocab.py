"""Tests for the ProcedureProgress Decision vocabulary.

Covers the DECISION_CONTEXT_PROCEDURE_PROGRESS context constant, the closed
PROCEDURE_PROGRESS_CHOICES set, its parity with the ProcedureProgressChoice
Literal, and that `Stall` does not collide in the shared, globally-filtered
DecisionChoice projection column. The ProcedureWatcher agent is flag-only (one
Decision per stall episode); the context noun is `ProcedureProgress` (the
lifecycle dimension) while the agent kind is `ProcedureWatcher` (a deliberate
context-noun-vs-doer asymmetry, not drift).

The disjointness check unions EVERY closed sibling choice set, including
REACTION_DISMISSAL_CHOICES (imported from the submodule because it is not
re-exported from the package); the calibration vocab test omits it, so this is
the most complete cross-context uniqueness assertion in the suite.
"""

from typing import get_args

import pytest

from cora.decision.aggregates.decision import (
    CALIBRATION_VERIFICATION_CHOICES,
    CAUTION_PROMOTION_CHOICES,
    CAUTION_PROPOSAL_CHOICES,
    CLEARANCE_EXPIRY_CHOICES,
    CLEARANCE_PROGRESS_CHOICES,
    DECISION_CONTEXT_PROCEDURE_PROGRESS,
    PROCEDURE_PROGRESS_CHOICES,
    RUN_DEBRIEF_CHOICES,
    RUN_SUPERVISION_CHOICES,
    ProcedureProgressChoice,
)
from cora.decision.aggregates.decision.state import REACTION_DISMISSAL_CHOICES


@pytest.mark.unit
def test_decision_context_procedure_progress_constant() -> None:
    assert DECISION_CONTEXT_PROCEDURE_PROGRESS == "ProcedureProgress"


@pytest.mark.unit
def test_procedure_progress_choices_closed_set() -> None:
    assert frozenset({"Stall"}) == PROCEDURE_PROGRESS_CHOICES


@pytest.mark.unit
def test_procedure_progress_choices_match_literal() -> None:
    """The frozenset and the Literal stay in lockstep."""
    assert frozenset(get_args(ProcedureProgressChoice)) == PROCEDURE_PROGRESS_CHOICES


@pytest.mark.unit
def test_procedure_progress_choice_is_unique_in_shared_namespace() -> None:
    """`Stall` does not collide with any sibling context's choice values in the
    globally-filtered DecisionChoice projection column (Flag / Stale / Expire /
    EventDismissed / ...). naming-r3 chose `Stall` precisely because `Flag` was
    taken by ClearanceProgress and `Stale` by CalibrationVerification."""
    siblings = (
        CALIBRATION_VERIFICATION_CHOICES
        | CAUTION_PROMOTION_CHOICES
        | CAUTION_PROPOSAL_CHOICES
        | CLEARANCE_EXPIRY_CHOICES
        | CLEARANCE_PROGRESS_CHOICES
        | REACTION_DISMISSAL_CHOICES
        | RUN_DEBRIEF_CHOICES
        | RUN_SUPERVISION_CHOICES
    )
    assert PROCEDURE_PROGRESS_CHOICES.isdisjoint(siblings)
    assert "Stall" in PROCEDURE_PROGRESS_CHOICES
