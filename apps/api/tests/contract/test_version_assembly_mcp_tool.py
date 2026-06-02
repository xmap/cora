"""Contract tests for the `version_assembly` MCP tool."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _define_family_via_tool(
    client: TestClient,
    headers: dict[str, str],
    name: str = "Detector",
) -> UUID:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "define_family",
                "arguments": {"name": name, "affordances": []},
            },
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    return UUID(body["result"]["structuredContent"]["family_id"])


def _define_assembly_via_tool(
    client: TestClient,
    headers: dict[str, str],
    family_id: UUID,
    *,
    name: str = "MCTOptics",
) -> UUID:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "define_assembly",
                "arguments": {
                    "name": name,
                    "presents_as_family_id": str(family_id),
                    "required_slots": [],
                    "required_wires": [],
                },
            },
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    return UUID(body["result"]["structuredContent"]["assembly_id"])


@pytest.mark.contract
def test_mcp_lists_version_assembly_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "version_assembly" in tool_names


@pytest.mark.contract
def test_mcp_version_assembly_tool_succeeds_for_defined_assembly() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        family_id = _define_family_via_tool(client, headers)
        assembly_id = _define_assembly_via_tool(client, headers, family_id)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "version_assembly",
                    "arguments": {
                        "assembly_id": str(assembly_id),
                        "name": "MCTOptics",
                        "presents_as_family_id": str(family_id),
                        "required_slots": [],
                        "required_wires": [],
                        "version": "v0.2.0",
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_version_assembly_tool_returns_iserror_for_unknown_assembly() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        family_id = _define_family_via_tool(client, headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "version_assembly",
                    "arguments": {
                        "assembly_id": str(uuid4()),
                        "name": "X",
                        "presents_as_family_id": str(family_id),
                        "required_slots": [],
                        "required_wires": [],
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()


@pytest.mark.contract
def test_mcp_version_assembly_tool_succeeds_on_versioned_state() -> None:
    """Multi-source FSM: Versioned -> Versioned is accepted."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        family_id = _define_family_via_tool(client, headers)
        assembly_id = _define_assembly_via_tool(client, headers, family_id)
        for tag in ("v1", "v2"):
            response = client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 5,
                    "method": "tools/call",
                    "params": {
                        "name": "version_assembly",
                        "arguments": {
                            "assembly_id": str(assembly_id),
                            "name": "MCTOptics",
                            "presents_as_family_id": str(family_id),
                            "required_slots": [],
                            "required_wires": [],
                            "version": tag,
                        },
                    },
                },
                headers=headers,
            )
            body = parse_sse_data(response.text)
            assert body["result"]["isError"] is False
