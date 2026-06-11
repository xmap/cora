"""Contract tests for the `bind_asset_to_facility` MCP tool (Slice 8C)."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data

_FACILITY_CODE = "cora"


def _register_asset_via_tool(
    client: TestClient,
    headers: dict[str, str],
) -> UUID:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "register_asset",
                "arguments": {
                    "name": "Beamline 2-BM",
                    "tier": "Unit",
                    "parent_id": str(uuid4()),
                },
            },
        },
        headers=headers,
    )
    assert response.status_code == 200
    return UUID(parse_sse_data(response.text)["result"]["structuredContent"]["asset_id"])


@pytest.mark.contract
def test_mcp_bind_asset_to_facility_tool_succeeds_on_happy_path() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        asset_id = _register_asset_via_tool(client, headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "bind_asset_to_facility",
                    "arguments": {
                        "asset_id": str(asset_id),
                        "facility_code": _FACILITY_CODE,
                    },
                },
            },
            headers=headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_bind_asset_to_facility_tool_rejects_missing_argument() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "bind_asset_to_facility",
                    "arguments": {"asset_id": str(uuid4())},
                },
            },
            headers=headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_bind_asset_to_facility_tool_rejects_malformed_facility_code() -> None:
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
                    "name": "bind_asset_to_facility",
                    "arguments": {
                        "asset_id": str(asset_id),
                        "facility_code": "INVALID UPPER",
                    },
                },
            },
            headers=headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
