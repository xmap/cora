"""Contract tests for the `decommission_enclosure` MCP tool."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _register_enclosure_via_tool(client: TestClient, headers: dict[str, str]) -> UUID:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 100,
            "method": "tools/call",
            "params": {
                "name": "register_enclosure",
                "arguments": {
                    "name": "2-BM Hutch A",
                    "containing_asset_id": str(uuid4()),
                },
            },
        },
        headers=headers,
    )
    body = parse_sse_data(response.text)
    return UUID(body["result"]["structuredContent"]["enclosure_id"])


@pytest.mark.contract
def test_mcp_lists_decommission_enclosure_tool() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "decommission_enclosure" in tool_names


@pytest.mark.contract
def test_mcp_decommission_enclosure_tool_succeeds_from_active() -> None:
    """`decommission_enclosure` accepts any non-Decommissioned lifecycle; pin
    the Active case (no intervening transitions)."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        enclosure_id = _register_enclosure_via_tool(client, session_headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "decommission_enclosure",
                    "arguments": {
                        "enclosure_id": str(enclosure_id),
                        "reason": "end-of-life",
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["enclosure_id"] == str(enclosure_id)


@pytest.mark.contract
def test_mcp_decommission_enclosure_tool_is_strict_not_idempotent() -> None:
    """Re-decommission returns an MCP error (mapped from EnclosureCannotDecommissionError)."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        enclosure_id = _register_enclosure_via_tool(client, session_headers)
        first = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "decommission_enclosure",
                    "arguments": {"enclosure_id": str(enclosure_id), "reason": "first"},
                },
            },
            headers=session_headers,
        )
        assert parse_sse_data(first.text)["result"]["isError"] is False
        second = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "decommission_enclosure",
                    "arguments": {"enclosure_id": str(enclosure_id), "reason": "second"},
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(second.text)
    assert body["result"]["isError"] is True
