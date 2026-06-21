"""Application-handler tests for `try_conduct_procedure` (pause-to-Held conduct).

Orchestration handler delegating to `Conductor.try_conduct`. Pins the
hold-vs-abort branch + the guards against a real Conductor + real
start/complete/abort/hold handlers over an in-memory store:

  - recoverable setpoint failure -> start + pause to Held (held=True), manifest pinned
  - recoverable check failure    -> start + pause to Held
  - action (acquisition) failure -> start + abort (held=False, Aborted)
  - clean run                    -> start + complete (Completed)
  - hold itself fails            -> left Running, original failure surfaced
  - authz deny                   -> UnauthorizedError
  - unknown procedure            -> ProcedureNotFoundError
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.adapters.in_memory_recipe_expander import InMemoryRecipeExpander
from cora.operation.aggregates.procedure import (
    InMemoryActivityStore,
    ProcedureNotFoundError,
    ProcedureRegistered,
    ProcedureStarted,
    ProcedureStatus,
    event_type_name,
    load_procedure,
    to_payload,
)
from cora.operation.conductor import (
    ActionStep,
    CheckStep,
    Conductor,
    EqualsCriterion,
    SetpointStep,
    Step,
)
from cora.operation.errors import UnauthorizedError
from cora.operation.features import (
    abort_procedure,
    append_activities,
    complete_procedure,
    hold_procedure,
    start_procedure,
    try_conduct_procedure,
)
from cora.operation.features.complete_procedure.command import CompleteProcedure
from cora.operation.features.hold_procedure.command import HoldProcedure
from cora.operation.features.try_conduct_procedure import (
    Handler as TryConductHandler,
)
from cora.operation.features.try_conduct_procedure import (
    TryConductProcedure,
    TryConductProcedureResult,
)
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 6, 21, 12, 0, 0, tzinfo=UTC)
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-0000000d0b01")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@dataclass
class _LenientIds:
    """Conductor id_generator that never exhausts (markers double appends)."""

    def new_id(self) -> UUID:
        return uuid4()


async def _raising_hold(
    command: HoldProcedure,
    *,
    principal_id: UUID,
    correlation_id: UUID,
    causation_id: UUID | None = None,
    surface_id: UUID = NIL_SENTINEL_ID,
) -> None:
    _ = (command, principal_id, correlation_id, causation_id, surface_id)
    msg = "hold backend unavailable"
    raise RuntimeError(msg)


async def _raising_complete(
    command: CompleteProcedure,
    *,
    principal_id: UUID,
    correlation_id: UUID,
    causation_id: UUID | None = None,
    surface_id: UUID = NIL_SENTINEL_ID,
) -> None:
    _ = (command, principal_id, correlation_id, causation_id, surface_id)
    msg = "complete backend unavailable"
    raise RuntimeError(msg)


def _deps(store: InMemoryEventStore, *, deny: bool = False) -> Kernel:
    return _build_deps_shared(
        ids=[uuid4() for _ in range(30)], now=_NOW, event_store=store, deny=deny
    )


def _make_try_conduct(
    deps: Kernel,
    port: InMemoryControlPort,
    *,
    hold_fails: bool = False,
    complete_fails: bool = False,
) -> TryConductHandler:
    conductor = Conductor(
        control_port=port,
        append_step=append_activities.bind(deps, step_store=InMemoryActivityStore()),
        clock=deps.clock,
        id_generator=_LenientIds(),
        start_procedure=start_procedure.bind(deps),
        complete_procedure=_raising_complete if complete_fails else complete_procedure.bind(deps),
        abort_procedure=abort_procedure.bind(deps),
        hold_procedure=_raising_hold if hold_fails else hold_procedure.bind(deps),
    )
    return try_conduct_procedure.bind(
        deps, conductor=conductor, expansion_port=InMemoryRecipeExpander()
    )


async def _seed_defined(store: InMemoryEventStore) -> None:
    """Seed a standalone Defined Procedure (no recipe, no parent Run)."""
    event = ProcedureRegistered(
        procedure_id=_PROCEDURE_ID,
        name="alignment",
        kind="alignment",
        target_asset_ids=(),
        parent_run_id=None,
        occurred_at=_NOW,
    )
    await store.append(
        stream_type="Procedure",
        stream_id=_PROCEDURE_ID,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=event.occurred_at,
                event_id=uuid4(),
                command_name="seed",
                correlation_id=_CORRELATION_ID,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )


async def _seed_running(store: InMemoryEventStore) -> None:
    """Seed a Registered + Started (Running) Procedure so try_conduct's
    start_procedure rejects it (Defined-only) as a lifecycle failure."""
    events = [
        ProcedureRegistered(
            procedure_id=_PROCEDURE_ID,
            name="alignment",
            kind="alignment",
            target_asset_ids=(),
            parent_run_id=None,
            occurred_at=_NOW,
        ),
        ProcedureStarted(procedure_id=_PROCEDURE_ID, occurred_at=_NOW),
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


async def _status(store: InMemoryEventStore) -> ProcedureStatus:
    state = await load_procedure(store, _PROCEDURE_ID)
    assert state is not None
    return state.status


async def _event_types(store: InMemoryEventStore) -> list[str]:
    events, _ = await store.load("Procedure", _PROCEDURE_ID)
    return [e.event_type for e in events]


async def _call(handler: TryConductHandler, steps: Sequence[Step]) -> TryConductProcedureResult:
    return await handler(
        TryConductProcedure(procedure_id=_PROCEDURE_ID, steps=steps),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.unit
async def test_recoverable_setpoint_failure_pauses_to_held() -> None:
    store = InMemoryEventStore()
    port = InMemoryControlPort()  # 2bma:a NOT connected -> write fails (recoverable)
    await _seed_defined(store)
    result = await _call(
        _make_try_conduct(_deps(store), port),
        (SetpointStep(address="2bma:a", value=1.0),),
    )

    assert result.succeeded is False
    assert result.held is True
    assert result.failure is not None
    assert result.failure.error_class == "ControlNotConnectedError"
    assert await _status(store) is ProcedureStatus.HELD
    types = await _event_types(store)
    assert "ResolvedStepsRecorded" in types  # manifest pinned -> reconduct-ready
    assert "ProcedureHeld" in types
    assert "ProcedureAborted" not in types
    assert "ProcedureCompleted" not in types


@pytest.mark.unit
async def test_recoverable_check_failure_pauses_to_held() -> None:
    store = InMemoryEventStore()
    port = InMemoryControlPort()  # read of unconnected address fails (recoverable)
    await _seed_defined(store)
    result = await _call(
        _make_try_conduct(_deps(store), port),
        (CheckStep(address="2bma:a", criterion=EqualsCriterion(expected=1.0)),),
    )

    assert result.held is True
    assert result.failure is not None
    assert result.failure.source_kind == "check"
    assert await _status(store) is ProcedureStatus.HELD


@pytest.mark.unit
async def test_action_failure_aborts_not_held() -> None:
    store = InMemoryEventStore()
    port = InMemoryControlPort()
    await _seed_defined(store)
    # An unregistered action -> UnknownActionError (source_kind=action), which
    # is NOT recoverable: an interrupted acquisition aborts rather than pausing.
    result = await _call(_make_try_conduct(_deps(store), port), (ActionStep(name="unregistered"),))

    assert result.succeeded is False
    assert result.held is False
    assert result.failure is not None
    assert result.failure.source_kind == "action"
    assert await _status(store) is ProcedureStatus.ABORTED


@pytest.mark.unit
async def test_clean_run_completes() -> None:
    store = InMemoryEventStore()
    port = InMemoryControlPort()
    port.simulate_connect("2bma:a")
    await _seed_defined(store)
    result = await _call(
        _make_try_conduct(_deps(store), port),
        (SetpointStep(address="2bma:a", value=1.0),),
    )

    assert result.succeeded is True
    assert result.held is False
    assert result.completed_count == 1
    assert await _status(store) is ProcedureStatus.COMPLETED
    assert (await port.read("2bma:a")).value == 1.0


@pytest.mark.unit
async def test_empty_step_list_completes() -> None:
    store = InMemoryEventStore()
    await _seed_defined(store)
    result = await _call(_make_try_conduct(_deps(store), InMemoryControlPort()), ())

    assert result.succeeded is True
    assert result.held is False
    assert await _status(store) is ProcedureStatus.COMPLETED


@pytest.mark.unit
async def test_hold_itself_failing_leaves_running() -> None:
    store = InMemoryEventStore()
    port = InMemoryControlPort()  # 2bma:a not connected -> recoverable failure
    await _seed_defined(store)
    result = await _call(
        _make_try_conduct(_deps(store), port, hold_fails=True),
        (SetpointStep(address="2bma:a", value=1.0),),
    )

    # Recoverable failure, but the hold transition itself failed: leave the
    # Procedure Running and surface the original step failure (held=False).
    assert result.held is False
    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_class == "ControlNotConnectedError"
    assert await _status(store) is ProcedureStatus.RUNNING
    types = await _event_types(store)
    assert "ProcedureHeld" not in types
    assert "ProcedureAborted" not in types


@pytest.mark.unit
async def test_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_defined(store)
    deps = _deps(store, deny=True)
    with pytest.raises(UnauthorizedError):
        await _call(_make_try_conduct(deps, InMemoryControlPort()), ())


@pytest.mark.unit
async def test_try_conduct_raises_not_found_when_procedure_absent() -> None:
    store = InMemoryEventStore()
    with pytest.raises(ProcedureNotFoundError):
        await _call(_make_try_conduct(_deps(store), InMemoryControlPort()), ())


@pytest.mark.unit
async def test_start_rejected_records_lifecycle_failure() -> None:
    """An already-Running Procedure cannot start: a lifecycle failure lands in
    the result (not held, not a step failure), and no step runs."""
    store = InMemoryEventStore()
    await _seed_running(store)
    result = await _call(_make_try_conduct(_deps(store), InMemoryControlPort()), ())

    assert result.succeeded is False
    assert result.held is False
    assert result.failure is not None
    assert result.failure.source_kind == "lifecycle"
    assert result.failure.target == "start"
    assert await _status(store) is ProcedureStatus.RUNNING


@pytest.mark.unit
async def test_complete_rejected_records_lifecycle_failure() -> None:
    """A clean run whose complete transition itself fails records a lifecycle
    failure (target=complete), not held."""
    store = InMemoryEventStore()
    await _seed_defined(store)
    result = await _call(
        _make_try_conduct(_deps(store), InMemoryControlPort(), complete_fails=True), ()
    )

    assert result.succeeded is False
    assert result.held is False
    assert result.failure is not None
    assert result.failure.source_kind == "lifecycle"
    assert result.failure.target == "complete"
