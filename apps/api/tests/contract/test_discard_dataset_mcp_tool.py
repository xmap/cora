"""Contract tests for the `discard_dataset` MCP tool."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.data.aggregates.dataset import DATASET_CHECKSUM_SHA256_HEX_LENGTH
from tests.contract._mcp_helpers import open_session, parse_sse_data

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH


def _register(client: TestClient) -> str:
    return client.post(
        "/datasets",
        json={
            "name": "D",
            "uri": "s3://b/k",
            "checksum": {"algorithm": "sha256", "value": _GOOD_SHA256},
            "byte_size": 0,
            "encoding": {"media_type": "application/x-hdf5", "conforms_to": []},
        },
    ).json()["dataset_id"]


@pytest.mark.contract
def test_mcp_lists_discard_dataset_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "discard_dataset" in tool_names


@pytest.mark.contract
def test_mcp_discard_dataset_tool_succeeds_on_happy_path() -> None:
    with TestClient(create_app()) as client:
        dataset_id = _register(client)
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "discard_dataset",
                    "arguments": {
                        "dataset_id": dataset_id,
                        "reason": "GDPR Article 17 erasure",
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_discard_dataset_tool_returns_iserror_for_unknown_dataset() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "discard_dataset",
                    "arguments": {"dataset_id": str(uuid4()), "reason": "X"},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()


@pytest.mark.contract
def test_mcp_discard_dataset_tool_returns_iserror_when_already_discarded() -> None:
    with TestClient(create_app()) as client:
        dataset_id = _register(client)
        first = client.post(f"/datasets/{dataset_id}/discard", json={"reason": "first"})
        assert first.status_code == 204
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "discard_dataset",
                    "arguments": {"dataset_id": dataset_id, "reason": "second"},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "Registered" in body["result"]["content"][0]["text"]
