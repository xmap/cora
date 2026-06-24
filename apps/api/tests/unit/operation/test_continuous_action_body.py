"""Unit tests for the `continuous` action body and its `ContinuousParams` schema.

`continuous` drives an axis from `start` to `stop` while the detector
consumes externally-fired trigger pulses. Tests verify the fly-scan
ordering contract (config -> axis-to-start blocking -> arm -> axis-to-
stop non-blocking -> poll) without re-asserting the inner detector
contract that `test_collect_action_body.py` covers.

  Params validation (ContinuousParams.model_validate):
  - Inherited CollectParams shape passes through (Internal, ExternalEdge)
  - start == stop rejected (zero-range scan is meaningless)
  - rate optional; defaults to None
  - rate > 0 enforced when present
  - rate=None accepted

  Body behaviour (continuous called directly with ActionContext):
  - Happy path: writes config, moves to start, arms, moves to stop,
    polls done, reads final state + axis position
  - Write order is preserved (config -> start@wait -> Acquire -> stop@nowait)
  - axis-to-start uses wait=True; axis-to-stop uses wait=False
  - rate is evidence-only (NOT written to any PV)
  - Evidence carries axis_final_actual = readback of axis after sweep
  - Unconnected axis propagates ControlNotConnectedError

  End-to-end via Conductor:
  - InMemoryActionRegistry({"continuous": continuous}) + ActionStep
    produces ConductorResult.succeeded=True with the expected payload
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
from cora.operation.acquisitions import ContinuousParams, continuous
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

_FIXED_NOW = datetime(2026, 5, 31, 12, 0, 0, tzinfo=UTC)
_DETECTOR = "2bma:cam1"
_AXIS = "2bma:rot:val"


def _seed_detector_and_axis(port: InMemoryControlPort) -> None:
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


# --- ContinuousParams validation ---------------------------------------


@pytest.mark.unit
def test_continuous_params_internal_sweep_accepted() -> None:
    params = ContinuousParams.model_validate(
        {
            "detector": _DETECTOR,
            "trigger_mode": "Internal",
            "axis": _AXIS,
            "start": 0.0,
            "stop": 180.0,
            "repetitions": 1500,
            "dwell": 0.025,
        }
    )
    assert params.start == 0.0
    assert params.stop == 180.0
    assert params.rate is None


@pytest.mark.unit
def test_continuous_params_external_edge_with_rate_accepted() -> None:
    params = ContinuousParams.model_validate(
        {
            "detector": _DETECTOR,
            "trigger_mode": "ExternalEdge",
            "polarity": "Rising",
            "source": "2bma:PCOMP1.OUT",
            "axis": _AXIS,
            "start": 0.0,
            "stop": 360.0,
            "rate": 90.0,
            "repetitions": 1500,
            "dwell": 0.025,
        }
    )
    assert params.rate == 90.0
    assert params.polarity == "Rising"


@pytest.mark.unit
def test_continuous_params_zero_range_rejected() -> None:
    """Start == stop is a meaningless zero-range sweep; the validator catches it."""
    with pytest.raises(ValidationError, match="start != stop"):
        ContinuousParams.model_validate(
            {
                "detector": _DETECTOR,
                "trigger_mode": "Internal",
                "axis": _AXIS,
                "start": 45.0,
                "stop": 45.0,
                "dwell": 0.05,
            }
        )


@pytest.mark.unit
@pytest.mark.parametrize("bad_rate", [0.0, -1.0, -100.0])
def test_continuous_params_non_positive_rate_rejected(bad_rate: float) -> None:
    with pytest.raises(ValidationError):
        ContinuousParams.model_validate(
            {
                "detector": _DETECTOR,
                "trigger_mode": "Internal",
                "axis": _AXIS,
                "start": 0.0,
                "stop": 180.0,
                "rate": bad_rate,
                "dwell": 0.05,
            }
        )


@pytest.mark.unit
def test_continuous_params_reverse_sweep_accepted() -> None:
    """Stop < start is a valid reverse direction; only zero range is rejected."""
    params = ContinuousParams.model_validate(
        {
            "detector": _DETECTOR,
            "trigger_mode": "Internal",
            "axis": _AXIS,
            "start": 180.0,
            "stop": 0.0,
            "dwell": 0.05,
        }
    )
    assert params.start == 180.0
    assert params.stop == 0.0


# --- continuous body behaviour -----------------------------------------


@pytest.mark.unit
async def test_continuous_writes_in_fly_scan_order_and_returns_evidence() -> None:
    """Body writes detector config, moves to start, arms, moves to stop, polls, reads."""

    @dataclass
    class _RecordingPort:
        delegate: InMemoryControlPort
        writes: list[tuple[str, Any, bool]] = field(default_factory=list[tuple[str, Any, bool]])

        async def write(
            self,
            address: str,
            value: Any,
            *,
            wait: bool = True,
            timeout_s: float = 30.0,
        ) -> None:
            self.writes.append((address, value, wait))
            await self.delegate.write(address, value, wait=wait, timeout_s=timeout_s)

        async def read(self, address: str) -> Measurement:
            return await self.delegate.read(address)

        def subscribe(self, address: str) -> AsyncIterator[Measurement]:
            return self.delegate.subscribe(address)

    inner = InMemoryControlPort()
    _seed_detector_and_axis(inner)
    port = _RecordingPort(delegate=inner)
    result = await continuous(
        _ctx(
            port,  # type: ignore[arg-type]
            {
                "detector": _DETECTOR,
                "trigger_mode": "ExternalEdge",
                "polarity": "Rising",
                "source": "2bma:PCOMP1.OUT",
                "axis": _AXIS,
                "start": 0.0,
                "stop": 180.0,
                "repetitions": 1500,
                "dwell": 0.025,
            },
        )
    )
    addresses = [(addr, value, wait) for addr, value, wait in port.writes]
    # Fly-scan order:
    #   1. TriggerMode (config)
    #   2. AcquireTime (config)
    #   3. NumImages (config)
    #   4. axis -> start (BLOCKING, wait=True)
    #   5. Acquire = 1 (arm)
    #   6. axis -> stop (NON-blocking, wait=False)
    assert addresses == [
        (f"{_DETECTOR}:TriggerMode", "External", True),
        (f"{_DETECTOR}:AcquireTime", 0.025, True),
        (f"{_DETECTOR}:NumImages", 1500, True),
        (_AXIS, 0.0, True),
        (f"{_DETECTOR}:Acquire", 1, True),
        (_AXIS, 180.0, False),
    ]
    assert result["axis"] == _AXIS
    assert result["axis_start_requested"] == 0.0
    assert result["axis_stop_requested"] == 180.0
    assert result["axis_final_actual"] == 180.0  # in-memory port shows last write
    assert result["repetitions_requested"] == 1500
    assert result["trigger_mode"] == "ExternalEdge"
    assert result["polarity"] == "Rising"
    assert result["source"] == "2bma:PCOMP1.OUT"
    assert result["detector_state_final"] == "Idle"


@pytest.mark.unit
async def test_continuous_rate_is_evidence_only_not_written() -> None:
    """Rate flows into result_data but body must NOT write to any axis-rate PV."""

    @dataclass
    class _WriteAddressOnly:
        delegate: InMemoryControlPort
        addresses: list[str] = field(default_factory=list[str])

        async def write(
            self,
            address: str,
            value: Any,
            *,
            wait: bool = True,
            timeout_s: float = 30.0,
        ) -> None:
            self.addresses.append(address)
            await self.delegate.write(address, value, wait=wait, timeout_s=timeout_s)

        async def read(self, address: str) -> Measurement:
            return await self.delegate.read(address)

        def subscribe(self, address: str) -> AsyncIterator[Measurement]:
            return self.delegate.subscribe(address)

    inner = InMemoryControlPort()
    _seed_detector_and_axis(inner)
    port = _WriteAddressOnly(delegate=inner)
    result = await continuous(
        _ctx(
            port,  # type: ignore[arg-type]
            {
                "detector": _DETECTOR,
                "trigger_mode": "Internal",
                "axis": _AXIS,
                "start": 0.0,
                "stop": 180.0,
                "rate": 90.0,
                "dwell": 0.025,
            },
        )
    )
    # No rate-PV write happened.
    assert not any("VELO" in addr or "rate" in addr.lower() for addr in port.addresses)
    assert result["rate_requested"] == 90.0


@pytest.mark.unit
async def test_continuous_unconnected_axis_propagates_not_connected_error() -> None:
    """Axis disconnected -> write to start raises ControlNotConnectedError."""
    port = InMemoryControlPort()
    _seed_detector_and_axis(port)
    port.simulate_disconnect(_AXIS)
    with pytest.raises(ControlNotConnectedError):
        await continuous(
            _ctx(
                port,
                {
                    "detector": _DETECTOR,
                    "trigger_mode": "Internal",
                    "axis": _AXIS,
                    "start": 0.0,
                    "stop": 180.0,
                    "dwell": 0.025,
                },
            )
        )


@pytest.mark.unit
async def test_continuous_reverse_sweep_writes_decreasing_axis_values() -> None:
    port = InMemoryControlPort()
    _seed_detector_and_axis(port)
    result = await continuous(
        _ctx(
            port,
            {
                "detector": _DETECTOR,
                "trigger_mode": "Internal",
                "axis": _AXIS,
                "start": 180.0,
                "stop": 0.0,
                "dwell": 0.025,
            },
        )
    )
    assert result["axis_start_requested"] == 180.0
    assert result["axis_stop_requested"] == 0.0
    assert (await port.read(_AXIS)).value == 0.0


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
async def test_conductor_executes_continuous_action_and_records_step_entry() -> None:
    port = InMemoryControlPort()
    _seed_detector_and_axis(port)
    appender = _FakeAppendStep()
    registry = InMemoryActionRegistry({"continuous": continuous})
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
                name="continuous",
                params={
                    "detector": _DETECTOR,
                    "trigger_mode": "ExternalEdge",
                    "polarity": "Rising",
                    "source": "2bma:PCOMP1.OUT",
                    "axis": _AXIS,
                    "start": 0.0,
                    "stop": 180.0,
                    "repetitions": 1500,
                    "dwell": 0.025,
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
    assert entry.payload["name"] == "continuous"
    assert entry.payload["result"] == "ok"
    result_data = entry.payload["result_data"]
    assert result_data["axis"] == _AXIS
    assert result_data["repetitions_requested"] == 1500
    assert result_data["axis_final_actual"] == 180.0
