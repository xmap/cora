"""Property-based tests for `remove_run_from_campaign.decide` (Campaign BC).

Complements the example-based `test_remove_run_from_campaign_decider.py`
with universal claims across generated inputs. This is a cross-aggregate
decider returning `MembershipEvents` (one event per stream) for the
atomic two-stream `append_streams` write.

    (state, command, context, now) -> MembershipEvents

Load-bearing properties:

  - A membership-eligible Campaign (`{Planned, Active, Held}`) holding
    the target Run with a valid reason emits exactly one
    `CampaignRunRemoved` (Campaign stream) and one
    `RunRemovedFromCampaign` (Run stream), both keyed on the state's id
    and occurred_at=now.
  - A terminal Campaign (`{Closed, Abandoned}`) always raises
    `CampaignCannotRemoveRunError` carrying the current status.
  - A Run NOT in the Campaign's run_ids always raises
    `CampaignRunNotMemberError`.
  - Pure: same inputs return equal results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.campaign.aggregates.campaign import (
    Campaign,
    CampaignCannotRemoveRunError,
    CampaignIntent,
    CampaignName,
    CampaignRunNotMemberError,
    CampaignRunRemoved,
    CampaignStatus,
)
from cora.campaign.features import remove_run_from_campaign
from cora.campaign.features.remove_run_from_campaign import RemoveRunFromCampaign
from cora.campaign.features.remove_run_from_campaign.context import CampaignMembershipContext
from cora.run.aggregates.run import (
    Run,
    RunName,
    RunRemovedFromCampaign,
    RunStatus,
)
from tests._strategies import aware_datetimes, printable_ascii_text

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
    reason=printable_ascii_text(min_size=1, max_size=500),
    now=aware_datetimes(),
)
def test_remove_run_eligible_campaign_emits_one_event_per_stream(
    campaign_id: UUID,
    run_id: UUID,
    source: CampaignStatus,
    reason: str,
    now: datetime,
) -> None:
    """Eligible Campaign holding the Run emits a CampaignRunRemoved and a RunRemovedFromCampaign."""
    campaign = _campaign(campaign_id=campaign_id, status=source, run_ids=frozenset({run_id}))
    run = _run(run_id=run_id, campaign_id=campaign_id)
    result = remove_run_from_campaign.decide(
        state=campaign,
        command=RemoveRunFromCampaign(campaign_id=campaign_id, run_id=run_id, reason=reason),
        context=_context(campaign, run),
        now=now,
    )
    trimmed = reason.strip()
    assert result.campaign_events == [
        CampaignRunRemoved(campaign_id=campaign_id, run_id=run_id, reason=trimmed, occurred_at=now)
    ]
    assert result.run_events == [
        RunRemovedFromCampaign(
            run_id=run_id, campaign_id=campaign_id, reason=trimmed, occurred_at=now
        )
    ]


@pytest.mark.unit
@given(
    campaign_id=st.uuids(),
    run_id=st.uuids(),
    source=st.sampled_from(_TERMINAL_SOURCES),
    reason=printable_ascii_text(min_size=1, max_size=500),
    now=aware_datetimes(),
)
def test_remove_run_terminal_campaign_always_raises_cannot_remove_run(
    campaign_id: UUID,
    run_id: UUID,
    source: CampaignStatus,
    reason: str,
    now: datetime,
) -> None:
    """A Closed or Abandoned Campaign refuses removal, carrying the status."""
    campaign = _campaign(campaign_id=campaign_id, status=source, run_ids=frozenset({run_id}))
    run = _run(run_id=run_id, campaign_id=campaign_id)
    with pytest.raises(CampaignCannotRemoveRunError) as exc:
        remove_run_from_campaign.decide(
            state=campaign,
            command=RemoveRunFromCampaign(campaign_id=campaign_id, run_id=run_id, reason=reason),
            context=_context(campaign, run),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    campaign_id=st.uuids(),
    run_id=st.uuids(),
    source=st.sampled_from(_ELIGIBLE_SOURCES),
    reason=printable_ascii_text(min_size=1, max_size=500),
    now=aware_datetimes(),
)
def test_remove_run_not_member_always_raises_not_member(
    campaign_id: UUID,
    run_id: UUID,
    source: CampaignStatus,
    reason: str,
    now: datetime,
) -> None:
    """A Run absent from run_ids raises CampaignRunNotMemberError."""
    campaign = _campaign(campaign_id=campaign_id, status=source)
    run = _run(run_id=run_id, campaign_id=None)
    with pytest.raises(CampaignRunNotMemberError):
        remove_run_from_campaign.decide(
            state=campaign,
            command=RemoveRunFromCampaign(campaign_id=campaign_id, run_id=run_id, reason=reason),
            context=_context(campaign, run),
            now=now,
        )


@pytest.mark.unit
@given(
    state_campaign_id=st.uuids(),
    command_campaign_id=st.uuids(),
    run_id=st.uuids(),
    reason=printable_ascii_text(min_size=1, max_size=500),
    now=aware_datetimes(),
)
def test_remove_run_uses_state_id_not_command_campaign_id(
    state_campaign_id: UUID,
    command_campaign_id: UUID,
    run_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """Emitted events key on the state's Campaign id, not the command's campaign_id."""
    campaign = _campaign(
        campaign_id=state_campaign_id,
        status=CampaignStatus.ACTIVE,
        run_ids=frozenset({run_id}),
    )
    run = _run(run_id=run_id, campaign_id=state_campaign_id)
    result = remove_run_from_campaign.decide(
        state=campaign,
        command=RemoveRunFromCampaign(
            campaign_id=command_campaign_id, run_id=run_id, reason=reason
        ),
        context=_context(campaign, run),
        now=now,
    )
    assert result.campaign_events[0].campaign_id == state_campaign_id
    assert result.run_events[0].campaign_id == state_campaign_id


@pytest.mark.unit
@given(
    campaign_id=st.uuids(),
    run_id=st.uuids(),
    reason=printable_ascii_text(min_size=1, max_size=500),
    now=aware_datetimes(),
)
def test_remove_run_is_pure_same_input_same_output(
    campaign_id: UUID,
    run_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """Two calls with identical args return equal results (no clock leakage)."""
    campaign = _campaign(
        campaign_id=campaign_id, status=CampaignStatus.ACTIVE, run_ids=frozenset({run_id})
    )
    run = _run(run_id=run_id, campaign_id=campaign_id)
    command = RemoveRunFromCampaign(campaign_id=campaign_id, run_id=run_id, reason=reason)
    first = remove_run_from_campaign.decide(
        state=campaign, command=command, context=_context(campaign, run), now=now
    )
    second = remove_run_from_campaign.decide(
        state=campaign, command=command, context=_context(campaign, run), now=now
    )
    assert first == second
