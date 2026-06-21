"""Application-handler tests for `resume_procedure` slice.

Custom cross-aggregate handler. Source state is `Held`, reached here by
seeding Running then holding. Covers the status-guard path AND the
off-diagonal guard (the handler loads the parent Run and refuses while
the Run is itself `Held`).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.operation.aggregates.procedure import (
    ProcedureCannotResumeError,
    ProcedureNotFoundError,
    ProcedureRegistered,
    ProcedureStarted,
    event_type_name,
    to_payload,
)
from cora.operation.errors import UnauthorizedError
from cora.operation.features import hold_procedure, resume_procedure
from cora.operation.features.hold_procedure import HoldProcedure
from cora.operation.features.resume_procedure import ResumeProcedure
from cora.run.aggregates.run import RunHeld, RunNotFoundError, RunStarted
from cora.run.aggregates.run import event_type_name as run_event_type_name
from cora.run.aggregates.run import to_payload as run_to_payload
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.operation._helpers import seed_running_procedure

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_PRIOR = datetime(2026, 5, 15, 11, 0, 0, tzinfo=UTC)
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-0000000c0f01")
_EVENT_ID = UUID("01900000-0000-7000-8000-0000000c0f02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_held_procedure(
    store: InMemoryEventStore,
    *,
    procedure_id: UUID = _PROCEDURE_ID,
    parent_run_id: UUID | None = None,
) -> None:
    """Land `procedure_id` in `Held`, optionally as a Phase-of-Run Procedure."""
    if parent_run_id is None:
        await seed_running_procedure(
            store,
            procedure_id=procedure_id,
            when=_PRIOR,
            correlation_id=_CORRELATION_ID,
            principal_id=_PRINCIPAL_ID,
        )
    else:
        # Phase-of-Run: ProcedureRegistered carries parent_run_id, then Started.
        registered = ProcedureRegistered(
            procedure_id=procedure_id,
            name="mid-run alignment",
            kind="alignment",
            target_asset_ids=(),
            parent_run_id=parent_run_id,
            occurred_at=_PRIOR,
        )
        started = ProcedureStarted(procedure_id=procedure_id, occurred_at=_PRIOR)
        await store.append(
            stream_type="Procedure",
            stream_id=procedure_id,
            expected_version=0,
            events=[
                to_new_event(
                    event_type=event_type_name(e),
                    payload=to_payload(e),
                    occurred_at=e.occurred_at,
                    event_id=uuid4(),
                    command_name="seed",
                    correlation_id=_CORRELATION_ID,
                    principal_id=_PRINCIPAL_ID,
                )
                for e in (registered, started)
            ],
        )
    await hold_procedure.bind(_build_deps_shared(ids=[uuid4()], now=_PRIOR, event_store=store))(
        HoldProcedure(procedure_id=procedure_id, reason="beam dropped"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _seed_run(store: InMemoryEventStore, *, run_id: UUID, held: bool) -> None:
    """Land a parent Run in `Running` (held=False) or `Held` (held=True)."""
    events: list[object] = [
        RunStarted(
            run_id=run_id,
            name="parent run",
            plan_id=uuid4(),
            subject_id=None,
            occurred_at=_PRIOR,
        )
    ]
    if held:
        events.append(RunHeld(run_id=run_id, occurred_at=_PRIOR))
    await store.append(
        stream_type="Run",
        stream_id=run_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=run_event_type_name(e),  # type: ignore[arg-type]
                payload=run_to_payload(e),  # type: ignore[arg-type]
                occurred_at=e.occurred_at,  # type: ignore[attr-defined]
                event_id=uuid4(),
                command_name="seed",
                correlation_id=_CORRELATION_ID,
                principal_id=_PRINCIPAL_ID,
            )
            for e in events
        ],
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


# --- off-diagonal guard: parent Run Held ---

_PARENT_RUN_ID = UUID("01900000-0000-7000-8000-0000000c0f0a")
_PHASE_PROCEDURE_ID = UUID("01900000-0000-7000-8000-0000000c0f0b")


@pytest.mark.unit
async def test_handler_refuses_resume_when_parent_run_held() -> None:
    """A Phase-of-Run Procedure cannot resume while its parent Run is Held."""
    store = InMemoryEventStore()
    await _seed_run(store, run_id=_PARENT_RUN_ID, held=True)
    await _seed_held_procedure(
        store, procedure_id=_PHASE_PROCEDURE_ID, parent_run_id=_PARENT_RUN_ID
    )
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store)
    with pytest.raises(ProcedureCannotResumeError) as exc:
        await resume_procedure.bind(deps)(
            ResumeProcedure(procedure_id=_PHASE_PROCEDURE_ID, re_establishment_boundary=0),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc.value.parent_run_held is True
    # No ProcedureResumed appended (still Held: Registered, Started, Held).
    events, version = await store.load("Procedure", _PHASE_PROCEDURE_ID)
    assert version == 3
    assert events[-1].event_type == "ProcedureHeld"


@pytest.mark.unit
async def test_handler_allows_resume_when_parent_run_running() -> None:
    """A Phase-of-Run Procedure resumes when its parent Run is Running."""
    store = InMemoryEventStore()
    await _seed_run(store, run_id=_PARENT_RUN_ID, held=False)
    await _seed_held_procedure(
        store, procedure_id=_PHASE_PROCEDURE_ID, parent_run_id=_PARENT_RUN_ID
    )
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store)
    await resume_procedure.bind(deps)(
        ResumeProcedure(procedure_id=_PHASE_PROCEDURE_ID, re_establishment_boundary=4),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Procedure", _PHASE_PROCEDURE_ID)
    assert events[-1].event_type == "ProcedureResumed"
    assert events[-1].payload["re_establishment_boundary"] == 4


@pytest.mark.unit
async def test_handler_raises_run_not_found_when_parent_run_missing() -> None:
    """Phase-of-Run Procedure with a parent_run_id pointing at an empty Run
    stream is corruption: the handler raises rather than skipping the guard."""
    store = InMemoryEventStore()
    await _seed_held_procedure(
        store, procedure_id=_PHASE_PROCEDURE_ID, parent_run_id=_PARENT_RUN_ID
    )  # parent Run never seeded
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store)
    with pytest.raises(RunNotFoundError):
        await resume_procedure.bind(deps)(
            ResumeProcedure(procedure_id=_PHASE_PROCEDURE_ID, re_establishment_boundary=0),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
