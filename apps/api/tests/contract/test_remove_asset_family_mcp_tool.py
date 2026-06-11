"""Contract tests for the `remove_asset_family` MCP tool."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _register_and_add_via_tools(
    client: TestClient,
    headers: dict[str, str],
    family_id: str,
) -> UUID:
    register = client.post(
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
    asset_id = UUID(parse_sse_data(register.text)["result"]["structuredContent"]["asset_id"])
    add = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "add_asset_family",
                "arguments": {
                    "asset_id": str(asset_id),
                    "family_id": family_id,
                },
            },
        },
        headers=headers,
    )
    assert parse_sse_data(add.text)["result"]["isError"] is False
    return asset_id


@pytest.mark.contract
def test_mcp_lists_remove_asset_family_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "remove_asset_family" in tool_names


@pytest.mark.contract
def test_mcp_remove_asset_family_tool_succeeds_on_happy_path() -> None:
    cap = str(uuid4())
    with TestClient(create_app()) as client:
        headers = open_session(client)
        asset_id = _register_and_add_via_tools(client, headers, cap)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "remove_asset_family",
                    "arguments": {
                        "asset_id": str(asset_id),
                        "family_id": cap,
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_remove_asset_family_tool_returns_iserror_for_unknown_asset() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "remove_asset_family",
                    "arguments": {
                        "asset_id": str(uuid4()),
                        "family_id": str(uuid4()),
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()


@pytest.mark.contract
def test_mcp_remove_asset_family_tool_returns_iserror_when_not_present() -> None:
    """Strict-not-idempotent at the MCP surface."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        register = client.post(
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
        asset_id = UUID(parse_sse_data(register.text)["result"]["structuredContent"]["asset_id"])
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "remove_asset_family",
                    "arguments": {
                        "asset_id": str(asset_id),
                        "family_id": str(uuid4()),
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "not in" in body["result"]["content"][0]["text"]
