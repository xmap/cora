"""GlobusComputePort adapter: run a compute job on a remote Globus Compute endpoint.

The second real `ComputePort` substrate, the off-host sibling of
`LocalProcessComputePort`. Where the local adapter runs a subprocess on the same
box, this submits a task to a Globus Compute endpoint (a process the facility
runs on a remote resource such as an ALCF Polaris login node), polls the task to
a terminal state, and surfaces the artifact the job wrote. It is the executor
behind an off-storage reconstruction: the raw data is staged to the endpoint's
readable storage (the transfer leg), the recon runs here, the volume lands back.

## CORA-owned seam, not an SDK wrapper

The adapter depends on an injected `GlobusComputeClient` Protocol (submit a
task, poll its status, fetch its result), NOT on `globus-compute-sdk` directly.
This keeps the adapter unit-testable against a fake and avoids a hard dependency:
`globus-compute-sdk` pins `globus-sdk>=4`, which conflicts with the transfer
leg's `globus-sdk>=3,<4`, so the concrete SDK client is bound at the composition
root (where a deployment that uses Globus Compute resolves the version), never
imported here. Same posture as `GlobusTransferPort` over `GlobusTransferClient`.

## Submission model: blocking submit + internal poll-to-terminal

This satisfies the existing `ComputePort` surface unchanged: `submit` returns a
`JobId` (the Globus task id), and `await_terminal_state` polls the endpoint
(poll, sleep, poll) until the task reports a terminal state or a wall-clock
ceiling elapses (`ComputeTimeoutError`). A remote recon runs for hours, so the
await is a poll loop rather than a process wait, but the run-driver cannot tell
the difference: the port contract is submission-to-terminal, and the poll lives
entirely inside the adapter. Fire-and-reconcile submission (submit returns, a
separate reconciler drives the terminal so the wait survives a process restart)
stays the deferred trigger the port docstring names; it is a runtime-layer change
that does NOT reshape this port, since `submit` already returns a handle and
`await_terminal_state` is already a separate call.

## Status mapping

Globus Compute task status maps into CORA's closed `ComputeStatus`:
`success` -> `Succeeded`; `failed` -> a `ComputeJobFailedError` carrying the task
exception detail (richer than a bare `Failed`, mirroring the local adapter's
stderr tail); a task that is still `waiting`/`running` keeps the poll loop going.
A caller-driven cancellation surfaces as `Cancelled` via the run-driver
cancelling the awaiting task, the same as the local adapter; explicit
cancel-by-handle stays the deferred trigger.

## Artifact stat is injected, not local

The job wrote its output on the endpoint's storage, which this process cannot
stat directly (it is a different host). So `fetch_artifact_ref` delegates to an
injected `RemoteArtifactProbe` that resolves `output_uri` into a checksum + size
on the endpoint's side (in practice the submitted task returns this, or a
companion probe reads it over the same channel). This keeps the checksum the
job's own claim about the bytes it wrote, distinct from CORA's authoritative
`Attestation` (which re-verifies on arrival after the result is transferred
back). `fetch_measurements` raises `MeasurementNotFoundError`: the value arm is
not implemented for this substrate (mirrors the local adapter at this slice).

## Not run against a live endpoint

Unit-tested against a fake client + fake probe; NOT exercised against a real
Globus Compute endpoint (that needs credentials and a registered endpoint).
Treat live behaviour as unverified until a credentialed sanity run.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from cora.operation.ports.compute_port import (
    ArtifactNotFoundError,
    ArtifactRef,
    ComputeJobFailedError,
    ComputeNotAvailableError,
    ComputeResult,
    ComputeStatus,
    ComputeSubmitRejectedError,
    ComputeTimeoutError,
    JobId,
    JobSpec,
    MeasurementNotFoundError,
)
from cora.operation.ports.control_port import ActuationKind

if TYPE_CHECKING:
    from collections.abc import Mapping

    from cora.operation.ports.measurement import Measurement

_TASK_STATUS_SUCCESS = "success"
"""Globus Compute terminal status string for a task that completed cleanly."""

_TASK_STATUS_FAILED = "failed"
"""Globus Compute terminal status string for a task that errored."""

_DEFAULT_POLL_INTERVAL_S = 5.0
"""Seconds between endpoint status polls. A remote recon runs for minutes-to-hours,
so a coarse interval keeps the poll cost negligible without delaying the terminal
observation meaningfully."""


@dataclass(frozen=True)
class RemoteTaskStatus:
    """A poll snapshot of a Globus Compute task, in adapter-neutral terms.

    `terminal` is False while the task is still waiting/running; True once it has
    reached success or failure. `succeeded` is meaningful only when `terminal`.
    `detail` carries the endpoint's failure text (a traceback / exception string)
    for a failed task, surfaced on `ComputeJobFailedError`.
    """

    terminal: bool
    succeeded: bool
    detail: str | None = None


class GlobusComputeClient(Protocol):
    """The slice of a Globus Compute client this adapter calls.

    A real `globus_compute_sdk.Client` / `Executor` satisfies this structurally;
    a deployment binds the concrete client at the composition root. Owning the
    seam keeps the adapter testable with a fake and pins exactly the three
    operations CORA relies on: submit a task, poll its status, fetch its result.
    """

    def submit_task(
        self, endpoint_id: str, command: tuple[str, ...], payload: Mapping[str, object]
    ) -> str: ...

    def task_status(self, task_id: str) -> RemoteTaskStatus: ...

    def task_result(self, task_id: str) -> Mapping[str, object]: ...


class RemoteArtifactProbe(Protocol):
    """Resolves a remote `output_uri` into an `ArtifactRef` (checksum + size).

    The produced bytes live on the endpoint's storage, which this process cannot
    stat directly, so the checksum + size are the endpoint's claim (returned by
    the task or read by a companion probe over the same channel). Injected so the
    adapter stays testable and substrate-network details stay out of the port.
    """

    async def stat(self, output_uri: str) -> ArtifactRef: ...


@dataclass
class GlobusComputePort:
    """`ComputePort` backed by an injected Globus Compute client + artifact probe.

    Construct with an already-authorized client, the target `endpoint_id`, and a
    remote artifact probe. `default_timeout_s` is the hard await ceiling per job;
    `poll_interval_s` paces the status polls. See the module docstring for the
    blocking-submit + internal-poll model and why the SDK is injected.
    """

    client: GlobusComputeClient
    endpoint_id: str
    artifact_probe: RemoteArtifactProbe
    default_timeout_s: float = 3600.0
    poll_interval_s: float = _DEFAULT_POLL_INTERVAL_S
    _specs: dict[JobId, JobSpec] = field(default_factory=dict[JobId, JobSpec], init=False)

    async def submit(self, job_spec: JobSpec) -> JobId:
        try:
            task_id = await asyncio.to_thread(
                self.client.submit_task,
                self.endpoint_id,
                job_spec.command,
                dict(job_spec.parameters),
            )
        except _SUBMIT_REJECTED as exc:
            raise ComputeSubmitRejectedError(str(exc)) from exc
        except OSError as exc:
            raise ComputeNotAvailableError(str(exc)) from exc
        job_id = JobId(str(task_id))
        self._specs[job_id] = job_spec
        return job_id

    async def await_terminal_state(self, job_id: JobId) -> ComputeStatus:
        waited = 0.0
        while True:
            status = await asyncio.to_thread(self.client.task_status, str(job_id))
            if status.terminal:
                if status.succeeded:
                    return ComputeStatus.SUCCEEDED
                raise ComputeJobFailedError(job_id, status.detail or "task failed")
            if waited >= self.default_timeout_s:
                raise ComputeTimeoutError(job_id, self.default_timeout_s)
            await asyncio.sleep(self.poll_interval_s)
            waited += self.poll_interval_s

    async def fetch_artifact_ref(self, job_id: JobId) -> ArtifactRef:
        spec = self._specs[job_id]
        if spec.output_uri is None:
            raise ArtifactNotFoundError(job_id, "<no output_uri declared>")
        return await self.artifact_probe.stat(spec.output_uri)

    async def fetch_measurements(self, job_id: JobId) -> tuple[Measurement, ...]:
        raise MeasurementNotFoundError(job_id)

    def provide_result(
        self,
        job_id: JobId,
        status: ComputeStatus,
        artifacts: tuple[ArtifactRef, ...] = (),
        measurements: tuple[Measurement, ...] = (),
    ) -> ComputeResult:
        return ComputeResult(
            job_id=job_id,
            status=status,
            actuation_kind=ActuationKind.PHYSICAL,
            artifacts=artifacts,
            measurements=measurements,
        )

    async def aclose(self) -> None:
        """No-op: the injected client's lifecycle is the composition root's."""


_SUBMIT_REJECTED: tuple[type[Exception], ...] = (ValueError, KeyError)
"""Client-side exceptions from a malformed submit that map to a rejection rather
than an unreachable substrate. A real SDK client raises its own exception types;
the composition-root binding adapts those into this tuple (or a thin wrapper),
keeping substrate-specific exception classes out of this module. OSError (a
genuine connection failure) maps to ComputeNotAvailableError instead."""


__all__ = [
    "GlobusComputeClient",
    "GlobusComputePort",
    "RemoteArtifactProbe",
    "RemoteTaskStatus",
]
