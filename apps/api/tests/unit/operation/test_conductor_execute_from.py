"""Behavioural tests for `Conductor.execute_from` (resumable conduct, Tier 1).

`execute_from` REPLAYS a pinned resolved step list from a re-establishment
boundary rather than re-deriving the step list:

  - setpoint  -> re-drive (idempotent absolute write)
  - check     -> re-run as a fresh gate
  - action    -> HALT for an operator decision (interrupted acquisition)

Headline acceptance test (per the design memo): replay walks the pinned
tail BYTE-FOR-BYTE -- two identical setpoints land on the in-memory port,
identical to what the original conduct wrote. `steps_from_payload` is the
exact inverse of `step_to_payload`, so the pinned `ResolvedStepsRecorded`
step list round-trips into the replayed `Step`s.
"""

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.clock import FakeClock
from cora.operation.conductor import (
    ActionStep,
    CaptureStep,
    CheckStep,
    Conductor,
    EqualsCriterion,
    ResumePolicy,
    SetpointStep,
    Step,
    WithinToleranceCriterion,
    step_to_payload,
    steps_from_payload,
)
from cora.operation.features.append_activities.command import AppendProcedureActivities
from cora.operation.ports.control_port import ControlNotConnectedError, Measurement
from cora.recipe.aggregates.recipe.body import CaptureRef

_FIXED_NOW = datetime(2026, 6, 21, 9, 0, 0, tzinfo=UTC)


@dataclass
class _FakeAppendStep:
    """Captures each append call (the replayed journal)."""

    calls: list[AppendProcedureActivities] = field(default_factory=list[AppendProcedureActivities])

    async def __call__(self, command: AppendProcedureActivities, **_kwargs: Any) -> int:
        self.calls.append(command)
        return len(command.entries)


@dataclass
class _LenientIds:
    """id_generator that never exhausts (markers double appends)."""

    def new_id(self) -> UUID:
        return uuid4()


@dataclass
class _RecordingControlPort:
    """Captures writes in order (for byte-for-byte assertions); reads from a seed."""

    writes: list[tuple[str, Any]] = field(default_factory=list[tuple[str, Any]])
    readings: dict[str, Measurement] = field(default_factory=dict[str, Measurement])

    async def read(self, address: str) -> Measurement:
        if address not in self.readings:
            raise ControlNotConnectedError(address)
        return self.readings[address]

    async def write(
        self,
        address: str,
        value: int | float | bool | str | tuple[Any, ...],
        *,
        wait: bool = True,
        timeout_s: float = 30.0,
    ) -> None:
        _ = (wait, timeout_s)
        self.writes.append((address, value))

    def subscribe(self, address: str) -> AsyncIterator[Measurement]:  # pragma: no cover - unused
        raise NotImplementedError


def _conductor(port: _RecordingControlPort, appender: _FakeAppendStep) -> Conductor:
    return Conductor(
        control_port=port,  # type: ignore[arg-type]
        append_step=appender,  # type: ignore[arg-type]
        clock=FakeClock(_FIXED_NOW),
        id_generator=_LenientIds(),  # type: ignore[arg-type]
    )


def _good_reading(value: Any) -> Measurement:
    return Measurement(value=value, kind="Scalar", quality="Good", produced_at=_FIXED_NOW)


def _pin_and_parse(steps: tuple[Step, ...]) -> tuple[Step, ...]:
    """Serialize steps the way conduct pins them, then parse back (the
    ResolvedStepsRecorded round-trip a real resume performs)."""
    steps_wire = tuple(step_to_payload(s) for s in steps)
    return steps_from_payload(steps_wire)


# --- headline acceptance: byte-for-byte replay of the pinned tail ----------


@pytest.mark.unit
async def test_execute_from_replays_pinned_tail_byte_for_byte() -> None:
    """Two setpoints pinned on the step list re-drive byte-for-byte on resume."""
    original = (
        SetpointStep(address="2bma:rot:val", value=45.0),
        SetpointStep(address="2bma:cam:exposure", value=0.025),
    )
    steps = _pin_and_parse(original)
    assert steps == original  # the pinned step list round-trips to the same Steps

    port = _RecordingControlPort()
    appender = _FakeAppendStep()
    result = await _conductor(port, appender).execute_from(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=steps,
        boundary=0,
    )

    assert result.succeeded is True
    assert result.completed_count == 2
    # Byte-for-byte: the replayed writes equal the pinned step list.s setpoints.
    assert port.writes == [("2bma:rot:val", 45.0), ("2bma:cam:exposure", 0.025)]


