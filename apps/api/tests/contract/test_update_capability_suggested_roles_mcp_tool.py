"""Contract tests for the `update_capability_suggested_roles` MCP tool (3E)."""

from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _seed(client: TestClient, app: FastAPI) -> tuple[UUID, UUID]:
    cap_resp = client.post(
        "/capabilities",
        json={
            "code": "cora.capability.acquire",
            "name": "Acquire",
            "required_affordances": [],
            "executor_shapes": ["Method"],
        },
    )
    capability_id = UUID(cap_resp.json()["capability_id"])
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
    role_id = UUID(role_resp.json()["role_id"])
    app.state.deps.role_lookup.register(
        role_id=role_id,
        name="Diagnostician",
        required_affordances=["Imageable"],
    )
    return capability_id, role_id


@pytest.mark.contract
def test_mcp_lists_update_capability_suggested_roles_tool() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "update_capability_suggested_roles" in tool_names


@pytest.mark.contract
def test_mcp_update_capability_suggested_roles_tool_call_succeeds() -> None:
    app = create_app()
    with TestClient(app) as client:
        capability_id, role_id = _seed(client, app)
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "update_capability_suggested_roles",
                    "arguments": {
                        "capability_id": str(capability_id),
                        "suggested_role_ids": [str(role_id)],
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False, body


@pytest.mark.contract
def test_mcp_tool_returns_iserror_on_unresolved_role_id() -> None:
    with TestClient(create_app()) as client:
        cap_resp = client.post(
            "/capabilities",
            json={
                "code": "cora.capability.acquire",
                "name": "Acquire",
                "required_affordances": [],
                "executor_shapes": ["Method"],
            },
        )
        capability_id = UUID(cap_resp.json()["capability_id"])
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "update_capability_suggested_roles",
                    "arguments": {
                        "capability_id": str(capability_id),
                        "suggested_role_ids": ["00000000-0000-0000-0000-000000000999"],
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is True
