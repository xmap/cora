"""Contract tests for the `get_family` MCP tool.

Mirrors `test_get_subject_mcp_tool.py` / `test_get_actor_mcp_tool.py`.
Shared MCP helpers live in `tests/contract/_mcp_helpers.py`.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _define_family_via_tool(client: TestClient, headers: dict[str, str]) -> UUID:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "define_family",
                "arguments": {"name": "Tomography", "affordances": []},
            },
        },
        headers=headers,
    )
    body = parse_sse_data(response.text)
    return UUID(body["result"]["structuredContent"]["family_id"])


@pytest.mark.contract
def test_mcp_lists_get_family_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "get_family" in tool_names


@pytest.mark.contract
def test_mcp_get_family_tool_returns_structured_capability_for_known_id() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        family_id = _define_family_via_tool(client, headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "get_family",
                    "arguments": {"family_id": str(family_id)},
                },
            },
            headers=headers,
        )

    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    structured = result["structuredContent"]
    assert structured["id"] == str(family_id)
    assert structured["name"] == "Tomography"
    assert structured["status"] == "Defined"
    # Null until version_family runs (5f-2).
    assert structured["version"] is None


@pytest.mark.contract
def test_mcp_get_family_tool_returns_iserror_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "get_family",
                    "arguments": {"family_id": str(uuid4())},
                },
            },
            headers=headers,
        )

    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()
