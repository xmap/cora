"""Contract tests for the `conduct_run` MCP tool.

Mirrors the REST contract (same wire shape, same in-process wire-up).
Covers tool listing and a structured failure-in-body result. The happy
path (a real Running Run conducted to Completed) is covered by the REST
contract test and the ComputeRuntime unit tests; here we prove the tool
is registered, accepts the body schema, reaches the wired runtime, and
returns a structured result rather than raising.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


@pytest.mark.contract
def test_mcp_lists_conduct_run_tool() -> None:
    """The composition root registers the conduct_run tool."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "conduct_run" in tool_names


@pytest.mark.contract
def test_mcp_conduct_run_unknown_run_returns_structured_failure() -> None:
    """Conducting an unknown Run returns a structured succeeded=False
    result (the Run cannot be completed), not a raised error."""
    run_id = str(uuid4())
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "conduct_run",
                    "arguments": {
                        "run_id": run_id,
                        "body": {"command": ["noop"], "output_uri": "file:///o.h5"},
                    },
                },
            },
            headers=headers,
        )
    result = parse_sse_data(response.text)["result"]["structuredContent"]
    assert result["run_id"] == run_id
    assert result["succeeded"] is False
    assert result["failure"] is not None
