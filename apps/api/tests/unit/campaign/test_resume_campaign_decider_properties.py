"""Property-based tests for `resume_campaign.decide` (Campaign BC).

Complements the example-based `test_resume_campaign_decider.py` with
universal claims across generated inputs. The decider is a pure
single-source FSM transition

    (state, command, now) -> list[CampaignResumed]

Load-bearing properties:

  - state=None always raises `CampaignNotFoundError` carrying
    command.campaign_id.
  - The source-state partition is total over `CampaignStatus`: only
    `Held` emits exactly one `CampaignResumed` (campaign_id=state.id,
    occurred_at=now); every other status raises `CampaignCannotResumeError`
    carrying the current status.
  - The emitted event's campaign_id is `state.id`, never
    command.campaign_id.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.campaign.aggregates.campaign import (
    Campaign,
    CampaignCannotResumeError,
    CampaignIntent,
    CampaignName,
    CampaignNotFoundError,
    CampaignResumed,
    CampaignStatus,
)
from cora.campaign.features import resume_campaign
from cora.campaign.features.resume_campaign import ResumeCampaign
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime

_LEAD_ACTOR_ID = UUID(int=5)

_RESUMABLE_SOURCES = (CampaignStatus.HELD,)
_DISALLOWED_SOURCES = tuple(s for s in CampaignStatus if s not in frozenset(_RESUMABLE_SOURCES))


def _campaign(*, campaign_id: UUID, status: CampaignStatus) -> Campaign:
    return Campaign(
        id=campaign_id,
        name=CampaignName("Beamtime 2026-1"),
        intent=CampaignIntent.SERIES,
        lead_actor_id=_LEAD_ACTOR_ID,
        status=status,
    )


@pytest.mark.unit
@given(campaign_id=st.uuids(), now=aware_datetimes())
def test_resume_with_none_state_always_raises_not_found(campaign_id: UUID, now: datetime) -> None:
    """Empty stream always raises `CampaignNotFoundError` carrying command.campaign_id."""
    with pytest.raises(CampaignNotFoundError) as exc:
        resume_campaign.decide(state=None, command=ResumeCampaign(campaign_id=campaign_id), now=now)
    assert exc.value.campaign_id == campaign_id


@pytest.mark.unit
@given(campaign_id=st.uuids(), now=aware_datetimes())
def test_resume_from_held_emits_single_event(campaign_id: UUID, now: datetime) -> None:
    """Held is the only resumable source; emits one CampaignResumed."""
    events = resume_campaign.decide(
        state=_campaign(campaign_id=campaign_id, status=CampaignStatus.HELD),
        command=ResumeCampaign(campaign_id=campaign_id),
        now=now,
    )
    assert events == [CampaignResumed(campaign_id=campaign_id, occurred_at=now)]


@pytest.mark.unit
@given(
    campaign_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_resume_from_disallowed_source_always_raises_cannot_resume(
    campaign_id: UUID,
    source: CampaignStatus,
    now: datetime,
) -> None:
    """Any source other than Held raises, carrying the current status."""
    with pytest.raises(CampaignCannotResumeError) as exc:
        resume_campaign.decide(
            state=_campaign(campaign_id=campaign_id, status=source),
            command=ResumeCampaign(campaign_id=campaign_id),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(state_campaign_id=st.uuids(), command_campaign_id=st.uuids(), now=aware_datetimes())
def test_resume_uses_state_id_not_command_campaign_id(
    state_campaign_id: UUID,
    command_campaign_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's campaign_id is state.id, not command.campaign_id."""
    assume(state_campaign_id != command_campaign_id)
    events = resume_campaign.decide(
        state=_campaign(campaign_id=state_campaign_id, status=CampaignStatus.HELD),
        command=ResumeCampaign(campaign_id=command_campaign_id),
        now=now,
    )
    assert events[0].campaign_id == state_campaign_id


@pytest.mark.unit
@given(campaign_id=st.uuids(), now=aware_datetimes())
def test_resume_is_pure_same_input_same_output(campaign_id: UUID, now: datetime) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _campaign(campaign_id=campaign_id, status=CampaignStatus.HELD)
    command = ResumeCampaign(campaign_id=campaign_id)
    first = resume_campaign.decide(state=state, command=command, now=now)
    second = resume_campaign.decide(state=state, command=command, now=now)
    assert first == second
