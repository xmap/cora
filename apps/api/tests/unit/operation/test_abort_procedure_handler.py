"""Application-handler tests for `abort_procedure` slice.

Update-style handler via `make_update_handler`. The reason field is
captured on the emitted event payload but intentionally NOT logged at
the handler boundary (mirrors abort_run precedent).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.operation.aggregates.procedure import (
    InvalidProcedureAbortReasonError,
    ProcedureCannotAbortError,
    ProcedureNotFoundError,
)
from cora.operation.errors import UnauthorizedError
from cora.operation.features import abort_procedure
from cora.operation.features.abort_procedure import AbortProcedure
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.operation._helpers import seed_running_procedure

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_PRIOR = datetime(2026, 5, 15, 11, 0, 0, tzinfo=UTC)
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-0000000c0d01")
_EVENT_ID = UUID("01900000-0000-7000-8000-0000000c0d02")
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
async def test_handler_appends_procedure_aborted_event_with_trimmed_reason() -> None:
    store = InMemoryEventStore()
    await _seed_running_procedure(store)
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store)
    handler = abort_procedure.bind(deps)

    await handler(
        AbortProcedure(procedure_id=_PROCEDURE_ID, reason="  vacuum loss  "),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Procedure", _PROCEDURE_ID)
    assert version == 3
    assert events[2].event_type == "ProcedureAborted"
    assert events[2].payload == {
        "procedure_id": str(_PROCEDURE_ID),
        "reason": "vacuum loss",
        "occurred_at": _NOW.isoformat(),
        # None when aborted outside a conduct (this handler path).
        "actuation_kind": None,
    }


@pytest.mark.unit
async def test_handler_raises_when_procedure_not_found() -> None:
    store = InMemoryEventStore()
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store)
    handler = abort_procedure.bind(deps)
    with pytest.raises(ProcedureNotFoundError):
        await handler(
            AbortProcedure(procedure_id=_PROCEDURE_ID, reason="x"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_abort_when_re_aborting() -> None:
    """Strict-not-idempotent: re-aborting an Aborted procedure raises."""
    store = InMemoryEventStore()
    await _seed_running_procedure(store)
    deps1 = _build_deps_shared(ids=[uuid4()], now=_NOW, event_store=store)
    await abort_procedure.bind(deps1)(
        AbortProcedure(procedure_id=_PROCEDURE_ID, reason="first"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    deps2 = _build_deps_shared(ids=[uuid4()], now=_NOW, event_store=store)
    with pytest.raises(ProcedureCannotAbortError):
        await abort_procedure.bind(deps2)(
            AbortProcedure(procedure_id=_PROCEDURE_ID, reason="second"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_invalid_reason_for_whitespace_only() -> None:
    store = InMemoryEventStore()
    await _seed_running_procedure(store)
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store)
    handler = abort_procedure.bind(deps)
    with pytest.raises(InvalidProcedureAbortReasonError):
        await handler(
            AbortProcedure(procedure_id=_PROCEDURE_ID, reason="   "),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_running_procedure(store)
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store, deny=True)
    handler = abort_procedure.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            AbortProcedure(procedure_id=_PROCEDURE_ID, reason="r"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_does_not_append_when_denied() -> None:
    store = InMemoryEventStore()
    await _seed_running_procedure(store)
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store, deny=True)
    handler = abort_procedure.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            AbortProcedure(procedure_id=_PROCEDURE_ID, reason="r"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version = await store.load("Procedure", _PROCEDURE_ID)
    assert version == 2
