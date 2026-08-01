"""Contract tests for the `deprecate_capability` MCP tool."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _define_capability_via_tool(
    client: TestClient, session_headers: dict[str, str], code: str = "cora.capability.x"
) -> UUID:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "define_capability",
                "arguments": {
                    "code": code,
                    "name": code.rsplit(".", 1)[-1],
                    "required_affordances": [],
                    "executor_shapes": ["Method"],
                },
            },
        },
        headers=session_headers,
    )
    body = parse_sse_data(response.text)
    return UUID(body["result"]["structuredContent"]["capability_id"])


@pytest.mark.contract
def test_mcp_lists_deprecate_capability_tool() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "deprecate_capability" in tool_names


@pytest.mark.contract
def test_mcp_deprecate_capability_succeeds_on_happy_path() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        cap_id = _define_capability_via_tool(client, session_headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "deprecate_capability",
                    "arguments": {"capability_id": str(cap_id), "reason": "Superseded"},
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_deprecate_capability_with_replaced_by_pointer() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        original = _define_capability_via_tool(client, session_headers, "cora.capability.original")
        successor = _define_capability_via_tool(
            client, session_headers, "cora.capability.successor"
        )
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "deprecate_capability",
                    "arguments": {
                        "capability_id": str(original),
                        "reason": "Superseded",
                        "replaced_by_capability_id": str(successor),
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_deprecate_capability_returns_iserror_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "deprecate_capability",
                    "arguments": {"capability_id": str(uuid4()), "reason": "Superseded"},
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
