"""Contract tests for the `deprecate_family` MCP tool."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _define_family_via_tool(
    client: TestClient, headers: dict[str, str], name: str = "Tomography"
) -> UUID:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "define_family",
                "arguments": {"name": name, "affordances": []},
            },
        },
        headers=headers,
    )
    body = parse_sse_data(response.text)
    return UUID(body["result"]["structuredContent"]["family_id"])


@pytest.mark.contract
def test_mcp_lists_deprecate_family_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "deprecate_family" in tool_names


@pytest.mark.contract
def test_mcp_deprecate_family_tool_succeeds_on_happy_path() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        family_id = _define_family_via_tool(client, headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "deprecate_family",
                    "arguments": {"family_id": str(family_id), "reason": "Superseded"},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_deprecate_family_tool_returns_iserror_for_unknown_capability() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "deprecate_family",
                    "arguments": {"family_id": str(uuid4()), "reason": "Superseded"},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()


@pytest.mark.contract
def test_mcp_deprecate_family_tool_returns_iserror_when_already_deprecated() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        family_id = _define_family_via_tool(client, headers)
        first = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "deprecate_family",
                    "arguments": {"family_id": str(family_id), "reason": "Superseded"},
                },
            },
            headers=headers,
        )
        assert parse_sse_data(first.text)["result"]["isError"] is False
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {
                    "name": "deprecate_family",
                    "arguments": {"family_id": str(family_id), "reason": "Superseded"},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    text = body["result"]["content"][0]["text"]
    assert "Defined" in text
    assert "Versioned" in text
