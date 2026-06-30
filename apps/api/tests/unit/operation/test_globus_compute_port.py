"""Unit tests for GlobusComputePort against a fake Globus Compute client + probe.

The adapter submits a task, polls it to a terminal via the existing blocking
submit -> await -> fetch surface (the poll loop lives inside the adapter), and
maps Globus task status into ComputeStatus. The client + artifact probe are
faked, so nothing here reaches a live endpoint; live behaviour is unverified.
"""

from collections.abc import Mapping

import pytest

from cora.operation.adapters.compute_port_config import ComputePortConfig, build_compute_port
from cora.operation.adapters.globus_compute_port import (
    GlobusComputePort,
    RemoteTaskStatus,
)
from cora.operation.adapters.in_memory_compute_port import InMemoryComputePort
from cora.operation.adapters.local_process_compute_port import LocalProcessComputePort
from cora.operation.ports.compute_port import (
    ArtifactNotFoundError,
    ArtifactRef,
    ComputeJobFailedError,
    ComputeNotAvailableError,
    ComputePort,
    ComputeStatus,
    ComputeSubmitRejectedError,
    ComputeTimeoutError,
    JobSpec,
    MeasurementNotFoundError,
)

_ENDPOINT = "endpoint-polaris-01"
_ARTIFACT = ArtifactRef(
    uri="globus://eagle/recon/scan_001_rec/",
    checksum_algorithm="sha256-tree",
    checksum_value="a" * 64,
    byte_size=8192,
    entry_count=180,
)
_JOB = JobSpec(command=("tomocupy", "recon"), output_uri="globus://eagle/recon/scan_001_rec/")


class _FakeProbe:
    def __init__(self, artifact: ArtifactRef = _ARTIFACT) -> None:
        self._artifact = artifact
        self.stat_calls: list[str] = []

    async def stat(self, output_uri: str) -> ArtifactRef:
        self.stat_calls.append(output_uri)
        return self._artifact


class _FakeClient:
    """Records the submitted task and replays a seeded status sequence."""

    def __init__(
        self,
        *,
        task_id: str = "task-globus-1",
        statuses: list[RemoteTaskStatus] | None = None,
        submit_error: Exception | None = None,
    ) -> None:
        self.submitted: list[tuple[str, tuple[str, ...], Mapping[str, object]]] = []
        self._task_id = task_id
        self._statuses = list(statuses or [RemoteTaskStatus(terminal=True, succeeded=True)])
        self._submit_error = submit_error

    def submit_task(
        self, endpoint_id: str, command: tuple[str, ...], payload: Mapping[str, object]
    ) -> str:
        if self._submit_error is not None:
            raise self._submit_error
        self.submitted.append((endpoint_id, command, payload))
        return self._task_id

    def task_status(self, task_id: str) -> RemoteTaskStatus:
        status = self._statuses[0]
        if len(self._statuses) > 1:
            self._statuses.pop(0)
        return status

    def task_result(self, task_id: str) -> Mapping[str, object]:
        return {}


def _port(client: _FakeClient, probe: _FakeProbe | None = None) -> GlobusComputePort:
    return GlobusComputePort(
        client=client,
        endpoint_id=_ENDPOINT,
        artifact_probe=probe or _FakeProbe(),
        poll_interval_s=0.0,
    )


@pytest.mark.unit
async def test_submit_returns_the_task_id_as_job_id_and_targets_the_endpoint() -> None:
    client = _FakeClient(task_id="task-abc")
    port = _port(client)
    job_id = await port.submit(_JOB)
    assert job_id == "task-abc"
    assert client.submitted[0][0] == _ENDPOINT
    assert client.submitted[0][1] == ("tomocupy", "recon")


@pytest.mark.unit
async def test_await_polls_running_then_success_to_succeeded() -> None:
    client = _FakeClient(
        statuses=[
            RemoteTaskStatus(terminal=False, succeeded=False),
            RemoteTaskStatus(terminal=False, succeeded=False),
            RemoteTaskStatus(terminal=True, succeeded=True),
        ]
    )
    port = _port(client)
    job_id = await port.submit(_JOB)
    assert await port.await_terminal_state(job_id) is ComputeStatus.SUCCEEDED


