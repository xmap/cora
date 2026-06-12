"""Property-based tests for `close_campaign.decide` (Campaign BC).

Complements the example-based `test_close_campaign_decider.py` with
universal claims across generated inputs. The decider is a pure
multi-source FSM transition

    (state, command, now) -> list[CampaignClosed]

Load-bearing properties:

  - state=None always raises `CampaignNotFoundError` carrying
    command.campaign_id.
  - The source-state partition is total over `CampaignStatus`: only
    `Active` and `Held` emit exactly one `CampaignClosed`
    (campaign_id=state.id, occurred_at=now); every other status raises
    `CampaignCannotCloseError` carrying the current status.
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
    CampaignCannotCloseError,
    CampaignClosed,
    CampaignIntent,
    CampaignName,
    CampaignNotFoundError,
    CampaignStatus,
)
from cora.campaign.features import close_campaign
from cora.campaign.features.close_campaign import CloseCampaign
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime

_LEAD_ACTOR_ID = UUID(int=5)

_CLOSABLE_SOURCES = (CampaignStatus.ACTIVE, CampaignStatus.HELD)
_DISALLOWED_SOURCES = tuple(s for s in CampaignStatus if s not in frozenset(_CLOSABLE_SOURCES))


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
def test_close_with_none_state_always_raises_not_found(campaign_id: UUID, now: datetime) -> None:
    """Empty stream always raises `CampaignNotFoundError` carrying command.campaign_id."""
    with pytest.raises(CampaignNotFoundError) as exc:
        close_campaign.decide(state=None, command=CloseCampaign(campaign_id=campaign_id), now=now)
    assert exc.value.campaign_id == campaign_id


@pytest.mark.unit
@given(
    campaign_id=st.uuids(),
    source=st.sampled_from(_CLOSABLE_SOURCES),
    now=aware_datetimes(),
)
def test_close_from_permitted_source_emits_single_event(
    campaign_id: UUID,
    source: CampaignStatus,
    now: datetime,
) -> None:
    """Active and Held are the closable sources; each emits one CampaignClosed."""
    events = close_campaign.decide(
        state=_campaign(campaign_id=campaign_id, status=source),
        command=CloseCampaign(campaign_id=campaign_id),
        now=now,
    )
    assert events == [CampaignClosed(campaign_id=campaign_id, occurred_at=now)]


@pytest.mark.unit
@given(
    campaign_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_close_from_disallowed_source_always_raises_cannot_close(
    campaign_id: UUID,
    source: CampaignStatus,
    now: datetime,
) -> None:
    """Any source other than Active or Held raises, carrying the current status."""
    with pytest.raises(CampaignCannotCloseError) as exc:
        close_campaign.decide(
            state=_campaign(campaign_id=campaign_id, status=source),
            command=CloseCampaign(campaign_id=campaign_id),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    state_campaign_id=st.uuids(),
    command_campaign_id=st.uuids(),
    source=st.sampled_from(_CLOSABLE_SOURCES),
    now=aware_datetimes(),
)
def test_close_uses_state_id_not_command_campaign_id(
    state_campaign_id: UUID,
    command_campaign_id: UUID,
    source: CampaignStatus,
    now: datetime,
) -> None:
    """The emitted event's campaign_id is state.id, not command.campaign_id."""
    assume(state_campaign_id != command_campaign_id)
    events = close_campaign.decide(
        state=_campaign(campaign_id=state_campaign_id, status=source),
        command=CloseCampaign(campaign_id=command_campaign_id),
        now=now,
    )
    assert events[0].campaign_id == state_campaign_id


@pytest.mark.unit
@given(
    campaign_id=st.uuids(),
    source=st.sampled_from(_CLOSABLE_SOURCES),
    now=aware_datetimes(),
)
def test_close_is_pure_same_input_same_output(
    campaign_id: UUID,
    source: CampaignStatus,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _campaign(campaign_id=campaign_id, status=source)
    command = CloseCampaign(campaign_id=campaign_id)
    first = close_campaign.decide(state=state, command=command, now=now)
    second = close_campaign.decide(state=state, command=command, now=now)
    assert first == second
