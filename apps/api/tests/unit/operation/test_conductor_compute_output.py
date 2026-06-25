"""Behavioural tests for the Conductor's ComputeStep OutputRef chaining (compute branch).

Coverage for the artifact bus (`outputs`) twin of the captures bus (slice 6c):

  Deposit + resolve (the chain):
  - a file-arm ComputeStep with `output_ref_name` deposits its ArtifactRef into
    the per-conduct `outputs` bus, surfaced on `ConductorResult.outputs` keyed
    by name
  - a later ComputeStep with an `OutputRef` input resolves it to the produced
    artifact's URI BEFORE building the JobSpec, so the resolved input == the
    producer's output_uri (the in-memory fake synthesises the ArtifactRef from
    output_uri)

  Fan-in:
  - a step with input_uris=(OutputRef("pr"), OutputRef("norm")) resolves BOTH
    against the bus, in order

  Loud-fails (each -> recorded `failed` entry + ConductorFailure halt):
  - an OutputRef to a name never deposited: FAILED before any in-flight marker,
    NOTHING submitted (parity with _run_setpoint's UnresolvedCaptureRef)
  - a duplicate output_ref_name deposit: FAILED after the OK record (the slot
    is already filled)

The unit tier uses `InMemoryComputePort` (synthesises an ArtifactRef from each
job spec's output_uri) + the shared fake append-step handler.
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
from cora.recipe.aggregates.recipe.body import OutputRef

_FIXED_NOW = datetime(2026, 6, 24, 9, 0, 0, tzinfo=UTC)


class _RecordingComputePort(InMemoryComputePort):
    """`InMemoryComputePort` that records every submitted `JobSpec`.

    Lets a test assert what the Conductor actually submitted (the RESOLVED
    input_uris) without reaching into the fake's private job map, and count
    submits to prove the unseeded-ref path submits NOTHING for the failing
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

    def last_spec_for(self, output_uri: str) -> JobSpec:
        for spec in reversed(self.submitted_specs):
            if spec.output_uri == output_uri:
                return spec
        msg = f"no submitted spec with output_uri {output_uri!r}"
        raise AssertionError(msg)


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


_PR_URI = "file:///data/2bm/pr.h5"
_NORM_URI = "file:///data/2bm/norm.h5"
_RECON_URI = "file:///data/2bm/recon.h5"


@pytest.mark.unit
async def test_output_ref_chain_resolves_producer_uri_into_later_input() -> None:
    """A file-arm step deposits its artifact; a later step's OutputRef resolves to it.

    The deposited ArtifactRef surfaces on ConductorResult.outputs by name, and
    the consumer's JobSpec input_uris == the producer's output_uri (the fake
    synthesises the ArtifactRef.uri from output_uri).
    """
    appender = _FakeAppendStep()
    port = _RecordingComputePort()
    conductor = _conductor(appender, compute_port=port)

    produce = ComputeStep(
        command=("tomopy", "phase"),
        input_uris=("file:///data/2bm/raw.h5",),
        output_uri=_PR_URI,
        output_ref_name="pr",
    )
    consume = ComputeStep(
        command=("tomopy", "norm"),
        input_uris=(OutputRef("pr"),),
        output_uri=_NORM_URI,
        output_ref_name="norm",
    )

    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(produce, consume),
    )

    assert result.succeeded is True
    assert result.completed_count == 2
    # both artifacts deposited into the named bus + surfaced
    assert set(result.outputs) == {"pr", "norm"}
    assert result.outputs["pr"].uri == _PR_URI
    assert result.outputs["norm"].uri == _NORM_URI
    # the consumer's job spec resolved the OutputRef to the producer's output_uri
    consume_spec = port.last_spec_for(_NORM_URI)
    assert consume_spec.input_uris == (_PR_URI,)
    # the recorded payload carries the RESOLVED uri + the pre-resolution ref
    consume_marker = next(
        p
        for p in _entries(appender)
        if p.get("output_uri") == _NORM_URI and p["result"] == "in_flight"
    )
    assert consume_marker["input_uris"] == [_PR_URI]
    assert consume_marker["input_refs"] == [{"__output__": "pr"}]


