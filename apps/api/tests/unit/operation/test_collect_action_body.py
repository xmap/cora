"""Unit tests for the `collect` action body and its `CollectParams` schema.

Coverage spans the two boundaries the body sits on:

  Params validation (CollectParams.model_validate):
  - Internal trigger valid shapes (with / without repetitions)
  - ExternalEdge valid: polarity + source both present
  - ExternalLevel valid: source present, polarity may be omitted
  - polarity required when trigger_mode == ExternalEdge
  - source required when trigger_mode != Internal
  - source must be None when trigger_mode == Internal
  - repetitions >= 1 (or None); 0 and negatives rejected
  - dwell > 0 (zero and negatives rejected)
  - dwell carries the canonical {system, code} unit annotation in JSON Schema

  Body behaviour (collect called directly with ActionContext):
  - Internal + repetitions=5 happy path: writes the four configure PVs,
    polls Acquire_RBV (seeded Done immediately), reads DetectorState_RBV,
    returns the evidence Mapping with timestamps + final state
  - ExternalEdge trigger maps to AD "External" string on TriggerMode
  - repetitions=None translates to NumImages=0 for AD continuous mode
  - Poll loop iterates while Acquire_RBV stays 1 and exits on 0
  - Unseeded Acquire_RBV propagates ControlNotConnectedError
  - Unseeded detector base PVs propagate ControlNotConnectedError from write

  End-to-end via Conductor:
  - InMemoryActionRegistry({"collect": collect}) + ActionStep("collect", ...)
    produces ConductorResult.succeeded=True and a step entry whose
    payload carries name + params + result + result_data with the
    evidence shape from the body
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
from cora.operation.acquisitions import CollectParams, collect
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

_FIXED_NOW = datetime(2026, 5, 31, 10, 0, 0, tzinfo=UTC)
_DETECTOR = "2bma:cam1"


def _seed_detector(port: InMemoryControlPort, *, acquire_rbv: Any = 0) -> None:
    """Seed the six AD-convention PVs `collect` touches.

    `acquire_rbv` defaults to `0` so the poll loop exits on its first
    read; tests that exercise the loop pass a custom value or replace
    the port with a stateful fixture.
    """
    port.simulate_connect(f"{_DETECTOR}:TriggerMode")
    port.simulate_connect(f"{_DETECTOR}:AcquireTime")
    port.simulate_connect(f"{_DETECTOR}:NumImages")
    port.simulate_connect(f"{_DETECTOR}:Acquire")
    port.set_reading(
        f"{_DETECTOR}:Acquire_RBV",
        Measurement(value=acquire_rbv, kind="Scalar", quality="Good", produced_at=_FIXED_NOW),
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


# --- CollectParams validation ------------------------------------------


@pytest.mark.unit
def test_collect_params_internal_with_repetitions_accepted() -> None:
    params = CollectParams.model_validate(
        {"detector": _DETECTOR, "trigger_mode": "Internal", "repetitions": 5, "dwell": 0.1}
    )
    assert params.trigger_mode == "Internal"
    assert params.repetitions == 5
    assert params.polarity is None
    assert params.source is None


@pytest.mark.unit
def test_collect_params_internal_without_repetitions_means_continuous() -> None:
    params = CollectParams.model_validate(
        {"detector": _DETECTOR, "trigger_mode": "Internal", "dwell": 0.1}
    )
    assert params.repetitions is None


@pytest.mark.unit
def test_collect_params_external_edge_with_polarity_and_source_accepted() -> None:
    params = CollectParams.model_validate(
        {
            "detector": _DETECTOR,
            "trigger_mode": "ExternalEdge",
            "polarity": "Rising",
            "source": "2bma:PCOMP1.OUT",
            "repetitions": 1500,
            "dwell": 0.025,
        }
    )
    assert params.polarity == "Rising"
    assert params.source == "2bma:PCOMP1.OUT"


@pytest.mark.unit
def test_collect_params_external_level_without_polarity_accepted() -> None:
    """ExternalLevel does not require polarity; source still required."""
    params = CollectParams.model_validate(
        {
            "detector": _DETECTOR,
            "trigger_mode": "ExternalLevel",
            "source": "2bma:gate:OUT",
            "dwell": 0.1,
        }
    )
    assert params.polarity is None
    assert params.source == "2bma:gate:OUT"


@pytest.mark.unit
def test_collect_params_external_edge_without_polarity_rejected() -> None:
    with pytest.raises(ValidationError, match="polarity required"):
        CollectParams.model_validate(
            {
                "detector": _DETECTOR,
                "trigger_mode": "ExternalEdge",
                "source": "2bma:PCOMP1.OUT",
                "dwell": 0.1,
            }
        )


@pytest.mark.unit
def test_collect_params_external_without_source_rejected() -> None:
    with pytest.raises(ValidationError, match="source required"):
        CollectParams.model_validate(
            {
                "detector": _DETECTOR,
                "trigger_mode": "ExternalLevel",
                "dwell": 0.1,
            }
        )


@pytest.mark.unit
def test_collect_params_internal_with_source_rejected() -> None:
    with pytest.raises(ValidationError, match="source must be None"):
        CollectParams.model_validate(
            {
                "detector": _DETECTOR,
                "trigger_mode": "Internal",
                "source": "should_not_be_here",
                "dwell": 0.1,
            }
        )


@pytest.mark.unit
@pytest.mark.parametrize("bad_repetitions", [0, -1, -100])
def test_collect_params_non_positive_repetitions_rejected(bad_repetitions: int) -> None:
    with pytest.raises(ValidationError):
        CollectParams.model_validate(
            {
                "detector": _DETECTOR,
                "trigger_mode": "Internal",
                "repetitions": bad_repetitions,
                "dwell": 0.1,
            }
        )


@pytest.mark.unit
@pytest.mark.parametrize("bad_dwell", [0.0, -0.1])
def test_collect_params_non_positive_dwell_rejected(bad_dwell: float) -> None:
    with pytest.raises(ValidationError):
        CollectParams.model_validate(
            {"detector": _DETECTOR, "trigger_mode": "Internal", "dwell": bad_dwell}
        )


@pytest.mark.unit
def test_collect_params_json_schema_carries_unit_annotation_on_dwell() -> None:
    """The `dwell` field's JSON Schema includes {system, code} unit annotation.

    Pins the contract that Capability templates rely on per
    project_units_design: the unit lives on the schema, not the field name.
    """
    schema = CollectParams.model_json_schema()
    dwell_schema = schema["properties"]["dwell"]
    assert dwell_schema["unit"] == {"system": "udunits", "code": "s"}


# --- collect body behaviour --------------------------------------------


@pytest.mark.unit
async def test_collect_internal_trigger_writes_configure_pvs_and_returns_evidence() -> None:
    """Happy path: writes land on the four configure PVs and evidence shape is right."""
    port = InMemoryControlPort()
    _seed_detector(port)
    result = await collect(
        _ctx(
            port,
            {
                "detector": _DETECTOR,
                "trigger_mode": "Internal",
                "repetitions": 5,
                "dwell": 0.1,
            },
        )
    )
    assert (await port.read(f"{_DETECTOR}:TriggerMode")).value == "Internal"
    assert (await port.read(f"{_DETECTOR}:AcquireTime")).value == 0.1
    assert (await port.read(f"{_DETECTOR}:NumImages")).value == 5
    assert (await port.read(f"{_DETECTOR}:Acquire")).value == 1
    assert result == {
        "started_at": _FIXED_NOW.isoformat(),
        "stopped_at": _FIXED_NOW.isoformat(),
        "repetitions_requested": 5,
        "trigger_mode": "Internal",
        "polarity": None,
        "source": None,
        "detector_state_final": "Idle",
    }


@pytest.mark.unit
async def test_collect_external_edge_maps_trigger_mode_to_ad_external_string() -> None:
    """ExternalEdge -> areaDetector's 'External' string on TriggerMode."""
    port = InMemoryControlPort()
    _seed_detector(port)
    await collect(
        _ctx(
            port,
            {
                "detector": _DETECTOR,
                "trigger_mode": "ExternalEdge",
                "polarity": "Rising",
                "source": "2bma:PCOMP1.OUT",
                "repetitions": 10,
                "dwell": 0.025,
            },
        )
    )
    assert (await port.read(f"{_DETECTOR}:TriggerMode")).value == "External"


