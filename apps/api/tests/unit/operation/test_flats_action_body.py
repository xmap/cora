"""Unit tests for the `flats` action body and its `FlatsParams` schema.

`flats` brackets one `collect` cycle with a save-and-restore of the
sample axis: read the current position, drive off the beam centre by
`clearance` (an absolute write, since CORA has no relative-move
primitive), run the collect cycle, then restore the axis to the saved
position. Tests verify that bracketing contract (retract before collect,
restore after, signed clearance, and the no-rollback-on-failure
behaviour) without re-asserting the inner collect contract that
`test_collect_action_body.py` covers.

  Params validation (FlatsParams.model_validate):
  - Inherited CollectParams shape passes through (axis + clearance added)
  - clearance is required
  - clearance must be nonzero (zero leaves the sample in the beam)
  - Inherited polarity-required rule still applies (ExternalEdge)
  - clearance carries the canonical {system, code} mm unit annotation

  Body behaviour (flats called directly with ActionContext):
  - Reads the axis, drives saved+clearance, collects, restores saved
  - Final axis value is the saved value (restore landed)
  - Negative clearance retracts the other direction
  - Write order: axis off-centre, then the collect cycle, then axis restore
  - A collect failure propagates AND leaves the axis retracted (no restore)
  - A non-numeric axis read maps to ControlValueCoercionError, no move
  - A non-finite (NaN/inf) axis read maps to ControlValueCoercionError

  End-to-end via Conductor:
  - InMemoryActionRegistry({"flats": flats}) + ActionStep produces
    ConductorResult.succeeded=True with the expected payload shape
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from cora.infrastructure.ports.clock import FakeClock
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.conductor import (
    ActionContext,
    ActionStep,
    Conductor,
    InMemoryActionRegistry,
)
from cora.operation.ports.control_port import (
    ControlNotConnectedError,
    ControlValueCoercionError,
    Reading,
)
from cora.operation.staging import FlatsParams, flats

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping

    from cora.operation.features.append_activities.command import (
        AppendProcedureActivities,
    )

_FIXED_NOW = datetime(2026, 6, 22, 11, 0, 0, tzinfo=UTC)
_DETECTOR = "2bma:cam1"
_AXIS = "2bma:sample:x"


def _seed_detector_and_axis(port: InMemoryControlPort, *, axis_value: float = 12.5) -> None:
    """Seed the AD PVs `collect` touches plus the axis `flats` reads + restores."""
    port.simulate_connect(f"{_DETECTOR}:TriggerMode")
    port.simulate_connect(f"{_DETECTOR}:AcquireTime")
    port.simulate_connect(f"{_DETECTOR}:NumImages")
    port.simulate_connect(f"{_DETECTOR}:Acquire")
    port.simulate_connect(_AXIS)
    port.set_reading(
        _AXIS,
        Reading(value=axis_value, kind="Scalar", quality="Good", sampled_at=_FIXED_NOW),
    )
    port.set_reading(
        f"{_DETECTOR}:Acquire_RBV",
        Reading(value=0, kind="Scalar", quality="Good", sampled_at=_FIXED_NOW),
    )
    port.set_reading(
        f"{_DETECTOR}:DetectorState_RBV",
        Reading(value="Idle", kind="Categorical", quality="Good", sampled_at=_FIXED_NOW),
    )


def _ctx(port: InMemoryControlPort, params: Mapping[str, Any]) -> ActionContext:
    return ActionContext(
        control_port=port,
        clock=FakeClock(_FIXED_NOW),
        params=params,
    )


def _params(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "detector": _DETECTOR,
        "trigger_mode": "Internal",
        "axis": _AXIS,
        "clearance": 5.0,
        "dwell": 0.05,
    }
    base.update(overrides)
    return base


# --- FlatsParams validation --------------------------------------------


@pytest.mark.unit
def test_flats_params_internal_with_axis_and_clearance_accepted() -> None:
    params = FlatsParams.model_validate(_params())
    assert params.axis == _AXIS
    assert params.clearance == 5.0


@pytest.mark.unit
def test_flats_params_clearance_required() -> None:
    bad = _params()
    del bad["clearance"]
    with pytest.raises(ValidationError):
        FlatsParams.model_validate(bad)


@pytest.mark.unit
def test_flats_params_zero_clearance_rejected() -> None:
    """Zero clearance would leave the sample in the beam -> a flat with the
    sample present, silently corrupting downstream normalization."""
    with pytest.raises(ValidationError, match="nonzero"):
        FlatsParams.model_validate(_params(clearance=0.0))


@pytest.mark.unit
def test_flats_params_inherits_collect_external_edge_constraint() -> None:
    """FlatsParams reuses CollectParams's polarity-required rule."""
    with pytest.raises(ValidationError, match="polarity required"):
        FlatsParams.model_validate(_params(trigger_mode="ExternalEdge", source="2bma:PCOMP1.OUT"))


