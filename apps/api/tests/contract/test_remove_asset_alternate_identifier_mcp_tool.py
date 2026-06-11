"""Contract tests for the `remove_asset_alternate_identifier` MCP tool."""

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


def _add_identifier_via_tool(
    client: TestClient,
    headers: dict[str, str],
    asset_id: UUID,
    *,
    kind: str = "SerialNumber",
    value: str = "XYZ-001",
) -> None:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "add_asset_alternate_identifier",
                "arguments": {
                    "asset_id": str(asset_id),
                    "identifier": {"kind": kind, "value": value},
                },
            },
        },
        headers=headers,
    )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_lists_remove_asset_alternate_identifier_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "remove_asset_alternate_identifier" in tool_names


@pytest.mark.contract
def test_mcp_remove_asset_alternate_identifier_succeeds_on_happy_path() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        asset_id = _register_asset_via_tool(client, headers)
        _add_identifier_via_tool(client, headers, asset_id)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "remove_asset_alternate_identifier",
                    "arguments": {
                        "asset_id": str(asset_id),
                        "identifier": {"kind": "SerialNumber", "value": "XYZ-001"},
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_remove_asset_alternate_identifier_returns_iserror_for_missing_pair() -> None:
    """Strict-not-idempotent: removing without a prior add surfaces as isError=true."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        asset_id = _register_asset_via_tool(client, headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "remove_asset_alternate_identifier",
                    "arguments": {
                        "asset_id": str(asset_id),
                        "identifier": {"kind": "SerialNumber", "value": "missing"},
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_remove_asset_alternate_identifier_returns_iserror_when_decommissioned() -> None:
    """Lifecycle guard mirrors `remove_asset_port`: a Decommissioned
    asset rejects identifier changes; surfaces as isError=true."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        asset_id = _register_asset_via_tool(client, headers)
        _add_identifier_via_tool(client, headers, asset_id)
        decom = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "decommission_asset",
                    "arguments": {"asset_id": str(asset_id)},
                },
            },
            headers=headers,
        )
        assert parse_sse_data(decom.text)["result"]["isError"] is False
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {
                    "name": "remove_asset_alternate_identifier",
                    "arguments": {
                        "asset_id": str(asset_id),
                        "identifier": {"kind": "SerialNumber", "value": "XYZ-001"},
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "Decommissioned" in body["result"]["content"][0]["text"]