@pytest.mark.unit
async def test_output_ref_fan_in_resolves_every_named_output() -> None:
    """A step consuming (OutputRef("pr"), OutputRef("norm")) resolves BOTH, in order."""
    appender = _FakeAppendStep()
    port = _RecordingComputePort()
    conductor = _conductor(appender, compute_port=port)

    produce_pr = ComputeStep(
        command=("tomopy", "phase"),
        output_uri=_PR_URI,
        output_ref_name="pr",
    )
    produce_norm = ComputeStep(
        command=("tomopy", "norm"),
        output_uri=_NORM_URI,
        output_ref_name="norm",
    )
    reconstruct = ComputeStep(
        command=("tomopy", "recon"),
        input_uris=(OutputRef("pr"), OutputRef("norm")),
        output_uri=_RECON_URI,
        output_ref_name="recon",
    )

    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(produce_pr, produce_norm, reconstruct),
    )

    assert result.succeeded is True
    assert result.completed_count == 3
    recon_spec = port.last_spec_for(_RECON_URI)
    assert recon_spec.input_uris == (_PR_URI, _NORM_URI)
    assert result.outputs["recon"].uri == _RECON_URI


@pytest.mark.unit
async def test_unseeded_output_ref_records_failure_with_no_marker_and_no_submit() -> None:
    """An OutputRef to a name never deposited loud-fails BEFORE the marker + submit.

    Parity with _run_setpoint's UnresolvedCaptureRef: a single FAILED entry, no
    in-flight marker, and NOTHING submitted to the compute substrate.
    """
    appender = _FakeAppendStep()
    port = _RecordingComputePort()
    conductor = _conductor(appender, compute_port=port)

    # First a good produce, then a step that references both a seeded ("pr") and
    # an unseeded ("missing") output (the fan-in good+unseeded case): the
    # unseeded element halts the step before any effect.
    produce = ComputeStep(command=("tomopy", "phase"), output_uri=_PR_URI, output_ref_name="pr")
    consume = ComputeStep(
        command=("tomopy", "recon"),
        input_uris=(OutputRef("pr"), OutputRef("missing")),
        output_uri=_RECON_URI,
        output_ref_name="recon",
    )

    submits_before = port.submit_count
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(produce, consume),
    )

    assert result.succeeded is False
    assert result.completed_count == 1  # the produce step ran; the consume halted
    assert result.failure is not None
    assert result.failure.source_kind == "compute"
    assert result.failure.error_class == "UnresolvedOutputRef"
    # NOTHING submitted for the failing step: exactly one submit (the produce step).
    assert port.submit_count == submits_before + 1
    # the failing step recorded a SINGLE failed entry, NO in-flight marker.
    recon_entries = [p for p in _entries(appender) if p.get("output_uri") == _RECON_URI]
    assert len(recon_entries) == 1
    assert recon_entries[0]["result"] == "failed"
    assert recon_entries[0]["error_class"] == "UnresolvedOutputRef"
    assert recon_entries[0]["input_refs"] == [{"__output__": "pr"}, {"__output__": "missing"}]
    # the recon artifact never deposited
    assert "recon" not in result.outputs


@pytest.mark.unit
async def test_duplicate_output_ref_name_records_failure_after_ok() -> None:
    """Two file-arm steps depositing the same output_ref_name loud-fail (DuplicateOutput).

    The job's OK outcome records first (the artifact was produced); a SEPARATE
    failed entry records the duplicate-slot fault and the conduct halts.
    """
    appender = _FakeAppendStep()
    port = _RecordingComputePort()
    conductor = _conductor(appender, compute_port=port)

    first = ComputeStep(command=("tomopy", "phase"), output_uri=_PR_URI, output_ref_name="dup")
    second = ComputeStep(command=("tomopy", "norm"), output_uri=_NORM_URI, output_ref_name="dup")

    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(first, second),
    )

    assert result.succeeded is False
    assert result.completed_count == 1
    assert result.failure is not None
    assert result.failure.error_class == "DuplicateOutput"
    assert result.failure.target == "dup"
    # the first deposit holds the slot (the duplicate never overwrote it)
    assert result.outputs["dup"].uri == _PR_URI
    # the second step recorded its OK outcome THEN a duplicate-output failed entry
    second_entries = [p for p in _entries(appender) if p.get("output_uri") == _NORM_URI]
    assert [p["result"] for p in second_entries] == ["in_flight", "ok", "failed"]
    assert second_entries[-1]["error_class"] == "DuplicateOutput"
