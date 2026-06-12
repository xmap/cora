"""Property-based tests for `start_campaign.decide` (Campaign BC).

Complements the example-based `test_start_campaign_decider.py` with
universal claims across generated inputs. The decider is a pure
single-source FSM transition

    (state, command, now) -> list[CampaignStarted]

Load-bearing properties:

  - state=None always raises `CampaignNotFoundError` carrying
    command.campaign_id.
  - The source-state partition is total over `CampaignStatus`: only
    `Planned` emits exactly one `CampaignStarted` (campaign_id=state.id,
    occurred_at=now); every other status raises `CampaignCannotStartError`
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
    CampaignCannotStartError,
    CampaignIntent,
    CampaignName,
    CampaignNotFoundError,
    CampaignStarted,
    CampaignStatus,
)
from cora.campaign.features import start_campaign
from cora.campaign.features.start_campaign import StartCampaign
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime

_LEAD_ACTOR_ID = UUID(int=5)

_STARTABLE_SOURCES = (CampaignStatus.PLANNED,)
_DISALLOWED_SOURCES = tuple(s for s in CampaignStatus if s not in frozenset(_STARTABLE_SOURCES))


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
def test_start_with_none_state_always_raises_not_found(campaign_id: UUID, now: datetime) -> None:
    """Empty stream always raises `CampaignNotFoundError` carrying command.campaign_id."""
    with pytest.raises(CampaignNotFoundError) as exc:
        start_campaign.decide(state=None, command=StartCampaign(campaign_id=campaign_id), now=now)
    assert exc.value.campaign_id == campaign_id


@pytest.mark.unit
@given(campaign_id=st.uuids(), now=aware_datetimes())
def test_start_from_planned_emits_single_event(campaign_id: UUID, now: datetime) -> None:
    """Planned is the only startable source; emits one CampaignStarted."""
    events = start_campaign.decide(
        state=_campaign(campaign_id=campaign_id, status=CampaignStatus.PLANNED),
        command=StartCampaign(campaign_id=campaign_id),
        now=now,
    )
    assert events == [CampaignStarted(campaign_id=campaign_id, occurred_at=now)]


@pytest.mark.unit
@given(
    campaign_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_start_from_disallowed_source_always_raises_cannot_start(
    campaign_id: UUID,
    source: CampaignStatus,
    now: datetime,
) -> None:
    """Any source other than Planned raises, carrying the current status."""
    with pytest.raises(CampaignCannotStartError) as exc:
        start_campaign.decide(
            state=_campaign(campaign_id=campaign_id, status=source),
            command=StartCampaign(campaign_id=campaign_id),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(state_campaign_id=st.uuids(), command_campaign_id=st.uuids(), now=aware_datetimes())
def test_start_uses_state_id_not_command_campaign_id(
    state_campaign_id: UUID,
    command_campaign_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's campaign_id is state.id, not command.campaign_id."""
    assume(state_campaign_id != command_campaign_id)
    events = start_campaign.decide(
        state=_campaign(campaign_id=state_campaign_id, status=CampaignStatus.PLANNED),
        command=StartCampaign(campaign_id=command_campaign_id),
        now=now,
    )
    assert events[0].campaign_id == state_campaign_id


@pytest.mark.unit
@given(campaign_id=st.uuids(), now=aware_datetimes())
def test_start_is_pure_same_input_same_output(campaign_id: UUID, now: datetime) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _campaign(campaign_id=campaign_id, status=CampaignStatus.PLANNED)
    command = StartCampaign(campaign_id=campaign_id)
    first = start_campaign.decide(state=state, command=command, now=now)
    second = start_campaign.decide(state=state, command=command, now=now)
    assert first == second