@pytest.mark.unit
async def test_await_maps_a_failed_task_to_compute_job_failed_with_detail() -> None:
    client = _FakeClient(
        statuses=[RemoteTaskStatus(terminal=True, succeeded=False, detail="solver OOM")]
    )
    port = _port(client)
    job_id = await port.submit(_JOB)
    with pytest.raises(ComputeJobFailedError):
        await port.await_terminal_state(job_id)


@pytest.mark.unit
async def test_await_raises_timeout_when_the_ceiling_elapses_before_terminal() -> None:
    client = _FakeClient(statuses=[RemoteTaskStatus(terminal=False, succeeded=False)])
    port = GlobusComputePort(
        client=client,
        endpoint_id=_ENDPOINT,
        artifact_probe=_FakeProbe(),
        default_timeout_s=0.0,
        poll_interval_s=0.0,
    )
    job_id = await port.submit(_JOB)
    with pytest.raises(ComputeTimeoutError):
        await port.await_terminal_state(job_id)


@pytest.mark.unit
async def test_fetch_artifact_ref_delegates_to_the_remote_probe() -> None:
    client = _FakeClient()
    probe = _FakeProbe()
    port = _port(client, probe)
    job_id = await port.submit(_JOB)
    artifact = await port.fetch_artifact_ref(job_id)
    assert artifact == _ARTIFACT
    assert probe.stat_calls == ["globus://eagle/recon/scan_001_rec/"]


@pytest.mark.unit
async def test_fetch_artifact_ref_raises_when_no_output_uri_declared() -> None:
    client = _FakeClient()
    port = _port(client)
    job_id = await port.submit(JobSpec(command=("noop",)))
    with pytest.raises(ArtifactNotFoundError):
        await port.fetch_artifact_ref(job_id)


@pytest.mark.unit
async def test_fetch_measurements_raises_not_found_value_arm_unimplemented() -> None:
    client = _FakeClient()
    port = _port(client)
    job_id = await port.submit(_JOB)
    with pytest.raises(MeasurementNotFoundError):
        await port.fetch_measurements(job_id)


@pytest.mark.unit
async def test_submit_rejection_maps_to_compute_submit_rejected() -> None:
    client = _FakeClient(submit_error=ValueError("bad resource request"))
    port = _port(client)
    with pytest.raises(ComputeSubmitRejectedError):
        await port.submit(_JOB)


@pytest.mark.unit
async def test_submit_connection_failure_maps_to_not_available() -> None:
    client = _FakeClient(submit_error=OSError("endpoint unreachable"))
    port = _port(client)
    with pytest.raises(ComputeNotAvailableError):
        await port.submit(_JOB)


@pytest.mark.unit
async def test_provide_result_stamps_physical_actuation() -> None:
    client = _FakeClient()
    port = _port(client)
    job_id = await port.submit(_JOB)
    result = port.provide_result(job_id, ComputeStatus.SUCCEEDED, artifacts=(_ARTIFACT,))
    assert result.is_simulated is False
    assert result.artifacts == (_ARTIFACT,)


@pytest.mark.unit
def test_adapter_satisfies_the_compute_port_protocol() -> None:
    port = _port(_FakeClient())
    assert isinstance(port, ComputePort)


@pytest.mark.unit
async def test_aclose_is_a_noop() -> None:
    port = _port(_FakeClient())
    await port.aclose()


@pytest.mark.unit
def test_build_compute_port_in_memory_default() -> None:
    assert isinstance(build_compute_port(), InMemoryComputePort)


@pytest.mark.unit
def test_build_compute_port_local_process() -> None:
    port = build_compute_port(ComputePortConfig(substrate="local_process"))
    assert isinstance(port, LocalProcessComputePort)


@pytest.mark.unit
def test_build_compute_port_globus_returns_the_prebuilt_instance() -> None:
    prebuilt = _port(_FakeClient())
    port = build_compute_port(ComputePortConfig(substrate="globus"), prebuilt_port=prebuilt)
    assert port is prebuilt


@pytest.mark.unit
def test_build_compute_port_globus_without_prebuilt_is_a_wiring_error() -> None:
    with pytest.raises(ValueError, match="globus"):
        build_compute_port(ComputePortConfig(substrate="globus"))
