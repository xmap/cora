"""Contract tests for the `add_method_required_role` MCP tool.

Mirrors `test_version_method_mcp_tool.py`. Slice 1 of the positional
role-tagging workstream.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._helpers import create_capability_via_api
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _define_method_via_tool(
    client: TestClient, headers: dict[str, str], name: str = "Tomography"
) -> UUID:
    cap_id = create_capability_via_api(client)
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "define_method",
                "arguments": {
                    "execution_pattern": "Batch",
                    "name": name,
                    "capability_id": cap_id,
                    "needed_family_ids": [],
                },
            },
        },
        headers=headers,
    )
    body = parse_sse_data(response.text)
    return UUID(body["result"]["structuredContent"]["method_id"])


def _requirement_args(role_name: str = "detector") -> dict[str, object]:
    return {
        "role_name": role_name,
        "family_id": str(uuid4()),
        "required_ports": [
            {
                "port_name": "trigger_in",
                "direction": "Input",
                "signal_type": "TTL",
            }
        ],
        "optional": False,
    }


@pytest.mark.contract
def test_mcp_lists_add_method_required_role_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "add_method_required_role" in tool_names


@pytest.mark.contract
def test_mcp_add_method_required_role_tool_succeeds_on_happy_path() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        method_id = _define_method_via_tool(client, headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "add_method_required_role",
                    "arguments": {
                        "method_id": str(method_id),
                        "requirement": _requirement_args(),
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_add_method_required_role_tool_returns_iserror_for_duplicate_role() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        method_id = _define_method_via_tool(client, headers)
        for call_id in (4, 5):
            response = client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": call_id,
                    "method": "tools/call",
                    "params": {
                        "name": "add_method_required_role",
                        "arguments": {
                            "method_id": str(method_id),
                            "requirement": _requirement_args("detector"),
                        },
                    },
                },
                headers=headers,
            )
        body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_lists_remove_method_required_role_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "remove_method_required_role" in tool_names


@pytest.mark.contract
def test_mcp_remove_method_required_role_tool_succeeds_on_happy_path() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        method_id = _define_method_via_tool(client, headers)
        # Seed a role first.
        client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "add_method_required_role",
                    "arguments": {
                        "method_id": str(method_id),
                        "requirement": _requirement_args("detector"),
                    },
                },
            },
            headers=headers,
        )
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "remove_method_required_role",
                    "arguments": {
                        "method_id": str(method_id),
                        "role_name": "detector",
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False
