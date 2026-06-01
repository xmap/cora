"""Contract tests for the `version_model` MCP tool.

In-memory contract harness has no Postgres pool, so happy-path
versioning end-to-end requires seeding a Model first. We exercise:
- tool registration (the tool appears in `tools/list`)
- description matches the wholesale-replacement spec
- missing-argument call surfaces `isError: true`
- unknown `model_id` surfaces `ModelNotFoundError` as `isError: true`
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


@pytest.mark.contract
def test_mcp_lists_version_model_tool() -> None:
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
    assert "version_model" in tool_names


@pytest.mark.contract
def test_mcp_version_model_tool_description_matches_replacement_spec() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    tools_by_name = {t["name"]: t for t in body["result"]["tools"]}
    version_model = tools_by_name["version_model"]
    description = version_model["description"]
    assert "vendor-catalog Model" in description
    assert "Deprecated" in description
    assert "REPLACE" in description


@pytest.mark.contract
def test_mcp_version_model_tool_rejects_missing_argument() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "version_model",
                    "arguments": {},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_version_model_tool_returns_iserror_for_unknown_model() -> None:
    unknown_id = str(uuid4())
    family_id = str(uuid4())
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "version_model",
                    "arguments": {
                        "model_id": unknown_id,
                        "name": "ANT130-L rev-B",
                        "manufacturer": {"name": "Aerotech"},
                        "part_number": "ANT130-L-B",
                        "declared_families": [family_id],
                        "version_tag": "v2",
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
