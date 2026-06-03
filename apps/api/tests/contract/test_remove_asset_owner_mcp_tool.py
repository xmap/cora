"""Contract tests for the `remove_asset_owner` MCP tool."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _register_asset_with_owner_via_tool(
    client: TestClient,
    headers: dict[str, str],
    owner_name: str = "HZB",
) -> UUID:
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
                    "level": "Device",
                    "parent_id": str(uuid4()),
                    "owners": [{"name": owner_name}],
                },
            },
        },
        headers=headers,
    )
    body = parse_sse_data(response.text)
    return UUID(body["result"]["structuredContent"]["asset_id"])


@pytest.mark.contract
def test_mcp_lists_remove_asset_owner_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "remove_asset_owner" in tool_names


@pytest.mark.contract
def test_mcp_remove_asset_owner_tool_schema_advertises_owner_name() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tools = {t["name"]: t for t in body["result"]["tools"]}
    schema = tools["remove_asset_owner"]["inputSchema"]
    properties = schema.get("properties", {})
    assert "asset_id" in properties
    assert "owner_name" in properties


@pytest.mark.contract
def test_mcp_remove_asset_owner_succeeds_on_happy_path() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        asset_id = _register_asset_with_owner_via_tool(client, headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "remove_asset_owner",
                    "arguments": {
                        "asset_id": str(asset_id),
                        "owner_name": "HZB",
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_remove_asset_owner_returns_iserror_for_unknown_owner() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        asset_id = _register_asset_with_owner_via_tool(client, headers, owner_name="APS")
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "remove_asset_owner",
                    "arguments": {
                        "asset_id": str(asset_id),
                        "owner_name": "HZB",
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
