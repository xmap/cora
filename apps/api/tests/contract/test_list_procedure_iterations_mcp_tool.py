"""Contract tests for the `list_procedure_iterations` MCP tool."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


@pytest.mark.contract
def test_mcp_lists_list_procedure_iterations_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    tool_names = [t["name"] for t in parse_sse_data(response.text)["result"]["tools"]]
    assert "list_procedure_iterations" in tool_names


@pytest.mark.contract
def test_mcp_list_procedure_iterations_tool_succeeds() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "list_procedure_iterations",
                    "arguments": {"procedure_id": str(uuid4())},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False
    assert body["result"]["structuredContent"] == {"items": []}
