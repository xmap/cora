"""Behavioural tests for the Operation BC `Conductor`.

Coverage spans both step kinds shipped to date (setpoint + action):

  Setpoint:
  - empty steps -> trivially succeeds, no handler call
  - 3 setpoints -> 3 ControlPort writes + 3 step entries recorded
  - first write raises ControlNotConnectedError -> halt at index 0,
    failure entry recorded, ConductorResult.failure populated
  - middle write raises ControlTimeoutError -> halt at index N,
    earlier successes recorded, failure entry for the failing step,
    remaining steps untouched
  - non-port exception (asyncio.CancelledError) propagates without
    being caught + without recording anything
  - recorded payload shape (address + value + result + error_class on
    failure) survives across kind values + tuple values

  Action:
  - registered name + body invoked -> result_data recorded in payload
  - unknown name -> UnknownActionError failure recorded + halt
  - body raises ControlTimeoutError -> failure recorded + halt
  - body receives ControlPort + Clock + params via ActionContext
  - mixed setpoint + action step list walked in order

  Check:
  - EqualsCriterion matches the read value -> success
  - EqualsCriterion mismatches -> CheckFailedError halt
  - WithinToleranceCriterion numeric inside tolerance -> success
  - WithinToleranceCriterion numeric outside tolerance -> CheckFailedError halt
  - WithinToleranceCriterion on non-numeric value -> clean mismatch (no exception escape)
  - Reading.quality != Good -> CheckFailedError halt with "quality=" reason
  - read raises Control*Error -> failure halt with the substrate error_class
  - recorded payload carries the observed reading (value + quality + sampled_at)
  - mixed setpoint + action + check walked in order

  Conduct (FSM lifecycle wrapper):
  - happy path: start + execute + complete all fire in order
  - missing handlers at __init__ -> conduct() raises RuntimeError
  - start_procedure rejects -> lifecycle failure recorded, no execute
  - execute fails -> abort_procedure called with reason derived from failure
  - abort_procedure itself fails -> original execute failure is what surfaces
  - complete_procedure fails -> lifecycle failure replaces the prior success result
  - CancelledError mid-execute -> best-effort abort + re-raise
  - CancelledError + abort also fails -> CancelledError still surfaces

  Setpoint verify (post-write evidence capture):
  - verify=False (default): no post_reading field in payload
  - verify=True success: post_reading carries the read value + quality
  - verify=True with Bad quality on the readback: still success (observational)
  - verify=True with Control*Error on read: post_read_error in payload, still success
  - verify=True does NOT change write-failure halt behavior

The unit tier uses `InMemoryControlPort` plus a fake append-step
handler that captures each call's command + envelope into a list. No
real handler wiring, no Procedure event store, no step store; the
Conductor's contract is "call the handler with the right args" and
the fake asserts on that.
"""

import asyncio
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.clock import FakeClock
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.adapters.control_port_registry import ControlPortRegistry
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.conductor import (
    ActionContext,
    ActionStep,
    CheckStep,
    Conductor,
    ConductorFailure,
    ConductorResult,
    EqualsCriterion,
    InMemoryActionRegistry,
    SetpointStep,
    WithinToleranceCriterion,
)
from cora.operation.features.append_activities.command import AppendProcedureActivities
from cora.operation.ports.control_port import (
    ActuationKind,
    ControlPort,
    ControlTimeoutError,
    Reading,
)

_FIXED_NOW = datetime(2026, 5, 30, 9, 0, 0, tzinfo=UTC)


@dataclass
class _AppendCall:
    """One recorded invocation of the fake append-step handler."""

    command: AppendProcedureActivities
    principal_id: UUID
    correlation_id: UUID
    causation_id: UUID | None
    surface_id: UUID


@dataclass
class _FakeAppendStep:
    """Fake `Handler` for the append_activities slice.

    Records every call; returns the entry count to match the real
    handler's `int` return type. Tests assert against `calls`.
    """

    calls: list[_AppendCall] = field(default_factory=list[_AppendCall])

    async def __call__(
        self,
        command: AppendProcedureActivities,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> int:
        self.calls.append(
            _AppendCall(
                command=command,
                principal_id=principal_id,
                correlation_id=correlation_id,
                causation_id=causation_id,
                surface_id=surface_id,
            )
        )
        return len(command.entries)


@dataclass
class _SequenceIdGenerator:
    """Deterministic id_generator that returns a pre-supplied list of ids.

    Lets tests pin event_id values into the recorded entries so the
    payload assertion is exact. Raises on exhaustion so missing ids
    are loud, not silent.
    """

    ids: list[UUID]
    _index: int = 0

    def new_id(self) -> UUID:
        if self._index >= len(self.ids):
            raise RuntimeError("FixedIdGenerator exhausted")
        out = self.ids[self._index]
        self._index += 1
        return out


def _conductor(
    port: ControlPort,
    appender: _FakeAppendStep,
    *,
    ids: Sequence[UUID] = (),
    registry: InMemoryActionRegistry | None = None,
) -> Conductor:
    return Conductor(
        control_port=port,
        append_step=appender,
        clock=FakeClock(_FIXED_NOW),
        id_generator=_SequenceIdGenerator(list(ids)),
        action_registry=registry,
    )


# --- setpoint coverage --------------------------------------------------


@pytest.mark.unit
async def test_execute_with_empty_steps_succeeds_without_handler_call() -> None:
    """Zero steps -> ConductorResult(completed_count=0); no handler call."""
    port = InMemoryControlPort()
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender)
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(),
    )
    assert result.completed_count == 0
    assert result.succeeded is True
    assert result.failure is None
    assert appender.calls == []


@pytest.mark.unit
async def test_execute_setpoints_writes_each_step_via_control_port_in_order() -> None:
    """Three setpoints -> three sequential writes; final values visible via read."""
    port = InMemoryControlPort(now=lambda: _FIXED_NOW)
    port.simulate_connect("2bma:rot:val")
    port.simulate_connect("2bma:cam:exposure")
    port.simulate_connect("2bma:shutter:open")
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender, ids=[uuid4() for _ in range(3)])
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(
            SetpointStep(address="2bma:rot:val", value=45.0),
            SetpointStep(address="2bma:cam:exposure", value=0.025),
            SetpointStep(address="2bma:shutter:open", value=True),
        ),
    )
    assert result.completed_count == 3
    assert result.succeeded is True
    assert (await port.read("2bma:rot:val")).value == 45.0
    assert (await port.read("2bma:cam:exposure")).value == 0.025
    assert (await port.read("2bma:shutter:open")).value is True


