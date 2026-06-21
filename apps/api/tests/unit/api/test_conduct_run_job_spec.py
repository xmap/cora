"""Unit tests for the conduct route's request/result mapping.

Covers `build_job_spec` (request -> JobSpec) and `result_to_wire`
(runtime result -> response), including the directory `sha256-tree`
artifact fields surfaced for the operator to register.
"""

from uuid import uuid4

import pytest

from cora.api._compute_runtime import ComputeRunResult
from cora.api._conduct_run_route import (
    ComputeResourcesRequest,
    ConductRunRequest,
    build_job_spec,
    result_to_wire,
)
from cora.operation.ports.compute_port import (
    ArtifactRef,
    ComputeResources,
    ComputeStatus,
    JobId,
)
from cora.operation.ports.control_port import ActuationKind


@pytest.mark.unit
def test_build_job_spec_maps_command_uris_and_parameters() -> None:
    request = ConductRunRequest(
        command=["tomopy", "recon", "--algorithm", "sirt"],
        input_uris=["file:///data/raw.h5"],
        output_uri="file:///data/recon.h5",
        parameters={"num_iter": 200, "tol": 0.0005},
    )
    spec = build_job_spec(request)
    assert spec.command == ("tomopy", "recon", "--algorithm", "sirt")
    assert spec.input_uris == ("file:///data/raw.h5",)
    assert spec.output_uri == "file:///data/recon.h5"
    assert dict(spec.parameters) == {"num_iter": 200, "tol": 0.0005}
    # Resources omitted -> unspecified defaults.
    assert spec.resources == ComputeResources()


@pytest.mark.unit
def test_build_job_spec_maps_resources_when_present() -> None:
    request = ConductRunRequest(
        command=["noop"],
        resources=ComputeResourcesRequest(
            gpu_count=4, gpu_memory_gb=80.0, system_ram_gb=512.0, cpus=64
        ),
    )
    spec = build_job_spec(request)
    assert spec.resources == ComputeResources(
        gpu_count=4, gpu_memory_gb=80.0, system_ram_gb=512.0, cpus=64
    )


@pytest.mark.unit
def test_build_job_spec_defaults_empty_inputs_and_no_output() -> None:
    spec = build_job_spec(ConductRunRequest(command=["noop"]))
    assert spec.input_uris == ()
    assert spec.output_uri is None
    assert dict(spec.parameters) == {}


@pytest.mark.unit
def test_result_to_wire_surfaces_directory_tree_hash_artifact_fields() -> None:
    artifact = ArtifactRef(
        uri="file:///data/sample_rec",
        checksum_algorithm="sha256-tree",
        checksum_value="a" * 64,
        byte_size=4096,
        entry_count=512,
    )
    result = ComputeRunResult(
        run_id=uuid4(),
        status=ComputeStatus.SUCCEEDED,
        job_id=JobId("local-1-1"),
        artifact_ref=artifact,
        actuation_kind=ActuationKind.PHYSICAL,
    )

    wire = result_to_wire(result)

    assert wire.succeeded is True
    assert wire.artifact_uri == "file:///data/sample_rec"
    assert wire.checksum_algorithm == "sha256-tree"
    assert wire.checksum_value == "a" * 64
    assert wire.byte_size == 4096
    assert wire.entry_count == 512


@pytest.mark.unit
def test_result_to_wire_single_file_artifact_has_no_entry_count() -> None:
    artifact = ArtifactRef(
        uri="file:///data/recon.h5",
        checksum_algorithm="sha256",
        checksum_value="b" * 64,
        byte_size=2048,
    )
    result = ComputeRunResult(
        run_id=uuid4(),
        status=ComputeStatus.SUCCEEDED,
        job_id=JobId("local-1-1"),
        artifact_ref=artifact,
        actuation_kind=ActuationKind.PHYSICAL,
    )

    wire = result_to_wire(result)

    assert wire.checksum_algorithm == "sha256"
    assert wire.byte_size == 2048
    assert wire.entry_count is None


@pytest.mark.unit
def test_result_to_wire_failure_has_no_artifact_fields() -> None:
    result = ComputeRunResult(
        run_id=uuid4(),
        status=ComputeStatus.FAILED,
        job_id=JobId("local-1-1"),
        failure="compute job failed",
    )

    wire = result_to_wire(result)

    assert wire.succeeded is False
    assert wire.failure == "compute job failed"
    assert wire.checksum_algorithm is None
    assert wire.checksum_value is None
    assert wire.byte_size is None
    assert wire.entry_count is None