@pytest.mark.unit
async def test_execute_from_boundary_skips_the_prefix() -> None:
    """boundary=K re-drives only steps[K:]; the prefix is not re-driven."""
    steps = _pin_and_parse(
        (
            SetpointStep(address="2bma:a", value=1.0),
            SetpointStep(address="2bma:b", value=2.0),
            SetpointStep(address="2bma:c", value=3.0),
        )
    )
    port = _RecordingControlPort()
    result = await _conductor(port, _FakeAppendStep()).execute_from(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=steps,
        boundary=1,
    )
    assert result.completed_count == 2
    assert port.writes == [("2bma:b", 2.0), ("2bma:c", 3.0)]  # 2bma:a (prefix) untouched


@pytest.mark.unit
async def test_execute_from_records_marker_and_outcome_with_absolute_index() -> None:
    """A re-driven setpoint records the in-flight marker + ok outcome, each
    carrying its ABSOLUTE position in the step list (so the replayed journal lines up)."""
    steps = _pin_and_parse(
        (
            SetpointStep(address="2bma:a", value=1.0),
            SetpointStep(address="2bma:b", value=2.0),
        )
    )
    appender = _FakeAppendStep()
    await _conductor(_RecordingControlPort(), appender).execute_from(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=steps,
        boundary=1,
    )
    payloads = [c.entries[0].payload for c in appender.calls]
    # Only the boundary step (index 1) replayed: marker then outcome, both index 1.
    assert [(p["step_index"], p["result"]) for p in payloads] == [(1, "in_flight"), (1, "ok")]


@pytest.mark.unit
async def test_execute_from_on_action_requires_operator_decision() -> None:
    """An acquisition (ActionStep) is NOT re-run: resume halts for an operator
    decision; the action and everything after it are untouched."""
    steps = _pin_and_parse(
        (
            SetpointStep(address="2bma:a", value=1.0),
            ActionStep(name="collect", params={"dwell": 0.1}),
            SetpointStep(address="2bma:c", value=3.0),
        )
    )
    port = _RecordingControlPort()
    result = await _conductor(port, _FakeAppendStep()).execute_from(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=steps,
        boundary=0,
    )
    assert result.succeeded is False
    assert result.completed_count == 1  # the leading setpoint re-driven
    assert result.failure is not None
    assert result.failure.step_index == 1
    assert result.failure.source_kind == "action"
    assert result.failure.target == "collect"
    assert result.failure.error_class == "AcquisitionResumeRequiresOperator"
    # The action did not run and the trailing setpoint was never reached.
    assert port.writes == [("2bma:a", 1.0)]


@pytest.mark.unit
async def test_execute_from_reruns_check_fresh() -> None:
    """A check in the tail is re-run as a fresh gate (read + evaluate)."""
    steps = _pin_and_parse(
        (CheckStep(address="2bma:rbv", criterion=EqualsCriterion(expected=45.0)),)
    )
    port = _RecordingControlPort(readings={"2bma:rbv": _good_reading(45.0)})
    result = await _conductor(port, _FakeAppendStep()).execute_from(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=steps,
        boundary=0,
    )
    assert result.succeeded is True
    assert result.completed_count == 1


@pytest.mark.unit
async def test_execute_from_check_mismatch_on_rerun_halts() -> None:
    """A re-run check whose criterion no longer matches halts the resume."""
    steps = _pin_and_parse(
        (CheckStep(address="2bma:rbv", criterion=EqualsCriterion(expected=45.0)),)
    )
    port = _RecordingControlPort(readings={"2bma:rbv": _good_reading(12.5)})
    result = await _conductor(port, _FakeAppendStep()).execute_from(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=steps,
        boundary=0,
    )
    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_class == "CheckFailedError"
    assert result.failure.source_kind == "check"


@pytest.mark.unit
async def test_execute_from_boundary_past_end_is_a_no_op() -> None:
    """Boundary >= len(steps) replays an empty tail (a no-op resume)."""
    steps = _pin_and_parse((SetpointStep(address="2bma:a", value=1.0),))
    port = _RecordingControlPort()
    result = await _conductor(port, _FakeAppendStep()).execute_from(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=steps,
        boundary=5,
    )
    assert result.succeeded is True
    assert result.completed_count == 0
    assert port.writes == []


@pytest.mark.unit
async def test_execute_from_rejects_negative_boundary() -> None:
    with pytest.raises(ValueError, match="boundary must be >= 0"):
        await _conductor(_RecordingControlPort(), _FakeAppendStep()).execute_from(
            procedure_id=uuid4(),
            principal_id=uuid4(),
            correlation_id=uuid4(),
            steps=(),
            boundary=-1,
        )


