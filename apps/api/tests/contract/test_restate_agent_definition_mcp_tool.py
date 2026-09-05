"""Contract tests for the `restate_agent_definition` MCP tool."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data

_REASON = "restated after the brain migration"


def _define_args() -> dict[str, object]:
    """Define via the legacy `model_ref` path: a pre-brain stream is exactly
    what a restatement exists to correct."""
    return {
        "kind": "RunInitiator",
        "name": "Run Initiator",
        "version": "v1",
        "model_ref": {
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "snapshot_pin": None,
        },
    }


def _call(client: TestClient, headers: dict[str, str], *, call_id: int, name: str, args: object):
    return client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": call_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": args},
        },
        headers=headers,
    )


@pytest.mark.contract
def test_mcp_lists_restate_agent_definition_tool() -> None:
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
    assert "restate_agent_definition" in tool_names


@pytest.mark.contract
def test_mcp_restate_agent_definition_returns_structured_output() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        define_resp = _call(
            client, session_headers, call_id=3, name="define_agent", args=_define_args()
        )
        agent_id = parse_sse_data(define_resp.text)["result"]["structuredContent"]["agent_id"]
        response = _call(
            client,
            session_headers,
            call_id=4,
            name="restate_agent_definition",
            args={
                "agent_id": agent_id,
                "reason": _REASON,
                "brain": {"kind": "Rule", "rule": "RunInitiator:v1"},
            },
        )
    result = parse_sse_data(response.text)["result"]
    assert result["isError"] is False, result
    assert result["structuredContent"]["agent_id"] == agent_id
    assert result["structuredContent"]["brain_kind"] == "Rule"
    assert result["structuredContent"]["name"] is None


@pytest.mark.contract
def test_mcp_restate_agent_definition_renames() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        define_resp = _call(
            client, session_headers, call_id=3, name="define_agent", args=_define_args()
        )
        agent_id = parse_sse_data(define_resp.text)["result"]["structuredContent"]["agent_id"]
        response = _call(
            client,
            session_headers,
            call_id=4,
            name="restate_agent_definition",
            args={"agent_id": agent_id, "reason": _REASON, "name": "Campaign Coordinator"},
        )
    result = parse_sse_data(response.text)["result"]
    assert result["isError"] is False, result
    assert result["structuredContent"]["name"] == "Campaign Coordinator"
    assert result["structuredContent"]["brain_kind"] is None


@pytest.mark.contract
def test_mcp_restate_agent_definition_errors_when_nothing_is_restated() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        define_resp = _call(
            client, session_headers, call_id=3, name="define_agent", args=_define_args()
        )
        agent_id = parse_sse_data(define_resp.text)["result"]["structuredContent"]["agent_id"]
        response = _call(
            client,
            session_headers,
            call_id=4,
            name="restate_agent_definition",
            args={"agent_id": agent_id, "reason": _REASON},
        )
    assert parse_sse_data(response.text)["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_restate_agent_definition_returns_iserror_on_unknown_id() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = _call(
            client,
            session_headers,
            call_id=4,
            name="restate_agent_definition",
            args={"agent_id": str(uuid4()), "reason": _REASON, "name": "Ghost"},
        )
    assert parse_sse_data(response.text)["result"]["isError"] is True
