"""Contract tests for the `try_conduct_procedure` MCP tool."""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _register_via_mcp(client: TestClient, headers: dict[str, str]) -> UUID:
    reg = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "register_procedure",
                "arguments": {"name": "Vessel-A bakeout", "kind": "bakeout"},
            },
        },
        headers=headers,
    )
    return UUID(parse_sse_data(reg.text)["result"]["structuredContent"]["procedure_id"])


@pytest.mark.contract
def test_mcp_lists_try_conduct_procedure_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "try_conduct_procedure" in tool_names


@pytest.mark.contract
def test_mcp_try_conduct_procedure_pauses_to_held() -> None:
    """A recoverable setpoint failure pauses the Procedure to Held via the tool;
    the structured output carries held=True (the tool wiring is exercised
    end-to-end)."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        pid = _register_via_mcp(client, headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "try_conduct_procedure",
                    "arguments": {
                        "procedure_id": str(pid),
                        "body": {
                            "steps": [{"kind": "setpoint", "address": "2bma:x", "value": 1.0}]
                        },
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    structured = body["result"]["structuredContent"]
    assert structured["held"] is True
    assert structured["succeeded"] is False
