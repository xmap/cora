"""Unit tests for the composition-root `ComputeRuntime`.

Drives `conduct()` over the in-memory event store with the
`InMemoryComputePort` fake (plus tiny purpose-built fakes for the
submit-failure and cancellation paths). Asserts the Run FSM transition
and the captured conduct provenance on the terminal event.
"""

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.api._compute_runtime import ComputeRuntime
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.operation.adapters.in_memory_compute_port import InMemoryComputePort
from cora.operation.ports.compute_port import (
    ComputeStatus,
    ComputeSubmitRejectedError,
    JobId,
    JobSpec,
)
from cora.run.aggregates.run.events import RunStarted, event_type_name, to_payload
from cora.run.features import abort_run, complete_run

_NOW = datetime(2026, 5, 20, 9, 30, 0, tzinfo=UTC)
_RUN_ID = UUID("01900000-0000-7000-8000-00000000ab01")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-00000000ab02")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000000ab03")
_SPEC = JobSpec(command=("tomopy", "recon"), output_uri="file:///data/recon.h5")


async def _seed_run_started(store: InMemoryEventStore, run_id: UUID) -> None:
    event = RunStarted(
        run_id=run_id,
        name="SIRT reconstruction",
        plan_id=uuid4(),
        subject_id=None,
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="StartRun",
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
    )
    await store.append(stream_type="Run", stream_id=run_id, expected_version=0, events=[new_event])


def _runtime(store: InMemoryEventStore, compute_port: object) -> ComputeRuntime:
    from tests.unit._helpers import build_deps

    deps = build_deps(ids=[uuid4() for _ in range(8)], now=_NOW, event_store=store)
    return ComputeRuntime(
        compute_port=compute_port,  # type: ignore[arg-type]
        complete_run=complete_run.bind(deps),
        abort_run=abort_run.bind(deps),
    )


@pytest.mark.unit
async def test_successful_conduct_completes_run_with_captured_provenance() -> None:
    store = InMemoryEventStore()
    await _seed_run_started(store, _RUN_ID)
    runtime = _runtime(store, InMemoryComputePort())

    result = await runtime.conduct(
        run_id=_RUN_ID,
        job_spec=_SPEC,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert result.succeeded
    assert result.status is ComputeStatus.SUCCEEDED
    assert result.artifact_ref is not None
    assert result.artifact_ref.uri == "file:///data/recon.h5"

    events, _ = await store.load("Run", _RUN_ID)
    assert [e.event_type for e in events] == ["RunStarted", "RunCompleted"]
    completed = events[1].payload
    assert completed["actuation_kind"] == "Simulated"
    assert completed["producing_job_id"] == "inmem-job-1"
    assert completed["artifact_uri"] == "file:///data/recon.h5"


@pytest.mark.unit
async def test_failed_job_aborts_run_and_taints_with_actuation_kind() -> None:
    store = InMemoryEventStore()
    await _seed_run_started(store, _RUN_ID)
    port = InMemoryComputePort()
    port.set_next_result(ComputeStatus.FAILED)
    runtime = _runtime(store, port)

    result = await runtime.conduct(
        run_id=_RUN_ID,
        job_spec=_SPEC,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert not result.succeeded
    assert result.status is ComputeStatus.FAILED
    assert result.failure == "compute job failed"

    events, _ = await store.load("Run", _RUN_ID)
    assert [e.event_type for e in events] == ["RunStarted", "RunAborted"]
    aborted = events[1].payload
    assert aborted["reason"] == "compute job failed"
    # Even a failed conduct taints the Run so a Dataset off it can't promote.
    assert aborted["actuation_kind"] == "Simulated"
    assert aborted["producing_job_id"] == "inmem-job-1"


class _RejectingComputePort:
    """Fake whose `submit` always rejects; the job never starts."""

    async def submit(self, job_spec: JobSpec) -> JobId:
        _ = job_spec
        raise ComputeSubmitRejectedError("quota exceeded")

    async def await_terminal_state(self, job_id: JobId) -> ComputeStatus:  # pragma: no cover
        raise NotImplementedError

    async def fetch_artifact_ref(self, job_id: JobId) -> object:  # pragma: no cover
        raise NotImplementedError

    def provide_provenance_payload(self, *args: object) -> object:  # pragma: no cover
        raise NotImplementedError

    async def aclose(self) -> None:  # pragma: no cover
        return None


@pytest.mark.unit
async def test_submit_rejection_aborts_run_with_no_terminal_status() -> None:
    store = InMemoryEventStore()
    await _seed_run_started(store, _RUN_ID)
    runtime = _runtime(store, _RejectingComputePort())

    result = await runtime.conduct(
        run_id=_RUN_ID,
        job_spec=_SPEC,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert result.status is None
    assert (
        result.failure == "compute submit failed: Compute job submission rejected: quota exceeded"
    )

    events, _ = await store.load("Run", _RUN_ID)
    assert [e.event_type for e in events] == ["RunStarted", "RunAborted"]
    # No job ran, so no actuation kind was observed.
    assert events[1].payload["actuation_kind"] is None


class _CancellingComputePort:
    """Fake whose `await_terminal_state` is cancelled mid-flight."""

    async def submit(self, job_spec: JobSpec) -> JobId:
        _ = job_spec
        return JobId("job-cancelled")

    async def await_terminal_state(self, job_id: JobId) -> ComputeStatus:
        _ = job_id
        raise asyncio.CancelledError

    async def fetch_artifact_ref(self, job_id: JobId) -> object:  # pragma: no cover
        raise NotImplementedError

    def provide_provenance_payload(self, *args: object) -> object:  # pragma: no cover
        raise NotImplementedError

    async def aclose(self) -> None:  # pragma: no cover
        return None


@pytest.mark.unit
async def test_cancellation_best_effort_aborts_run_then_reraises() -> None:
    store = InMemoryEventStore()
    await _seed_run_started(store, _RUN_ID)
    runtime = _runtime(store, _CancellingComputePort())

    with pytest.raises(asyncio.CancelledError):
        await runtime.conduct(
            run_id=_RUN_ID,
            job_spec=_SPEC,
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, _ = await store.load("Run", _RUN_ID)
    assert [e.event_type for e in events] == ["RunStarted", "RunAborted"]
    assert events[1].payload["reason"] == "cancelled mid-compute"