@pytest.mark.unit
async def test_execute_setpoint_records_success_entry_with_expected_payload() -> None:
    """Each successful write produces one append call with the expected payload."""
    port = InMemoryControlPort(now=lambda: _FIXED_NOW)
    port.simulate_connect("2bma:rot:val")
    appender = _FakeAppendStep()
    procedure_id = uuid4()
    principal_id = uuid4()
    correlation_id = uuid4()
    event_id = uuid4()
    conductor = _conductor(port, appender, ids=[event_id])
    await conductor.execute(
        procedure_id=procedure_id,
        principal_id=principal_id,
        correlation_id=correlation_id,
        steps=(SetpointStep(address="2bma:rot:val", value=12.5),),
    )
    assert len(appender.calls) == 1
    call = appender.calls[0]
    assert call.command.procedure_id == procedure_id
    assert call.principal_id == principal_id
    assert call.correlation_id == correlation_id
    assert len(call.command.entries) == 1
    entry = call.command.entries[0]
    assert entry.event_id == event_id
    assert entry.step_kind == "setpoint"
    assert entry.sampled_at == _FIXED_NOW
    assert entry.occurred_at == _FIXED_NOW
    assert entry.payload == {
        "address": "2bma:rot:val",
        "value": 12.5,
        "result": "ok",
    }


@pytest.mark.unit
async def test_execute_halts_at_first_not_connected_error_on_setpoint() -> None:
    """First write raises ControlNotConnectedError -> failure at index 0."""
    port = InMemoryControlPort()  # nothing connected
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender, ids=[uuid4()])
    procedure_id = uuid4()
    result = await conductor.execute(
        procedure_id=procedure_id,
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(
            SetpointStep(address="2bma:rot:val", value=1.0),
            SetpointStep(address="2bma:cam:exposure", value=0.01),
        ),
    )
    assert result.completed_count == 0
    assert result.succeeded is False
    assert result.failure == ConductorFailure(
        step_index=0,
        source_kind="setpoint",
        target="2bma:rot:val",
        error_class="ControlNotConnectedError",
        message="Control address '2bma:rot:val' not connected",
    )
    # Exactly one failure entry recorded; the second step is untouched.
    assert len(appender.calls) == 1
    failure_entry = appender.calls[0].command.entries[0]
    assert failure_entry.payload["result"] == "failed"
    assert failure_entry.payload["error_class"] == "ControlNotConnectedError"
    assert "not connected" in failure_entry.payload["message"]


@pytest.mark.unit
async def test_execute_records_earlier_setpoint_successes_before_middle_failure() -> None:
    """Middle step failure leaves earlier success records + a failure record."""
    port = InMemoryControlPort()
    port.simulate_connect("2bma:rot:val")
    # 2bma:cam:exposure NEVER simulate_connect'd -> NotConnected on second write
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender, ids=[uuid4() for _ in range(2)])
    procedure_id = uuid4()
    result = await conductor.execute(
        procedure_id=procedure_id,
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(
            SetpointStep(address="2bma:rot:val", value=1.0),
            SetpointStep(address="2bma:cam:exposure", value=0.01),
            SetpointStep(address="2bma:shutter:open", value=True),
        ),
    )
    assert result.completed_count == 1
    assert result.failure is not None
    assert result.failure.step_index == 1
    assert result.failure.target == "2bma:cam:exposure"
    # 2 append calls: one OK at index 0, one FAILED at index 1; index 2 never tried.
    assert len(appender.calls) == 2
    assert appender.calls[0].command.entries[0].payload["result"] == "ok"
    assert appender.calls[1].command.entries[0].payload["result"] == "failed"


@pytest.mark.unit
async def test_execute_passes_through_causation_and_surface_ids() -> None:
    """Optional envelope fields reach the handler verbatim."""
    port = InMemoryControlPort()
    port.simulate_connect("2bma:rot:val")
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender, ids=[uuid4()])
    causation_id = uuid4()
    surface_id = uuid4()
    await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(SetpointStep(address="2bma:rot:val", value=1.0),),
        causation_id=causation_id,
        surface_id=surface_id,
    )
    assert appender.calls[0].causation_id == causation_id
    assert appender.calls[0].surface_id == surface_id


@pytest.mark.unit
async def test_execute_does_not_catch_non_port_exceptions_on_setpoint() -> None:
    """A CancelledError mid-write propagates; nothing is recorded for it."""

    class _CancellingPort:
        async def read(self, _address: str) -> Reading:  # pragma: no cover  # unused
            raise NotImplementedError

        async def write(self, *_args: Any, **_kwargs: Any) -> None:
            raise asyncio.CancelledError

        def subscribe(self, _address: str) -> AsyncIterator[Reading]:  # pragma: no cover  # unused
            raise NotImplementedError

    appender = _FakeAppendStep()
    conductor = Conductor(
        control_port=_CancellingPort(),  # type: ignore[arg-type]
        append_step=appender,
        clock=FakeClock(_FIXED_NOW),
        id_generator=_SequenceIdGenerator([]),
    )
    with pytest.raises(asyncio.CancelledError):
        await conductor.execute(
            procedure_id=uuid4(),
            principal_id=uuid4(),
            correlation_id=uuid4(),
            steps=(SetpointStep(address="anywhere", value=1.0),),
        )
    assert appender.calls == []


@pytest.mark.unit
def test_conductor_result_succeeded_property_reflects_failure_absence() -> None:
    """`.succeeded` is True iff `.failure is None`."""
    ok = ConductorResult(procedure_id=uuid4(), completed_count=3, failure=None)
    bad = ConductorResult(
        procedure_id=uuid4(),
        completed_count=1,
        failure=ConductorFailure(
            step_index=1, source_kind="setpoint", target="x", error_class="y", message="z"
        ),
    )
    assert ok.succeeded is True
    assert bad.succeeded is False


# --- action coverage ----------------------------------------------------


@pytest.mark.unit
async def test_execute_action_invokes_registered_body_and_records_result_data() -> None:
    """Action name resolves to body; body's return Mapping lands in payload."""
    captured: list[ActionContext] = []

    async def home_motor(ctx: ActionContext) -> Mapping[str, Any]:
        captured.append(ctx)
        return {"final_position": 0.0, "homed": True}

    registry = InMemoryActionRegistry({"home_motor": home_motor})
    port = InMemoryControlPort()
    appender = _FakeAppendStep()
    event_id = uuid4()
    conductor = _conductor(port, appender, ids=[event_id], registry=registry)
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(ActionStep(name="home_motor", params={"axis": "rot"}),),
    )
    assert result.succeeded is True
    assert result.completed_count == 1
    assert len(captured) == 1
    assert captured[0].params == {"axis": "rot"}
    # The action body receives the per-conduct observing wrapper (so its IO
    # is captured for actuation provenance); it delegates to the real port.
    port.simulate_connect("2bma:rot:val")
    await captured[0].control_port.write("2bma:rot:val", 4.2)
    assert (await port.read("2bma:rot:val")).value == 4.2
    entry = appender.calls[0].command.entries[0]
    assert entry.step_kind == "action"
    assert entry.payload == {
        "name": "home_motor",
        "params": {"axis": "rot"},
        "result": "ok",
        "result_data": {"final_position": 0.0, "homed": True},
    }


