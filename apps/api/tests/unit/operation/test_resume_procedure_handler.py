"""Application-handler tests for `resume_procedure` slice.

Update-style handler via `make_procedure_update_handler`. Source state
is `Held`, reached here by seeding Running then holding. The
off-diagonal parent-Run-Held guard is a follow-up slice; this test
covers the status-guard handler only.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.operation.aggregates.procedure import (
    ProcedureCannotResumeError,
    ProcedureNotFoundError,
)
from cora.operation.errors import UnauthorizedError
from cora.operation.features import hold_procedure, resume_procedure
from cora.operation.features.hold_procedure import HoldProcedure
from cora.operation.features.resume_procedure import ResumeProcedure
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.operation._helpers import seed_running_procedure

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_PRIOR = datetime(2026, 5, 15, 11, 0, 0, tzinfo=UTC)
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-0000000c0f01")
_EVENT_ID = UUID("01900000-0000-7000-8000-0000000c0f02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_held_procedure(store: InMemoryEventStore) -> None:
    await seed_running_procedure(
        store,
        procedure_id=_PROCEDURE_ID,
        when=_PRIOR,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
    )
    await hold_procedure.bind(_build_deps_shared(ids=[uuid4()], now=_PRIOR, event_store=store))(
        HoldProcedure(procedure_id=_PROCEDURE_ID, reason="beam dropped"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.unit
async def test_handler_appends_procedure_resumed_event() -> None:
    store = InMemoryEventStore()
    await _seed_held_procedure(store)
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store)
    handler = resume_procedure.bind(deps)

    await handler(
        ResumeProcedure(procedure_id=_PROCEDURE_ID, re_establishment_boundary=2),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Procedure", _PROCEDURE_ID)
    assert version == 4  # Registered, Started, Held, Resumed
    assert events[3].event_type == "ProcedureResumed"
    assert events[3].payload == {
        "procedure_id": str(_PROCEDURE_ID),
        "re_establishment_boundary": 2,
        "decided_by_decision_id": None,
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
async def test_handler_raises_when_procedure_not_found() -> None:
    store = InMemoryEventStore()
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store)
    handler = resume_procedure.bind(deps)
    with pytest.raises(ProcedureNotFoundError):
        await handler(
            ResumeProcedure(procedure_id=_PROCEDURE_ID, re_establishment_boundary=0),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_resume_when_running() -> None:
    """Resuming a Running (not Held) procedure raises."""
    store = InMemoryEventStore()
    await seed_running_procedure(
        store,
        procedure_id=_PROCEDURE_ID,
        when=_PRIOR,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
    )
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store)
    with pytest.raises(ProcedureCannotResumeError):
        await resume_procedure.bind(deps)(
            ResumeProcedure(procedure_id=_PROCEDURE_ID, re_establishment_boundary=0),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_round_trips_hold_then_resume_back_to_running() -> None:
    """Hold then resume lands the Procedure back in Running (bidirectional cycle)."""
    store = InMemoryEventStore()
    await _seed_held_procedure(store)
    await resume_procedure.bind(_build_deps_shared(ids=[uuid4()], now=_NOW, event_store=store))(
        ResumeProcedure(procedure_id=_PROCEDURE_ID, re_establishment_boundary=0),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # A second hold now succeeds (the cycle is open again).
    await hold_procedure.bind(_build_deps_shared(ids=[uuid4()], now=_NOW, event_store=store))(
        HoldProcedure(procedure_id=_PROCEDURE_ID, reason="second pause"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Procedure", _PROCEDURE_ID)
    assert [e.event_type for e in events] == [
        "ProcedureRegistered",
        "ProcedureStarted",
        "ProcedureHeld",
        "ProcedureResumed",
        "ProcedureHeld",
    ]


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_held_procedure(store)
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store, deny=True)
    handler = resume_procedure.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            ResumeProcedure(procedure_id=_PROCEDURE_ID, re_establishment_boundary=0),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
