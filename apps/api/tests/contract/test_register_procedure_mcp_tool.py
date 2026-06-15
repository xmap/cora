"""Contract tests for the `register_procedure` MCP tool."""

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _good_args(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "name": "Vessel-A bakeout",
        "kind": "bakeout",
    }
    base.update(overrides)
    return base


@pytest.mark.contract
def test_mcp_lists_register_procedure_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "register_procedure" in tool_names


@pytest.mark.contract
def test_mcp_register_procedure_tool_succeeds_on_minimum_args() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "register_procedure",
                    "arguments": _good_args(),
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False
    assert "procedure_id" in body["result"]["structuredContent"]


@pytest.mark.contract
def test_mcp_register_procedure_tool_accepts_target_asset_ids() -> None:
    asset = str(uuid4())
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "register_procedure",
                    "arguments": _good_args(kind="alignment", target_asset_ids=[asset]),
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False
    assert "procedure_id" in body["result"]["structuredContent"]


@pytest.mark.contract
def test_mcp_register_procedure_tool_accepts_parent_run_id() -> None:
    parent_run = str(uuid4())
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "register_procedure",
                    "arguments": _good_args(kind="alignment", parent_run_id=parent_run),
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False
    assert "procedure_id" in body["result"]["structuredContent"]
