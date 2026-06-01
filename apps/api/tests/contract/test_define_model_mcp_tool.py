"""Contract tests for the `define_model` MCP tool.

Shared MCP helpers live in `tests/contract/_mcp_helpers.py`.

In-memory contract harness has no Postgres pool, so the cross-BC
`list_family_ids` lookup returns `[]` and every `define_model` call
surfaces `FamilyNotFoundError`. The structured-output happy path is
pinned at the integration tier (see `tests/integration/equipment/`);
this file pins the MCP-wire shape: tool registration, description,
structured-output schema (declares `model_id`), and the failure
branches reachable without a database.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


@pytest.mark.contract
def test_mcp_lists_define_model_tool() -> None:
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
    assert "define_model" in tool_names


@pytest.mark.contract
def test_mcp_define_model_tool_description_matches_vendor_catalog_spec() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    tools_by_name = {t["name"]: t for t in body["result"]["tools"]}
    define_model = tools_by_name["define_model"]
    description = define_model["description"]
    assert "vendor-catalog Model" in description
    assert "manufacturer" in description
    assert "part number" in description
    assert "Family" in description


@pytest.mark.contract
def test_mcp_define_model_tool_advertises_model_id_in_output_schema() -> None:
    """Pin the structured-output schema: DefineModelOutput.model_id is on the
    wire. The actual happy-path emission of a model_id value requires a
    Postgres pool (cross-BC family_lookup), so it is covered at the
    integration tier; here we verify the schema contract."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 4, "method": "tools/list"},
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    tools_by_name = {t["name"]: t for t in body["result"]["tools"]}
    define_model = tools_by_name["define_model"]
    output_schema = define_model["outputSchema"]
    assert "model_id" in output_schema["properties"]
    assert output_schema["properties"]["model_id"]["format"] == "uuid"
    assert "model_id" in output_schema["required"]


@pytest.mark.contract
def test_mcp_define_model_tool_rejects_missing_argument() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "define_model",
                    "arguments": {},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_define_model_tool_returns_iserror_on_unregistered_family() -> None:
    """Cross-BC check: declared_families must resolve to a registered Family.
    An unknown family id surfaces FamilyNotFoundError, which FastMCP wraps as
    isError: true with a 'not found' diagnostic (same shape as the REST 404).
    """
    unknown_family_id = str(uuid4())
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "define_model",
                    "arguments": {
                        "name": "ANT130-L",
                        "manufacturer": {"name": "Aerotech"},
                        "part_number": "ANT130-L",
                        "declared_families": [unknown_family_id],
                    },
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is True
    assert "not found" in result["content"][0]["text"].lower()
