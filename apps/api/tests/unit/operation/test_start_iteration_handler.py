"""Application-handler tests for the `start_iteration` slice.

Update-style handler via `make_procedure_update_handler`. Tests seed a
Procedure in `Running` via the shared `_helpers.seed_running_procedure`.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.operation.aggregates.procedure import (
    ProcedureCannotStartIterationError,
    ProcedureNotFoundError,
)
from cora.operation.errors import UnauthorizedError
from cora.operation.features import start_iteration
from cora.operation.features.start_iteration import StartProcedureIteration
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.operation._helpers import seed_running_procedure

_NOW = datetime(2026, 6, 13, 12, 0, 0, tzinfo=UTC)
_PRIOR = datetime(2026, 6, 13, 11, 0, 0, tzinfo=UTC)
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-0000000d0d01")
_EVENT_ID = UUID("01900000-0000-7000-8000-0000000d0d02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_running(store: InMemoryEventStore) -> None:
    await seed_running_procedure(
        store,
        procedure_id=_PROCEDURE_ID,
        when=_PRIOR,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
    )


@pytest.mark.unit
async def test_handler_appends_iteration_started_event() -> None:
    store = InMemoryEventStore()
    await _seed_running(store)
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store)
    handler = start_iteration.bind(deps)

    await handler(
        StartProcedureIteration(procedure_id=_PROCEDURE_ID, iteration_index=1),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Procedure", _PROCEDURE_ID)
    assert version == 3
    assert events[2].event_type == "ProcedureIterationStarted"
    assert events[2].payload == {
        "procedure_id": str(_PROCEDURE_ID),
        "iteration_index": 1,
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
async def test_handler_raises_when_procedure_not_found() -> None:
    store = InMemoryEventStore()
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store)
    handler = start_iteration.bind(deps)
    with pytest.raises(ProcedureNotFoundError):
        await handler(
            StartProcedureIteration(procedure_id=_PROCEDURE_ID, iteration_index=1),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_when_iteration_already_open() -> None:
    store = InMemoryEventStore()
    await _seed_running(store)
    await start_iteration.bind(_build_deps_shared(ids=[uuid4()], now=_NOW, event_store=store))(
        StartProcedureIteration(procedure_id=_PROCEDURE_ID, iteration_index=1),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    deps2 = _build_deps_shared(ids=[uuid4()], now=_NOW, event_store=store)
    with pytest.raises(ProcedureCannotStartIterationError):
        await start_iteration.bind(deps2)(
            StartProcedureIteration(procedure_id=_PROCEDURE_ID, iteration_index=2),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny_and_does_not_append() -> None:
    store = InMemoryEventStore()
    await _seed_running(store)
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store, deny=True)
    handler = start_iteration.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            StartProcedureIteration(procedure_id=_PROCEDURE_ID, iteration_index=1),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version = await store.load("Procedure", _PROCEDURE_ID)
    assert version == 2  # only the seeded Registered + Started
