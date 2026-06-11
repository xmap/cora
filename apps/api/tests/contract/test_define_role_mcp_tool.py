"""Contract tests for the `define_role` MCP tool."""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _args(**overrides: object) -> dict[str, object]:
    # Default name avoids the 4 SEED_ROLES auto-defined at lifespan
    # (Imager/Positioner/Controller/Detector); see the REST endpoint
    # test test_post_roles_with_seed_role_name_returns_409.
    base: dict[str, object] = {
        "name": "Diagnostician",
        "docstring": "Acquires 2D image frames on exposure or trigger.",
        "required_affordances": ["Imageable"],
        "optional_affordances": ["Binnable"],
        "produces": ["Image"],
        "consumes": ["TriggerIn"],
    }
    base.update(overrides)
    return base


@pytest.mark.contract
def test_mcp_lists_define_role_tool() -> None:
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
    assert "define_role" in tool_names


@pytest.mark.contract
def test_mcp_define_role_tool_returns_structured_role_id() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "define_role",
                    "arguments": _args(),
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    assert "role_id" in result["structuredContent"]
    UUID(result["structuredContent"]["role_id"])


@pytest.mark.contract
def test_mcp_define_role_tool_returns_iserror_on_invalid_name() -> None:
    """Whitespace-only name trips the RoleName VO."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "define_role",
                    "arguments": _args(name="   "),
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is True
    assert "Role name" in result["content"][0]["text"]


@pytest.mark.contract
def test_mcp_define_role_tool_returns_iserror_on_overlapping_affordances() -> None:
    """Required + optional Affordance sets must be disjoint."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "define_role",
                    "arguments": _args(
                        required_affordances=["Imageable", "Binnable"],
                        optional_affordances=["Binnable"],
                    ),
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is True


@pytest.mark.contract
def test_mcp_define_role_tool_rejects_missing_argument() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "define_role",
                    "arguments": {},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
