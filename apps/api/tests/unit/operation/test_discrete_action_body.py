"""Unit tests for the `discrete` action body and its `DiscreteParams` schema.

`discrete` composes `collect` per point on a trajectory; tests verify
the composition contract (axis writes interleave with collect cycles,
per-point evidence aggregates, failures halt) without re-asserting the
inner collect contract that `test_collect_action_body.py` covers.

  Params validation (DiscreteParams.model_validate):
  - Inherited CollectParams shape passes through (Internal, ExternalEdge, etc.)
  - Empty points tuple rejected (min_length=1)
  - Single-point trajectory accepted
  - wait defaults to 0.0
  - Negative wait rejected
  - wait carries the canonical {system, code} unit annotation in JSON Schema

  Body behaviour (discrete called directly with ActionContext):
  - Three points -> three axis writes interleaved with three collect cycles
  - per_point_results entries stamp the visited point value
  - Top-level evidence carries axis + points_visited + per_point_results
  - wait=0 skips per-point asyncio.sleep
  - First-point axis write failure propagates
  - Single-point trajectory still produces one cycle

  End-to-end via Conductor:
  - InMemoryActionRegistry({"discrete": discrete}) + ActionStep
    produces ConductorResult.succeeded=True with the expected payload shape
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
from cora.operation.acquisitions import DiscreteParams, discrete
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.conductor import (
    ActionContext,
    ActionStep,
    Conductor,
    InMemoryActionRegistry,
)
from cora.operation.ports.control_port import (
    ControlNotConnectedError,
    Measurement,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping

    from cora.operation.features.append_activities.command import (
        AppendProcedureActivities,
    )

_FIXED_NOW = datetime(2026, 5, 31, 11, 0, 0, tzinfo=UTC)
_DETECTOR = "2bma:cam1"
_AXIS = "2bma:rot:val"


def _seed_detector_and_axis(port: InMemoryControlPort) -> None:
    """Seed the AD PVs `collect` touches plus the axis address `discrete` writes."""
    port.simulate_connect(f"{_DETECTOR}:TriggerMode")
    port.simulate_connect(f"{_DETECTOR}:AcquireTime")
    port.simulate_connect(f"{_DETECTOR}:NumImages")
    port.simulate_connect(f"{_DETECTOR}:Acquire")
    port.simulate_connect(_AXIS)
    port.set_reading(
        f"{_DETECTOR}:Acquire_RBV",
        Measurement(value=0, kind="Scalar", quality="Good", produced_at=_FIXED_NOW),
    )
    port.set_reading(
        f"{_DETECTOR}:DetectorState_RBV",
        Measurement(value="Idle", kind="Categorical", quality="Good", produced_at=_FIXED_NOW),
    )


def _ctx(port: InMemoryControlPort, params: Mapping[str, Any]) -> ActionContext:
    return ActionContext(
        control_port=port,
        clock=FakeClock(_FIXED_NOW),
        params=params,
    )


# --- DiscreteParams validation -----------------------------------------


@pytest.mark.unit
def test_discrete_params_internal_three_points_accepted() -> None:
    params = DiscreteParams.model_validate(
        {
            "detector": _DETECTOR,
            "trigger_mode": "Internal",
            "axis": _AXIS,
            "points": (0.0, 45.0, 90.0),
            "dwell": 0.1,
        }
    )
    assert params.axis == _AXIS
    assert params.points == (0.0, 45.0, 90.0)
    assert params.wait == 0.0


@pytest.mark.unit
def test_discrete_params_inherits_collect_external_edge_constraint() -> None:
    """DiscreteParams reuses CollectParams's polarity-required rule."""
    with pytest.raises(ValidationError, match="polarity required"):
        DiscreteParams.model_validate(
            {
                "detector": _DETECTOR,
                "trigger_mode": "ExternalEdge",
                "source": "2bma:PCOMP1.OUT",
                "axis": _AXIS,
                "points": (0.0,),
                "dwell": 0.05,
            }
        )


@pytest.mark.unit
def test_discrete_params_empty_points_rejected() -> None:
    with pytest.raises(ValidationError):
        DiscreteParams.model_validate(
            {
                "detector": _DETECTOR,
                "trigger_mode": "Internal",
                "axis": _AXIS,
                "points": (),
                "dwell": 0.05,
            }
        )


@pytest.mark.unit
def test_discrete_params_single_point_accepted() -> None:
    params = DiscreteParams.model_validate(
        {
            "detector": _DETECTOR,
            "trigger_mode": "Internal",
            "axis": _AXIS,
            "points": (42.0,),
            "dwell": 0.05,
        }
    )
    assert params.points == (42.0,)


@pytest.mark.unit
def test_discrete_params_negative_wait_rejected() -> None:
    with pytest.raises(ValidationError):
        DiscreteParams.model_validate(
            {
                "detector": _DETECTOR,
                "trigger_mode": "Internal",
                "axis": _AXIS,
                "points": (0.0,),
                "wait": -0.05,
                "dwell": 0.1,
            }
        )


@pytest.mark.unit
def test_discrete_params_json_schema_carries_unit_annotation_on_wait() -> None:
    schema = DiscreteParams.model_json_schema()
    wait_schema = schema["properties"]["wait"]
    assert wait_schema["unit"] == {"system": "udunits", "code": "s"}


