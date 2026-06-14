"""Contract tests for the `get_fixture` MCP tool."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _define_family(client: TestClient, headers: dict[str, str]) -> UUID:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "define_family",
                "arguments": {"name": "Camera", "affordances": []},
            },
        },
        headers=headers,
    )
    return UUID(parse_sse_data(response.text)["result"]["structuredContent"]["family_id"])


def _register_asset(client: TestClient, headers: dict[str, str], family_id: UUID) -> UUID:
    create = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "register_asset",
                "arguments": {
                    "name": "Cam-1",
                    "tier": "Device",
                    "parent_id": str(uuid4()),
                },
            },
        },
        headers=headers,
    )
    asset_id = UUID(parse_sse_data(create.text)["result"]["structuredContent"]["asset_id"])
    client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "add_asset_family",
                "arguments": {
                    "asset_id": str(asset_id),
                    "family_id": str(family_id),
                },
            },
        },
        headers=headers,
    )
    return asset_id


def _define_assembly(client: TestClient, headers: dict[str, str], family_id: UUID) -> UUID:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "define_assembly",
                "arguments": {
                    "name": "Microscope",
                    "presents_as_family_id": str(family_id),
                    "required_slots": [
                        {
                            "slot_name": "camera",
                            "required_family_ids": [str(family_id)],
                            "cardinality": "Exactly1",
                        }
                    ],
                    "required_wires": [],
                },
            },
        },
        headers=headers,
    )
    return UUID(parse_sse_data(response.text)["result"]["structuredContent"]["assembly_id"])


def _register_fixture(
    client: TestClient, headers: dict[str, str], assembly_id: UUID, asset_id: UUID
) -> UUID:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "register_fixture",
                "arguments": {
                    "assembly_id": str(assembly_id),
                    "slot_asset_bindings": [
                        {"slot_name": "camera", "asset_id": str(asset_id)},
                    ],
                    "parameter_overrides": {},
                },
            },
        },
        headers=headers,
    )
    return UUID(parse_sse_data(response.text)["result"]["structuredContent"]["fixture_id"])


@pytest.mark.contract
def test_mcp_lists_get_fixture_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    tool_names = [t["name"] for t in parse_sse_data(response.text)["result"]["tools"]]
    assert "get_fixture" in tool_names


@pytest.mark.contract
def test_mcp_get_fixture_returns_full_state_on_hit() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        family_id = _define_family(client, headers)
        asset_id = _register_asset(client, headers, family_id)
        assembly_id = _define_assembly(client, headers, family_id)
        fixture_id = _register_fixture(client, headers, assembly_id, asset_id)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "get_fixture",
                    "arguments": {"fixture_id": str(fixture_id)},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False
    out = body["result"]["structuredContent"]
    assert out["id"] == str(fixture_id)
    assert out["assembly_id"] == str(assembly_id)
    assert out["slot_asset_bindings"] == [
        {"slot_name": "camera", "asset_id": str(asset_id)},
    ]


@pytest.mark.contract
def test_mcp_get_fixture_returns_iserror_for_unknown_fixture() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {
                    "name": "get_fixture",
                    "arguments": {"fixture_id": str(uuid4())},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()
