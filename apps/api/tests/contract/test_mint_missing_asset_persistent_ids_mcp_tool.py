"""Contract tests for the `mint_missing_asset_persistent_ids` MCP tool.

Shared MCP helpers live in `tests/contract/_mcp_helpers.py`. `APP_ENV=test`
runs in-memory (`pool=None`), so the sweep enumerates nothing: these pin the
tool's wire contract (listed + callable + structured result shape), not the
sweep behavior (that is the Postgres integration suite's job).
"""

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


@pytest.mark.contract
def test_mcp_lists_mint_missing_asset_persistent_ids_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "mint_missing_asset_persistent_ids" in tool_names


@pytest.mark.contract
def test_mcp_mint_missing_tool_returns_empty_summary_in_memory() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "mint_missing_asset_persistent_ids",
                    "arguments": {"body": {}},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False
    summary = body["result"]["structuredContent"]
    assert summary == {"scanned": 0, "minted": [], "skipped": [], "failed": []}
