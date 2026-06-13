"""Contract tests for the `suspend_permit` MCP tool."""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.shared.text_bounds import REASON_MAX_LENGTH
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _register_args(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "peer_facility_code": "aps-2bm",
        "direction": "Outbound",
        "allowed_credential_ids": [str(uuid4())],
        "allowed_payload_types": ["application/vnd.cora.dataset+json"],
        "allowed_artifact_kinds": ["dataset"],
        "abi_tier_floor": "Stable",
        "expires_at": "2030-01-01T00:00:00+00:00",
        "terms": {
            "kind": "Outbound",
            "scopes": [{"kind": "dataset", "name": "alpha", "qualifier": None}],
            "read_scope": "ReadAllArtifacts",
            "onward_action_scope": "ReadOnly",
        },
    }
    base.update(overrides)
    return base


def _call_tool(
    client: TestClient,
    *,
    headers: dict[str, str],
    request_id: int,
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return parse_sse_data(response.text)


def _register_and_activate(client: TestClient, headers: dict[str, str]) -> str:
    register = _call_tool(
        client,
        headers=headers,
        request_id=10,
        name="define_permit",
        arguments=_register_args(),
    )
    assert register["result"]["isError"] is False, register
    permit_id = register["result"]["structuredContent"]["permit_id"]
    activate = _call_tool(
        client,
        headers=headers,
        request_id=11,
        name="activate_permit",
        arguments={"permit_id": permit_id},
    )
    assert activate["result"]["isError"] is False, activate
    return permit_id


@pytest.mark.contract
def test_mcp_lists_suspend_permit_tool() -> None:
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
    assert "suspend_permit" in tool_names


@pytest.mark.contract
def test_mcp_suspend_permit_tool_returns_structured_permit_id() -> None:
    """Happy path: Active permit suspends cleanly; tool returns
    structured permit_id (matches REST 204 + path-id contract)."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        permit_id = _register_and_activate(client, session_headers)
        body = _call_tool(
            client,
            headers=session_headers,
            request_id=20,
            name="suspend_permit",
            arguments={"permit_id": permit_id, "reason": "peer paused"},
        )
    result = body["result"]
    assert result["isError"] is False, result
    assert result["structuredContent"]["permit_id"] == permit_id
    UUID(result["structuredContent"]["permit_id"])


@pytest.mark.contract
def test_mcp_suspend_permit_tool_accepts_omitted_reason() -> None:
    """`reason` is optional; omitting it from arguments succeeds."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        permit_id = _register_and_activate(client, session_headers)
        body = _call_tool(
            client,
            headers=session_headers,
            request_id=21,
            name="suspend_permit",
            arguments={"permit_id": permit_id},
        )
    assert body["result"]["isError"] is False, body


@pytest.mark.contract
def test_mcp_suspend_permit_tool_returns_iserror_on_defined_permit() -> None:
    """Decider-layer FSM rejection (Defined != Active) surfaces through
    FastMCP as isError: true."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        register = _call_tool(
            client,
            headers=session_headers,
            request_id=30,
            name="define_permit",
            arguments=_register_args(),
        )
        permit_id = register["result"]["structuredContent"]["permit_id"]
        body = _call_tool(
            client,
            headers=session_headers,
            request_id=31,
            name="suspend_permit",
            arguments={"permit_id": permit_id, "reason": "x"},
        )
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_suspend_permit_tool_returns_iserror_on_unknown_permit() -> None:
    """A handler raising PermitNotFoundError surfaces through FastMCP."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        body = _call_tool(
            client,
            headers=session_headers,
            request_id=40,
            name="suspend_permit",
            arguments={"permit_id": str(uuid4()), "reason": "x"},
        )
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_suspend_permit_tool_returns_iserror_on_re_suspend() -> None:
    """Strict-not-idempotent: re-suspending raises through FastMCP."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        permit_id = _register_and_activate(client, session_headers)
        first = _call_tool(
            client,
            headers=session_headers,
            request_id=50,
            name="suspend_permit",
            arguments={"permit_id": permit_id, "reason": "first"},
        )
        assert first["result"]["isError"] is False, first
        second = _call_tool(
            client,
            headers=session_headers,
            request_id=51,
            name="suspend_permit",
            arguments={"permit_id": permit_id, "reason": "second"},
        )
    assert second["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_suspend_permit_tool_rejects_missing_required_argument() -> None:
    """Pydantic-layer rejection (missing permit_id) bubbles as isError."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        body = _call_tool(
            client,
            headers=session_headers,
            request_id=60,
            name="suspend_permit",
            arguments={"reason": "x"},
        )
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_suspend_permit_tool_rejects_overlong_reason() -> None:
    """Pydantic max_length=500 enforcement bubbles as isError via FastMCP."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        body = _call_tool(
            client,
            headers=session_headers,
            request_id=70,
            name="suspend_permit",
            arguments={
                "permit_id": str(uuid4()),
                "reason": "x" * (REASON_MAX_LENGTH + 1),
            },
        )
    assert body["result"]["isError"] is True
