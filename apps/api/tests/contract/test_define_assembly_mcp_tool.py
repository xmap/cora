"""Contract tests for the `define_assembly` MCP tool.

Mirrors `test_activate_asset_mcp_tool.py`. Shared MCP helpers live
in `tests/contract/_mcp_helpers.py`.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _define_family_via_tool(
    client: TestClient,
    headers: dict[str, str],
    name: str = "Camera",
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


@pytest.mark.contract
def test_mcp_lists_define_assembly_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "define_assembly" in tool_names


@pytest.mark.contract
def test_mcp_define_assembly_tool_succeeds_for_minimal_args() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        family_id = _define_family_via_tool(client, headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "define_assembly",
                    "arguments": {
                        "name": "Detector",
                        "presents_as_family_id": str(family_id),
                        "required_slots": [],
                        "required_wires": [],
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False
    assembly_id = body["result"]["structuredContent"]["assembly_id"]
    UUID(assembly_id)


@pytest.mark.contract
def test_mcp_define_assembly_tool_returns_iserror_for_unknown_family() -> None:
    """FamilyNotFoundForAssemblyError propagates -> FastMCP wraps as isError."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "define_assembly",
                    "arguments": {
                        "name": "Detector",
                        "presents_as_family_id": str(uuid4()),
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
def test_mcp_define_assembly_tool_succeeds_with_slot_and_wire() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        presents_id = _define_family_via_tool(client, headers, "Detector")
        camera_family = _define_family_via_tool(client, headers, "Camera")
        trigger_family = _define_family_via_tool(client, headers, "TriggerSource")
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "define_assembly",
                    "arguments": {
                        "name": "Microscope",
                        "presents_as_family_id": str(presents_id),
                        "required_slots": [
                            {
                                "slot_name": "camera",
                                "required_family_ids": [str(camera_family)],
                                "cardinality": "Exactly1",
                            },
                            {
                                "slot_name": "trigger_source",
                                "required_family_ids": [str(trigger_family)],
                                "cardinality": "Exactly1",
                            },
                        ],
                        "required_wires": [
                            {
                                "source_slot_name": "trigger_source",
                                "source_port_name": "trigger_out",
                                "target_slot_name": "camera",
                                "target_port_name": "trigger_in",
                            }
                        ],
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False
