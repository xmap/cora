"""Unit tests for `GlobusTransferPort` against a fake Globus `TransferClient`.

These exercise the adapter's translation both ways: a `TransferRequest` into a
Globus `TransferData` submission, and a Globus task response back into a
`TransferProgress`. The Globus client is faked, so nothing here touches a live
endpoint; live behaviour is unverified until a credentialed sanity run.
"""

from typing import Any

import pytest
import requests
from globus_sdk import MISSING, NetworkError, TransferAPIError, TransferData
from requests.structures import CaseInsensitiveDict

from cora.operation.adapters.globus_transfer_port import GlobusTransferPort
from cora.operation.ports.transfer_port import (
    TransferAccessDeniedError,
    TransferEndpointUnreachableError,
    TransferHandle,
    TransferPort,
    TransferRejectedError,
    TransferRequest,
    TransferState,
)

_SOURCE = "src-endpoint:/data/dm/2BM/exp123/"
_DESTINATION = "dst-endpoint:/archive/2BM/exp123/"
_RAW_SYNC = TransferRequest(source=_SOURCE, destination=_DESTINATION, recursive=True)


class _FakeResponse:
    """Dict-backed stand-in for a Globus HTTP response (read shape only)."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)


class _FakeTransferClient:
    """Records what the adapter submits; replays seeded task responses / errors."""

    def __init__(
        self,
        *,
        task_id: str = "globus-task-1",
        get_responses: list[dict[str, Any]] | None = None,
        submit_error: Exception | None = None,
    ) -> None:
        self.submitted: list[TransferData] = []
        self.cancelled: list[str] = []
        self._task_id = task_id
        self._get_responses = list(get_responses or [])
        self._submit_error = submit_error

    def submit_transfer(self, data: TransferData) -> _FakeResponse:
        if self._submit_error is not None:
            raise self._submit_error
        self.submitted.append(data)
        return _FakeResponse({"task_id": self._task_id})

    def get_task(self, task_id: str) -> _FakeResponse:
        if self._get_responses:
            return _FakeResponse(self._get_responses.pop(0))
        return _FakeResponse({"status": "SUCCEEDED"})

    def cancel_task(self, task_id: str) -> _FakeResponse:
        self.cancelled.append(task_id)
        return _FakeResponse({"code": "Canceled"})


def _api_error(status: int, *, code: str = "Error", message: str = "boom") -> TransferAPIError:
    """Build a real `TransferAPIError` carrying `status` for the mapping tests."""
    response = requests.Response()
    response.status_code = status
    prepared = requests.PreparedRequest()
    prepared.method = "POST"
    prepared.url = "https://transfer.api.globus.org/v0.10/transfer"
    prepared.headers = CaseInsensitiveDict()
    response.request = prepared
    response._content = f'{{"code":"{code}","message":"{message}"}}'.encode()
    response.headers["Content-Type"] = "application/json"
    return TransferAPIError(response)


@pytest.mark.unit
async def test_begin_returns_handle_from_the_task_id() -> None:
    client = _FakeTransferClient(task_id="task-abc")
    port = GlobusTransferPort(client)
    handle = await port.begin(_RAW_SYNC)
    assert handle == "task-abc"


@pytest.mark.unit
async def test_begin_builds_recursive_transferdata_with_endpoints_and_paths() -> None:
    client = _FakeTransferClient()
    port = GlobusTransferPort(client)
    await port.begin(_RAW_SYNC)

    data = client.submitted[0]
    assert data.get("source_endpoint") == "src-endpoint"
    assert data.get("destination_endpoint") == "dst-endpoint"
    item = data["DATA"][0]
    assert item.get("source_path") == "/data/dm/2BM/exp123/"
    assert item.get("destination_path") == "/archive/2BM/exp123/"
    assert item.get("recursive") is True


@pytest.mark.unit
async def test_begin_skip_unchanged_sets_a_checksum_sync_level_and_verify() -> None:
    client = _FakeTransferClient()
    port = GlobusTransferPort(client)
    await port.begin(
        TransferRequest(
            source=_SOURCE,
            destination=_DESTINATION,
            recursive=True,
            skip_unchanged=True,
            verify_on_arrival=True,
        )
    )
    data = client.submitted[0]
    # "checksum" is sync level 3 in the Globus wire form.
    assert data.get("sync_level") == 3
    assert data.get("verify_checksum") is True


@pytest.mark.unit
async def test_begin_without_skip_unchanged_leaves_sync_level_unset() -> None:
    client = _FakeTransferClient()
    port = GlobusTransferPort(client)
    await port.begin(_RAW_SYNC)
    # globus-sdk v4 leaves an unset payload field as MISSING (stripped before
    # the wire) rather than None.
    assert client.submitted[0].get("sync_level") is MISSING


@pytest.mark.unit
async def test_begin_passes_idempotency_key_as_submission_id() -> None:
    client = _FakeTransferClient()
    port = GlobusTransferPort(client)
    await port.begin(
        TransferRequest(source=_SOURCE, destination=_DESTINATION, idempotency_key="sub-42")
    )
    assert client.submitted[0].get("submission_id") == "sub-42"


@pytest.mark.unit
async def test_malformed_location_is_rejected_before_any_submit() -> None:
    client = _FakeTransferClient()
    port = GlobusTransferPort(client)
    with pytest.raises(TransferRejectedError):
        await port.begin(TransferRequest(source="no-colon-here", destination=_DESTINATION))
    assert client.submitted == []


@pytest.mark.unit
@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("ACTIVE", TransferState.ACTIVE),
        ("INACTIVE", TransferState.SUSPENDED),
        ("SUCCEEDED", TransferState.SUCCEEDED),
        ("FAILED", TransferState.FAILED),
    ],
)
async def test_observe_maps_globus_status_to_transfer_state(
    status: str, expected: TransferState
) -> None:
    client = _FakeTransferClient(get_responses=[{"status": status}])
    port = GlobusTransferPort(client)
    progress = await port.observe(TransferHandle("globus-task-1"))
    assert progress.state is expected


@pytest.mark.unit
async def test_observe_maps_progress_counts_from_the_task_document() -> None:
    client = _FakeTransferClient(
        get_responses=[
            {
                "status": "ACTIVE",
                "bytes_transferred": 8_000,
                "files": 400,
                "files_transferred": 120,
                "files_skipped": 8,
                "subtasks_failed": 0,
            }
        ]
    )
    port = GlobusTransferPort(client)
    progress = await port.observe(TransferHandle("globus-task-1"))
    assert progress.bytes_moved == 8_000
    assert progress.files_total == 400
    assert progress.files_moved == 120
    assert progress.files_skipped == 8


@pytest.mark.unit
async def test_observe_partial_failed_task_carries_the_failed_count() -> None:
    client = _FakeTransferClient(
        get_responses=[
            {
                "status": "FAILED",
                "files": 400,
                "files_transferred": 397,
                "subtasks_failed": 3,
                "fatal_error": {"code": "PERMISSION_DENIED", "description": "3 files unreadable"},
            }
        ]
    )
    port = GlobusTransferPort(client)
    progress = await port.observe(TransferHandle("globus-task-1"))
    assert progress.state is TransferState.FAILED
    assert progress.is_partial is True
    assert progress.files_failed == 3
    assert progress.detail == "3 files unreadable"


@pytest.mark.unit
async def test_observe_suspended_task_surfaces_the_credential_detail() -> None:
    client = _FakeTransferClient(
        get_responses=[{"status": "INACTIVE", "nice_status": "EXPIRED_CREDENTIALS"}]
    )
    port = GlobusTransferPort(client)
    progress = await port.observe(TransferHandle("globus-task-1"))
    assert progress.state is TransferState.SUSPENDED
    assert progress.detail == "EXPIRED_CREDENTIALS"


@pytest.mark.unit
async def test_cancel_calls_globus_cancel_task_with_the_handle() -> None:
    client = _FakeTransferClient()
    port = GlobusTransferPort(client)
    await port.cancel(TransferHandle("globus-task-9"))
    assert client.cancelled == ["globus-task-9"]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, TransferAccessDeniedError),
        (403, TransferAccessDeniedError),
        (500, TransferEndpointUnreachableError),
        (503, TransferEndpointUnreachableError),
        (400, TransferRejectedError),
        (404, TransferRejectedError),
        (429, TransferRejectedError),
    ],
)
async def test_globus_api_status_maps_to_the_right_transfer_error(
    status: int, expected: type[Exception]
) -> None:
    client = _FakeTransferClient(submit_error=_api_error(status))
    port = GlobusTransferPort(client)
    with pytest.raises(expected):
        await port.begin(_RAW_SYNC)


@pytest.mark.unit
async def test_network_error_maps_to_endpoint_unreachable() -> None:
    client = _FakeTransferClient(
        submit_error=NetworkError("connection refused", requests.ConnectionError("down"))
    )
    port = GlobusTransferPort(client)
    with pytest.raises(TransferEndpointUnreachableError):
        await port.begin(_RAW_SYNC)


@pytest.mark.unit
def test_adapter_satisfies_the_transfer_port_protocol() -> None:
    port = GlobusTransferPort(_FakeTransferClient())
    assert isinstance(port, TransferPort)


@pytest.mark.unit
async def test_aclose_is_a_noop() -> None:
    port = GlobusTransferPort(_FakeTransferClient())
    await port.aclose()