@pytest.mark.unit
async def test_execute_action_unknown_name_records_failure_and_halts() -> None:
    """Unknown action name -> UnknownActionError, failure recorded, halt."""
    registry = InMemoryActionRegistry({})
    port = InMemoryControlPort()
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender, ids=[uuid4()], registry=registry)
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(
            ActionStep(name="nope", params={}),
            ActionStep(name="also_nope", params={}),
        ),
    )
    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.step_index == 0
    assert result.failure.source_kind == "action"
    assert result.failure.target == "nope"
    assert result.failure.error_class == "UnknownActionError"
    # Only one record (the failure); the second action is untouched.
    assert len(appender.calls) == 1
    payload = appender.calls[0].command.entries[0].payload
    assert payload["result"] == "failed"
    assert payload["error_class"] == "UnknownActionError"
    assert payload["name"] == "nope"


@pytest.mark.unit
async def test_execute_action_body_raising_control_error_records_failure_and_halts() -> None:
    """Body raising a Control*Error halts the Conductor + records the failure."""

    async def picky(_ctx: ActionContext) -> Mapping[str, Any]:
        raise ControlTimeoutError("test_pv", 0.5)

    registry = InMemoryActionRegistry({"picky": picky})
    port = InMemoryControlPort()
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender, ids=[uuid4()], registry=registry)
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(ActionStep(name="picky"),),
    )
    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_class == "ControlTimeoutError"
    assert result.failure.source_kind == "action"
    assert result.failure.target == "picky"
    payload = appender.calls[0].command.entries[0].payload
    assert payload["result"] == "failed"
    assert payload["error_class"] == "ControlTimeoutError"


@pytest.mark.unit
async def test_execute_action_body_raising_non_port_exception_propagates() -> None:
    """Generic exceptions in a body propagate; the Conductor does not swallow them."""

    async def buggy(_ctx: ActionContext) -> Mapping[str, Any]:
        raise RuntimeError("oops")

    registry = InMemoryActionRegistry({"buggy": buggy})
    port = InMemoryControlPort()
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender, ids=[], registry=registry)
    with pytest.raises(RuntimeError, match="oops"):
        await conductor.execute(
            procedure_id=uuid4(),
            principal_id=uuid4(),
            correlation_id=uuid4(),
            steps=(ActionStep(name="buggy"),),
        )
    assert appender.calls == []


@pytest.mark.unit
async def test_execute_walks_mixed_setpoint_and_action_steps_in_order() -> None:
    """Setpoint + action in the same step list run sequentially, in order."""
    invocations: list[str] = []

    async def open_shutter(_ctx: ActionContext) -> Mapping[str, Any]:
        invocations.append("open_shutter")
        return {"state": "open"}

    async def close_shutter(_ctx: ActionContext) -> Mapping[str, Any]:
        invocations.append("close_shutter")
        return {"state": "closed"}

    registry = InMemoryActionRegistry(
        {"open_shutter": open_shutter, "close_shutter": close_shutter}
    )
    port = InMemoryControlPort()
    port.simulate_connect("2bma:rot:val")
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender, ids=[uuid4() for _ in range(3)], registry=registry)
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(
            ActionStep(name="open_shutter"),
            SetpointStep(address="2bma:rot:val", value=90.0),
            ActionStep(name="close_shutter"),
        ),
    )
    assert result.succeeded is True
    assert result.completed_count == 3
    assert invocations == ["open_shutter", "close_shutter"]
    # 3 recorded entries in order: action / setpoint / action.
    kinds = [c.command.entries[0].step_kind for c in appender.calls]
    assert kinds == ["action", "setpoint", "action"]


@pytest.mark.unit
async def test_execute_action_default_registry_is_empty_when_omitted() -> None:
    """Conductor with no registry treats every action name as unknown."""
    port = InMemoryControlPort()
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender, ids=[uuid4()])
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(ActionStep(name="any_name"),),
    )
    assert result.failure is not None
    assert result.failure.error_class == "UnknownActionError"


# --- check coverage -----------------------------------------------------


def _good_reading(value: Any, kind: str = "Scalar") -> Reading:
    return Reading(
        value=value,
        kind=kind,  # type: ignore[arg-type]
        quality="Good",
        sampled_at=_FIXED_NOW,
    )


@pytest.mark.unit
async def test_execute_check_equals_match_records_success_with_reading() -> None:
    """EqualsCriterion that matches -> success; payload carries the reading."""
    port = InMemoryControlPort()
    port.set_reading("2bma:rot:rbv", _good_reading(45.0))
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender, ids=[uuid4()])
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(CheckStep(address="2bma:rot:rbv", criterion=EqualsCriterion(expected=45.0)),),
    )
    assert result.succeeded is True
    entry = appender.calls[0].command.entries[0]
    assert entry.step_kind == "check"
    assert entry.payload["address"] == "2bma:rot:rbv"
    assert entry.payload["criterion"] == {"kind": "equals", "expected": 45.0}
    assert entry.payload["result"] == "ok"
    assert entry.payload["reading"]["value"] == 45.0
    assert entry.payload["reading"]["quality"] == "Good"
    assert entry.payload["reading"]["sampled_at"] == _FIXED_NOW.isoformat()


@pytest.mark.unit
async def test_execute_check_equals_mismatch_halts_with_check_failed_error() -> None:
    """EqualsCriterion mismatch -> CheckFailedError halt; payload + result.failure match."""
    port = InMemoryControlPort()
    port.set_reading("2bma:rot:rbv", _good_reading(12.5))
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender, ids=[uuid4()])
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(
            CheckStep(address="2bma:rot:rbv", criterion=EqualsCriterion(expected=45.0)),
            CheckStep(address="2bma:rot:rbv", criterion=EqualsCriterion(expected=12.5)),
        ),
    )
    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.step_index == 0
    assert result.failure.source_kind == "check"
    assert result.failure.target == "2bma:rot:rbv"
    assert result.failure.error_class == "CheckFailedError"
    assert "did not equal" in result.failure.message
    # second check never runs
    assert len(appender.calls) == 1


@pytest.mark.unit
async def test_execute_check_within_tolerance_inside_range_succeeds() -> None:
    port = InMemoryControlPort()
    port.set_reading("2bma:temp:rbv", _good_reading(295.4))
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender, ids=[uuid4()])
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(
            CheckStep(
                address="2bma:temp:rbv",
                criterion=WithinToleranceCriterion(expected=295.0, tolerance=0.5),
            ),
        ),
    )
    assert result.succeeded is True


