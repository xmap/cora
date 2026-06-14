"""Contract tests for the `remove_family_presents_as` MCP tool."""

from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _seed_family_with_detector(client: TestClient, app: FastAPI) -> tuple[str, str]:
    family_resp = client.post(
        "/families",
        json={"name": "Camera", "affordances": ["Imageable"]},
    )
    family_id = str(family_resp.json()["family_id"])
    role_resp = client.post(
        "/roles",
        json={
            "name": "Diagnostician",
            "docstring": "Acquires 2D image frames.",
            "required_affordances": ["Imageable"],
            "optional_affordances": [],
            "produces": [],
            "consumes": [],
        },
    )
    role_id = str(role_resp.json()["role_id"])
    app.state.deps.role_lookup.register(
        role_id=UUID(role_id),
        name="Detector",
        required_affordances=["Imageable"],
    )
    add_resp = client.post(
        f"/families/{family_id}/add-presents-as",
        json={"role_id": role_id},
    )
    assert add_resp.status_code == 204
    return family_id, role_id


@pytest.mark.contract
def test_mcp_lists_remove_family_presents_as_tool() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "remove_family_presents_as" in tool_names


@pytest.mark.contract
def test_mcp_remove_family_presents_as_tool_call_succeeds() -> None:
    app = create_app()
    with TestClient(app) as client:
        family_id, role_id = _seed_family_with_detector(client, app)
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "remove_family_presents_as",
                    "arguments": {"family_id": family_id, "role_id": role_id},
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False, body


@pytest.mark.contract
def test_mcp_remove_family_presents_as_tool_returns_iserror_on_not_advertised() -> None:
    """Strict-not-idempotent: removing a Role not in presents_as raises."""
    with TestClient(create_app()) as client:
        family_resp = client.post(
            "/families",
            json={"name": "Camera", "affordances": ["Imageable"]},
        )
        family_id = str(family_resp.json()["family_id"])
        role_resp = client.post(
            "/roles",
            json={
                "name": "Diagnostician",
                "docstring": "Acquires 2D image frames.",
                "required_affordances": ["Imageable"],
                "optional_affordances": [],
                "produces": [],
                "consumes": [],
            },
        )
        role_id = str(role_resp.json()["role_id"])
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "remove_family_presents_as",
                    "arguments": {"family_id": family_id, "role_id": role_id},
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is True
