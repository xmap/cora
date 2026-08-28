"""Unit tests for `get_run_history`'s route-level DTO mapping.

Unlike `get_run`'s route, there is no vault destructuring here by design
(see `handler.py`'s module docstring), so this only pins the 404 mapping
and the event/observation list shape.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.run.adapters.in_memory_run_observation_trail import InMemoryRunObservationTrail
from cora.run.aggregates.run.entries import InMemoryObservationStore
from cora.run.aggregates.run.events import RunStarted, event_type_name, to_payload
from cora.run.features import get_run_history
from cora.run.features.get_run_history.route import get_run_history_route
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 8, 16, 12, 0, 0, tzinfo=UTC)
_PLAN_ID = UUID("01900000-0000-7000-8000-00000000ff02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_run(store: InMemoryEventStore, run_id: UUID) -> None:
    event = RunStarted(
        run_id=run_id,
        name="32-ID FlyScan",
        plan_id=_PLAN_ID,
        subject_id=None,
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="StartRun",
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await store.append(stream_type="Run", stream_id=run_id, expected_version=0, events=[new_event])


@pytest.mark.unit
async def test_get_run_history_route_returns_events_for_known_run() -> None:
    run_id = uuid4()
    store = InMemoryEventStore()
    await _seed_run(store, run_id)
    deps = build_deps(ids=[run_id], now=_NOW, event_store=store)
    handler = get_run_history.bind(
        deps, observation_trail=InMemoryRunObservationTrail(InMemoryObservationStore())
    )

    response = await get_run_history_route(
        run_id,
        handler,
        _CORRELATION_ID,
        _PRINCIPAL_ID,
        NIL_SENTINEL_ID,
    )

    assert response.run_id == run_id
    assert response.name == "32-ID FlyScan"
    assert response.status == "Running"
    assert len(response.events) == 1
    assert response.events[0].event_type == "RunStarted"
    assert response.observations == []
    assert response.observations_truncated is False


@pytest.mark.unit
async def test_get_run_history_route_raises_404_for_unknown_run() -> None:
    deps = build_deps(ids=[uuid4()], now=_NOW)
    handler = get_run_history.bind(
        deps, observation_trail=InMemoryRunObservationTrail(InMemoryObservationStore())
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_run_history_route(
            uuid4(),
            handler,
            _CORRELATION_ID,
            _PRINCIPAL_ID,
            NIL_SENTINEL_ID,
        )
    assert exc_info.value.status_code == 404