@pytest.mark.unit
async def test_collect_external_level_maps_trigger_mode_to_ad_external_string() -> None:
    port = InMemoryControlPort()
    _seed_detector(port)
    await collect(
        _ctx(
            port,
            {
                "detector": _DETECTOR,
                "trigger_mode": "ExternalLevel",
                "source": "2bma:gate:OUT",
                "repetitions": 1,
                "dwell": 0.5,
            },
        )
    )
    assert (await port.read(f"{_DETECTOR}:TriggerMode")).value == "External"


@pytest.mark.unit
async def test_collect_repetitions_none_writes_zero_to_num_images() -> None:
    """None repetitions -> NumImages=0, the AD sentinel for continuous mode."""
    port = InMemoryControlPort()
    _seed_detector(port)
    result = await collect(
        _ctx(port, {"detector": _DETECTOR, "trigger_mode": "Internal", "dwell": 0.05})
    )
    assert (await port.read(f"{_DETECTOR}:NumImages")).value == 0
    assert result["repetitions_requested"] is None


@pytest.mark.unit
async def test_collect_polarity_and_source_are_evidence_only_not_written() -> None:
    """Body must NOT touch emitter-side PVs; polarity + source surface only in evidence."""
    port = InMemoryControlPort()
    _seed_detector(port)
    # The emitter PV is intentionally NOT connected: if `collect` ever
    # tries to write to it, the unseeded port will raise.
    result = await collect(
        _ctx(
            port,
            {
                "detector": _DETECTOR,
                "trigger_mode": "ExternalEdge",
                "polarity": "Falling",
                "source": "2bma:PCOMP1.OUT",
                "repetitions": 3,
                "dwell": 0.2,
            },
        )
    )
    assert result["polarity"] == "Falling"
    assert result["source"] == "2bma:PCOMP1.OUT"


