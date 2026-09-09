"""Behavioural tests for CaptureRef/SteeringRef values in ComputeStep.parameters.

Coverage for the runtime resolution added to `_run_compute` (the fourth and
final slice of the compute-parameter-refs feature; the prior three slices
covered the Recipe event-payload wire, the determinism-hash wire, and the
`ResolvedStepsRecorded` payload wire, all encode/decode only):

  Resolve (the actual behavior):
  - a CaptureRef parameter value resolves against the per-conduct `captures`
    dict BEFORE the JobSpec is built, so a measured value can become a
    compute job's parameter
  - a SteeringRef parameter value resolves the same way, so a steering brain
    can tune a compute parameter directly rather than only a motor position
  - a literal value alongside ref values resolves together in one JobSpec

  Loud-fails (each -> recorded `failed` entry + ConductorFailure halt, NO
  in-flight marker, NOTHING submitted, parity with the ComputeStep OutputRef
  case and with _run_setpoint's CaptureRef/SteeringRef):
  - a CaptureRef to a name never captured
  - a SteeringRef to an axis never seeded

  Provenance:
  - a ref-bearing ComputeStep's recorded entries carry a `parameter_refs` key
    (the pre-resolution sentinel shapes); a literal-only step's entries carry
    none, so no existing recorded payload changes shape (backward-compat).

  Interaction with the OutputRef resolve (input_uris) that runs first:
  - an unresolved OutputRef input on a step that ALSO carries a parameter ref
    must not crash the failure body, since parameters resolution never runs
    (the OutputRef failure returns first).

The unit tier uses `InMemoryComputePort` (records what it received) + the
shared fake append-step handler, mirroring `test_conductor_compute_output.py`.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.clock import FakeClock
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.adapters.in_memory_compute_port import InMemoryComputePort
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.conductor import ComputeStep, Conductor
from cora.operation.features.append_activities.command import AppendProcedureActivities
from cora.operation.ports.compute_port import JobId, JobSpec
from cora.operation.ports.measurement import Measurement
from cora.recipe.aggregates.recipe.body import CaptureRef, OutputRef, SteeringRef

_FIXED_NOW = datetime(2026, 6, 24, 9, 0, 0, tzinfo=UTC)


class _RecordingComputePort(InMemoryComputePort):
    """`InMemoryComputePort` that records every submitted `JobSpec`.

    Lets a test assert what the Conductor actually submitted (the RESOLVED
    parameters) without reaching into the fake's private job map, and count
    submits to prove the unresolved-ref path submits NOTHING for the failing
    step."""

    def __init__(self) -> None:
        super().__init__()
        self.submitted_specs: list[JobSpec] = []

    async def submit(self, job_spec: JobSpec) -> JobId:
        self.submitted_specs.append(job_spec)
        return await super().submit(job_spec)

    @property
    def submit_count(self) -> int:
        return len(self.submitted_specs)


@dataclass
class _AppendCall:
    command: AppendProcedureActivities


@dataclass
class _FakeAppendStep:
    """Fake `Handler` for the append_activities slice; records every call."""

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
        self.calls.append(_AppendCall(command=command))
        return len(command.entries)


def _conductor(appender: _FakeAppendStep, *, compute_port: _RecordingComputePort) -> Conductor:
    return Conductor(
        control_port=InMemoryControlPort(),
        append_step=appender,
        clock=FakeClock(_FIXED_NOW),
        id_generator=_NilIdGenerator(),
        compute_port=compute_port,
    )


@dataclass
class _NilIdGenerator:
    def new_id(self) -> UUID:
        return uuid4()


def _entries(appender: _FakeAppendStep) -> list[dict[str, object]]:
    return [call.command.entries[0].payload for call in appender.calls]


_RECON_URI = "file:///data/2bm/recon.h5"


def _offset_measurement(value: object, *, name: str = "offset") -> Measurement:
    return Measurement(
        value=value,
        kind="Scalar",
        quality="Good",  # type: ignore[arg-type]
        produced_at=_FIXED_NOW,
        name=name,
        units="pixel",
    )


@pytest.mark.unit
async def test_capture_ref_parameter_resolves_into_job_spec() -> None:
    """A CaptureRef parameter value resolves against externally-seeded captures."""
    appender = _FakeAppendStep()
    port = _RecordingComputePort()
    conductor = _conductor(appender, compute_port=port)

    step = ComputeStep(
        command=("tomopy", "recon"),
        output_uri=_RECON_URI,
        parameters={"rotation_center": CaptureRef("offset")},
    )

    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(step,),
        captures={"offset": 12.5},
    )

    assert result.succeeded is True
    assert port.submitted_specs[-1].parameters == {"rotation_center": 12.5}


@pytest.mark.unit
async def test_capture_ref_parameter_resolves_value_deposited_earlier_in_same_pass() -> None:
    """A value-arm ComputeStep's capture_name deposit feeds a LATER compute parameter.

    Mirrors `test_conductor_compute_capture.py`'s same-pass deposit idiom: the
    first ComputeStep's produced Measurement deposits into `captures` via
    `capture_name`; the second ComputeStep's CaptureRef parameter reads it.
    """
    appender = _FakeAppendStep()
    port = _RecordingComputePort()
    port.set_next_measurements((_offset_measurement(7.5),))
    conductor = _conductor(appender, compute_port=port)

    find_offset = ComputeStep(
        command=("tomopy", "find_center"),
        input_uris=("file:///a.h5",),
        output_uri=None,
        parameters={"algorithm": "vo"},
        capture_name="offset",
    )
    reconstruct = ComputeStep(
        command=("tomopy", "recon"),
        output_uri=_RECON_URI,
        parameters={"rotation_center": CaptureRef("offset")},
    )

    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(find_offset, reconstruct),
    )

    assert result.succeeded is True
    assert port.submitted_specs[-1].parameters == {"rotation_center": 7.5}


@pytest.mark.unit
async def test_steering_ref_parameter_resolves_into_job_spec() -> None:
    """A SteeringRef parameter value resolves against externally-seeded captures.

    Mirrors how the decide loop seeds a steering axis before a pass; a unit
    test seeds it directly via `execute(..., captures=...)`.
    """
    appender = _FakeAppendStep()
    port = _RecordingComputePort()
    conductor = _conductor(appender, compute_port=port)

    step = ComputeStep(
        command=("tomopy", "recon"),
        output_uri=_RECON_URI,
        parameters={"seed": SteeringRef("focus")},
    )

    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(step,),
        captures={"focus": 0.42},
    )

    assert result.succeeded is True
    assert port.submitted_specs[-1].parameters == {"seed": 0.42}


@pytest.mark.unit
async def test_mixed_literal_and_ref_parameters_resolve_together() -> None:
    """A literal, a CaptureRef, and a SteeringRef in one parameters dict all resolve."""
    appender = _FakeAppendStep()
    port = _RecordingComputePort()
    conductor = _conductor(appender, compute_port=port)

    step = ComputeStep(
        command=("tomopy", "recon"),
        output_uri=_RECON_URI,
        parameters={
            "algorithm": "sirt",
            "rotation_center": CaptureRef("offset"),
            "seed": SteeringRef("focus"),
        },
    )

    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(step,),
        captures={"offset": 12.5, "focus": 0.42},
    )

    assert result.succeeded is True
    assert port.submitted_specs[-1].parameters == {
        "algorithm": "sirt",
        "rotation_center": 12.5,
        "seed": 0.42,
    }


@pytest.mark.unit
async def test_unresolved_capture_ref_parameter_records_failure_with_no_marker_and_no_submit() -> (
    None
):
    """A CaptureRef to a name never captured loud-fails BEFORE the marker + submit.

    Parity with the ComputeStep OutputRef case and with _run_setpoint's
    UnresolvedCaptureRef: a single FAILED entry, no in-flight marker, and
    NOTHING submitted to the compute substrate.
    """
    appender = _FakeAppendStep()
    port = _RecordingComputePort()
    conductor = _conductor(appender, compute_port=port)

    step = ComputeStep(
        command=("tomopy", "recon"),
        output_uri=_RECON_URI,
        parameters={"rotation_center": CaptureRef("missing")},
    )

    submits_before = port.submit_count
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(step,),
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.source_kind == "compute"
    assert result.failure.error_class == "UnresolvedCaptureRef"
    assert port.submit_count == submits_before
    entries = _entries(appender)
    assert len(entries) == 1
    assert entries[0]["result"] == "failed"
    assert entries[0]["error_class"] == "UnresolvedCaptureRef"


@pytest.mark.unit
async def test_unseeded_steering_ref_parameter_records_failure_with_no_marker_and_no_submit() -> (
    None
):
    """A SteeringRef to an axis never seeded loud-fails the same way as an unresolved CaptureRef."""
    appender = _FakeAppendStep()
    port = _RecordingComputePort()
    conductor = _conductor(appender, compute_port=port)

    step = ComputeStep(
        command=("tomopy", "recon"),
        output_uri=_RECON_URI,
        parameters={"seed": SteeringRef("missing")},
    )

    submits_before = port.submit_count
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(step,),
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_class == "UnresolvedCaptureRef"
    assert port.submit_count == submits_before
    entries = _entries(appender)
    assert len(entries) == 1
    assert entries[0]["result"] == "failed"


@pytest.mark.unit
async def test_parameter_refs_recorded_only_when_present() -> None:
    """A literal-only ComputeStep's recorded entries carry no parameter_refs key.

    Backward-compat pin: the new provenance field must not appear on a step
    that carries no ref, so no existing recorded payload changes shape. A
    ref-bearing step's entries DO carry it, with the sentinel shape.
    """
    literal_appender = _FakeAppendStep()
    literal_conductor = _conductor(literal_appender, compute_port=_RecordingComputePort())
    literal_step = ComputeStep(
        command=("tomopy", "recon"),
        output_uri=_RECON_URI,
        parameters={"algorithm": "sirt"},
    )

    literal_result = await literal_conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(literal_step,),
    )

    assert literal_result.succeeded is True
    for entry in _entries(literal_appender):
        assert "parameter_refs" not in entry

    ref_appender = _FakeAppendStep()
    ref_conductor = _conductor(ref_appender, compute_port=_RecordingComputePort())
    ref_step = ComputeStep(
        command=("tomopy", "recon"),
        output_uri=_RECON_URI,
        parameters={"rotation_center": CaptureRef("offset")},
    )

    ref_result = await ref_conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(ref_step,),
        captures={"offset": 12.5},
    )

    assert ref_result.succeeded is True
    marker = next(e for e in _entries(ref_appender) if e["result"] == "in_flight")
    assert marker["parameter_refs"] == {"rotation_center": {"__capture__": "offset"}}


@pytest.mark.unit
async def test_unresolved_output_ref_does_not_crash_when_parameters_also_carry_a_ref() -> None:
    """An unresolved OutputRef input records its failure body even with a parameter ref present.

    The OutputRef resolve (input_uris) runs BEFORE the new parameters resolve,
    so a step failing there never reaches parameter resolution. Its failure
    body must still serialize `parameters` safely (via the wire encoder, not
    a raw `dict()` copy) even though `parameters` still holds an unresolved
    CaptureRef at that point.
    """
    appender = _FakeAppendStep()
    port = _RecordingComputePort()
    conductor = _conductor(appender, compute_port=port)

    step = ComputeStep(
        command=("tomopy", "recon"),
        input_uris=(OutputRef("missing"),),
        output_uri=_RECON_URI,
        parameters={"rotation_center": CaptureRef("offset")},
    )

    submits_before = port.submit_count
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(step,),
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_class == "UnresolvedOutputRef"
    assert port.submit_count == submits_before
    entries = _entries(appender)
    assert len(entries) == 1
    assert entries[0]["parameters"] == {"rotation_center": {"__capture__": "offset"}}
