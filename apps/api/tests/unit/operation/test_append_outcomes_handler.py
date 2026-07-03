"""Application-handler tests for the `append_outcomes` slice.

Lazy open-on-first-write + batch append, mirroring
`test_append_diagnostics_handler.py` but for the steered-pass outcome logbook
(the measured y a resume reads back). Tests seed a Running Procedure into the
in-memory event store, then exercise the handler with an InMemoryOutcomeStore.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.operation.aggregates.procedure import (
    InMemoryOutcomeStore,
    ProcedureNotFoundError,
    ProcedureStepsLogbookClosedError,
    fold,
    from_stored,
)
from cora.operation.features import append_outcomes
from cora.operation.features.append_outcomes import (
    AppendProcedureOutcomes,
    OutcomeInput,
)
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.operation._helpers import (
    seed_completed_procedure,
    seed_running_procedure,
)

_NOW = datetime(2026, 7, 1, 12, 0, 0, tzinfo=UTC)
_PRIOR = datetime(2026, 7, 1, 11, 0, 0, tzinfo=UTC)
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-0000000e0f01")
_LOGBOOK_ID = UUID("01900000-0000-7000-8000-0000000e0f02")
_OPEN_EVENT_ID = UUID("01900000-0000-7000-8000-0000000e0f03")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _entry(*, event_id: UUID | None = None, iteration_index: int = 0) -> OutcomeInput:
    return OutcomeInput(
        event_id=event_id or uuid4(),
        iteration_index=iteration_index,
        point={"energy": 8.0},
        measurements=[
            {"name": "flux", "value": 12.5, "kind": "Scalar", "quality": "Good", "units": None}
        ],
        succeeded=True,
        actuation_kind="Physical",
        sampled_at=_NOW,
    )


@pytest.mark.unit
async def test_handler_lazy_opens_outcome_logbook_on_first_append() -> None:
    store = InMemoryEventStore()
    await seed_running_procedure(
        store,
        procedure_id=_PROCEDURE_ID,
        when=_PRIOR,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
    )
    deps = _build_deps_shared(ids=[_LOGBOOK_ID, _OPEN_EVENT_ID], now=_NOW, event_store=store)
    outcome_store = InMemoryOutcomeStore()
    handler = append_outcomes.bind(deps, outcome_store=outcome_store)

    count = await handler(
        AppendProcedureOutcomes(procedure_id=_PROCEDURE_ID, entries=(_entry(),)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert count == 1
    events, version = await store.load("Procedure", _PROCEDURE_ID)
    assert version == 3
    assert events[2].event_type == "ProcedureOutcomeLogbookOpened"
    state = fold([from_stored(s) for s in events])
    assert state is not None
    assert state.outcome_logbook_id == _LOGBOOK_ID
    rows = outcome_store.all()
    assert len(rows) == 1
    assert rows[0].logbook_id == _LOGBOOK_ID
    assert rows[0].procedure_id == _PROCEDURE_ID
    assert rows[0].succeeded is True
    assert rows[0].measurements[0]["name"] == "flux"


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
    outcome_store = InMemoryOutcomeStore()
    handler = append_outcomes.bind(deps, outcome_store=outcome_store)

    await handler(
        AppendProcedureOutcomes(procedure_id=_PROCEDURE_ID, entries=(_entry(iteration_index=0),)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    deps2 = _build_deps_shared(ids=[], now=_NOW, event_store=store)
    handler2 = append_outcomes.bind(deps2, outcome_store=outcome_store)
    await handler2(
        AppendProcedureOutcomes(procedure_id=_PROCEDURE_ID, entries=(_entry(iteration_index=1),)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Procedure", _PROCEDURE_ID)
    open_count = sum(1 for e in events if e.event_type == "ProcedureOutcomeLogbookOpened")
    assert open_count == 1
    assert version == 3
    assert len(outcome_store.all()) == 2


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
    outcome_store = InMemoryOutcomeStore()
    handler = append_outcomes.bind(deps, outcome_store=outcome_store)
    eid = uuid4()

    await handler(
        AppendProcedureOutcomes(procedure_id=_PROCEDURE_ID, entries=(_entry(event_id=eid),)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    deps2 = _build_deps_shared(ids=[], now=_NOW, event_store=store)
    handler2 = append_outcomes.bind(deps2, outcome_store=outcome_store)
    await handler2(
        AppendProcedureOutcomes(procedure_id=_PROCEDURE_ID, entries=(_entry(event_id=eid),)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert len(outcome_store.all()) == 1


@pytest.mark.unit
async def test_handler_rejects_unknown_procedure() -> None:
    store = InMemoryEventStore()
    deps = _build_deps_shared(ids=[_LOGBOOK_ID, _OPEN_EVENT_ID], now=_NOW, event_store=store)
    handler = append_outcomes.bind(deps, outcome_store=InMemoryOutcomeStore())

    with pytest.raises(ProcedureNotFoundError):
        await handler(
            AppendProcedureOutcomes(procedure_id=_PROCEDURE_ID, entries=(_entry(),)),
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
    handler = append_outcomes.bind(deps, outcome_store=InMemoryOutcomeStore())

    with pytest.raises(ProcedureStepsLogbookClosedError):
        await handler(
            AppendProcedureOutcomes(procedure_id=_PROCEDURE_ID, entries=(_entry(),)),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
