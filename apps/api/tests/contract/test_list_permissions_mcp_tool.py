"""Contract tests for the `list_permissions` MCP tool.

Same in-process in-memory store backs both REST and MCP via the
FastAPI lifespan. Mirrors `test_evaluate_policy_mcp_tool.py`.
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


def _define_policy_via_rest(client: TestClient) -> str:
    response = client.post(
        "/policies",
        json={
            "name": "Beam-team",
            "conduit_id": _CONDUIT,
            "permitted_principal_ids": [_ALLOWED_PRINCIPAL],
            "permitted_commands": ["RegisterActor", "DefinePolicy"],
            "surface_id": _SURFACE,
        },
    )
    assert response.status_code == 201
    policy_id: str = response.json()["policy_id"]
    return policy_id


def _call_list_tool(
    client: TestClient,
    headers: dict[str, str],
    *,
    policy_id: str,
    evaluated_principal_id: str = _ALLOWED_PRINCIPAL,
    evaluated_conduit_id: str = _CONDUIT,
) -> dict[str, Any]:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 99,
            "method": "tools/call",
            "params": {
                "name": "list_permissions",
                "arguments": {
                    "policy_id": policy_id,
                    "evaluated_principal_id": evaluated_principal_id,
                    "evaluated_conduit_id": evaluated_conduit_id,
                },
            },
        },
        headers=headers,
    )
    assert response.status_code == 200
    return parse_sse_data(response.text)


@pytest.mark.contract
def test_mcp_lists_list_permissions_tool() -> None:
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
    assert "list_permissions" in tool_names


@pytest.mark.contract
def test_mcp_list_permissions_description_carries_anti_cache_warning() -> None:
    """Gate-review F4: the MCP tool description must explicitly warn
    agents not to use the returned set for authorization decisions
    (per the anti-hook). Pin the load-bearing substring so a future
    refactor can't silently strip it."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    list_perms = next(t for t in body["result"]["tools"] if t["name"] == "list_permissions")
    description = list_perms["description"]
    assert "Do NOT use" in description
    assert "authorization decisions" in description


@pytest.mark.contract
def test_mcp_list_permissions_returns_sorted_commands_when_eligible() -> None:
    with TestClient(create_app()) as client:
        policy_id = _define_policy_via_rest(client)
        session_headers = open_session(client)
        body = _call_list_tool(client, session_headers, policy_id=policy_id)
    result = body["result"]
    assert result["isError"] is False
    output = result["structuredContent"]
    assert output["permitted_commands"] == ["DefinePolicy", "RegisterActor"]
    assert output["incomplete"] is False


@pytest.mark.contract
def test_mcp_list_permissions_returns_empty_for_other_principal() -> None:
    with TestClient(create_app()) as client:
        policy_id = _define_policy_via_rest(client)
        session_headers = open_session(client)
        body = _call_list_tool(
            client,
            session_headers,
            policy_id=policy_id,
            evaluated_principal_id=_OTHER_PRINCIPAL,
        )
    result = body["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["permitted_commands"] == []


@pytest.mark.contract
def test_mcp_list_permissions_returns_empty_for_other_conduit() -> None:
    with TestClient(create_app()) as client:
        policy_id = _define_policy_via_rest(client)
        session_headers = open_session(client)
        body = _call_list_tool(
            client,
            session_headers,
            policy_id=policy_id,
            evaluated_conduit_id=_OTHER_CONDUIT,
        )
    result = body["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["permitted_commands"] == []


@pytest.mark.contract
def test_mcp_list_permissions_returns_iserror_when_policy_missing() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        body = _call_list_tool(client, session_headers, policy_id=missing_id)
    result = body["result"]
    assert result["isError"] is True
    assert "not found" in result["content"][0]["text"].lower()


@pytest.mark.contract
def test_mcp_list_permissions_returns_iserror_on_invalid_uuid() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        body = _call_list_tool(client, session_headers, policy_id="not-a-uuid")
    assert body["result"]["isError"] is True
