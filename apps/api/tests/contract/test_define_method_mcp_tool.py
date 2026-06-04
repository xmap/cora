"""Contract tests for the `define_method` MCP tool.

Mirrors `test_define_family_mcp_tool.py`. Adds a pin that the
needed_family_ids argument round-trips through the MCP boundary
(pydantic UUID list serialization) — the first MCP tool in the
codebase to take a list-of-UUIDs argument.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._helpers import create_capability_via_api
from tests.contract._mcp_helpers import open_session, parse_sse_data


@pytest.mark.contract
def test_mcp_lists_define_method_tool() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "define_method" in tool_names


@pytest.mark.contract
def test_mcp_define_method_tool_returns_structured_method_id() -> None:
    cap1 = str(uuid4())
    with TestClient(create_app()) as client:
        cap_id = create_capability_via_api(client)
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "define_method",
                    "arguments": {
                        "name": "XRF Mapping",
                        "capability_id": cap_id,
                        "needed_family_ids": [cap1],
                    },
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    assert "method_id" in result["structuredContent"]
    UUID(result["structuredContent"]["method_id"])  # parses


@pytest.mark.contract
def test_mcp_define_method_tool_accepts_empty_needed_family_ids() -> None:
    """Procedural Method via MCP."""
    with TestClient(create_app()) as client:
        cap_id = create_capability_via_api(client)
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "define_method",
                    "arguments": {
                        "name": "Sample Cleaning",
                        "capability_id": cap_id,
                        "needed_family_ids": [],
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_define_method_tool_accepts_needed_assembly_ids() -> None:
    """needed_assembly_ids is OPTIONAL on the MCP tool and round-trips
    as a list of UUID strings through the MCP boundary."""
    asm_id = str(uuid4())
    with TestClient(create_app()) as client:
        cap_id = create_capability_via_api(client)
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "define_method",
                    "arguments": {
                        "name": "MCTOptics Tomography",
                        "capability_id": cap_id,
                        "needed_family_ids": [],
                        "needed_assembly_ids": [asm_id],
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_define_method_tool_returns_iserror_on_invalid_input() -> None:
    """Whitespace-only name passes Pydantic min_length=1 but trips
    the domain VO; FastMCP wraps the raised InvalidMethodNameError as
    isError: true with a text diagnostic."""
    with TestClient(create_app()) as client:
        cap_id = create_capability_via_api(client)
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "define_method",
                    "arguments": {
                        "name": "   ",
                        "capability_id": cap_id,
                        "needed_family_ids": [],
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is True
    assert "Method name" in result["content"][0]["text"]


@pytest.mark.contract
def test_mcp_define_method_tool_rejects_missing_arguments() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "define_method",
                    "arguments": {},
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