@pytest.mark.unit
def test_flats_params_json_schema_carries_unit_annotation_on_clearance() -> None:
    schema = FlatsParams.model_json_schema()
    clearance_schema = schema["properties"]["clearance"]
    assert clearance_schema["unit"] == {"system": "udunits", "code": "mm"}


# --- flats body behaviour ----------------------------------------------


@pytest.mark.unit
async def test_flats_reads_axis_drives_offcenter_collects_and_restores() -> None:
    """Positive clearance: retract to saved+clearance, collect, restore to saved."""
    port = InMemoryControlPort()
    _seed_detector_and_axis(port, axis_value=12.5)
    result = await flats(_ctx(port, _params(clearance=5.0)))

    assert result["axis"] == _AXIS
    assert result["saved_value"] == 12.5
    assert result["offcenter_target"] == 17.5
    assert result["clearance"] == 5.0
    assert result["collect"]["trigger_mode"] == "Internal"
    assert result["collect"]["detector_state_final"] == "Idle"
    # The axis ended back at the saved aligned-centre position (restore landed).
    assert (await port.read(_AXIS)).value == 12.5


@pytest.mark.unit
async def test_flats_negative_clearance_retracts_other_direction() -> None:
    port = InMemoryControlPort()
    _seed_detector_and_axis(port, axis_value=12.5)
    result = await flats(_ctx(port, _params(clearance=-5.0)))
    assert result["offcenter_target"] == 7.5
    assert (await port.read(_AXIS)).value == 12.5


@pytest.mark.unit
async def test_flats_write_order_offcenter_then_collect_then_restore() -> None:
    """Retract write precedes the collect cycle; restore write follows it."""

    @dataclass
    class _RecordingPort:
        delegate: InMemoryControlPort
        writes: list[tuple[str, Any]] = field(default_factory=list[tuple[str, Any]])

        async def write(
            self,
            address: str,
            value: Any,
            *,
            wait: bool = True,
            timeout_s: float = 30.0,
        ) -> None:
            self.writes.append((address, value))
            await self.delegate.write(address, value, wait=wait, timeout_s=timeout_s)

        async def read(self, address: str) -> Reading:
            return await self.delegate.read(address)

        def subscribe(self, address: str) -> AsyncIterator[Reading]:
            return self.delegate.subscribe(address)

    inner = InMemoryControlPort()
    _seed_detector_and_axis(inner, axis_value=12.5)
    port = _RecordingPort(delegate=inner)
    await flats(
        _ctx(
            port,  # type: ignore[arg-type]
            _params(clearance=5.0),
        )
    )
    addresses = [addr for addr, _ in port.writes]
    assert addresses == [
        _AXIS,  # retract to off-centre
        f"{_DETECTOR}:TriggerMode",
        f"{_DETECTOR}:AcquireTime",
        f"{_DETECTOR}:NumImages",
        f"{_DETECTOR}:Acquire",
        _AXIS,  # restore to saved
    ]
    axis_values = [value for addr, value in port.writes if addr == _AXIS]
    assert axis_values == [17.5, 12.5]


