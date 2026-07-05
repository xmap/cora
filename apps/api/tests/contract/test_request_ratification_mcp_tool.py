"""Contract tests for the `request_ratification` MCP tool.

Mirror of `test_define_conduit_mcp_tool.py`. Shared MCP helpers live in
`tests/contract/_mcp_helpers.py`.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


@pytest.mark.contract
def test_mcp_lists_request_ratification_tool() -> None:
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
    assert "request_ratification" in tool_names


@pytest.mark.contract
def test_mcp_request_ratification_tool_returns_structured_ratification_id() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "request_ratification",
                    "arguments": {
                        "ratification_id": str(uuid4()),
                        "target_action_id": str(uuid4()),
                        "command_name": "AbortRun",
                        "consequence_class": "first_of_kind",
                    },
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    assert "ratification_id" in result["structuredContent"]
    UUID(result["structuredContent"]["ratification_id"])  # parses without raising


@pytest.mark.contract
def test_mcp_request_ratification_tool_returns_iserror_on_invalid_input() -> None:
    """Whitespace-only consequence_class passes Pydantic min_length=1 but trips
    the domain guard; FastMCP wraps the raised InvalidConsequenceClassError as
    isError: true with a text diagnostic."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "request_ratification",
                    "arguments": {
                        "ratification_id": str(uuid4()),
                        "target_action_id": str(uuid4()),
                        "command_name": "AbortRun",
                        "consequence_class": "   ",
                    },
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_request_ratification_tool_rejects_missing_argument() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "request_ratification",
                    "arguments": {"ratification_id": str(uuid4())},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