@pytest.mark.unit
async def test_execute_check_within_tolerance_outside_range_halts() -> None:
    port = InMemoryControlPort()
    port.set_reading("2bma:temp:rbv", _good_reading(296.0))
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender, ids=[uuid4()])
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(
            CheckStep(
                address="2bma:temp:rbv",
                criterion=WithinToleranceCriterion(expected=295.0, tolerance=0.5),
            ),
        ),
    )
    assert result.failure is not None
    assert result.failure.error_class == "CheckFailedError"
    assert "not within" in result.failure.message


@pytest.mark.unit
async def test_execute_check_within_tolerance_on_non_numeric_value_clean_mismatch() -> None:
    """Tolerance check on a string value treats it as a clean mismatch (no escape)."""
    port = InMemoryControlPort()
    port.set_reading("2bma:state", _good_reading("open"))
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender, ids=[uuid4()])
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(
            CheckStep(
                address="2bma:state",
                criterion=WithinToleranceCriterion(expected=1.0, tolerance=0.1),
            ),
        ),
    )
    assert result.failure is not None
    assert result.failure.error_class == "CheckFailedError"


@pytest.mark.unit
async def test_execute_check_non_good_quality_halts() -> None:
    """A Bad-quality reading halts the check with a quality= reason."""
    port = InMemoryControlPort()
    port.set_reading(
        "2bma:rot:rbv",
        Reading(
            value=45.0,
            kind="Scalar",
            quality="Bad",
            sampled_at=_FIXED_NOW,
            quality_detail="alarm_status=3",
        ),
    )
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender, ids=[uuid4()])
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(CheckStep(address="2bma:rot:rbv", criterion=EqualsCriterion(expected=45.0)),),
    )
    assert result.failure is not None
    assert result.failure.error_class == "CheckFailedError"
    assert "quality=Bad" in result.failure.message
    # The reading IS recorded in the payload alongside the failure.
    payload = appender.calls[0].command.entries[0].payload
    assert payload["reading"]["quality"] == "Bad"


@pytest.mark.unit
async def test_execute_check_uncertain_quality_halts_with_quality_reason() -> None:
    """An Uncertain-quality reading halts the check; tests the non-Bad non-Good arm.

    Pins that the implementation treats `quality != "Good"` not
    `quality == "Bad"`. A regression to the latter would silently
    let MINOR_ALARM readings through.
    """
    port = InMemoryControlPort()
    port.set_reading(
        "2bma:rot:rbv",
        Reading(
            value=45.0,
            kind="Scalar",
            quality="Uncertain",
            sampled_at=_FIXED_NOW,
            quality_detail="alarm_status=1",
        ),
    )
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender, ids=[uuid4()])
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(CheckStep(address="2bma:rot:rbv", criterion=EqualsCriterion(expected=45.0)),),
    )
    assert result.failure is not None
    assert result.failure.error_class == "CheckFailedError"
    assert "quality=Uncertain" in result.failure.message
    payload = appender.calls[0].command.entries[0].payload
    assert payload["reading"]["quality"] == "Uncertain"


@pytest.mark.unit
async def test_execute_check_read_raises_control_error_halts_with_substrate_class() -> None:
    """When read raises Control*Error, the failure carries the substrate error_class."""
    port = InMemoryControlPort()  # nothing connected -> NotConnected on read
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender, ids=[uuid4()])
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(CheckStep(address="missing", criterion=EqualsCriterion(expected=0)),),
    )
    assert result.failure is not None
    assert result.failure.error_class == "ControlNotConnectedError"
    assert result.failure.source_kind == "check"
    # No reading observed -> no reading field in the payload.
    payload = appender.calls[0].command.entries[0].payload
    assert "reading" not in payload


@pytest.mark.unit
async def test_execute_walks_mixed_setpoint_action_check_steps_in_order() -> None:
    """Mixed step kinds dispatch in order; success records carry per-kind shape."""

    async def open_shutter(_ctx: ActionContext) -> Mapping[str, Any]:
        return {"state": "open"}

    registry = InMemoryActionRegistry({"open_shutter": open_shutter})
    port = InMemoryControlPort()
    port.simulate_connect("2bma:rot:val")
    port.set_reading("2bma:rot:rbv", _good_reading(45.0))
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender, ids=[uuid4() for _ in range(3)], registry=registry)
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(
            SetpointStep(address="2bma:rot:val", value=45.0),
            ActionStep(name="open_shutter"),
            CheckStep(address="2bma:rot:rbv", criterion=EqualsCriterion(expected=45.0)),
        ),
    )
    assert result.succeeded is True
    assert result.completed_count == 3
    kinds = [c.command.entries[0].step_kind for c in appender.calls]
    assert kinds == ["setpoint", "action", "check"]


# --- conduct (FSM lifecycle) coverage -----------------------------------


@dataclass
class _LifecycleCall:
    """One recorded invocation of a fake start/complete/abort handler."""

    command: Any
    principal_id: UUID
    correlation_id: UUID
    causation_id: UUID | None
    surface_id: UUID


@dataclass
class _FakeLifecycleHandler:
    """Fake `Handler` for start/complete/abort_procedure slices.

    Records every call. Optionally raises a configured exception on
    invocation, letting tests pin the lifecycle-failure branches.
    """

    raises: Exception | None = None
    calls: list[_LifecycleCall] = field(default_factory=list[_LifecycleCall])

    async def __call__(
        self,
        command: Any,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        self.calls.append(
            _LifecycleCall(
                command=command,
                principal_id=principal_id,
                correlation_id=correlation_id,
                causation_id=causation_id,
                surface_id=surface_id,
            )
        )
        if self.raises is not None:
            raise self.raises


def _conductor_full_lifecycle(
    port: ControlPort,
    appender: _FakeAppendStep,
    *,
    start: _FakeLifecycleHandler,
    complete: _FakeLifecycleHandler,
    abort: _FakeLifecycleHandler,
    ids: Sequence[UUID] = (),
    registry: InMemoryActionRegistry | None = None,
) -> Conductor:
    return Conductor(
        control_port=port,
        append_step=appender,
        clock=FakeClock(_FIXED_NOW),
        id_generator=_SequenceIdGenerator(list(ids)),
        action_registry=registry,
        start_procedure=start,
        complete_procedure=complete,
        abort_procedure=abort,
    )


@pytest.mark.unit
async def test_conduct_happy_path_runs_start_execute_complete_in_order() -> None:
    port = InMemoryControlPort()
    port.simulate_connect("2bma:rot:val")
    appender = _FakeAppendStep()
    start = _FakeLifecycleHandler()
    complete = _FakeLifecycleHandler()
    abort = _FakeLifecycleHandler()
    procedure_id = uuid4()
    conductor = _conductor_full_lifecycle(
        port,
        appender,
        start=start,
        complete=complete,
        abort=abort,
        ids=[uuid4()],
    )
    result = await conductor.conduct(
        procedure_id=procedure_id,
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(SetpointStep(address="2bma:rot:val", value=1.0),),
    )
    assert result.succeeded is True
    assert result.completed_count == 1
    assert len(start.calls) == 1
    assert start.calls[0].command.procedure_id == procedure_id
    assert len(complete.calls) == 1
    assert complete.calls[0].command.procedure_id == procedure_id
    assert abort.calls == []


@pytest.mark.unit
async def test_conduct_without_lifecycle_handlers_raises_runtime_error() -> None:
    """conduct() requires all three FSM handlers; missing any is a wiring bug."""
    port = InMemoryControlPort()
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender)  # no FSM handlers
    with pytest.raises(RuntimeError, match="conduct"):
        await conductor.conduct(
            procedure_id=uuid4(),
            principal_id=uuid4(),
            correlation_id=uuid4(),
            steps=(),
        )


