"""Contract tests for the `evaluate_policy` MCP tool.

Shared MCP helpers live in `tests/contract/_mcp_helpers.py`.
"""

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.infrastructure.routing import SYSTEM_HTTP_SURFACE_ID
from tests.contract._mcp_helpers import open_session, parse_sse_data

_CONDUIT = "01900000-0000-7000-8000-00000000aaaa"
_OTHER_CONDUIT = "01900000-0000-7000-8000-00000000bbbb"
_ALLOWED_PRINCIPAL = "01900000-0000-7000-8000-000000000a01"
_OTHER_PRINCIPAL = "01900000-0000-7000-8000-000000000a02"
_SURFACE = str(SYSTEM_HTTP_SURFACE_ID)
_OTHER_SURFACE = "01900000-0000-7000-8000-00000000face"


def _define_policy_via_rest(client: TestClient) -> str:
    """Reuse the REST endpoint to seed a policy. Same in-process
    in-memory store backs both REST and MCP via the lifespan. The
    policy binds the HTTP Surface."""
    response = client.post(
        "/policies",
        json={
            "name": "Beam-team",
            "conduit_id": _CONDUIT,
            "permitted_principal_ids": [_ALLOWED_PRINCIPAL],
            "permitted_commands": ["RegisterActor"],
            "surface_id": _SURFACE,
        },
    )
    assert response.status_code == 201
    policy_id: str = response.json()["policy_id"]
    return policy_id


def _call_evaluate_tool(
    client: TestClient,
    headers: dict[str, str],
    *,
    policy_id: str,
    evaluated_principal_id: str = _ALLOWED_PRINCIPAL,
    evaluated_command_name: str = "RegisterActor",
    evaluated_conduit_id: str = _CONDUIT,
    evaluated_surface_id: str = _SURFACE,
) -> dict[str, Any]:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 99,
            "method": "tools/call",
            "params": {
                "name": "evaluate_policy",
                "arguments": {
                    "policy_id": policy_id,
                    "evaluated_principal_id": evaluated_principal_id,
                    "evaluated_command_name": evaluated_command_name,
                    "evaluated_conduit_id": evaluated_conduit_id,
                    "evaluated_surface_id": evaluated_surface_id,
                },
            },
        },
        headers=headers,
    )
    assert response.status_code == 200
    return parse_sse_data(response.text)


@pytest.mark.contract
def test_mcp_lists_evaluate_policy_tool() -> None:
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
    assert "evaluate_policy" in tool_names


@pytest.mark.contract
def test_mcp_evaluate_policy_returns_allow_for_matching_subject() -> None:
    with TestClient(create_app()) as client:
        policy_id = _define_policy_via_rest(client)
        session_headers = open_session(client)
        body = _call_evaluate_tool(client, session_headers, policy_id=policy_id)
    result = body["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["decision"] == "Allow"
    assert result["structuredContent"]["reason"] is None


@pytest.mark.contract
def test_mcp_evaluate_policy_returns_deny_with_reason() -> None:
    with TestClient(create_app()) as client:
        policy_id = _define_policy_via_rest(client)
        session_headers = open_session(client)
        body = _call_evaluate_tool(
            client,
            session_headers,
            policy_id=policy_id,
            evaluated_principal_id=_OTHER_PRINCIPAL,
        )
    result = body["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["decision"] == "Deny"
    assert result["structuredContent"]["reason"] is not None


@pytest.mark.contract
def test_mcp_evaluate_policy_returns_deny_when_surface_does_not_match() -> None:
    """Strict surface matching: the policy binds the HTTP Surface, so an
    evaluated surface that differs denies even when principal, command,
    and conduit all match."""
    with TestClient(create_app()) as client:
        policy_id = _define_policy_via_rest(client)
        session_headers = open_session(client)
        body = _call_evaluate_tool(
            client,
            session_headers,
            policy_id=policy_id,
            evaluated_surface_id=_OTHER_SURFACE,
        )
    result = body["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["decision"] == "Deny"
    assert "surface" in result["structuredContent"]["reason"].lower()


@pytest.mark.contract
def test_mcp_evaluate_policy_returns_iserror_when_policy_missing() -> None:
    """Missing policy → handler returns None → tool raises ValueError →
    FastMCP wraps as isError: true (matches REST 404 in MCP idiom)."""
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        body = _call_evaluate_tool(client, session_headers, policy_id=missing_id)
    result = body["result"]
    assert result["isError"] is True
    assert "not found" in result["content"][0]["text"].lower()


@pytest.mark.contract
def test_mcp_evaluate_policy_returns_iserror_on_invalid_uuid_argument() -> None:
    """FastMCP's input-schema validation rejects non-UUID strings."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        body = _call_evaluate_tool(
            client,
            session_headers,
            policy_id="not-a-uuid",
        )
    assert body["result"]["isError"] is True
