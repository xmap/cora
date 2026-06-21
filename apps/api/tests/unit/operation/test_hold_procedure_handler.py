"""Application-handler tests for `hold_procedure` slice.

Update-style handler via `make_procedure_update_handler`. The reason is
captured on the emitted `ProcedureHeld` payload but NOT logged at the
handler boundary (mirrors abort_procedure precedent).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.operation.aggregates.procedure import (
    InvalidProcedureHoldReasonError,
    ProcedureCannotHoldError,
    ProcedureNotFoundError,
)
from cora.operation.errors import UnauthorizedError
from cora.operation.features import hold_procedure
from cora.operation.features.hold_procedure import HoldProcedure
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.operation._helpers import seed_running_procedure

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_PRIOR = datetime(2026, 5, 15, 11, 0, 0, tzinfo=UTC)
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-0000000c0e01")
_EVENT_ID = UUID("01900000-0000-7000-8000-0000000c0e02")
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
async def test_handler_appends_procedure_held_event_with_trimmed_reason() -> None:
    store = InMemoryEventStore()
    await _seed_running_procedure(store)
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store)
    handler = hold_procedure.bind(deps)

    await handler(
        HoldProcedure(procedure_id=_PROCEDURE_ID, reason="  beam dropped  "),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Procedure", _PROCEDURE_ID)
    assert version == 3
    assert events[2].event_type == "ProcedureHeld"
    assert events[2].payload == {
        "procedure_id": str(_PROCEDURE_ID),
        "reason": "beam dropped",
        "decided_by_decision_id": None,
        "occurred_at": _NOW.isoformat(),
        # Operator hold (no conduct observer) leaves actuation_kind None.
        "actuation_kind": None,
    }


@pytest.mark.unit
async def test_handler_raises_when_procedure_not_found() -> None:
    store = InMemoryEventStore()
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store)
    handler = hold_procedure.bind(deps)
    with pytest.raises(ProcedureNotFoundError):
        await handler(
            HoldProcedure(procedure_id=_PROCEDURE_ID, reason="x"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_hold_when_re_holding() -> None:
    """Strict-not-idempotent: re-holding a Held procedure raises."""
    store = InMemoryEventStore()
    await _seed_running_procedure(store)
    await hold_procedure.bind(_build_deps_shared(ids=[uuid4()], now=_NOW, event_store=store))(
        HoldProcedure(procedure_id=_PROCEDURE_ID, reason="first"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    with pytest.raises(ProcedureCannotHoldError):
        await hold_procedure.bind(_build_deps_shared(ids=[uuid4()], now=_NOW, event_store=store))(
            HoldProcedure(procedure_id=_PROCEDURE_ID, reason="second"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_invalid_reason_for_whitespace_only() -> None:
    store = InMemoryEventStore()
    await _seed_running_procedure(store)
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store)
    handler = hold_procedure.bind(deps)
    with pytest.raises(InvalidProcedureHoldReasonError):
        await handler(
            HoldProcedure(procedure_id=_PROCEDURE_ID, reason="   "),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_running_procedure(store)
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store, deny=True)
    handler = hold_procedure.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            HoldProcedure(procedure_id=_PROCEDURE_ID, reason="r"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version = await store.load("Procedure", _PROCEDURE_ID)
    assert version == 2
