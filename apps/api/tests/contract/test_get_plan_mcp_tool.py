"""Contract tests for the `get_plan` MCP tool."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._helpers import create_capability_via_api
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _setup_full_plan(client: TestClient) -> tuple[str, str, str]:
    _cap_id = create_capability_via_api(client)
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
    plan_id = client.post(
        "/plans",
        json={"name": "32-ID FlyScan", "practice_id": practice_id, "asset_ids": [asset_id]},
    ).json()["plan_id"]
    return plan_id, practice_id, asset_id


@pytest.mark.contract
def test_mcp_lists_get_plan_tool() -> None:
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
    assert "get_plan" in tool_names


@pytest.mark.contract
def test_mcp_get_plan_tool_returns_structured_plan_for_known_id() -> None:
    with TestClient(create_app()) as client:
        plan_id, practice_id, asset_id = _setup_full_plan(client)
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "get_plan",
                    "arguments": {"plan_id": plan_id},
                },
            },
            headers=session_headers,
        )

    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    structured = result["structuredContent"]
    assert structured["id"] == plan_id
    assert structured["name"] == "32-ID FlyScan"
    assert structured["practice_id"] == practice_id
    assert structured["asset_ids"] == [asset_id]
    assert structured["status"] == "Defined"
    # Null until version_plan runs (6e-2).
    assert structured["version"] is None


@pytest.mark.contract
def test_mcp_get_plan_tool_returns_iserror_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "get_plan",
                    "arguments": {"plan_id": str(uuid4())},
                },
            },
            headers=session_headers,
        )

    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()
