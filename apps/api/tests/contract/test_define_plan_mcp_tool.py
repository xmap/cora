"""Contract tests for the `define_plan` MCP tool."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._helpers import create_capability_via_api
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _setup_chain_via_rest(client: TestClient) -> tuple[str, str]:
    _cap_id = create_capability_via_api(client)
    """Seed Method+Practice+Asset (with capability) via REST so the
    MCP define_plan call has valid upstream to bind."""
    cap_id = client.post("/families", json={"name": "FlyMotion", "affordances": []}).json()[
        "family_id"
    ]
    method_id = client.post(
        "/methods",
        json={"name": "Test Method", "capability_id": _cap_id, "needed_family_ids": [cap_id]},
    ).json()["method_id"]
    practice_id = client.post(
        "/practices",
        json={"name": "Test Practice", "method_id": method_id, "site_id": str(uuid4())},
    ).json()["practice_id"]
    asset_id = client.post(
        "/assets",
        json={"name": "TestAsset", "tier": "Unit", "parent_id": None, "facility_code": "cora"},
    ).json()["asset_id"]
    client.post(f"/assets/{asset_id}/add-family", json={"family_id": cap_id})
    return practice_id, asset_id


@pytest.mark.contract
def test_mcp_lists_define_plan_tool() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "define_plan" in tool_names


@pytest.mark.contract
def test_mcp_define_plan_tool_returns_structured_plan_id() -> None:
    with TestClient(create_app()) as client:
        practice_id, asset_id = _setup_chain_via_rest(client)
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "define_plan",
                    "arguments": {
                        "name": "32-ID FlyScan Plan",
                        "practice_id": practice_id,
                        "asset_ids": [asset_id],
                    },
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    assert "plan_id" in result["structuredContent"]
    UUID(result["structuredContent"]["plan_id"])


@pytest.mark.contract
def test_mcp_define_plan_tool_returns_iserror_for_missing_practice() -> None:
    """Cross-aggregate pre-load fails: PracticeNotFoundError →
    isError: true with diagnostic text."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "define_plan",
                    "arguments": {
                        "name": "X",
                        "practice_id": str(uuid4()),
                        "asset_ids": [str(uuid4())],
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is True
    assert "not found" in result["content"][0]["text"].lower()


@pytest.mark.contract
def test_mcp_define_plan_tool_rejects_missing_arguments() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "define_plan",
                    "arguments": {"name": "X"},  # missing practice_id + asset_ids
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_define_plan_tool_rejects_empty_asset_ids() -> None:
    """min_length=1 on asset_ids enforced at the MCP boundary."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "define_plan",
                    "arguments": {
                        "name": "X",
                        "practice_id": str(uuid4()),
                        "asset_ids": [],
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