@pytest.mark.unit
async def test_conduct_start_failure_records_lifecycle_failure_without_execute() -> None:
    """start_procedure rejection -> lifecycle failure; no steps attempted."""
    port = InMemoryControlPort()
    port.simulate_connect("2bma:rot:val")
    appender = _FakeAppendStep()
    start = _FakeLifecycleHandler(raises=RuntimeError("Procedure not in Defined"))
    complete = _FakeLifecycleHandler()
    abort = _FakeLifecycleHandler()
    conductor = _conductor_full_lifecycle(
        port, appender, start=start, complete=complete, abort=abort, ids=[]
    )
    result = await conductor.conduct(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(SetpointStep(address="2bma:rot:val", value=1.0),),
    )
    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.step_index is None
    assert result.failure.source_kind == "lifecycle"
    assert result.failure.target == "start"
    assert result.failure.error_class == "RuntimeError"
    # No steps recorded; complete + abort not called.
    assert appender.calls == []
    assert complete.calls == []
    assert abort.calls == []


@pytest.mark.unit
async def test_conduct_execute_failure_invokes_abort_with_derived_reason() -> None:
    """Step failure -> abort_procedure called with reason derived from the failure."""
    port = InMemoryControlPort()  # not connected -> first setpoint fails
    appender = _FakeAppendStep()
    start = _FakeLifecycleHandler()
    complete = _FakeLifecycleHandler()
    abort = _FakeLifecycleHandler()
    procedure_id = uuid4()
    conductor = _conductor_full_lifecycle(
        port,
        appender,
        start=start,
        complete=complete,
        abort=abort,
        ids=[uuid4()],
    )
    result = await conductor.conduct(
        procedure_id=procedure_id,
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(SetpointStep(address="missing", value=1.0),),
    )
    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.source_kind == "setpoint"  # original step failure preserved
    assert result.failure.error_class == "ControlNotConnectedError"
    assert len(start.calls) == 1
    assert complete.calls == []
    assert len(abort.calls) == 1
    assert abort.calls[0].command.procedure_id == procedure_id
    reason = abort.calls[0].command.reason
    assert "setpoint" in reason
    assert "missing" in reason
    assert "ControlNotConnectedError" in reason
    assert len(reason) <= 500


@pytest.mark.unit
async def test_conduct_when_abort_itself_fails_returns_original_execute_failure() -> None:
    """If abort_procedure raises, the ORIGINAL execute failure surfaces."""
    port = InMemoryControlPort()  # NotConnected on first setpoint
    appender = _FakeAppendStep()
    start = _FakeLifecycleHandler()
    complete = _FakeLifecycleHandler()
    abort = _FakeLifecycleHandler(raises=RuntimeError("abort also failed"))
    conductor = _conductor_full_lifecycle(
        port,
        appender,
        start=start,
        complete=complete,
        abort=abort,
        ids=[uuid4()],
    )
    result = await conductor.conduct(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(SetpointStep(address="missing", value=1.0),),
    )
    # Original execute failure surfaces; the secondary abort failure is suppressed.
    assert result.failure is not None
    assert result.failure.source_kind == "setpoint"
    assert result.failure.error_class == "ControlNotConnectedError"
    assert len(abort.calls) == 1


# --- setpoint verify coverage -------------------------------------------


@pytest.mark.unit
async def test_setpoint_default_verify_omits_post_reading_from_payload() -> None:
    """verify=False (default) leaves the payload without post_reading / post_read_error."""
    port = InMemoryControlPort(now=lambda: _FIXED_NOW)
    port.simulate_connect("2bma:rot:val")
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender, ids=[uuid4()])
    await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(SetpointStep(address="2bma:rot:val", value=1.0),),
    )
    payload = appender.calls[0].command.entries[0].payload
    assert "post_reading" not in payload
    assert "post_read_error" not in payload


@pytest.mark.unit
async def test_setpoint_verify_attaches_post_reading_to_payload() -> None:
    """verify=True after a successful write records the read value as evidence."""
    port = InMemoryControlPort(now=lambda: _FIXED_NOW)
    port.simulate_connect("2bma:rot:val")
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender, ids=[uuid4()])
    await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(SetpointStep(address="2bma:rot:val", value=4.2, verify=True),),
    )
    payload = appender.calls[0].command.entries[0].payload
    assert payload["result"] == "ok"
    assert payload["post_reading"]["value"] == 4.2
    assert payload["post_reading"]["quality"] == "Good"
    assert payload["post_reading"]["sampled_at"] == _FIXED_NOW.isoformat()
    assert "post_read_error" not in payload


@pytest.mark.unit
async def test_setpoint_verify_records_bad_quality_reading_without_halting() -> None:
    """A Bad-quality post-read is evidence; the setpoint stays successful."""
    port = InMemoryControlPort(now=lambda: _FIXED_NOW)
    port.simulate_connect("2bma:rot:val")
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender, ids=[uuid4()])
    procedure_id = uuid4()
    # Wire the write to land + then overwrite the cached Reading with Bad quality.
    # InMemoryControlPort's write hard-codes Good, so use set_reading post-write
    # via a small fake. Simpler: subclass-shaped override is heavy; instead pre-seed
    # a Bad-quality reading that the write will overwrite, then immediately re-seed
    # Bad-quality through set_reading by patching write to skip overwrite.
    # Cleanest path: pre-seed Bad; rely on write to overwrite to Good; this test
    # does it differently - set_reading AFTER conductor.execute setpoint phase.
    # Workaround: build a minimal stub port instead.

    class _StubPort:
        async def read(self, _address: str) -> Reading:
            return Reading(
                value=4.2,
                kind="Scalar",
                quality="Bad",
                sampled_at=_FIXED_NOW,
                quality_detail="alarm_status=3",
            )

        async def write(self, *_args: Any, **_kwargs: Any) -> None:
            return None

        def subscribe(self, _address: str) -> AsyncIterator[Reading]:  # pragma: no cover
            raise NotImplementedError

    conductor = Conductor(
        control_port=_StubPort(),  # type: ignore[arg-type]
        append_step=appender,
        clock=FakeClock(_FIXED_NOW),
        id_generator=_SequenceIdGenerator([uuid4()]),
    )
    result = await conductor.execute(
        procedure_id=procedure_id,
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(SetpointStep(address="2bma:rot:val", value=4.2, verify=True),),
    )
    assert result.succeeded is True
    payload = appender.calls[0].command.entries[0].payload
    assert payload["result"] == "ok"
    assert payload["post_reading"]["quality"] == "Bad"
    assert payload["post_reading"]["quality_detail"] == "alarm_status=3"
    _ = port  # silence unused-var (kept for fixture parity with sibling tests)


