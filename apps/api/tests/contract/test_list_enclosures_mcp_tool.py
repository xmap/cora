"""Contract tests for the `list_enclosures` MCP tool."""

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


@pytest.mark.contract
def test_mcp_lists_list_enclosures_tool() -> None:
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
    assert "list_enclosures" in tool_names


@pytest.mark.contract
def test_mcp_list_enclosures_tool_returns_empty_page() -> None:
    """In-memory app has no pool; tool returns empty items + null cursor."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "list_enclosures", "arguments": {}},
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    structured = body["result"]["structuredContent"]
    assert structured["items"] == []
    assert structured["next_cursor"] is None
