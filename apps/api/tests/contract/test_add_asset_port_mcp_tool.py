"""Contract tests for the `add_asset_port` MCP tool."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _register_asset_via_tool(client: TestClient, headers: dict[str, str]) -> UUID:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "register_asset",
                "arguments": {
                    "name": "Detector-X",
                    "tier": "Device",
                    "parent_id": str(uuid4()),
                },
            },
        },
        headers=headers,
    )
    body = parse_sse_data(response.text)
    return UUID(body["result"]["structuredContent"]["asset_id"])


@pytest.mark.contract
def test_mcp_lists_add_asset_port_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "add_asset_port" in tool_names


@pytest.mark.contract
def test_mcp_add_asset_port_tool_succeeds_on_happy_path() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        asset_id = _register_asset_via_tool(client, headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "add_asset_port",
                    "arguments": {
                        "asset_id": str(asset_id),
                        "port_name": "trigger_in",
                        "direction": "Input",
                        "signal_type": "TTL",
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_add_asset_port_tool_returns_iserror_for_unknown_asset() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "add_asset_port",
                    "arguments": {
                        "asset_id": str(uuid4()),
                        "port_name": "x",
                        "direction": "Input",
                        "signal_type": "TTL",
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()