@pytest.mark.unit
async def test_setpoint_verify_records_read_failure_as_post_read_error() -> None:
    """post-read raising Control*Error -> post_read_error in payload, setpoint still succeeded."""

    class _WriteOnlyPort:
        async def read(self, address: str) -> Reading:
            from cora.operation.ports.control_port import ControlNotConnectedError

            raise ControlNotConnectedError(address)

        async def write(self, *_args: Any, **_kwargs: Any) -> None:
            return None

        def subscribe(self, _address: str) -> AsyncIterator[Reading]:  # pragma: no cover
            raise NotImplementedError

    appender = _FakeAppendStep()
    conductor = Conductor(
        control_port=_WriteOnlyPort(),  # type: ignore[arg-type]
        append_step=appender,
        clock=FakeClock(_FIXED_NOW),
        id_generator=_SequenceIdGenerator([uuid4()]),
    )
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(SetpointStep(address="lonely", value=1.0, verify=True),),
    )
    assert result.succeeded is True
    payload = appender.calls[0].command.entries[0].payload
    assert payload["result"] == "ok"
    assert "post_reading" not in payload
    assert payload["post_read_error"]["error_class"] == "ControlNotConnectedError"
    assert "not connected" in payload["post_read_error"]["message"]


@pytest.mark.unit
async def test_setpoint_verify_does_not_change_write_failure_halt_behavior() -> None:
    """A write failure halts regardless of verify; no post-read is attempted."""
    port = InMemoryControlPort()  # NotConnected on the write
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender, ids=[uuid4()])
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(SetpointStep(address="missing", value=1.0, verify=True),),
    )
    assert result.succeeded is False
    payload = appender.calls[0].command.entries[0].payload
    assert payload["result"] == "failed"
    assert payload["error_class"] == "ControlNotConnectedError"
    assert "post_reading" not in payload
    assert "post_read_error" not in payload


@pytest.mark.unit
async def test_conduct_cancellation_mid_execute_attempts_abort_then_reraises() -> None:
    """CancelledError mid-execute triggers best-effort abort + re-raises."""

    class _CancellingPort:
        async def read(self, _address: str) -> Reading:  # pragma: no cover  # unused
            raise NotImplementedError

        async def write(self, *_args: Any, **_kwargs: Any) -> None:
            raise asyncio.CancelledError

        def subscribe(self, _address: str) -> AsyncIterator[Reading]:  # pragma: no cover
            raise NotImplementedError

    appender = _FakeAppendStep()
    start = _FakeLifecycleHandler()
    complete = _FakeLifecycleHandler()
    abort = _FakeLifecycleHandler()
    procedure_id = uuid4()
    conductor = Conductor(
        control_port=_CancellingPort(),  # type: ignore[arg-type]
        append_step=appender,
        clock=FakeClock(_FIXED_NOW),
        id_generator=_SequenceIdGenerator([]),
        start_procedure=start,
        complete_procedure=complete,
        abort_procedure=abort,
    )
    with pytest.raises(asyncio.CancelledError):
        await conductor.conduct(
            procedure_id=procedure_id,
            principal_id=uuid4(),
            correlation_id=uuid4(),
            steps=(SetpointStep(address="any", value=1.0),),
        )
    # Start was called; complete was not; abort was called with the cancelled reason.
    assert len(start.calls) == 1
    assert complete.calls == []
    assert len(abort.calls) == 1
    assert abort.calls[0].command.procedure_id == procedure_id
    assert "cancelled" in abort.calls[0].command.reason


@pytest.mark.unit
async def test_conduct_cancellation_reraises_even_when_abort_itself_fails() -> None:
    """If abort_procedure raises during cancellation cleanup, CancelledError still surfaces."""

    class _CancellingPort:
        async def read(self, _address: str) -> Reading:  # pragma: no cover
            raise NotImplementedError

        async def write(self, *_args: Any, **_kwargs: Any) -> None:
            raise asyncio.CancelledError

        def subscribe(self, _address: str) -> AsyncIterator[Reading]:  # pragma: no cover
            raise NotImplementedError

    appender = _FakeAppendStep()
    start = _FakeLifecycleHandler()
    complete = _FakeLifecycleHandler()
    abort = _FakeLifecycleHandler(raises=RuntimeError("abort also failed"))
    conductor = Conductor(
        control_port=_CancellingPort(),  # type: ignore[arg-type]
        append_step=appender,
        clock=FakeClock(_FIXED_NOW),
        id_generator=_SequenceIdGenerator([]),
        start_procedure=start,
        complete_procedure=complete,
        abort_procedure=abort,
    )
    with pytest.raises(asyncio.CancelledError):
        await conductor.conduct(
            procedure_id=uuid4(),
            principal_id=uuid4(),
            correlation_id=uuid4(),
            steps=(SetpointStep(address="any", value=1.0),),
        )
    assert len(abort.calls) == 1


@pytest.mark.unit
async def test_conduct_complete_failure_overrides_success_with_lifecycle_failure() -> None:
    """complete_procedure rejection -> lifecycle failure replaces the prior success."""
    port = InMemoryControlPort()
    port.simulate_connect("2bma:rot:val")
    appender = _FakeAppendStep()
    start = _FakeLifecycleHandler()
    complete = _FakeLifecycleHandler(raises=RuntimeError("Procedure not in Running"))
    abort = _FakeLifecycleHandler()
    conductor = _conductor_full_lifecycle(
        port,
        appender,
        start=start,
        complete=complete,
        abort=abort,
        ids=[uuid4()],
    )
    result = await conductor.conduct(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(SetpointStep(address="2bma:rot:val", value=1.0),),
    )
    assert result.failure is not None
    assert result.failure.source_kind == "lifecycle"
    assert result.failure.target == "complete"
    assert result.failure.error_class == "RuntimeError"
    assert result.completed_count == 1  # the step DID succeed
    assert abort.calls == []  # complete failure doesn't trigger abort