@pytest.mark.unit
async def test_execute_from_capture_ref_before_boundary_loud_fails() -> None:
    """Captures start EMPTY on resume: a CaptureStep in the skipped prefix is not
    replayed, so a later CaptureRef setpoint resolves against nothing and fails
    loud rather than restoring against a stale value. Nothing is actuated."""
    steps = _pin_and_parse(
        (
            CaptureStep(address="2bma:sample:x", capture_name="home"),
            SetpointStep(address="2bma:sample:x", value=CaptureRef("home")),
        )
    )
    port = _RecordingControlPort()
    result = await _conductor(port, _FakeAppendStep()).execute_from(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=steps,
        boundary=1,  # skip the CaptureStep@0, replay only the CaptureRef setpoint
    )
    assert result.succeeded is False
    assert result.completed_count == 0
    assert result.failure is not None
    assert result.failure.error_class == "UnresolvedCaptureRef"
    assert port.writes == []


@pytest.mark.unit
async def test_execute_from_capture_in_tail_reseeds_then_restores() -> None:
    """A CaptureStep WITHIN the replayed tail re-reads and seeds captures, so a
    following CaptureRef setpoint resolves and re-drives on resume."""
    steps = _pin_and_parse(
        (
            CaptureStep(address="2bma:sample:x", capture_name="home"),
            SetpointStep(address="2bma:sample:x", value=CaptureRef("home")),
        )
    )
    port = _RecordingControlPort(readings={"2bma:sample:x": _good_reading(12.5)})
    result = await _conductor(port, _FakeAppendStep()).execute_from(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=steps,
        boundary=0,  # replay both: capture re-reads 12.5, restore writes 12.5
    )
    assert result.succeeded is True
    assert result.completed_count == 2
    assert port.writes == [("2bma:sample:x", 12.5)]


@pytest.mark.unit
async def test_execute_from_explicit_re_establish_policy_is_the_default() -> None:
    """Passing the only policy member behaves identically to the default."""
    steps = _pin_and_parse((SetpointStep(address="2bma:a", value=1.0),))
    port = _RecordingControlPort()
    result = await _conductor(port, _FakeAppendStep()).execute_from(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=steps,
        boundary=0,
        policy=ResumePolicy.RE_ESTABLISH,
    )
    assert result.succeeded is True
    assert port.writes == [("2bma:a", 1.0)]


# --- steps_from_payload is the exact inverse of step_to_payload -----------


@pytest.mark.unit
@pytest.mark.parametrize(
    "step",
    [
        SetpointStep(address="2bma:rot", value=12.5, verify=True),
        SetpointStep(address="2bma:energy", value=(1, 2, 3)),
        ActionStep(name="collect", params={"dwell": 0.1, "detector": "2bma:cam1"}),
        CheckStep(address="2bma:shutter", criterion=EqualsCriterion(expected="Open")),
        CheckStep(address="2bma:idx", criterion=EqualsCriterion(expected=(1, 2))),
        CheckStep(
            address="2bma:temp",
            criterion=WithinToleranceCriterion(expected=100.0, tolerance=0.5),
        ),
        CaptureStep(address="2bma:sample:x", capture_name="home"),
        SetpointStep(address="2bma:sample:x", value=CaptureRef("home")),
    ],
)
def test_steps_from_payload_round_trips_step_to_payload(step: Step) -> None:
    assert steps_from_payload((step_to_payload(step),)) == (step,)


@pytest.mark.unit
def test_step_to_payload_encodes_capture_ref_setpoint_as_a_sentinel() -> None:
    """A CaptureRef setpoint value pins as the {"__capture__": name} sentinel,
    distinct from any literal, so resume reconstructs the ref not a bare value."""
    payload = step_to_payload(SetpointStep(address="2bma:sample:x", value=CaptureRef("home")))
    assert payload["value"] == {"__capture__": "home"}


@pytest.mark.unit
def test_step_to_payload_encodes_capture_step_with_capture_kind() -> None:
    payload = step_to_payload(CaptureStep(address="2bma:sample:x", capture_name="home"))
    assert payload["kind"] == "capture"
    assert payload["capture_name"] == "home"


@pytest.mark.unit
def test_steps_from_payload_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="unknown step kind"):
        steps_from_payload(({"kind": "bogus"},))


@pytest.mark.unit
def test_steps_from_payload_rejects_unknown_criterion_kind() -> None:
    bad: Mapping[str, Any] = {
        "kind": "check",
        "address": "x",
        "criterion": {"kind": "bogus"},
    }
    with pytest.raises(ValueError, match="unknown criterion kind"):
        steps_from_payload((bad,))
