"""Contract tests for the `define_policy` MCP tool.

Shared MCP helpers live in `tests/contract/_mcp_helpers.py`.
"""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.infrastructure.routing import SYSTEM_HTTP_SURFACE_ID
from tests.contract._mcp_helpers import open_session, parse_sse_data

_CONDUIT = "01900000-0000-7000-8000-00000000aaaa"
_PRINCIPAL = "01900000-0000-7000-8000-000000000a01"


@pytest.mark.contract
def test_mcp_lists_define_policy_tool() -> None:
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
    assert "define_policy" in tool_names


@pytest.mark.contract
def test_mcp_define_policy_tool_returns_structured_policy_id() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "define_policy",
                    "arguments": {
                        "name": "Beam-team",
                        "conduit_id": _CONDUIT,
                        "permitted_principal_ids": [_PRINCIPAL],
                        "permitted_commands": ["RegisterActor"],
                        "surface_id": str(SYSTEM_HTTP_SURFACE_ID),
                    },
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    assert "policy_id" in result["structuredContent"]
    UUID(result["structuredContent"]["policy_id"])


@pytest.mark.contract
def test_mcp_define_policy_tool_returns_iserror_on_invalid_input() -> None:
    """Whitespace-only name passes Pydantic min_length=1 but trips the
    domain VO; FastMCP wraps the raised InvalidPolicyNameError."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "define_policy",
                    "arguments": {
                        "name": "   ",
                        "conduit_id": _CONDUIT,
                        "permitted_principal_ids": [_PRINCIPAL],
                        "permitted_commands": ["RegisterActor"],
                        # Valid surface so the deny is on the name VO, not surface.
                        "surface_id": str(SYSTEM_HTTP_SURFACE_ID),
                    },
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is True
    assert "Policy name" in result["content"][0]["text"]


@pytest.mark.contract
def test_mcp_define_policy_tool_rejects_missing_argument() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "define_policy",
                    "arguments": {"name": "Beam-team"},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
