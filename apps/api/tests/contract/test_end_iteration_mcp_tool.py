"""Contract tests for the `end_iteration` MCP tool."""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _register_start_open_via_mcp(client: TestClient, headers: dict[str, str]) -> UUID:
    reg = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "register_procedure",
                "arguments": {"name": "2-BM center alignment", "kind": "center_alignment"},
            },
        },
        headers=headers,
    )
    pid = UUID(parse_sse_data(reg.text)["result"]["structuredContent"]["procedure_id"])
    client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "start_procedure", "arguments": {"procedure_id": str(pid)}},
        },
        headers=headers,
    )
    client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "start_iteration",
                "arguments": {"procedure_id": str(pid), "iteration_index": 1},
            },
        },
        headers=headers,
    )
    return pid


@pytest.mark.contract
def test_mcp_lists_end_iteration_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    tool_names = [t["name"] for t in parse_sse_data(response.text)["result"]["tools"]]
    assert "end_iteration" in tool_names


@pytest.mark.contract
def test_mcp_end_iteration_tool_succeeds_for_open_iteration() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        pid = _register_start_open_via_mcp(client, headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "end_iteration",
                    "arguments": {
                        "procedure_id": str(pid),
                        "iteration_index": 1,
                        "converged": True,
                    },
                },
            },
            headers=headers,
        )
    assert parse_sse_data(response.text)["result"]["isError"] is False
