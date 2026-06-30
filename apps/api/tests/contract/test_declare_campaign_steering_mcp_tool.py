"""Contract tests for the `declare_campaign_steering` MCP tool."""

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data

_OBJECTIVE: dict[str, Any] = {
    "kind": "Satisfy",
    "target_measurement_name": "rotation_center",
    "target_value": 0.0,
}
_SPACE: dict[str, Any] = {"axes": [{"name": "theta", "lower": -5.0, "upper": 5.0}]}


def _register(client: TestClient) -> str:
    response = client.post(
        "/campaigns",
        json={"name": "test", "intent": "Sweep", "lead_actor_id": str(uuid4())},
    )
    return str(response.json()["campaign_id"])


@pytest.mark.contract
def test_mcp_lists_declare_campaign_steering_tool() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "declare_campaign_steering" in tool_names


@pytest.mark.contract
def test_mcp_declare_campaign_steering_returns_structured_campaign_id() -> None:
    with TestClient(create_app()) as client:
        cid = _register(client)
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "declare_campaign_steering",
                    "arguments": {
                        "campaign_id": cid,
                        "objective": _OBJECTIVE,
                        "space": _SPACE,
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False, result
    assert result["structuredContent"]["campaign_id"] == cid


@pytest.mark.contract
def test_mcp_declare_campaign_steering_returns_iserror_when_not_found() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "declare_campaign_steering",
                    "arguments": {
                        "campaign_id": str(uuid4()),
                        "objective": _OBJECTIVE,
                        "space": _SPACE,
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
