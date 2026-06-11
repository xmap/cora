"""Contract tests for the `relocate_asset` MCP tool.

Mirrors `test_decommission_asset_mcp_tool.py`. Covers tool listing,
the happy path, and one each of the disqualifying-condition errors
to keep coverage representative without re-running the full guard
matrix at the MCP surface (decider tests own that).
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _register_asset_via_tool(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str = "APS-2BM",
    tier: str = "Unit",
    root: bool = False,
) -> UUID:
    arguments: dict[str, str | None] = {"name": name, "tier": tier}
    if root:
        arguments["parent_id"] = None
        arguments["facility_code"] = "cora"
    else:
        arguments["parent_id"] = str(uuid4())
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "register_asset",
                "arguments": arguments,
            },
        },
        headers=headers,
    )
    body = parse_sse_data(response.text)
    return UUID(body["result"]["structuredContent"]["asset_id"])


@pytest.mark.contract
def test_mcp_lists_relocate_asset_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "relocate_asset" in tool_names


@pytest.mark.contract
def test_mcp_relocate_asset_tool_succeeds_on_happy_path() -> None:
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
                    "name": "relocate_asset",
                    "arguments": {
                        "asset_id": str(asset_id),
                        "to_parent_id": str(uuid4()),
                        "reason": "site reorganization",
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_relocate_asset_tool_returns_iserror_for_unknown_asset() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "relocate_asset",
                    "arguments": {
                        "asset_id": str(uuid4()),
                        "to_parent_id": str(uuid4()),
                        "reason": "moved",
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()


@pytest.mark.contract
def test_mcp_relocate_asset_tool_returns_iserror_for_root() -> None:
    """A root Asset is facility-anchored; cannot relocate."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        asset_id = _register_asset_via_tool(client, headers, name="ANL", root=True)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "relocate_asset",
                    "arguments": {
                        "asset_id": str(asset_id),
                        "to_parent_id": str(uuid4()),
                        "reason": "moved",
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "Root" in body["result"]["content"][0]["text"]


@pytest.mark.contract
def test_mcp_relocate_asset_tool_returns_iserror_for_self_loop() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        asset_id = _register_asset_via_tool(client, headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {
                    "name": "relocate_asset",
                    "arguments": {
                        "asset_id": str(asset_id),
                        "to_parent_id": str(asset_id),
                        "reason": "moved",
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "self-loop" in body["result"]["content"][0]["text"]
