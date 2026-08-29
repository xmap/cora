"""Contract tests for the `get_recipe` MCP tool."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _capability_args() -> dict[str, Any]:
    return {
        "code": "cora.capability.mcp_grecipe",
        "name": "MCPGRecipe",
        "required_affordances": [],
        "executor_shapes": ["Method", "Procedure"],
    }


def _recipe_args(capability_id: str) -> dict[str, Any]:
    return {
        "name": "R",
        "capability_id": capability_id,
        "steps": {
            "steps": [{"kind": "setpoint", "address": "dev:x", "value": 1.0, "verify": False}],
        },
    }


def _call_tool(
    client: TestClient,
    session_headers: dict[str, str],
    tool: str,
    arguments: dict[str, Any],
    request_id: int,
) -> dict[str, Any]:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        },
        headers=session_headers,
    )
    return parse_sse_data(response.text)["result"]


@pytest.mark.contract
def test_mcp_lists_get_recipe_tool() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "get_recipe" in tool_names


@pytest.mark.contract
def test_mcp_get_recipe_tool_returns_structured_recipe_state() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        cap_result = _call_tool(client, session_headers, "define_capability", _capability_args(), 2)
        capability_id = cap_result["structuredContent"]["capability_id"]
        recipe_result = _call_tool(
            client, session_headers, "define_recipe", _recipe_args(capability_id), 3
        )
        recipe_id = recipe_result["structuredContent"]["recipe_id"]
        result = _call_tool(client, session_headers, "get_recipe", {"recipe_id": recipe_id}, 4)
    assert result["isError"] is False
    body = result["structuredContent"]
    assert body["id"] == recipe_id
    assert body["status"] == "Defined"
    assert body["capability_id"] == capability_id


@pytest.mark.contract
def test_mcp_get_recipe_tool_surfaces_closing_steps_defined_via_mcp() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        cap_result = _call_tool(client, session_headers, "define_capability", _capability_args(), 2)
        capability_id = cap_result["structuredContent"]["capability_id"]
        args = _recipe_args(capability_id)
        args["closing_steps"] = {
            "steps": [{"kind": "setpoint", "address": "dev:shutter", "value": 0.0}],
        }
        recipe_result = _call_tool(client, session_headers, "define_recipe", args, 3)
        recipe_id = recipe_result["structuredContent"]["recipe_id"]
        result = _call_tool(client, session_headers, "get_recipe", {"recipe_id": recipe_id}, 4)
    assert result["isError"] is False
    body = result["structuredContent"]
    assert body["closing_steps"]["steps"][0]["address"] == "dev:shutter"
