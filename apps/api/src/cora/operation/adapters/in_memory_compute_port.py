"""In-memory `ComputePort` adapter for unit tests and `app_env=test`.

Mirrors `InMemoryControlPort`: dict-backed, no subprocess, no
scheduler. Tests seed outcomes via `set_next_result`; the conducting
runtime calls `submit` / `await_terminal_state` / `fetch_artifact_ref`
against the same instance and observes the seeded state.

Per [[project_test_infra]]'s 5-tier pyramid this serves the unit tier.
The production substrate adapter (`LocalProcessComputePort`) implements
the same `ComputePort` Protocol against a real subprocess.

## Intentional reversal of a deferred anti-hook

The compute design memo banned an `InMemoryComputePort` because at
RECORD-only time there was no consumer for a compute fake. That
justification ended when the CONDUCT runtime (`ComputeRuntime`) landed:
the fake now serves the unit and scenario tiers exactly as
`InMemoryControlPort` serves the Conductor's tests. The fake is
justified once a consumer exists, on CORA's own standard
([[feedback_port_generalization_trigger]]); this is a deliberate,
re-evaluated reversal, not an oversight.

## Result model

Each `submit` mints a deterministic `JobId` (`inmem-job-<n>`) and
binds it to a terminal outcome. By default a job `Succeeds` and its
artifact is synthesised from the spec's `output_uri`, so happy-path
tests need no seeding. `set_next_result` seeds the outcome for the
next submitted job (FIFO), letting failure-path tests drive `Failed`
/ `Cancelled` / `TimedOut` and custom artifacts.

## Actuation kind

The fake declares `ActuationKind.SIMULATED` on every provenance
payload: an in-memory job never touches real hardware or a real
solver, so any Dataset produced through it is correctly barred from
promotion to Production.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from cora.operation.ports.compute_port import (
    ArtifactNotFoundError,
    ArtifactRef,
    ComputeProvenance,
    ComputeStatus,
    JobId,
    JobSpec,
)
from cora.operation.ports.control_port import ActuationKind


@dataclass
class _SeededResult:
    """One seeded terminal outcome awaiting the next `submit`."""

    status: ComputeStatus
    artifact_ref: ArtifactRef | None


@dataclass
class _JobRecord:
    """The bound outcome of a submitted job."""

    spec: JobSpec
    status: ComputeStatus
    artifact_ref: ArtifactRef | None


class InMemoryComputePort:
    """Process-local dict adapter for `ComputePort`.

    See module docstring for the result model and the deliberate
    reversal of the deferred `InMemoryComputePort` anti-hook.
    """

    def __init__(self) -> None:
        self._seeded: list[_SeededResult] = []
        self._jobs: dict[JobId, _JobRecord] = {}
        self._counter = 0
        self._closed = False

    def set_next_result(
        self,
        status: ComputeStatus,
        *,
        artifact_ref: ArtifactRef | None = None,
    ) -> None:
        """Seed the terminal outcome of the next submitted job (FIFO).

        Test entry point. A `Succeeded` seed without an explicit
        `artifact_ref` falls back to a synthesised artifact from the
        spec's `output_uri` at `fetch_artifact_ref` time, matching the
        zero-seeding happy-path default.
        """
        self._seeded.append(_SeededResult(status=status, artifact_ref=artifact_ref))

    async def submit(self, job_spec: JobSpec) -> JobId:
        self._counter += 1
        job_id = JobId(f"inmem-job-{self._counter}")
        if self._seeded:
            seeded = self._seeded.pop(0)
            status, artifact_ref = seeded.status, seeded.artifact_ref
        else:
            status, artifact_ref = ComputeStatus.SUCCEEDED, None
        self._jobs[job_id] = _JobRecord(spec=job_spec, status=status, artifact_ref=artifact_ref)
        return job_id

    async def await_terminal_state(self, job_id: JobId) -> ComputeStatus:
        return self._jobs[job_id].status

    async def fetch_artifact_ref(self, job_id: JobId) -> ArtifactRef:
        record = self._jobs[job_id]
        if record.artifact_ref is not None:
            return record.artifact_ref
        output_uri = record.spec.output_uri
        if output_uri is None:
            raise ArtifactNotFoundError(job_id, "<no output_uri on job spec>")
        # Synthesise a deterministic artifact from the declared output
        # uri so happy-path tests need no seeding. The checksum is the
        # sha256 of the uri string (stable, not the real file bytes the
        # fake never wrote); byte_size is a fixed placeholder.
        digest = hashlib.sha256(output_uri.encode()).hexdigest()
        return ArtifactRef(
            uri=output_uri,
            checksum_algorithm="sha256",
            checksum_value=digest,
            byte_size=0,
        )

    def provide_provenance_payload(
        self,
        job_id: JobId,
        status: ComputeStatus,
        artifact_ref: ArtifactRef | None,
    ) -> ComputeProvenance:
        return ComputeProvenance(
            job_id=job_id,
            status=status,
            actuation_kind=ActuationKind.SIMULATED,
            artifact_ref=artifact_ref,
        )

    async def aclose(self) -> None:
        """No-op for the in-memory adapter; idempotent.

        Provided so composition code can call `aclose()` on any
        `ComputePort` without type-checking. The dict-backed state is
        not a substrate resource.
        """
        self._closed = True


__all__ = ["InMemoryComputePort"]
