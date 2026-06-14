"""Application-handler tests for `complete_procedure` slice.

Update-style handler via `make_update_handler` (no per-Procedure
wrapper yet; rule-of-three fires later). Tests seed a Procedure
in `Running` state via the shared `_seed_helpers.seed_running_procedure`.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.operation.aggregates.procedure import (
    ProcedureCannotCompleteError,
    ProcedureNotFoundError,
)
from cora.operation.errors import UnauthorizedError
from cora.operation.features import complete_procedure
from cora.operation.features.complete_procedure import CompleteProcedure
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.operation._helpers import seed_running_procedure

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_PRIOR = datetime(2026, 5, 15, 11, 0, 0, tzinfo=UTC)
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-0000000c0c01")
_EVENT_ID = UUID("01900000-0000-7000-8000-0000000c0c02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_running_procedure(store: InMemoryEventStore) -> None:
    await seed_running_procedure(
        store,
        procedure_id=_PROCEDURE_ID,
        when=_PRIOR,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
    )


@pytest.mark.unit
async def test_handler_appends_procedure_completed_event() -> None:
    store = InMemoryEventStore()
    await _seed_running_procedure(store)
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store)
    handler = complete_procedure.bind(deps)

    await handler(
        CompleteProcedure(procedure_id=_PROCEDURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Procedure", _PROCEDURE_ID)
    assert version == 3
    assert events[2].event_type == "ProcedureCompleted"
    assert events[2].payload == {
        "procedure_id": str(_PROCEDURE_ID),
        "occurred_at": _NOW.isoformat(),
        # None when the complete is issued outside a conduct (this handler
        # path); the Conductor supplies a real kind on its complete calls.
        "actuation_kind": None,
    }


@pytest.mark.unit
async def test_handler_raises_when_procedure_not_found() -> None:
    store = InMemoryEventStore()
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store)
    handler = complete_procedure.bind(deps)
    with pytest.raises(ProcedureNotFoundError):
        await handler(
            CompleteProcedure(procedure_id=_PROCEDURE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_complete_when_re_completing() -> None:
    """Strict-not-idempotent: re-completing a Completed procedure raises."""
    store = InMemoryEventStore()
    await _seed_running_procedure(store)
    deps1 = _build_deps_shared(ids=[uuid4()], now=_NOW, event_store=store)
    await complete_procedure.bind(deps1)(
        CompleteProcedure(procedure_id=_PROCEDURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    deps2 = _build_deps_shared(ids=[uuid4()], now=_NOW, event_store=store)
    with pytest.raises(ProcedureCannotCompleteError):
        await complete_procedure.bind(deps2)(
            CompleteProcedure(procedure_id=_PROCEDURE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_running_procedure(store)
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store, deny=True)
    handler = complete_procedure.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            CompleteProcedure(procedure_id=_PROCEDURE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_does_not_append_when_denied() -> None:
    store = InMemoryEventStore()
    await _seed_running_procedure(store)
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store, deny=True)
    handler = complete_procedure.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            CompleteProcedure(procedure_id=_PROCEDURE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version = await store.load("Procedure", _PROCEDURE_ID)
    assert version == 2  # only the seeded Registered + Started
