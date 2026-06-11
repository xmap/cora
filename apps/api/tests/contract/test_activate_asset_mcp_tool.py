"""Contract tests for the `activate_asset` MCP tool.

Mirrors `test_mount_subject_mcp_tool.py`. Shared MCP helpers live
in `tests/contract/_mcp_helpers.py`.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _register_asset_via_tool(client: TestClient, headers: dict[str, str]) -> UUID:
    """Helper: register a Unit-level asset via MCP tool and return its id."""
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
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    return UUID(body["result"]["structuredContent"]["asset_id"])


@pytest.mark.contract
def test_mcp_lists_activate_asset_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "activate_asset" in tool_names


@pytest.mark.contract
def test_mcp_activate_asset_tool_succeeds_for_commissioned_asset() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        asset_id = _register_asset_via_tool(client, headers)
        response = client.post(
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
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_activate_asset_tool_returns_iserror_for_unknown_asset() -> None:
    """AssetNotFoundError propagates -> FastMCP wraps as isError."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "activate_asset",
                    "arguments": {"asset_id": str(uuid4())},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()


@pytest.mark.contract
def test_mcp_activate_asset_tool_returns_iserror_when_already_active() -> None:
    """AssetCannotActivateError on Active asset -> isError. Same shape
    as the REST 409 response."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        asset_id = _register_asset_via_tool(client, headers)

        first = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "activate_asset",
                    "arguments": {"asset_id": str(asset_id)},
                },
            },
            headers=headers,
        )
        assert parse_sse_data(first.text)["result"]["isError"] is False

        second = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "activate_asset",
                    "arguments": {"asset_id": str(asset_id)},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(second.text)
    assert body["result"]["isError"] is True
    text = body["result"]["content"][0]["text"]
    assert "Active" in text
    assert "Commissioned" in text
