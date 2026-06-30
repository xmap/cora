"""Contract tests for the `discard_distribution` MCP tool.

The happy path (and the guarded redundancy / last-Verified branches)
are not reachable in TestClient: a Distribution cannot be registered
through the wire without a resolving SupplyLookup, and the
Verified-sibling signal is projection-only with no projection worker
running. Those branches are locked at the unit + integration tiers.
These contract tests pin the tool's presence on the MCP surface and
the target-not-found error path.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


@pytest.mark.contract
def test_mcp_lists_discard_distribution_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "discard_distribution" in tool_names


@pytest.mark.contract
def test_mcp_discard_distribution_tool_returns_iserror_for_unknown_distribution() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "discard_distribution",
                    "arguments": {"distribution_id": str(uuid4()), "reason": "X"},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()