# --- discrete body behaviour -------------------------------------------


@pytest.mark.unit
async def test_discrete_walks_three_points_in_order_and_runs_collect_per_point() -> None:
    """Three points -> three axis writes interleaved with three collect cycles."""
    port = InMemoryControlPort()
    _seed_detector_and_axis(port)
    result = await discrete(
        _ctx(
            port,
            {
                "detector": _DETECTOR,
                "trigger_mode": "Internal",
                "axis": _AXIS,
                "points": (0.0, 45.0, 90.0),
                "dwell": 0.05,
            },
        )
    )
    assert result["axis"] == _AXIS
    assert result["points_visited"] == 3
    per_point = result["per_point_results"]
    assert [entry["point"] for entry in per_point] == [0.0, 45.0, 90.0]
    for entry in per_point:
        assert entry["collect"]["trigger_mode"] == "Internal"
        assert entry["collect"]["detector_state_final"] == "Idle"
    # The last axis write should be visible on the port now.
    assert (await port.read(_AXIS)).value == 90.0


@pytest.mark.unit
async def test_discrete_single_point_produces_one_cycle() -> None:
    port = InMemoryControlPort()
    _seed_detector_and_axis(port)
    result = await discrete(
        _ctx(
            port,
            {
                "detector": _DETECTOR,
                "trigger_mode": "Internal",
                "axis": _AXIS,
                "points": (12.5,),
                "dwell": 0.05,
            },
        )
    )
    assert result["points_visited"] == 1
    assert result["per_point_results"][0]["point"] == 12.5
    assert (await port.read(_AXIS)).value == 12.5


@pytest.mark.unit
async def test_discrete_records_per_point_axis_writes_in_order() -> None:
    """Per-point composition: axis write BEFORE the collect cycle's detector writes.

    Uses a recording port wrapper so the interleaving is explicit
    (axis ordering vs detector-PV ordering inside a cycle).
    """

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

        async def read(self, address: str) -> Measurement:
            return await self.delegate.read(address)

        def subscribe(self, address: str) -> AsyncIterator[Measurement]:
            return self.delegate.subscribe(address)

    inner = InMemoryControlPort()
    _seed_detector_and_axis(inner)
    port = _RecordingPort(delegate=inner)
    await discrete(
        _ctx(
            port,  # type: ignore[arg-type]
            {
                "detector": _DETECTOR,
                "trigger_mode": "Internal",
                "axis": _AXIS,
                "points": (1.0, 2.0),
                "dwell": 0.05,
            },
        )
    )
    addresses = [addr for addr, _ in port.writes]
    # Per cycle: axis, then TriggerMode, AcquireTime, NumImages, Acquire.
    # Two cycles -> 10 writes total.
    assert addresses == [
        _AXIS,
        f"{_DETECTOR}:TriggerMode",
        f"{_DETECTOR}:AcquireTime",
        f"{_DETECTOR}:NumImages",
        f"{_DETECTOR}:Acquire",
        _AXIS,
        f"{_DETECTOR}:TriggerMode",
        f"{_DETECTOR}:AcquireTime",
        f"{_DETECTOR}:NumImages",
        f"{_DETECTOR}:Acquire",
    ]
    axis_values = [value for addr, value in port.writes if addr == _AXIS]
    assert axis_values == [1.0, 2.0]


@pytest.mark.unit
async def test_discrete_unconnected_axis_propagates_not_connected_error() -> None:
    """First axis write fails -> ControlNotConnectedError surfaces, no cycle runs."""
    port = InMemoryControlPort()
    _seed_detector_and_axis(port)
    port.simulate_disconnect(_AXIS)  # axis goes away
    with pytest.raises(ControlNotConnectedError):
        await discrete(
            _ctx(
                port,
                {
                    "detector": _DETECTOR,
                    "trigger_mode": "Internal",
                    "axis": _AXIS,
                    "points": (0.0, 1.0),
                    "dwell": 0.05,
                },
            )
        )


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
async def test_conductor_executes_discrete_action_and_records_step_entry() -> None:
    """Conductor + registered `discrete` body + ActionStep -> success + recorded evidence."""
    port = InMemoryControlPort()
    _seed_detector_and_axis(port)
    appender = _FakeAppendStep()
    registry = InMemoryActionRegistry({"discrete": discrete})
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
        steps=(
            ActionStep(
                name="discrete",
                params={
                    "detector": _DETECTOR,
                    "trigger_mode": "Internal",
                    "axis": _AXIS,
                    "points": (0.0, 30.0, 60.0),
                    "dwell": 0.05,
                },
            ),
        ),
    )
    assert result.succeeded is True
    assert result.completed_count == 1
    # calls[0] is the pre-effect in-flight marker; calls[1] is the outcome.
    assert appender.calls[0].command.entries[0].payload["result"] == "in_flight"
    entry = appender.calls[1].command.entries[0]
    assert entry.step_kind == "action"
    assert entry.payload["name"] == "discrete"
    assert entry.payload["result"] == "ok"
    result_data = entry.payload["result_data"]
    assert result_data["axis"] == _AXIS
    assert result_data["points_visited"] == 3
    assert [p["point"] for p in result_data["per_point_results"]] == [0.0, 30.0, 60.0]