@pytest.mark.unit
async def test_conduct_check_failure_after_setpoint_triggers_abort_with_check_target() -> None:
    """A check failing AFTER a setpoint succeeded aborts the procedure with check-targeted reason.

    Pins the multi-step abort flow: prior steps succeeded + recorded;
    the failing step is also recorded; abort fires with a reason
    derived from the check failure (not the prior setpoint).
    """
    port = InMemoryControlPort()
    port.simulate_connect("2bma:rot:val")
    port.set_reading(
        "2bma:rot:rbv",
        Reading(value=12.5, kind="Scalar", quality="Good", sampled_at=_FIXED_NOW),
    )
    appender = _FakeAppendStep()
    start = _FakeLifecycleHandler()
    complete = _FakeLifecycleHandler()
    abort = _FakeLifecycleHandler()
    conductor = _conductor_full_lifecycle(
        port,
        appender,
        start=start,
        complete=complete,
        abort=abort,
        ids=[uuid4(), uuid4()],
    )
    procedure_id = uuid4()
    result = await conductor.conduct(
        procedure_id=procedure_id,
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(
            SetpointStep(address="2bma:rot:val", value=45.0),
            CheckStep(address="2bma:rot:rbv", criterion=EqualsCriterion(expected=45.0)),
        ),
    )
    assert result.succeeded is False
    assert result.completed_count == 1  # setpoint succeeded
    assert result.failure is not None
    assert result.failure.step_index == 1
    assert result.failure.source_kind == "check"
    assert result.failure.target == "2bma:rot:rbv"
    assert result.failure.error_class == "CheckFailedError"
    # abort was invoked with a reason pointing at the failing check.
    assert len(abort.calls) == 1
    reason = abort.calls[0].command.reason
    assert "check[1]" in reason
    assert "CheckFailedError" in reason


@pytest.mark.unit
async def test_conduct_reraises_unauthorized_error_from_start_procedure() -> None:
    """UnauthorizedError from start_procedure propagates so the route maps it to 403.

    The conduct() lifecycle catch is narrowed so
    authz / not-found / concurrency errors surface as exceptions
    rather than as 200-OK structured failures. The route layer's
    existing exception handlers (`cora/operation/routes.py`) map them
    to the right HTTP status codes.
    """
    from cora.operation.errors import UnauthorizedError

    port = InMemoryControlPort()
    appender = _FakeAppendStep()
    start = _FakeLifecycleHandler(raises=UnauthorizedError("denied"))
    complete = _FakeLifecycleHandler()
    abort = _FakeLifecycleHandler()
    conductor = _conductor_full_lifecycle(
        port, appender, start=start, complete=complete, abort=abort, ids=[]
    )
    with pytest.raises(UnauthorizedError, match="denied"):
        await conductor.conduct(
            procedure_id=uuid4(),
            principal_id=uuid4(),
            correlation_id=uuid4(),
            steps=(),
        )


@pytest.mark.unit
async def test_conduct_reraises_procedure_not_found_error_from_start_procedure() -> None:
    """ProcedureNotFoundError propagates so the route maps it to 404."""
    from cora.operation.aggregates.procedure import ProcedureNotFoundError

    port = InMemoryControlPort()
    appender = _FakeAppendStep()
    procedure_id = uuid4()
    start = _FakeLifecycleHandler(raises=ProcedureNotFoundError(procedure_id))
    conductor = _conductor_full_lifecycle(
        port,
        appender,
        start=start,
        complete=_FakeLifecycleHandler(),
        abort=_FakeLifecycleHandler(),
        ids=[],
    )
    with pytest.raises(ProcedureNotFoundError):
        await conductor.conduct(
            procedure_id=procedure_id,
            principal_id=uuid4(),
            correlation_id=uuid4(),
            steps=(),
        )


@pytest.mark.unit
async def test_conduct_reraises_concurrency_error_from_complete_procedure() -> None:
    """ConcurrencyError on complete propagates so the route doesn't mask it as 200-OK."""
    from cora.infrastructure.ports.event_store import ConcurrencyError

    port = InMemoryControlPort()
    appender = _FakeAppendStep()
    complete = _FakeLifecycleHandler(
        raises=ConcurrencyError(
            stream_type="Procedure",
            stream_id=uuid4(),
            expected=2,
            actual=3,
        )
    )
    conductor = _conductor_full_lifecycle(
        port,
        appender,
        start=_FakeLifecycleHandler(),
        complete=complete,
        abort=_FakeLifecycleHandler(),
        ids=[],
    )
    with pytest.raises(ConcurrencyError):
        await conductor.conduct(
            procedure_id=uuid4(),
            principal_id=uuid4(),
            correlation_id=uuid4(),
            steps=(),
        )


@pytest.mark.unit
async def test_execute_setpoint_via_registry_with_unrouted_address_records_failure() -> None:
    """NoAdapterForAddressError now lives in _CONTROL_ERRORS; records + halts cleanly."""
    from cora.operation.adapters.control_port_registry import ControlPortRegistry

    registry = ControlPortRegistry()
    registry.register("known:", InMemoryControlPort())
    appender = _FakeAppendStep()
    conductor = Conductor(
        control_port=registry,
        append_step=appender,
        clock=FakeClock(_FIXED_NOW),
        id_generator=_SequenceIdGenerator([uuid4()]),
    )
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(SetpointStep(address="unknown:rot:val", value=1.0),),
    )
    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_class == "NoAdapterForAddressError"
    assert result.failure.source_kind == "setpoint"
    # Recorded in logbook, not propagated as a 500.
    assert len(appender.calls) == 1
    assert appender.calls[0].command.entries[0].payload["result"] == "failed"


# --- actuation provenance (ActuationKind) -------------------------------


@pytest.mark.unit
async def test_actuation_kind_is_physical_when_route_not_simulated() -> None:
    """A conduct over only physical routes records ActuationKind.Physical."""
    inner = InMemoryControlPort()
    inner.simulate_connect("2bma:rot:val")
    registry = ControlPortRegistry()
    registry.register("2bma:", inner, is_simulated=False)
    appender = _FakeAppendStep()
    conductor = _conductor(registry, appender, ids=[uuid4()])
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(SetpointStep(address="2bma:rot:val", value=1.0),),
    )
    assert result.succeeded is True
    assert result.actuation_kind is ActuationKind.PHYSICAL


