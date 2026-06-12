"""Property-based tests for `abandon_campaign.decide` (Campaign BC).

Complements the example-based `test_abandon_campaign_decider.py` with
universal claims across generated inputs. The decider is a pure
multi-source FSM transition with a mandatory reason

    (state, command, now) -> list[CampaignAbandoned]

Load-bearing properties:

  - state=None always raises `CampaignNotFoundError` carrying
    command.campaign_id.
  - The source-state partition is total over `CampaignStatus`: the
    permitted sources `{Planned, Active, Held}` each emit exactly one
    `CampaignAbandoned` (campaign_id=state.id, reason threaded,
    occurred_at=now); the terminals `{Closed, Abandoned}` raise
    `CampaignCannotAbandonError` carrying the current status (the
    status guard runs before reason validation).
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
    CampaignAbandoned,
    CampaignCannotAbandonError,
    CampaignIntent,
    CampaignName,
    CampaignNotFoundError,
    CampaignStatus,
)
from cora.campaign.features import abandon_campaign
from cora.campaign.features.abandon_campaign import AbandonCampaign
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_LEAD_ACTOR_ID = UUID(int=5)
_REASON = printable_ascii_text(min_size=1, max_size=500)

_ABANDONABLE_SOURCES = (
    CampaignStatus.PLANNED,
    CampaignStatus.ACTIVE,
    CampaignStatus.HELD,
)
_DISALLOWED_SOURCES = tuple(s for s in CampaignStatus if s not in frozenset(_ABANDONABLE_SOURCES))


def _campaign(*, campaign_id: UUID, status: CampaignStatus) -> Campaign:
    return Campaign(
        id=campaign_id,
        name=CampaignName("Beamtime 2026-1"),
        intent=CampaignIntent.SERIES,
        lead_actor_id=_LEAD_ACTOR_ID,
        status=status,
    )


@pytest.mark.unit
@given(campaign_id=st.uuids(), reason=_REASON, now=aware_datetimes())
def test_abandon_with_none_state_always_raises_not_found(
    campaign_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """Empty stream always raises `CampaignNotFoundError` carrying command.campaign_id."""
    with pytest.raises(CampaignNotFoundError) as exc:
        abandon_campaign.decide(
            state=None,
            command=AbandonCampaign(campaign_id=campaign_id, reason=reason),
            now=now,
        )
    assert exc.value.campaign_id == campaign_id


@pytest.mark.unit
@given(
    campaign_id=st.uuids(),
    source=st.sampled_from(_ABANDONABLE_SOURCES),
    reason=_REASON,
    now=aware_datetimes(),
)
def test_abandon_from_permitted_source_emits_single_event(
    campaign_id: UUID,
    source: CampaignStatus,
    reason: str,
    now: datetime,
) -> None:
    """Planned, Active, and Held each emit one CampaignAbandoned with the reason."""
    events = abandon_campaign.decide(
        state=_campaign(campaign_id=campaign_id, status=source),
        command=AbandonCampaign(campaign_id=campaign_id, reason=reason),
        now=now,
    )
    assert events == [CampaignAbandoned(campaign_id=campaign_id, reason=reason, occurred_at=now)]


@pytest.mark.unit
@given(
    campaign_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    reason=_REASON,
    now=aware_datetimes(),
)
def test_abandon_from_disallowed_source_always_raises_cannot_abandon(
    campaign_id: UUID,
    source: CampaignStatus,
    reason: str,
    now: datetime,
) -> None:
    """Any terminal source raises, carrying the current status (guard before reason)."""
    with pytest.raises(CampaignCannotAbandonError) as exc:
        abandon_campaign.decide(
            state=_campaign(campaign_id=campaign_id, status=source),
            command=AbandonCampaign(campaign_id=campaign_id, reason=reason),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    state_campaign_id=st.uuids(),
    command_campaign_id=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
)
def test_abandon_uses_state_id_not_command_campaign_id(
    state_campaign_id: UUID,
    command_campaign_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """The emitted event's campaign_id is state.id, not command.campaign_id."""
    assume(state_campaign_id != command_campaign_id)
    events = abandon_campaign.decide(
        state=_campaign(campaign_id=state_campaign_id, status=CampaignStatus.ACTIVE),
        command=AbandonCampaign(campaign_id=command_campaign_id, reason=reason),
        now=now,
    )
    assert events[0].campaign_id == state_campaign_id


@pytest.mark.unit
@given(campaign_id=st.uuids(), reason=_REASON, now=aware_datetimes())
def test_abandon_is_pure_same_input_same_output(
    campaign_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _campaign(campaign_id=campaign_id, status=CampaignStatus.ACTIVE)
    command = AbandonCampaign(campaign_id=campaign_id, reason=reason)
    first = abandon_campaign.decide(state=state, command=command, now=now)
    second = abandon_campaign.decide(state=state, command=command, now=now)
    assert first == second
