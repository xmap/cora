"""Contract tests for the `enter_asset_maintenance` MCP tool.

Mirrors `test_activate_asset_mcp_tool.py`.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _register_and_activate_via_tool(client: TestClient, headers: dict[str, str]) -> UUID:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "register_asset",
                "arguments": {
                    "name": "APS-2BM",
                    "tier": "Unit",
                    "parent_id": str(uuid4()),
                },
            },
        },
        headers=headers,
    )
    body = parse_sse_data(response.text)
    asset_id = UUID(body["result"]["structuredContent"]["asset_id"])
    activate = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "activate_asset",
                "arguments": {"asset_id": str(asset_id)},
            },
        },
        headers=headers,
    )
    assert parse_sse_data(activate.text)["result"]["isError"] is False
    return asset_id


@pytest.mark.contract
def test_mcp_lists_enter_asset_maintenance_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "enter_asset_maintenance" in tool_names


@pytest.mark.contract
def test_mcp_enter_asset_maintenance_tool_succeeds_from_active() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        asset_id = _register_and_activate_via_tool(client, headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "enter_asset_maintenance",
                    "arguments": {"asset_id": str(asset_id)},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_enter_asset_maintenance_tool_returns_iserror_for_unknown_asset() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "enter_asset_maintenance",
                    "arguments": {"asset_id": str(uuid4())},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()


@pytest.mark.contract
def test_mcp_enter_asset_maintenance_tool_returns_iserror_when_commissioned() -> None:
    """Pre-service Commissioned assets cannot enter maintenance."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        register = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "register_asset",
                    "arguments": {
                        "name": "APS-2BM",
                        "tier": "Unit",
                        "parent_id": str(uuid4()),
                    },
                },
            },
            headers=headers,
        )
        asset_id = UUID(parse_sse_data(register.text)["result"]["structuredContent"]["asset_id"])
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {
                    "name": "enter_asset_maintenance",
                    "arguments": {"asset_id": str(asset_id)},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "Commissioned" in body["result"]["content"][0]["text"]
