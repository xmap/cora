"""Contract tests for the `add_assembly_presents_as` MCP tool."""

from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _seed(client: TestClient, app: FastAPI) -> tuple[UUID, UUID]:
    family_resp = client.post(
        "/families",
        json={"name": "Imager", "affordances": []},
    )
    family_id = UUID(family_resp.json()["family_id"])
    asm_resp = client.post(
        "/assemblies",
        json={
            "name": "Microscope",
            "presents_as_family_id": str(family_id),
            "required_slots": [],
            "required_wires": [],
        },
    )
    assembly_id = UUID(asm_resp.json()["assembly_id"])
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
        name="Detector",
        required_affordances=["Imageable"],
    )
    return assembly_id, role_id


@pytest.mark.contract
def test_mcp_lists_add_assembly_presents_as_tool() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "add_assembly_presents_as" in tool_names


@pytest.mark.contract
def test_mcp_add_assembly_presents_as_tool_call_succeeds() -> None:
    app = create_app()
    with TestClient(app) as client:
        assembly_id, role_id = _seed(client, app)
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "add_assembly_presents_as",
                    "arguments": {
                        "assembly_id": str(assembly_id),
                        "role_id": str(role_id),
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False, body
