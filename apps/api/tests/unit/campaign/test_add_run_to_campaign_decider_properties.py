"""Property-based tests for `add_run_to_campaign.decide` (Campaign BC).

Complements the example-based `test_add_run_to_campaign_decider.py` with
universal claims across generated inputs. This is a cross-aggregate
decider returning `MembershipEvents` (one event per stream) for the
atomic two-stream `append_streams` write.

    (state, command, context, now) -> MembershipEvents

Load-bearing properties:

  - A membership-eligible Campaign (`{Planned, Active, Held}`) with a
    non-member, unassigned Run emits exactly one `CampaignRunAdded`
    (Campaign stream) and one `RunAddedToCampaign` (Run stream), both
    keyed on the context aggregates' ids and occurred_at=now.
  - A terminal Campaign (`{Closed, Abandoned}`) always raises
    `CampaignCannotAddRunError` carrying the current status.
  - A Run already in the Campaign's run_ids always raises
    `CampaignRunAlreadyMemberError`.
  - A Run already assigned to a different Campaign always raises
    `RunAlreadyAssignedToCampaignError`.
  - Pure: same inputs return equal results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.campaign.aggregates.campaign import (
    Campaign,
    CampaignCannotAddRunError,
    CampaignIntent,
    CampaignName,
    CampaignRunAdded,
    CampaignRunAlreadyMemberError,
    CampaignStatus,
)
from cora.campaign.features import add_run_to_campaign
from cora.campaign.features.add_run_to_campaign import AddRunToCampaign
from cora.campaign.features.add_run_to_campaign.context import CampaignMembershipContext
from cora.run.aggregates.run import (
    Run,
    RunAddedToCampaign,
    RunAlreadyAssignedToCampaignError,
    RunName,
    RunStatus,
)
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime

_LEAD_ACTOR_ID = UUID(int=5)

_ELIGIBLE_SOURCES = (CampaignStatus.PLANNED, CampaignStatus.ACTIVE, CampaignStatus.HELD)
_TERMINAL_SOURCES = (CampaignStatus.CLOSED, CampaignStatus.ABANDONED)


def _campaign(
    *,
    campaign_id: UUID,
    status: CampaignStatus,
    run_ids: frozenset[UUID] = frozenset(),
) -> Campaign:
    return Campaign(
        id=campaign_id,
        name=CampaignName("Beamtime 2026-1"),
        intent=CampaignIntent.SERIES,
        lead_actor_id=_LEAD_ACTOR_ID,
        status=status,
        run_ids=run_ids,
    )


def _run(*, run_id: UUID, campaign_id: UUID | None = None) -> Run:
    return Run(
        id=run_id,
        name=RunName("32-ID FlyScan"),
        plan_id=UUID(int=1),
        subject_id=None,
        status=RunStatus.RUNNING,
        campaign_id=campaign_id,
    )


def _context(campaign: Campaign, run: Run) -> CampaignMembershipContext:
    return CampaignMembershipContext(campaign=campaign, campaign_version=0, run=run, run_version=0)


@pytest.mark.unit
@given(
    campaign_id=st.uuids(),
    run_id=st.uuids(),
    source=st.sampled_from(_ELIGIBLE_SOURCES),
    now=aware_datetimes(),
)
def test_add_run_eligible_campaign_emits_one_event_per_stream(
    campaign_id: UUID,
    run_id: UUID,
    source: CampaignStatus,
    now: datetime,
) -> None:
    """Eligible Campaign + fresh Run emits a CampaignRunAdded and a RunAddedToCampaign."""
    campaign = _campaign(campaign_id=campaign_id, status=source)
    run = _run(run_id=run_id, campaign_id=None)
    result = add_run_to_campaign.decide(
        state=campaign,
        command=AddRunToCampaign(campaign_id=campaign_id, run_id=run_id),
        context=_context(campaign, run),
        now=now,
    )
    assert result.campaign_events == [
        CampaignRunAdded(campaign_id=campaign_id, run_id=run_id, occurred_at=now)
    ]
    assert result.run_events == [
        RunAddedToCampaign(run_id=run_id, campaign_id=campaign_id, occurred_at=now)
    ]


@pytest.mark.unit
@given(
    campaign_id=st.uuids(),
    run_id=st.uuids(),
    source=st.sampled_from(_TERMINAL_SOURCES),
    now=aware_datetimes(),
)
def test_add_run_terminal_campaign_always_raises_cannot_add(
    campaign_id: UUID,
    run_id: UUID,
    source: CampaignStatus,
    now: datetime,
) -> None:
    """A Closed or Abandoned Campaign refuses new members, carrying the status."""
    campaign = _campaign(campaign_id=campaign_id, status=source)
    run = _run(run_id=run_id, campaign_id=None)
    with pytest.raises(CampaignCannotAddRunError) as exc:
        add_run_to_campaign.decide(
            state=campaign,
            command=AddRunToCampaign(campaign_id=campaign_id, run_id=run_id),
            context=_context(campaign, run),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    campaign_id=st.uuids(),
    run_id=st.uuids(),
    source=st.sampled_from(_ELIGIBLE_SOURCES),
    now=aware_datetimes(),
)
def test_add_run_already_member_always_raises_already_member(
    campaign_id: UUID,
    run_id: UUID,
    source: CampaignStatus,
    now: datetime,
) -> None:
    """A Run already in run_ids raises CampaignRunAlreadyMemberError."""
    campaign = _campaign(campaign_id=campaign_id, status=source, run_ids=frozenset({run_id}))
    run = _run(run_id=run_id, campaign_id=campaign_id)
    with pytest.raises(CampaignRunAlreadyMemberError):
        add_run_to_campaign.decide(
            state=campaign,
            command=AddRunToCampaign(campaign_id=campaign_id, run_id=run_id),
            context=_context(campaign, run),
            now=now,
        )


@pytest.mark.unit
@given(
    campaign_id=st.uuids(),
    run_id=st.uuids(),
    other_campaign_id=st.uuids(),
    source=st.sampled_from(_ELIGIBLE_SOURCES),
    now=aware_datetimes(),
)
def test_add_run_assigned_elsewhere_always_raises_already_assigned(
    campaign_id: UUID,
    run_id: UUID,
    other_campaign_id: UUID,
    source: CampaignStatus,
    now: datetime,
) -> None:
    """A Run carrying a different campaign_id raises RunAlreadyAssignedToCampaignError."""
    assume(other_campaign_id != campaign_id)
    campaign = _campaign(campaign_id=campaign_id, status=source)
    run = _run(run_id=run_id, campaign_id=other_campaign_id)
    with pytest.raises(RunAlreadyAssignedToCampaignError):
        add_run_to_campaign.decide(
            state=campaign,
            command=AddRunToCampaign(campaign_id=campaign_id, run_id=run_id),
            context=_context(campaign, run),
            now=now,
        )


@pytest.mark.unit
@given(campaign_id=st.uuids(), run_id=st.uuids(), now=aware_datetimes())
def test_add_run_is_pure_same_input_same_output(
    campaign_id: UUID,
    run_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal results (no clock leakage)."""
    campaign = _campaign(campaign_id=campaign_id, status=CampaignStatus.ACTIVE)
    run = _run(run_id=run_id, campaign_id=None)
    command = AddRunToCampaign(campaign_id=campaign_id, run_id=run_id)
    first = add_run_to_campaign.decide(
        state=campaign, command=command, context=_context(campaign, run), now=now
    )
    second = add_run_to_campaign.decide(
        state=campaign, command=command, context=_context(campaign, run), now=now
    )
    assert first == second
