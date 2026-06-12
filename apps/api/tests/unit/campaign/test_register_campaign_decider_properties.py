"""Property-based tests for `register_campaign.decide` (Campaign BC).

Complements the example-based `test_register_campaign_decider.py` with
universal claims across generated inputs. The genesis decider is pure

    (state, command, now, new_id) -> list[CampaignRegistered]

Load-bearing properties:

  - Any non-None state always raises `CampaignAlreadyExistsError`
    carrying state.id (idempotency-as-error), regardless of command.
  - On the happy path the single `CampaignRegistered` carries the
    injected/passthrough fields: campaign_id=new_id, name (trimmed),
    intent, lead_actor_id, occurred_at=now.
  - Pure: same inputs return equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.campaign.aggregates.campaign import (
    Campaign,
    CampaignAlreadyExistsError,
    CampaignIntent,
    CampaignName,
    CampaignRegistered,
    CampaignStatus,
)
from cora.campaign.features import register_campaign
from cora.campaign.features.register_campaign import RegisterCampaign
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_NAME = printable_ascii_text(min_size=1, max_size=200)
_INTENT = st.sampled_from(list(CampaignIntent))
_STATUS = st.sampled_from(list(CampaignStatus))


@pytest.mark.unit
@given(
    existing_id=st.uuids(),
    existing_status=_STATUS,
    name=_NAME,
    intent=_INTENT,
    lead_actor_uuid=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_on_existing_state_always_raises_already_exists(
    existing_id: UUID,
    existing_status: CampaignStatus,
    name: str,
    intent: CampaignIntent,
    lead_actor_uuid: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """Any non-None state raises CampaignAlreadyExistsError carrying state.id."""
    existing = Campaign(
        id=existing_id,
        name=CampaignName("prior"),
        intent=CampaignIntent.SERIES,
        lead_actor_id=UUID(int=9),
        status=existing_status,
    )
    with pytest.raises(CampaignAlreadyExistsError) as exc:
        register_campaign.decide(
            state=existing,
            command=RegisterCampaign(name=name, intent=intent, lead_actor_id=lead_actor_uuid),
            now=now,
            new_id=new_id,
        )
    assert exc.value.campaign_id == existing_id


@pytest.mark.unit
@given(
    name=_NAME,
    intent=_INTENT,
    lead_actor_uuid=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_emits_single_event_with_injected_fields(
    name: str,
    intent: CampaignIntent,
    lead_actor_uuid: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """Empty stream + valid command emits one CampaignRegistered with injected fields."""
    events = register_campaign.decide(
        state=None,
        command=RegisterCampaign(name=name, intent=intent, lead_actor_id=lead_actor_uuid),
        now=now,
        new_id=new_id,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, CampaignRegistered)
    assert event.campaign_id == new_id
    assert event.name == name
    assert event.intent == intent.value
    assert event.lead_actor_id == lead_actor_uuid
    assert event.occurred_at == now


@pytest.mark.unit
@given(
    name=_NAME,
    intent=_INTENT,
    lead_actor_uuid=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_is_pure_same_input_same_output(
    name: str,
    intent: CampaignIntent,
    lead_actor_uuid: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock/id leakage)."""
    command = RegisterCampaign(name=name, intent=intent, lead_actor_id=lead_actor_uuid)
    first = register_campaign.decide(state=None, command=command, now=now, new_id=new_id)
    second = register_campaign.decide(state=None, command=command, now=now, new_id=new_id)
    assert first == second
