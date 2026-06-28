"""Contract tests for the `conduct_until_advised` MCP tool.

Mirrors the REST contract test (same wire shape + same in-process wire-up).
Covers tool listing and the not-found wrap. The steered-recipe-drives-over-the-
wire path (a SteeringRef recipe conducted with grid_walk) is exercised once in
the REST contract test: one in-process app drives both surfaces through the same
handler, so the recipe-path coverage is not duplicated here.
"""

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data

_OBJECTIVE: dict[str, Any] = {
    "kind": "Satisfy",
    "target_measurement_name": "rotation_center",
    "target_value": 0.0,
}
_SPACE: dict[str, Any] = {"axes": [{"name": "theta", "lower": -5.0, "upper": 5.0}]}


@pytest.mark.contract
def test_mcp_lists_conduct_until_advised_tool() -> None:
    """The Operation BC registers the conduct_until_advised tool on the FastMCP server."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "conduct_until_advised" in tool_names


@pytest.mark.contract
def test_mcp_conduct_until_advised_against_unregistered_procedure_returns_iserror() -> None:
    """The handler loads the Procedure stream up front -> ProcedureNotFoundError wrap."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        unknown_pid = uuid4()
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "conduct_until_advised",
                    "arguments": {
                        "procedure_id": str(unknown_pid),
                        "body": {
                            "objective": _OBJECTIVE,
                            "space": _SPACE,
                            "objective_capture_name": "rotation_center",
                        },
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert str(unknown_pid) in body["result"]["content"][0]["text"]
