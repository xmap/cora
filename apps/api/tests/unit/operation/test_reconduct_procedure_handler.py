"""Application-handler tests for `reconduct_procedure` (resume + replay).

Orchestration handler composing `resume_procedure` + `Conductor.execute_from`
+ complete/abort. Pins the three-way terminal contract and the guards:

  - clean tail -> resume + auto-complete (Completed)
  - acquisition halt -> resume, NO complete/abort, stays Running, halt in result
  - genuine step failure -> resume + abort (Aborted)
  - missing pinned resolved steps -> ResolvedStepsRecordNotFoundError
  - not Held / parent Run Held -> ProcedureCannotResumeError (no replay)
  - authz deny -> UnauthorizedError
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.operation.adapters.control_port_registry import ControlPortRegistry
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.aggregates.procedure import (
    InMemoryActivityStore,
    InvalidProcedureReEstablishmentBoundaryError,
    ProcedureCannotResumeError,
    ProcedureHeld,
    ProcedureNotFoundError,
    ProcedureRegistered,
    ProcedureStarted,
    ProcedureStatus,
    ResolvedStepsRecorded,
    ResolvedStepsRecordNotFoundError,
    event_type_name,
    load_procedure,
    to_payload,
)
from cora.operation.conductor import ActionStep, Conductor, SetpointStep, Step, step_to_payload
from cora.operation.errors import UnauthorizedError
from cora.operation.features import (
    abort_procedure,
    append_activities,
    complete_procedure,
    reconduct_procedure,
    resume_procedure,
)
from cora.operation.features.reconduct_procedure import (
    Handler as ReconductHandler,
)
from cora.operation.features.reconduct_procedure import (
    ReconductProcedure,
    ReconductProcedureResult,
)
from cora.operation.ports.control_port import ActuationKind, ControlPort
from cora.run.aggregates.run import RunHeld, RunStarted
from cora.run.aggregates.run import event_type_name as run_event_type_name
from cora.run.aggregates.run import to_payload as run_to_payload
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 6, 21, 12, 0, 0, tzinfo=UTC)
_PRIOR = datetime(2026, 6, 21, 11, 0, 0, tzinfo=UTC)
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-0000000d0a01")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@dataclass
class _LenientIds:
    """Conductor id_generator that never exhausts (markers double appends)."""

    def new_id(self) -> UUID:
        return uuid4()


def _deps(store: InMemoryEventStore, *, deny: bool = False) -> Kernel:
    # Generous id pool: resume + lazy logbook-open + complete/abort all draw
    # from deps.id_generator (the conductor's activity rows use a lenient one).
    return _build_deps_shared(
        ids=[uuid4() for _ in range(30)], now=_NOW, event_store=store, deny=deny
    )


def _make_reconduct(deps: Kernel, port: ControlPort) -> ReconductHandler:
    conductor = Conductor(
        control_port=port,
        append_step=append_activities.bind(deps, step_store=InMemoryActivityStore()),
        clock=deps.clock,
        id_generator=_LenientIds(),
        resume_procedure=resume_procedure.bind(deps),
        complete_procedure=complete_procedure.bind(deps),
        abort_procedure=abort_procedure.bind(deps),
    )
    return reconduct_procedure.bind(deps, conductor=conductor)


async def _seed_held_with_steps(
    store: InMemoryEventStore,
    *,
    steps: Sequence[Step],
    procedure_id: UUID = _PROCEDURE_ID,
    parent_run_id: UUID | None = None,
    held_actuation_kind: str | None = None,
) -> None:
    """Land a conducted-then-Held Procedure: Registered + ResolvedStepsRecorded
    (the pinned resolved steps) + Started + Held. `held_actuation_kind` is the
    kind the pre-hold conduct observed (carried on ProcedureHeld)."""
    resolved = tuple(step_to_payload(s) for s in steps)
    events = [
        ProcedureRegistered(
            procedure_id=procedure_id,
            name="alignment",
            kind="alignment",
            target_asset_ids=(),
            parent_run_id=parent_run_id,
            occurred_at=_PRIOR,
        ),
        ResolvedStepsRecorded(
            procedure_id=procedure_id,
            resolved_steps=resolved,
            step_count=len(resolved),
            occurred_at=_PRIOR,
        ),
        ProcedureStarted(procedure_id=procedure_id, occurred_at=_PRIOR),
        ProcedureHeld(
            procedure_id=procedure_id,
            reason="beam dropped",
            occurred_at=_PRIOR,
            actuation_kind=held_actuation_kind,
        ),
    ]
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
            for e in events
        ],
    )


async def _seed_held_run(store: InMemoryEventStore, *, run_id: UUID) -> None:
    events: list[RunStarted | RunHeld] = [
        RunStarted(
            run_id=run_id, name="parent", plan_id=uuid4(), subject_id=None, occurred_at=_PRIOR
        ),
        RunHeld(run_id=run_id, occurred_at=_PRIOR),
    ]
    await store.append(
        stream_type="Run",
        stream_id=run_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=run_event_type_name(e),
                payload=run_to_payload(e),
                occurred_at=e.occurred_at,
                event_id=uuid4(),
                command_name="seed",
                correlation_id=_CORRELATION_ID,
                principal_id=_PRINCIPAL_ID,
            )
            for e in events
        ],
    )


async def _status(store: InMemoryEventStore) -> ProcedureStatus:
    state = await load_procedure(store, _PROCEDURE_ID)
    assert state is not None
    return state.status


async def _call(handler: ReconductHandler, boundary: int) -> ReconductProcedureResult:
    return await handler(
        ReconductProcedure(procedure_id=_PROCEDURE_ID, re_establishment_boundary=boundary),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.unit
async def test_clean_tail_resumes_then_auto_completes() -> None:
    store = InMemoryEventStore()
    port = InMemoryControlPort()
    port.simulate_connect("2bma:a")
    port.simulate_connect("2bma:b")
    await _seed_held_with_steps(
        store,
        steps=(
            SetpointStep(address="2bma:a", value=1.0),
            SetpointStep(address="2bma:b", value=2.0),
        ),
    )
    deps = _deps(store)
    result = await _call(_make_reconduct(deps, port), 0)

    assert result.succeeded is True
    assert result.acquisition_halt is False
    assert result.completed_count == 2
    assert await _status(store) is ProcedureStatus.COMPLETED
    assert (await port.read("2bma:a")).value == 1.0
    assert (await port.read("2bma:b")).value == 2.0


@pytest.mark.unit
async def test_boundary_replays_only_the_tail_then_completes() -> None:
    store = InMemoryEventStore()
    port = InMemoryControlPort()
    port.simulate_connect("2bma:b")  # only the tail step is re-driven
    await _seed_held_with_steps(
        store,
        steps=(
            SetpointStep(address="2bma:a", value=1.0),
            SetpointStep(address="2bma:b", value=2.0),
        ),
    )
    deps = _deps(store)
    result = await _call(_make_reconduct(deps, port), 1)
    assert result.succeeded is True
    assert result.completed_count == 1
    assert await _status(store) is ProcedureStatus.COMPLETED
    # The prefix step (2bma:a) was never re-driven.
    with pytest.raises(Exception, match="not connected"):
        await port.read("2bma:a")


@pytest.mark.unit
async def test_acquisition_halt_resumes_but_leaves_running() -> None:
    store = InMemoryEventStore()
    port = InMemoryControlPort()
    port.simulate_connect("2bma:a")
    await _seed_held_with_steps(
        store,
        steps=(
            SetpointStep(address="2bma:a", value=1.0),
            ActionStep(name="collect", params={"dwell": 0.1}),
        ),
    )
    deps = _deps(store)
    result = await _call(_make_reconduct(deps, port), 0)

    assert result.succeeded is False
    assert result.acquisition_halt is True
    assert result.failure is not None
    assert result.failure.error_class == "AcquisitionResumeRequiresOperator"
    # Resumed (Held -> Running) but NOT completed/aborted: stays Running.
    assert await _status(store) is ProcedureStatus.RUNNING
    events, _ = await store.load("Procedure", _PROCEDURE_ID)
    types = [e.event_type for e in events]
    assert "ProcedureResumed" in types
    assert "ProcedureCompleted" not in types
    assert "ProcedureAborted" not in types


@pytest.mark.unit
async def test_genuine_step_failure_resumes_then_aborts() -> None:
    store = InMemoryEventStore()
    port = InMemoryControlPort()  # 2bma:a NOT connected -> write fails
    await _seed_held_with_steps(store, steps=(SetpointStep(address="2bma:a", value=1.0),))
    deps = _deps(store)
    result = await _call(_make_reconduct(deps, port), 0)

    assert result.succeeded is False
    assert result.acquisition_halt is False
    assert result.failure is not None
    assert result.failure.error_class == "ControlNotConnectedError"
    assert await _status(store) is ProcedureStatus.ABORTED


@pytest.mark.unit
async def test_raises_when_resolved_steps_record_missing() -> None:
    """A Held Procedure with no pinned ResolvedStepsRecorded is corruption."""
    store = InMemoryEventStore()
    # Seed Held WITHOUT a ResolvedStepsRecorded.
    events = [
        ProcedureRegistered(
            procedure_id=_PROCEDURE_ID,
            name="x",
            kind="bakeout",
            target_asset_ids=(),
            parent_run_id=None,
            occurred_at=_PRIOR,
        ),
        ProcedureStarted(procedure_id=_PROCEDURE_ID, occurred_at=_PRIOR),
        ProcedureHeld(procedure_id=_PROCEDURE_ID, reason="paused", occurred_at=_PRIOR),
    ]
    await store.append(
        stream_type="Procedure",
        stream_id=_PROCEDURE_ID,
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
            for e in events
        ],
    )
    deps = _deps(store)
    with pytest.raises(ResolvedStepsRecordNotFoundError):
        await _call(_make_reconduct(deps, InMemoryControlPort()), 0)


@pytest.mark.unit
async def test_reconduct_raises_not_found_when_procedure_absent() -> None:
    store = InMemoryEventStore()
    deps = _deps(store)
    with pytest.raises(ProcedureNotFoundError):
        await _call(_make_reconduct(deps, InMemoryControlPort()), 0)


@pytest.mark.unit
async def test_raises_cannot_resume_when_not_held() -> None:
    """A Running (not Held) Procedure with resolved steps cannot be reconducted."""
    store = InMemoryEventStore()
    # Registered + ResolvedStepsRecorded + Started (Running, has resolved steps).
    resolved = (step_to_payload(SetpointStep(address="2bma:a", value=1.0)),)
    events = [
        ProcedureRegistered(
            procedure_id=_PROCEDURE_ID,
            name="x",
            kind="alignment",
            target_asset_ids=(),
            parent_run_id=None,
            occurred_at=_PRIOR,
        ),
        ResolvedStepsRecorded(
            procedure_id=_PROCEDURE_ID,
            resolved_steps=resolved,
            step_count=1,
            occurred_at=_PRIOR,
        ),
        ProcedureStarted(procedure_id=_PROCEDURE_ID, occurred_at=_PRIOR),
    ]
    await store.append(
        stream_type="Procedure",
        stream_id=_PROCEDURE_ID,
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
            for e in events
        ],
    )
    deps = _deps(store)
    with pytest.raises(ProcedureCannotResumeError):
        await _call(_make_reconduct(deps, InMemoryControlPort()), 0)


@pytest.mark.unit
async def test_raises_cannot_resume_when_parent_run_held() -> None:
    """Off-diagonal guard: a Phase-of-Run Procedure whose parent Run is Held."""
    store = InMemoryEventStore()
    parent_run_id = uuid4()
    await _seed_held_run(store, run_id=parent_run_id)
    await _seed_held_with_steps(
        store,
        steps=(SetpointStep(address="2bma:a", value=1.0),),
        parent_run_id=parent_run_id,
    )
    deps = _deps(store)
    with pytest.raises(ProcedureCannotResumeError) as exc:
        await _call(_make_reconduct(deps, InMemoryControlPort()), 0)
    assert exc.value.parent_run_held is True


@pytest.mark.unit
async def test_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_held_with_steps(store, steps=(SetpointStep(address="2bma:a", value=1.0),))
    deps = _deps(store, deny=True)
    with pytest.raises(UnauthorizedError):
        await _call(_make_reconduct(deps, InMemoryControlPort()), 0)


@pytest.mark.unit
async def test_raises_when_boundary_past_step_count() -> None:
    """A boundary strictly past the pinned step count is rejected (it would
    replay an empty tail and silently auto-complete). boundary == count is
    allowed (a deliberate complete-with-nothing resume)."""
    store = InMemoryEventStore()
    await _seed_held_with_steps(store, steps=(SetpointStep(address="2bma:a", value=1.0),))
    deps = _deps(store)
    with pytest.raises(InvalidProcedureReEstablishmentBoundaryError):
        await _call(_make_reconduct(deps, InMemoryControlPort()), 2)  # only 1 step pinned


@pytest.mark.unit
async def test_reconduct_folds_pre_hold_actuation_kind_into_completion() -> None:
    """Regression (provenance gate): a conduct that touched a SIMULATED route
    before the hold must not complete as Physical when reconducted over a
    physical tail. The pre-hold kind carried on ProcedureHeld is merged with
    the replay-tail kind, so the terminal event reports Hybrid and the
    promote_dataset Simulated/Hybrid gate still bites."""
    store = InMemoryEventStore()
    inner = InMemoryControlPort()
    inner.simulate_connect("real:a")
    registry = ControlPortRegistry()
    registry.register("real:", inner, is_simulated=False)  # the replay tail is physical
    await _seed_held_with_steps(
        store,
        steps=(SetpointStep(address="real:a", value=1.0),),
        held_actuation_kind="Simulated",  # the pre-hold prefix touched a simulator
    )
    deps = _deps(store)
    result = await _call(_make_reconduct(deps, registry), 0)

    assert result.succeeded is True
    # Merged, NOT the tail-only Physical -> the response + the terminal event agree.
    assert result.actuation_kind == ActuationKind.HYBRID.value
    state = await load_procedure(store, _PROCEDURE_ID)
    assert state is not None
    assert state.status is ProcedureStatus.COMPLETED
    assert state.actuation_kind == ActuationKind.HYBRID.value
