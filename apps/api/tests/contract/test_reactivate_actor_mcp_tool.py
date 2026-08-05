"""Contract tests for the `reactivate_actor` MCP tool.

Mirrors test_register_actor_mcp_tool.py: full JSON-RPC handshake then
tool/call against the FastMCP-mounted endpoint with in-memory wiring.
Shared MCP helpers live in `tests/contract/_mcp_helpers.py`.

As on the REST side, the happy path needs an actor that is already
deactivated, so the helper below performs both steps.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _call_tool(
    client: TestClient,
    headers: dict[str, str],
    *,
    request_id: int,
    name: str,
    arguments: dict[str, str],
) -> dict[str, object]:
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
    assert response.status_code == 200
    result: dict[str, object] = parse_sse_data(response.text)["result"]
    return result


def _register_deactivated_via_tool(client: TestClient, headers: dict[str, str]) -> UUID:
    """Helper: register via MCP, deactivate, return the actor's id."""
    registered = _call_tool(
        client,
        headers,
        request_id=2,
        name="register_actor",
        arguments={"name": "Doga"},
    )
    assert registered["isError"] is False
    structured: dict[str, str] = registered["structuredContent"]  # type: ignore[assignment]
    actor_id = UUID(structured["actor_id"])

    deactivated = _call_tool(
        client,
        headers,
        request_id=3,
        name="deactivate_actor",
        arguments={"actor_id": str(actor_id)},
    )
    assert deactivated["isError"] is False
    return actor_id


@pytest.mark.contract
def test_mcp_lists_reactivate_actor_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "reactivate_actor" in tool_names


@pytest.mark.contract
def test_mcp_reactivate_actor_tool_succeeds_for_deactivated_actor() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        actor_id = _register_deactivated_via_tool(client, headers)
        result = _call_tool(
            client,
            headers,
            request_id=4,
            name="reactivate_actor",
            arguments={"actor_id": str(actor_id)},
        )
    assert result["isError"] is False


@pytest.mark.contract
def test_mcp_reactivate_actor_tool_returns_iserror_for_unknown_actor() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        result = _call_tool(
            client,
            headers,
            request_id=5,
            name="reactivate_actor",
            arguments={"actor_id": str(uuid4())},
        )
    assert result["isError"] is True
    content: list[dict[str, str]] = result["content"]  # type: ignore[assignment]
    assert "not found" in content[0]["text"].lower()


@pytest.mark.contract
def test_mcp_reactivate_actor_tool_returns_iserror_for_never_deactivated_actor() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        registered = _call_tool(
            client,
            headers,
            request_id=6,
            name="register_actor",
            arguments={"name": "Doga"},
        )
        structured: dict[str, str] = registered["structuredContent"]  # type: ignore[assignment]
        result = _call_tool(
            client,
            headers,
            request_id=7,
            name="reactivate_actor",
            arguments={"actor_id": structured["actor_id"]},
        )
    assert result["isError"] is True
    content: list[dict[str, str]] = result["content"]  # type: ignore[assignment]
    assert "already active" in content[0]["text"].lower()
