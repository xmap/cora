"""Tests for the CampaignProgress Decision vocabulary.

Covers the DECISION_CONTEXT_CAMPAIGN_PROGRESS context constant, the closed
CAMPAIGN_PROGRESS_CHOICES set, its parity with the CampaignProgressChoice
Literal, and that `Stuck` does not collide in the shared, globally-filtered
DecisionChoice projection column. The CampaignWatcher agent is flag-only (one
Decision per stuck-Held episode); the context noun is `CampaignProgress` (the
lifecycle dimension) while the agent kind is `CampaignWatcher` (a deliberate
context-noun-vs-doer asymmetry, not drift).

The disjointness check unions EVERY closed sibling choice set, including
REACTION_DISMISSAL_CHOICES (imported from the submodule because it is not
re-exported from the package).
"""

from typing import get_args

import pytest

from cora.decision.aggregates.decision import (
    CALIBRATION_VERIFICATION_CHOICES,
    CAMPAIGN_PROGRESS_CHOICES,
    CAUTION_PROMOTION_CHOICES,
    CAUTION_PROPOSAL_CHOICES,
    CLEARANCE_EXPIRY_CHOICES,
    CLEARANCE_PROGRESS_CHOICES,
    DECISION_CONTEXT_CAMPAIGN_PROGRESS,
    PROCEDURE_PROGRESS_CHOICES,
    RUN_DEBRIEF_CHOICES,
    RUN_SUPERVISION_CHOICES,
    CampaignProgressChoice,
)
from cora.decision.aggregates.decision.state import REACTION_DISMISSAL_CHOICES


@pytest.mark.unit
def test_decision_context_campaign_progress_constant() -> None:
    assert DECISION_CONTEXT_CAMPAIGN_PROGRESS == "CampaignProgress"


@pytest.mark.unit
def test_campaign_progress_choices_closed_set() -> None:
    assert frozenset({"Stuck"}) == CAMPAIGN_PROGRESS_CHOICES


@pytest.mark.unit
def test_campaign_progress_choices_match_literal() -> None:
    """The frozenset and the Literal stay in lockstep."""
    assert frozenset(get_args(CampaignProgressChoice)) == CAMPAIGN_PROGRESS_CHOICES


@pytest.mark.unit
def test_campaign_progress_choice_is_unique_in_shared_namespace() -> None:
    """`Stuck` does not collide with any sibling context's choice values in the
    globally-filtered DecisionChoice projection column (Flag / Stale / Stall /
    Expire / EventDismissed / ...). naming-r3 chose `Stuck` precisely because
    `Stall` was already taken by ProcedureProgress."""
    siblings = (
        CALIBRATION_VERIFICATION_CHOICES
        | CAUTION_PROMOTION_CHOICES
        | CAUTION_PROPOSAL_CHOICES
        | CLEARANCE_EXPIRY_CHOICES
        | CLEARANCE_PROGRESS_CHOICES
        | PROCEDURE_PROGRESS_CHOICES
        | REACTION_DISMISSAL_CHOICES
        | RUN_DEBRIEF_CHOICES
        | RUN_SUPERVISION_CHOICES
    )
    assert CAMPAIGN_PROGRESS_CHOICES.isdisjoint(siblings)
    assert "Stuck" in CAMPAIGN_PROGRESS_CHOICES
