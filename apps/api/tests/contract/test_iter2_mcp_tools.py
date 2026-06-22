"""MCP-tool contract tests for the Agent lifecycle + grants slices.

Covers tools/list visibility + happy-path tools/call for each of the
five tools (suspend / resume / grant / revoke / update-budget).
The REST endpoints already test the full status-code matrix; the
MCP layer just needs surface-level coverage that the tool exists,
returns structuredContent, and surfaces errors via `isError`.
"""

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _define_args() -> dict[str, object]:
    return {
        "kind": "RunDebriefer",
        "name": "Run Debrief",
        "version": "v1",
        "model_ref": {
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "snapshot_pin": None,
        },
    }


def _call(
    client: TestClient,
    headers: dict[str, str],
    rpc_id: int,
    tool_name: str,
    args: dict[str, object],
) -> dict[str, Any]:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": rpc_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": args},
        },
        headers=headers,
    )
    return parse_sse_data(response.text)


def _list_tools(client: TestClient, headers: dict[str, str]) -> list[str]:
    response = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        headers=headers,
    )
    body = parse_sse_data(response.text)
    return [t["name"] for t in body["result"]["tools"]]


@pytest.mark.contract
def test_mcp_lists_all_five_iter2_tools() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        tools = _list_tools(client, headers)
    for expected in (
        "suspend_agent",
        "resume_agent",
        "grant_tool_to_agent",
        "revoke_tool_from_agent",
        "update_agent_budget",
    ):
        assert expected in tools


@pytest.mark.contract
def test_mcp_suspend_then_resume_cycle() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        define = _call(client, headers, 2, "define_agent", _define_args())
        agent_id = define["result"]["structuredContent"]["agent_id"]
        _call(client, headers, 3, "version_agent", {"agent_id": agent_id})
        suspend = _call(
            client,
            headers,
            4,
            "suspend_agent",
            {"agent_id": agent_id, "reason": "cost overrun"},
        )
        resume = _call(client, headers, 5, "resume_agent", {"agent_id": agent_id})
    assert suspend["result"]["isError"] is False
    assert suspend["result"]["structuredContent"]["agent_id"] == agent_id
    assert resume["result"]["isError"] is False
    assert resume["result"]["structuredContent"]["agent_id"] == agent_id


@pytest.mark.contract
def test_mcp_grant_then_revoke_cycle_returns_structured_output() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        define = _call(client, headers, 2, "define_agent", _define_args())
        agent_id = define["result"]["structuredContent"]["agent_id"]
        grant = _call(
            client,
            headers,
            3,
            "grant_tool_to_agent",
            {"agent_id": agent_id, "tool_name": "read_run"},
        )
        revoke = _call(
            client,
            headers,
            4,
            "revoke_tool_from_agent",
            {"agent_id": agent_id, "tool_name": "read_run"},
        )
    assert grant["result"]["isError"] is False
    assert grant["result"]["structuredContent"]["tool_name"] == "read_run"
    assert revoke["result"]["isError"] is False
    assert revoke["result"]["structuredContent"]["tool_name"] == "read_run"


@pytest.mark.contract
def test_mcp_update_budget_returns_structured_output() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        define = _call(client, headers, 2, "define_agent", _define_args())
        agent_id = define["result"]["structuredContent"]["agent_id"]
        update = _call(
            client,
            headers,
            3,
            "update_agent_budget",
            {"agent_id": agent_id, "monthly_usd_cap": 100.0, "daily_token_cap": 500000},
        )
    assert update["result"]["isError"] is False
    sc = update["result"]["structuredContent"]
    assert sc["agent_id"] == agent_id
    assert sc["monthly_usd_cap"] == 100.0
    assert sc["daily_token_cap"] == 500000


@pytest.mark.contract
def test_mcp_suspend_unknown_agent_surfaces_iserror() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        result = _call(
            client,
            headers,
            2,
            "suspend_agent",
            {"agent_id": str(uuid4()), "reason": "x"},
        )
    assert result["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_grant_over_cap_tool_name_surfaces_iserror() -> None:
    """MCP-layer validation error surfaces as isError (not just not-found)."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        define = _call(client, headers, 2, "define_agent", _define_args())
        agent_id = define["result"]["structuredContent"]["agent_id"]
        result = _call(
            client,
            headers,
            3,
            "grant_tool_to_agent",
            {"agent_id": agent_id, "tool_name": "x" * 200},
        )
    assert result["result"]["isError"] is True
