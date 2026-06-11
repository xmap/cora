"""Contract tests for the `get_asset` MCP tool.

Mirrors `test_get_family_mcp_tool.py` / `test_get_subject_mcp_tool.py`.
Pinned structured output shape: `{id, name, tier, parent_id, lifecycle}`.
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
    parent_id: str | None = None,
    root: bool = False,
) -> UUID:
    arguments: dict[str, str | None] = {"name": name, "tier": tier}
    if root:
        arguments["parent_id"] = None
        arguments["facility_code"] = "cora"
    else:
        arguments["parent_id"] = parent_id if parent_id is not None else str(uuid4())
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
def test_mcp_lists_get_asset_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "get_asset" in tool_names


@pytest.mark.contract
def test_mcp_get_asset_tool_returns_structured_asset_for_known_id() -> None:
    parent_id = str(uuid4())
    with TestClient(create_app()) as client:
        headers = open_session(client)
        asset_id = _register_asset_via_tool(client, headers, parent_id=parent_id)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "get_asset",
                    "arguments": {"asset_id": str(asset_id)},
                },
            },
            headers=headers,
        )

    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    structured = result["structuredContent"]
    assert structured["id"] == str(asset_id)
    assert structured["name"] == "APS-2BM"
    assert structured["tier"] == "Unit"
    assert structured["parent_id"] == parent_id
    assert structured["lifecycle"] == "Commissioned"
    # Empty until add_asset_family runs (5f-1).
    assert structured["family_ids"] == []


@pytest.mark.contract
def test_mcp_get_asset_tool_returns_null_parent_for_facility_rooted_root() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        asset_id = _register_asset_via_tool(client, headers, name="ANL", tier="Unit", root=True)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "get_asset",
                    "arguments": {"asset_id": str(asset_id)},
                },
            },
            headers=headers,
        )

    body = parse_sse_data(response.text)
    structured = body["result"]["structuredContent"]
    assert structured["parent_id"] is None
    assert structured["tier"] == "Unit"


@pytest.mark.contract
def test_mcp_get_asset_tool_returns_iserror_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "get_asset",
                    "arguments": {"asset_id": str(uuid4())},
                },
            },
            headers=headers,
        )

    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()
