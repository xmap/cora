"""Contract tests for the `append_outcomes` MCP tool."""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _register_and_start_via_mcp(client: TestClient, headers: dict[str, str]) -> UUID:
    reg = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "register_procedure",
                "arguments": {"name": "rotation-center steer", "kind": "characterization"},
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
    return pid


def _entry() -> dict[str, Any]:
    return {
        "event_id": str(uuid4()),
        "iteration_index": 0,
        "point": {"energy": 8.0},
        "measurements": [
            {"name": "flux", "value": 12.5, "kind": "Scalar", "quality": "Good", "units": None}
        ],
        "succeeded": True,
        "actuation_kind": "Physical",
        "sampled_at": "2026-07-01T12:00:00+00:00",
    }


@pytest.mark.contract
def test_mcp_lists_append_outcomes_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "append_outcomes" in tool_names


@pytest.mark.contract
def test_mcp_append_outcomes_tool_succeeds_for_running() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        pid = _register_and_start_via_mcp(client, headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "append_outcomes",
                    "arguments": {"procedure_id": str(pid), "entries": [_entry()]},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False