@pytest.mark.unit
async def test_actuation_kind_is_simulated_when_route_is_simulated() -> None:
    """A route declared simulated records ActuationKind.Simulated.

    The transport here is in-memory, but the same holds for a soft IOC
    fronted by a real CA adapter: only the declared is_simulated flag,
    not the transport, distinguishes a rehearsal from real hardware.
    """
    inner = InMemoryControlPort()
    inner.simulate_connect("sim:rot:val")
    registry = ControlPortRegistry()
    registry.register("sim:", inner, is_simulated=True)
    appender = _FakeAppendStep()
    conductor = _conductor(registry, appender, ids=[uuid4()])
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(SetpointStep(address="sim:rot:val", value=1.0),),
    )
    assert result.succeeded is True
    assert result.actuation_kind is ActuationKind.SIMULATED


@pytest.mark.unit
async def test_actuation_kind_is_hybrid_when_conduct_touches_both() -> None:
    """One conduct over a simulated and a physical route records Hybrid."""
    sim = InMemoryControlPort()
    sim.simulate_connect("sim:m1")
    real = InMemoryControlPort()
    real.simulate_connect("real:m1")
    registry = ControlPortRegistry()
    registry.register("sim:", sim, is_simulated=True)
    registry.register("real:", real, is_simulated=False)
    appender = _FakeAppendStep()
    conductor = _conductor(registry, appender, ids=[uuid4(), uuid4()])
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(
            SetpointStep(address="sim:m1", value=1.0),
            SetpointStep(address="real:m1", value=2.0),
        ),
    )
    assert result.succeeded is True
    assert result.actuation_kind is ActuationKind.HYBRID


@pytest.mark.unit
async def test_actuation_kind_is_none_for_bare_port_without_routing_table() -> None:
    """An opt-out in-memory deployment (no registry) records no kind.

    Nothing declares simulated-ness, so the kind stays None and the
    downstream promotion gate is inactive.
    """
    port = InMemoryControlPort()
    port.simulate_connect("2bma:rot:val")
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender, ids=[uuid4()])
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(SetpointStep(address="2bma:rot:val", value=1.0),),
    )
    assert result.succeeded is True
    assert result.actuation_kind is None


@pytest.mark.unit
async def test_actuation_kind_is_none_when_no_step_touches_control_port() -> None:
    """A conduct that drives nothing (empty steps) records no kind."""
    registry = ControlPortRegistry()
    registry.register("2bma:", InMemoryControlPort(), is_simulated=True)
    appender = _FakeAppendStep()
    conductor = _conductor(registry, appender)
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(),
    )
    assert result.actuation_kind is None


@pytest.mark.unit
async def test_actuation_kind_is_simulated_when_action_body_drives_simulated_route() -> None:
    """Action-body IO routes through the same observer seam: an action that
    writes to a simulated route taints the conduct Simulated."""
    inner = InMemoryControlPort()
    inner.simulate_connect("sim:m1")
    control = ControlPortRegistry()
    control.register("sim:", inner, is_simulated=True)

    async def drive(ctx: ActionContext) -> Mapping[str, Any]:
        await ctx.control_port.write("sim:m1", 1.0)
        return {}

    appender = _FakeAppendStep()
    conductor = _conductor(
        control,
        appender,
        ids=[uuid4()],
        registry=InMemoryActionRegistry({"drive": drive}),
    )
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(ActionStep(name="drive", params={}),),
    )
    assert result.succeeded is True
    assert result.actuation_kind is ActuationKind.SIMULATED


@pytest.mark.unit
async def test_actuation_kind_is_simulated_when_setpoint_write_fails_on_simulated_route() -> None:
    """A write that resolves a simulated route and then fails still taints the
    conduct: the kind reflects routes attempted, not only succeeded."""
    inner = InMemoryControlPort()  # never connected -> write raises
    control = ControlPortRegistry()
    control.register("sim:", inner, is_simulated=True)
    appender = _FakeAppendStep()
    conductor = _conductor(control, appender, ids=[uuid4()])
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(SetpointStep(address="sim:m1", value=1.0),),
    )
    assert result.succeeded is False
    assert result.actuation_kind is ActuationKind.SIMULATED


# --- the bridge: conduct() threads the observed kind onto the terminal command ---


@pytest.mark.unit
async def test_conduct_threads_simulated_kind_into_complete_command() -> None:
    """The activation bridge: a successful conduct over a simulated route
    passes the observed ActuationKind value onto CompleteProcedure, where the
    decider records it on ProcedureCompleted for the Data BC to read back."""
    inner = InMemoryControlPort()
    inner.simulate_connect("sim:rot:val")
    registry = ControlPortRegistry()
    registry.register("sim:", inner, is_simulated=True)
    appender = _FakeAppendStep()
    start = _FakeLifecycleHandler()
    complete = _FakeLifecycleHandler()
    abort = _FakeLifecycleHandler()
    conductor = _conductor_full_lifecycle(
        registry, appender, start=start, complete=complete, abort=abort, ids=[uuid4()]
    )
    result = await conductor.conduct(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(SetpointStep(address="sim:rot:val", value=1.0),),
    )
    assert result.succeeded is True
    assert len(complete.calls) == 1
    assert complete.calls[0].command.actuation_kind == "Simulated"
    assert abort.calls == []


@pytest.mark.unit
async def test_conduct_threads_kind_into_abort_command_on_execute_failure() -> None:
    """A conduct that fails mid-execute over a simulated route still carries the
    observed kind onto AbortProcedure (honest provenance for aborted-conduct
    data; routes attempted before the failing step taint it)."""
    inner = InMemoryControlPort()  # never connected -> the write fails
    registry = ControlPortRegistry()
    registry.register("sim:", inner, is_simulated=True)
    appender = _FakeAppendStep()
    start = _FakeLifecycleHandler()
    complete = _FakeLifecycleHandler()
    abort = _FakeLifecycleHandler()
    conductor = _conductor_full_lifecycle(
        registry, appender, start=start, complete=complete, abort=abort, ids=[uuid4()]
    )
    result = await conductor.conduct(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(SetpointStep(address="sim:m1", value=1.0),),
    )
    assert result.succeeded is False
    assert len(abort.calls) == 1
    assert abort.calls[0].command.actuation_kind == "Simulated"
    assert complete.calls == []


@pytest.mark.unit
async def test_conduct_threads_none_kind_into_complete_for_bare_port() -> None:
    """An opt-out deployment (bare port, no routing table) observes no kind, so
    CompleteProcedure carries None and the downstream gate stays inactive."""
    port = InMemoryControlPort()
    port.simulate_connect("2bma:rot:val")
    appender = _FakeAppendStep()
    start = _FakeLifecycleHandler()
    complete = _FakeLifecycleHandler()
    abort = _FakeLifecycleHandler()
    conductor = _conductor_full_lifecycle(
        port, appender, start=start, complete=complete, abort=abort, ids=[uuid4()]
    )
    result = await conductor.conduct(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(SetpointStep(address="2bma:rot:val", value=1.0),),
    )
    assert result.succeeded is True
    assert complete.calls[0].command.actuation_kind is None
