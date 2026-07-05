"""Contract tests for the `revoke_grant` MCP tool.

Shared MCP helpers live in `tests/contract/_mcp_helpers.py`. Policies are seeded
via `define_policy`'s `POST /policies` (same app state as the MCP surface).
"""

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.infrastructure.routing import SYSTEM_HTTP_SURFACE_ID
from tests.contract._mcp_helpers import open_session, parse_sse_data

_CONDUIT = "01900000-0000-7000-8000-00000000aaaa"
_PRINCIPAL = "01900000-0000-7000-8000-000000000a01"


def _define_policy(client: TestClient) -> str:
    response = client.post(
        "/policies",
        json={
            "name": "Beam-team",
            "conduit_id": _CONDUIT,
            "permitted_principal_ids": [_PRINCIPAL],
            "permitted_commands": ["RegisterActor"],
            "surface_id": str(SYSTEM_HTTP_SURFACE_ID),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["policy_id"]


@pytest.mark.contract
def test_mcp_lists_revoke_grant_tool() -> None:
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
    assert "revoke_grant" in tool_names


@pytest.mark.contract
def test_mcp_revoke_grant_tool_returns_structured_policy_id() -> None:
    with TestClient(create_app()) as client:
        policy_id = _define_policy(client)
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "revoke_grant",
                    "arguments": {
                        "policy_id": policy_id,
                        "permitted_principal_id": _PRINCIPAL,
                        "reason": "access review",
                    },
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["policy_id"] == policy_id


@pytest.mark.contract
def test_mcp_revoke_grant_tool_returns_iserror_on_invalid_reason() -> None:
    """Whitespace-only reason passes Pydantic min_length=1 but trips the
    domain VO; FastMCP wraps the raised InvalidPolicyGrantRevokeReasonError."""
    with TestClient(create_app()) as client:
        policy_id = _define_policy(client)
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "revoke_grant",
                    "arguments": {
                        "policy_id": policy_id,
                        "permitted_principal_id": _PRINCIPAL,
                        "reason": "   ",
                    },
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is True
    assert "Policy grant-revoke reason" in result["content"][0]["text"]
