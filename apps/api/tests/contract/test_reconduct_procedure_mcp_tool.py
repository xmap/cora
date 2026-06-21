"""Contract tests for the `reconduct_procedure` MCP tool."""

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
def test_mcp_lists_reconduct_procedure_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "reconduct_procedure" in tool_names


@pytest.mark.contract
def test_mcp_reconduct_procedure_tool_errors_for_non_held() -> None:
    """Reconducting a Defined (non-Held) Procedure surfaces the resume guard
    as an MCP error (the tool wiring is exercised end-to-end)."""
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
                    "name": "reconduct_procedure",
                    "arguments": {"procedure_id": str(pid), "re_establishment_boundary": 0},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
