"""Contract tests for the `update_asset_settings` MCP tool.

Full bootstrap is done via other MCP tools (define_family,
update_family_settings_schema, register_asset,
add_asset_family) so the entire write path is exercised over
JSON-RPC, not Python imports.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data

_DRAFT = "https://json-schema.org/draft/2020-12/schema"
_SCHEMA = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {
        "energy": {"type": "number", "minimum": 5, "unit": {"system": "udunits", "code": "keV"}},
        "filter": {"type": "string"},
    },
}


def _call_tool(
    client: TestClient,
    headers: dict[str, str],
    *,
    call_id: int,
    name: str,
    arguments: dict[str, object],
) -> dict[str, object]:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": call_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
        headers=headers,
    )
    return parse_sse_data(response.text)


def _setup_asset_with_schemaful_capability(client: TestClient, headers: dict[str, str]) -> UUID:
    """Define Family + set schema + register Asset + assign Cap. Returns asset_id."""
    cap_body = _call_tool(
        client,
        headers,
        call_id=10,
        name="define_family",
        arguments={"name": "Tomography", "affordances": []},
    )
    cap_id = UUID(cap_body["result"]["structuredContent"]["family_id"])  # type: ignore[index]

    schema_body = _call_tool(
        client,
        headers,
        call_id=11,
        name="update_family_settings_schema",
        arguments={"family_id": str(cap_id), "settings_schema": _SCHEMA},
    )
    assert schema_body["result"]["isError"] is False  # type: ignore[index]

    asset_body = _call_tool(
        client,
        headers,
        call_id=12,
        name="register_asset",
        arguments={"name": "ANL", "tier": "Unit", "parent_id": None, "facility_code": "cora"},
    )
    asset_id = UUID(asset_body["result"]["structuredContent"]["asset_id"])  # type: ignore[index]

    add_body = _call_tool(
        client,
        headers,
        call_id=13,
        name="add_asset_family",
        arguments={"asset_id": str(asset_id), "family_id": str(cap_id)},
    )
    assert add_body["result"]["isError"] is False  # type: ignore[index]

    return asset_id


@pytest.mark.contract
def test_mcp_lists_update_asset_settings_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "update_asset_settings" in tool_names


@pytest.mark.contract
def test_mcp_update_asset_settings_tool_succeeds_on_happy_path() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        asset_id = _setup_asset_with_schemaful_capability(client, headers)
        body = _call_tool(
            client,
            headers,
            call_id=20,
            name="update_asset_settings",
            arguments={
                "asset_id": str(asset_id),
                "settings_patch": {"energy": 30, "filter": "Cu"},
            },
        )
    assert body["result"]["isError"] is False  # type: ignore[index]


@pytest.mark.contract
def test_mcp_update_asset_settings_tool_returns_iserror_for_unknown_asset() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        body = _call_tool(
            client,
            headers,
            call_id=21,
            name="update_asset_settings",
            arguments={
                "asset_id": str(uuid4()),
                "settings_patch": {"energy": 30},
            },
        )
    assert body["result"]["isError"] is True  # type: ignore[index]
    assert "not found" in body["result"]["content"][0]["text"].lower()  # type: ignore[index]


@pytest.mark.contract
def test_mcp_update_asset_settings_tool_returns_iserror_on_schema_violation() -> None:
    """Schema requires energy >= 5; pass 1 -> InvalidAssetSettingsError."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        asset_id = _setup_asset_with_schemaful_capability(client, headers)
        body = _call_tool(
            client,
            headers,
            call_id=22,
            name="update_asset_settings",
            arguments={
                "asset_id": str(asset_id),
                "settings_patch": {"energy": 1},
            },
        )
    assert body["result"]["isError"] is True  # type: ignore[index]