@pytest.mark.unit
async def test_collect_poll_loop_iterates_while_acquire_rbv_busy() -> None:
    """Acquire_RBV starts at 1, transitions to 0 on Nth read; loop iterates then exits."""

    @dataclass
    class _IteratingPort:
        """Tracks writes + returns a scripted Acquire_RBV sequence on reads."""

        writes: list[tuple[str, Any]] = field(default_factory=list[tuple[str, Any]])
        rbv_sequence: list[int] = field(default_factory=list[int])
        rbv_calls: int = 0

        async def write(
            self,
            address: str,
            value: Any,
            *,
            wait: bool = True,
            timeout_s: float = 30.0,
        ) -> None:
            _ = (wait, timeout_s)
            self.writes.append((address, value))

        async def read(self, address: str) -> Measurement:
            if address == f"{_DETECTOR}:Acquire_RBV":
                idx = min(self.rbv_calls, len(self.rbv_sequence) - 1)
                value = self.rbv_sequence[idx]
                self.rbv_calls += 1
                return Measurement(
                    value=value, kind="Scalar", quality="Good", produced_at=_FIXED_NOW
                )
            if address == f"{_DETECTOR}:DetectorState_RBV":
                return Measurement(
                    value="Idle",
                    kind="Categorical",
                    quality="Good",
                    produced_at=_FIXED_NOW,
                )
            raise AssertionError(f"unexpected read of {address!r}")

        def subscribe(self, address: str) -> AsyncIterator[Measurement]:
            raise AssertionError("subscribe should not be called by collect at v1")

    port = _IteratingPort(rbv_sequence=[1, 1, 1, 0])
    result = await collect(
        _ctx(
            port,  # type: ignore[arg-type]
            {"detector": _DETECTOR, "trigger_mode": "Internal", "dwell": 0.01},
        )
    )
    assert port.rbv_calls == 4
    assert result["detector_state_final"] == "Idle"


@pytest.mark.unit
async def test_collect_unconnected_acquire_rbv_propagates_not_connected_error() -> None:
    """Acquire_RBV not seeded -> ControlNotConnectedError surfaces from the read."""
    port = InMemoryControlPort()
    port.simulate_connect(f"{_DETECTOR}:TriggerMode")
    port.simulate_connect(f"{_DETECTOR}:AcquireTime")
    port.simulate_connect(f"{_DETECTOR}:NumImages")
    port.simulate_connect(f"{_DETECTOR}:Acquire")
    # Deliberately do NOT seed Acquire_RBV / DetectorState_RBV
    with pytest.raises(ControlNotConnectedError):
        await collect(
            _ctx(
                port,
                {"detector": _DETECTOR, "trigger_mode": "Internal", "dwell": 0.05},
            )
        )


@pytest.mark.unit
async def test_collect_unconnected_trigger_mode_propagates_not_connected_error() -> None:
    """First write target not seeded -> ControlNotConnectedError surfaces from the write."""
    port = InMemoryControlPort()  # nothing connected
    with pytest.raises(ControlNotConnectedError):
        await collect(
            _ctx(
                port,
                {"detector": _DETECTOR, "trigger_mode": "Internal", "dwell": 0.05},
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
async def test_conductor_executes_collect_action_and_records_step_entry() -> None:
    """Conductor + registered `collect` body + ActionStep -> success + recorded evidence."""
    port = InMemoryControlPort()
    _seed_detector(port)
    appender = _FakeAppendStep()
    registry = InMemoryActionRegistry({"collect": collect})
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
                name="collect",
                params={
                    "detector": _DETECTOR,
                    "trigger_mode": "Internal",
                    "repetitions": 3,
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
    assert entry.payload["name"] == "collect"
    assert entry.payload["result"] == "ok"
    result_data = entry.payload["result_data"]
    assert result_data["trigger_mode"] == "Internal"
    assert result_data["repetitions_requested"] == 3
    assert result_data["detector_state_final"] == "Idle"
