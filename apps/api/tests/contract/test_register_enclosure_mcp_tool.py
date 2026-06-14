"""Contract tests for the `register_enclosure` MCP tool."""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


@pytest.mark.contract
def test_mcp_lists_register_enclosure_tool() -> None:
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
    assert "register_enclosure" in tool_names


@pytest.mark.contract
def test_mcp_register_enclosure_tool_returns_structured_enclosure_id() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "register_enclosure",
                    "arguments": {
                        "name": "2-BM Hutch A",
                        "facility_code": "cora",
                    },
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    assert "enclosure_id" in result["structuredContent"]
    UUID(result["structuredContent"]["enclosure_id"])


@pytest.mark.contract
def test_mcp_register_enclosure_tool_returns_iserror_on_whitespace_name() -> None:
    """Whitespace-only name passes Pydantic min_length=1 but trips the
    EnclosureName VO; FastMCP wraps the raised InvalidEnclosureNameError
    as isError: true with a text diagnostic."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "register_enclosure",
                    "arguments": {
                        "name": "   ",
                        "facility_code": "cora",
                    },
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is True
    assert "Enclosure name" in result["content"][0]["text"]


@pytest.mark.contract
def test_mcp_register_enclosure_tool_rejects_missing_argument() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "register_enclosure",
                    "arguments": {"name": "2-BM Hutch A"},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