@pytest.mark.unit
async def test_flats_collect_failure_leaves_axis_retracted_without_restore() -> None:
    """A collect failure propagates and the axis stays off-centre (no rollback).

    Matches the collect / discrete / continuous no-try/finally contract:
    the Conductor records the step failure and the operator reconciles the
    retracted axis. Off-centre is the sample-out (out-of-beam) position, an
    acceptable fault state.
    """
    port = InMemoryControlPort()
    _seed_detector_and_axis(port, axis_value=12.5)
    port.simulate_disconnect(f"{_DETECTOR}:TriggerMode")  # collect's first write fails
    with pytest.raises(ControlNotConnectedError):
        await flats(_ctx(port, _params(clearance=5.0)))
    # The retract landed; the restore never ran.
    assert (await port.read(_AXIS)).value == 17.5


@pytest.mark.unit
async def test_flats_non_numeric_axis_read_raises_value_coercion_without_moving() -> None:
    """A non-numeric axis read maps to a Conductor-recordable error, no move.

    The saved+clearance arithmetic needs a number; a categorical/string
    read is mapped to ControlValueCoercionError (which the Conductor
    catches and records as a structured failure) instead of a bare
    TypeError that would escape the Conductor. The read precedes any
    write, so the axis never moves.
    """
    port = InMemoryControlPort()
    _seed_detector_and_axis(port)
    port.set_reading(
        _AXIS,
        Reading(value="parked", kind="Categorical", quality="Good", sampled_at=_FIXED_NOW),
    )
    with pytest.raises(ControlValueCoercionError):
        await flats(_ctx(port, _params(clearance=5.0)))
    # Nothing actuated: the axis still reads the same categorical value.
    assert (await port.read(_AXIS)).value == "parked"


@pytest.mark.unit
async def test_flats_non_finite_axis_read_raises_value_coercion() -> None:
    """A NaN/inf axis read maps to ControlValueCoercionError, not a NaN write.

    NaN/inf is a float (passes the isinstance check) but `saved + clearance`
    would carry it into an absolute write of an undefined setpoint. The
    isfinite guard turns it into a Conductor-recordable failure before any
    move (the read precedes the write).
    """
    port = InMemoryControlPort()
    _seed_detector_and_axis(port)
    port.set_reading(
        _AXIS,
        Reading(value=float("nan"), kind="Scalar", quality="Good", sampled_at=_FIXED_NOW),
    )
    with pytest.raises(ControlValueCoercionError):
        await flats(_ctx(port, _params(clearance=5.0)))


# --- end-to-end via Conductor ------------------------------------------


@dataclass
class _AppendCall:
    command: AppendProcedureActivities
    principal_id: UUID
    correlation_id: UUID
    causation_id: UUID | None
    surface_id: UUID


@dataclass
class _FakeAppendStep:
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
    ids: list[UUID]
    _index: int = 0

    def new_id(self) -> UUID:
        if self._index >= len(self.ids):
            raise RuntimeError("FixedIdGenerator exhausted")
        out = self.ids[self._index]
        self._index += 1
        return out


@pytest.mark.unit
async def test_conductor_executes_flats_action_and_records_step_entry() -> None:
    """Conductor + registered `flats` body + ActionStep -> success + recorded evidence."""
    port = InMemoryControlPort()
    _seed_detector_and_axis(port, axis_value=12.5)
    appender = _FakeAppendStep()
    registry = InMemoryActionRegistry({"flats": flats})
    conductor = Conductor(
        control_port=port,
        append_step=appender,
        clock=FakeClock(_FIXED_NOW),
        id_generator=_SequenceIdGenerator([uuid4(), uuid4()]),
        action_registry=registry,
    )
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(ActionStep(name="flats", params=_params(clearance=5.0)),),
    )
    assert result.succeeded is True
    assert result.completed_count == 1
    # calls[0] is the pre-effect in-flight marker; calls[1] is the outcome.
    assert appender.calls[0].command.entries[0].payload["result"] == "in_flight"
    entry = appender.calls[1].command.entries[0]
    assert entry.step_kind == "action"
    assert entry.payload["name"] == "flats"
    assert entry.payload["result"] == "ok"
    result_data = entry.payload["result_data"]
    assert result_data["axis"] == _AXIS
    assert result_data["saved_value"] == 12.5
    assert result_data["offcenter_target"] == 17.5
