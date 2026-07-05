"""Contract tests for the `deny_ratification` MCP tool.

Mirror of `test_define_conduit_mcp_tool.py`. Shared MCP helpers live in
`tests/contract/_mcp_helpers.py`.

The MCP tool runs as SYSTEM_PRINCIPAL_ID in legacy posture. To exercise the
happy path (an independent co-signer) the Ratification is first requested over
REST with a distinct `X-Principal-Id`, so the MCP deny is by a different
principal and does not trip the four-eyes independence guard.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data

_REQUESTER = "01910000-0000-7000-8000-0000000000d1"


def _request_ratification(client: TestClient) -> str:
    """Request a Ratification over REST as a non-SYSTEM requester; return its id."""
    ratification_id = str(uuid4())
    response = client.post(
        "/ratifications",
        json={
            "ratification_id": ratification_id,
            "target_action_id": str(uuid4()),
            "command_name": "AbortRun",
            "consequence_class": "first_of_kind",
        },
        headers={"X-Principal-Id": _REQUESTER},
    )
    assert response.status_code == 201, response.text
    return ratification_id


@pytest.mark.contract
def test_mcp_lists_deny_ratification_tool() -> None:
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
    assert "deny_ratification" in tool_names


@pytest.mark.contract
def test_mcp_deny_ratification_tool_returns_structured_ratification_id() -> None:
    with TestClient(create_app()) as client:
        rid = _request_ratification(client)
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "deny_ratification",
                    "arguments": {
                        "ratification_id": rid,
                        "reason": "unsafe first-of-kind action",
                    },
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["ratification_id"] == rid


@pytest.mark.contract
def test_mcp_deny_ratification_tool_returns_iserror_on_unknown_id() -> None:
    """Unknown ratification_id raises RatificationNotFoundError; FastMCP wraps it
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
                    "name": "deny_ratification",
                    "arguments": {
                        "ratification_id": str(uuid4()),
                        "reason": "unsafe first-of-kind action",
                    },
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_deny_ratification_tool_rejects_missing_argument() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "deny_ratification",
                    "arguments": {"ratification_id": str(uuid4())},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
