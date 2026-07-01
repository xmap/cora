"""Application-handler tests for the `append_diagnostics` slice.

Lazy open-on-first-write + batch append, mirroring
`test_append_activities_handler.py` but for the conductor-internal
diagnostics logbook (no authz / no wire). Tests seed a Running Procedure into
the in-memory event store, then exercise the handler with an
InMemoryDiagnosticStore.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.operation.aggregates.procedure import (
    InMemoryDiagnosticStore,
    ProcedureNotFoundError,
    ProcedureStepsLogbookClosedError,
    fold,
    from_stored,
)
from cora.operation.features import append_diagnostics
from cora.operation.features.append_diagnostics import (
    AppendProcedureDiagnostics,
    DiagnosticInput,
)
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.operation._helpers import (
    seed_completed_procedure,
    seed_running_procedure,
)

_NOW = datetime(2026, 7, 1, 12, 0, 0, tzinfo=UTC)
_PRIOR = datetime(2026, 7, 1, 11, 0, 0, tzinfo=UTC)
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-0000000d0e01")
_LOGBOOK_ID = UUID("01900000-0000-7000-8000-0000000d0e02")
_OPEN_EVENT_ID = UUID("01900000-0000-7000-8000-0000000d0e03")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _entry(*, event_id: UUID | None = None, iteration_index: int = 0) -> DiagnosticInput:
    return DiagnosticInput(
        event_id=event_id or uuid4(),
        iteration_index=iteration_index,
        model_ref="botorch",
        payload={"lengthscale_x": 0.8, "noise": 0.005, "acquisition_value": 0.12},
        sampled_at=_NOW,
    )


@pytest.mark.unit
async def test_handler_lazy_opens_diagnostic_logbook_on_first_append() -> None:
    store = InMemoryEventStore()
    await seed_running_procedure(
        store,
        procedure_id=_PROCEDURE_ID,
        when=_PRIOR,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
    )
    deps = _build_deps_shared(ids=[_LOGBOOK_ID, _OPEN_EVENT_ID], now=_NOW, event_store=store)
    diagnostic_store = InMemoryDiagnosticStore()
    handler = append_diagnostics.bind(deps, diagnostic_store=diagnostic_store)

    count = await handler(
        AppendProcedureDiagnostics(procedure_id=_PROCEDURE_ID, entries=(_entry(),)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert count == 1
    events, version = await store.load("Procedure", _PROCEDURE_ID)
    assert version == 3
    assert events[2].event_type == "ProcedureDiagnosticLogbookOpened"
    state = fold([from_stored(s) for s in events])
    assert state is not None
    assert state.diagnostic_logbook_id == _LOGBOOK_ID
    rows = diagnostic_store.all()
    assert len(rows) == 1
    assert rows[0].logbook_id == _LOGBOOK_ID
    assert rows[0].procedure_id == _PROCEDURE_ID
    assert rows[0].model_ref == "botorch"
    assert rows[0].payload["acquisition_value"] == 0.12


@pytest.mark.unit
async def test_handler_skips_open_on_second_append() -> None:
    store = InMemoryEventStore()
    await seed_running_procedure(
        store,
        procedure_id=_PROCEDURE_ID,
        when=_PRIOR,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
    )
    deps = _build_deps_shared(ids=[_LOGBOOK_ID, _OPEN_EVENT_ID], now=_NOW, event_store=store)
    diagnostic_store = InMemoryDiagnosticStore()
    handler = append_diagnostics.bind(deps, diagnostic_store=diagnostic_store)

    await handler(
        AppendProcedureDiagnostics(
            procedure_id=_PROCEDURE_ID, entries=(_entry(iteration_index=0),)
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    deps2 = _build_deps_shared(ids=[], now=_NOW, event_store=store)
    handler2 = append_diagnostics.bind(deps2, diagnostic_store=diagnostic_store)
    await handler2(
        AppendProcedureDiagnostics(
            procedure_id=_PROCEDURE_ID, entries=(_entry(iteration_index=1),)
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Procedure", _PROCEDURE_ID)
    open_count = sum(1 for e in events if e.event_type == "ProcedureDiagnosticLogbookOpened")
    assert open_count == 1
    assert version == 3
    assert len(diagnostic_store.all()) == 2


@pytest.mark.unit
async def test_handler_dedups_repeated_event_id() -> None:
    store = InMemoryEventStore()
    await seed_running_procedure(
        store,
        procedure_id=_PROCEDURE_ID,
        when=_PRIOR,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
    )
    deps = _build_deps_shared(ids=[_LOGBOOK_ID, _OPEN_EVENT_ID], now=_NOW, event_store=store)
    diagnostic_store = InMemoryDiagnosticStore()
    handler = append_diagnostics.bind(deps, diagnostic_store=diagnostic_store)
    eid = uuid4()

    await handler(
        AppendProcedureDiagnostics(procedure_id=_PROCEDURE_ID, entries=(_entry(event_id=eid),)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    deps2 = _build_deps_shared(ids=[], now=_NOW, event_store=store)
    handler2 = append_diagnostics.bind(deps2, diagnostic_store=diagnostic_store)
    await handler2(
        AppendProcedureDiagnostics(procedure_id=_PROCEDURE_ID, entries=(_entry(event_id=eid),)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert len(diagnostic_store.all()) == 1


@pytest.mark.unit
async def test_handler_rejects_unknown_procedure() -> None:
    store = InMemoryEventStore()
    deps = _build_deps_shared(ids=[_LOGBOOK_ID, _OPEN_EVENT_ID], now=_NOW, event_store=store)
    handler = append_diagnostics.bind(deps, diagnostic_store=InMemoryDiagnosticStore())

    with pytest.raises(ProcedureNotFoundError):
        await handler(
            AppendProcedureDiagnostics(procedure_id=_PROCEDURE_ID, entries=(_entry(),)),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_rejects_terminal_procedure() -> None:
    store = InMemoryEventStore()
    await seed_completed_procedure(
        store,
        procedure_id=_PROCEDURE_ID,
        when=_PRIOR,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
    )
    deps = _build_deps_shared(ids=[_LOGBOOK_ID, _OPEN_EVENT_ID], now=_NOW, event_store=store)
    handler = append_diagnostics.bind(deps, diagnostic_store=InMemoryDiagnosticStore())

    with pytest.raises(ProcedureStepsLogbookClosedError):
        await handler(
            AppendProcedureDiagnostics(procedure_id=_PROCEDURE_ID, entries=(_entry(),)),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
