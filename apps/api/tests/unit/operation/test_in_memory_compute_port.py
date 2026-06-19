"""Behavioural tests for `InMemoryComputePort`.

Mirror of `test_in_memory_control_port.py`: exercises the seeded
result model, the zero-seeding happy-path artifact synthesis, the
failure seeds, and the `Simulated` provenance the fake always declares.
"""

import pytest

from cora.operation.adapters.in_memory_compute_port import InMemoryComputePort
from cora.operation.ports.compute_port import (
    ArtifactNotFoundError,
    ArtifactRef,
    ComputeStatus,
    JobSpec,
)
from cora.operation.ports.control_port import ActuationKind

_SPEC = JobSpec(command=("tomopy", "recon"), output_uri="file:///data/recon.h5")


@pytest.mark.unit
async def test_happy_path_succeeds_and_synthesises_artifact_from_output_uri() -> None:
    port = InMemoryComputePort()
    job_id = await port.submit(_SPEC)
    status = await port.await_terminal_state(job_id)
    assert status is ComputeStatus.SUCCEEDED

    artifact = await port.fetch_artifact_ref(job_id)
    assert artifact.uri == "file:///data/recon.h5"
    assert artifact.checksum_algorithm == "sha256"
    assert len(artifact.checksum_value) == 64


@pytest.mark.unit
async def test_submit_mints_distinct_deterministic_job_ids() -> None:
    port = InMemoryComputePort()
    first = await port.submit(_SPEC)
    second = await port.submit(_SPEC)
    assert first == "inmem-job-1"
    assert second == "inmem-job-2"


@pytest.mark.unit
async def test_seeded_failure_status_is_returned() -> None:
    port = InMemoryComputePort()
    port.set_next_result(ComputeStatus.FAILED)
    job_id = await port.submit(_SPEC)
    assert await port.await_terminal_state(job_id) is ComputeStatus.FAILED


@pytest.mark.unit
async def test_seeded_results_apply_fifo() -> None:
    port = InMemoryComputePort()
    port.set_next_result(ComputeStatus.TIMED_OUT)
    port.set_next_result(ComputeStatus.SUCCEEDED)
    first = await port.submit(_SPEC)
    second = await port.submit(_SPEC)
    assert await port.await_terminal_state(first) is ComputeStatus.TIMED_OUT
    assert await port.await_terminal_state(second) is ComputeStatus.SUCCEEDED


@pytest.mark.unit
async def test_seeded_explicit_artifact_is_returned_verbatim() -> None:
    port = InMemoryComputePort()
    seeded = ArtifactRef(
        uri="file:///custom.h5",
        checksum_algorithm="sha256",
        checksum_value="c" * 64,
        byte_size=4096,
    )
    port.set_next_result(ComputeStatus.SUCCEEDED, artifact_ref=seeded)
    job_id = await port.submit(_SPEC)
    assert await port.fetch_artifact_ref(job_id) == seeded


@pytest.mark.unit
async def test_fetch_artifact_raises_when_no_output_uri_and_no_seed() -> None:
    port = InMemoryComputePort()
    job_id = await port.submit(JobSpec(command=("noop",)))
    with pytest.raises(ArtifactNotFoundError):
        await port.fetch_artifact_ref(job_id)


@pytest.mark.unit
async def test_provenance_payload_declares_simulated_actuation() -> None:
    port = InMemoryComputePort()
    job_id = await port.submit(_SPEC)
    status = await port.await_terminal_state(job_id)
    artifact = await port.fetch_artifact_ref(job_id)

    provenance = port.provide_provenance_payload(job_id, status, artifact)
    assert provenance.actuation_kind is ActuationKind.SIMULATED
    assert provenance.is_simulated is True
    assert provenance.job_id == job_id
    assert provenance.artifact_ref == artifact


@pytest.mark.unit
async def test_aclose_is_idempotent_noop() -> None:
    port = InMemoryComputePort()
    await port.aclose()
    await port.aclose()
