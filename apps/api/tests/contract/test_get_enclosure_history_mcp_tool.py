"""Contract tests for the `get_enclosure_history` MCP tool."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _setup_enclosure(client: TestClient) -> str:
    return client.post(
        "/enclosures",
        json={"name": "2-BM-A", "facility_code": "cora"},
    ).json()["enclosure_id"]


@pytest.mark.contract
def test_mcp_lists_get_enclosure_history_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "get_enclosure_history" in tool_names


@pytest.mark.contract
def test_mcp_get_enclosure_history_tool_returns_structured_history_for_known_id() -> None:
    with TestClient(create_app()) as client:
        enclosure_id = _setup_enclosure(client)
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "get_enclosure_history",
                    "arguments": {"enclosure_id": enclosure_id},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    structured = result["structuredContent"]
    assert structured["enclosure_id"] == enclosure_id
    assert structured["name"] == "2-BM-A"
    assert structured["permit_status"] == "Unknown"
    assert structured["lifecycle"] == "Active"
    assert len(structured["events"]) == 1
    assert structured["events"][0]["event_type"] == "EnclosureRegistered"


@pytest.mark.contract
def test_mcp_get_enclosure_history_tool_returns_iserror_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "get_enclosure_history",
                    "arguments": {"enclosure_id": str(uuid4())},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()
