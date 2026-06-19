"""Surface / contract tests for `ComputePort` and its value objects.

Mirror of `test_control_port.py`: pins the Protocol's value-object
shapes, the closed `ComputeStatus` enum, the derived `is_simulated`
provenance flag, and the exception attribute carriers. The in-memory
adapter's behavioural tests live in `test_in_memory_compute_port.py`.
"""

import pytest

from cora.operation.adapters.in_memory_compute_port import InMemoryComputePort
from cora.operation.ports.compute_port import (
    ArtifactNotFoundError,
    ArtifactRef,
    ComputeJobFailedError,
    ComputeNotAvailableError,
    ComputePort,
    ComputeProvenance,
    ComputeResources,
    ComputeStatus,
    ComputeSubmitRejectedError,
    ComputeTimeoutError,
    JobId,
    JobSpec,
)
from cora.operation.ports.control_port import ActuationKind


@pytest.mark.unit
def test_in_memory_adapter_satisfies_compute_port_protocol() -> None:
    assert isinstance(InMemoryComputePort(), ComputePort)


@pytest.mark.unit
def test_compute_status_is_a_closed_four_value_enum() -> None:
    assert {s.value for s in ComputeStatus} == {"Succeeded", "Failed", "Cancelled", "TimedOut"}


@pytest.mark.unit
def test_only_succeeded_is_a_success_status() -> None:
    assert ComputeStatus.SUCCEEDED.is_success is True
    assert ComputeStatus.FAILED.is_success is False
    assert ComputeStatus.CANCELLED.is_success is False
    assert ComputeStatus.TIMED_OUT.is_success is False


@pytest.mark.unit
def test_job_spec_defaults_are_empty_and_unspecified() -> None:
    spec = JobSpec(command=("tomopy", "recon"))
    assert spec.command == ("tomopy", "recon")
    assert spec.input_uris == ()
    assert spec.output_uri is None
    assert dict(spec.parameters) == {}
    assert spec.resources == ComputeResources()
    assert spec.working_dir is None
    assert dict(spec.env) == {}


@pytest.mark.unit
def test_artifact_ref_carries_register_dataset_shaped_fields() -> None:
    ref = ArtifactRef(
        uri="file:///data/recon.h5",
        checksum_algorithm="sha256",
        checksum_value="b" * 64,
        byte_size=1024,
        media_type="application/x-hdf5",
        conforms_to=("https://www.nexusformat.org/NXtomoproc",),
    )
    assert ref.uri == "file:///data/recon.h5"
    assert ref.checksum_algorithm == "sha256"
    assert ref.byte_size == 1024
    assert ref.conforms_to == ("https://www.nexusformat.org/NXtomoproc",)


@pytest.mark.unit
def test_provenance_is_simulated_is_derived_from_actuation_kind() -> None:
    job_id = JobId("job-1")
    physical = ComputeProvenance(
        job_id=job_id, status=ComputeStatus.SUCCEEDED, actuation_kind=ActuationKind.PHYSICAL
    )
    simulated = ComputeProvenance(
        job_id=job_id, status=ComputeStatus.SUCCEEDED, actuation_kind=ActuationKind.SIMULATED
    )
    hybrid = ComputeProvenance(
        job_id=job_id, status=ComputeStatus.SUCCEEDED, actuation_kind=ActuationKind.HYBRID
    )
    assert physical.is_simulated is False
    # Any simulator touch disqualifies promotion; Hybrid counts as simulated.
    assert simulated.is_simulated is True
    assert hybrid.is_simulated is True


@pytest.mark.unit
def test_compute_exception_attribute_carriers() -> None:
    job_id = JobId("job-7")
    assert ComputeSubmitRejectedError("quota exceeded").reason == "quota exceeded"
    assert ComputeNotAvailableError("binary missing").reason == "binary missing"

    timeout = ComputeTimeoutError(job_id, 30.0)
    assert timeout.job_id == job_id
    assert timeout.timeout_s == 30.0

    failed = ComputeJobFailedError(job_id, "exit code 1")
    assert failed.job_id == job_id
    assert failed.reason == "exit code 1"

    missing = ArtifactNotFoundError(job_id, "file:///nope.h5")
    assert missing.job_id == job_id
    assert missing.uri == "file:///nope.h5"
