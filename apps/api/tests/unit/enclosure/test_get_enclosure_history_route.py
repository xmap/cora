"""Unit tests for `get_enclosure_history`'s route-level DTO mapping."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from cora.enclosure.aggregates.enclosure.events import (
    EnclosureRegistered,
    event_type_name,
    to_payload,
)
from cora.enclosure.features import get_enclosure_history
from cora.enclosure.features.get_enclosure_history.route import get_enclosure_history_route
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_enclosure(store: InMemoryEventStore, enclosure_id: UUID) -> None:
    event = EnclosureRegistered(
        enclosure_id=enclosure_id,
        name="2-BM-A",
        facility_code=FacilityCode("aps"),
        registered_by=ActorId(uuid4()),
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="RegisterEnclosure",
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await store.append(
        stream_type="Enclosure", stream_id=enclosure_id, expected_version=0, events=[new_event]
    )


@pytest.mark.unit
async def test_get_enclosure_history_route_returns_events_for_known_enclosure() -> None:
    enclosure_id = uuid4()
    store = InMemoryEventStore()
    await _seed_enclosure(store, enclosure_id)
    deps = build_deps(ids=[enclosure_id], now=_NOW, event_store=store)
    handler = get_enclosure_history.bind(deps)

    response = await get_enclosure_history_route(
        enclosure_id,
        handler,
        _CORRELATION_ID,
        _PRINCIPAL_ID,
        NIL_SENTINEL_ID,
    )

    assert response.enclosure_id == enclosure_id
    assert response.name == "2-BM-A"
    assert response.permit_status == "Unknown"
    assert response.lifecycle == "Active"
    assert len(response.events) == 1
    assert response.events[0].event_type == "EnclosureRegistered"
    assert response.events_truncated is False


@pytest.mark.unit
async def test_get_enclosure_history_route_raises_404_for_unknown_enclosure() -> None:
    deps = build_deps(ids=[uuid4()], now=_NOW)
    handler = get_enclosure_history.bind(deps)

    with pytest.raises(HTTPException) as exc_info:
        await get_enclosure_history_route(
            uuid4(),
            handler,
            _CORRELATION_ID,
            _PRINCIPAL_ID,
            NIL_SENTINEL_ID,
        )
    assert exc_info.value.status_code == 404
