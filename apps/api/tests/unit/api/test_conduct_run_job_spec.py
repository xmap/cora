"""Unit tests for `build_job_spec` (request -> JobSpec mapping)."""

import pytest

from cora.api._conduct_run_route import (
    ComputeResourcesRequest,
    ConductRunRequest,
    build_job_spec,
)
from cora.operation.ports.compute_port import ComputeResources


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
