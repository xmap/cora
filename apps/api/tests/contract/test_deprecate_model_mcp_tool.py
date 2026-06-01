"""Contract tests for the `deprecate_model` MCP tool.

In-memory contract harness has no Postgres pool, so happy-path
deprecation end-to-end requires seeding a Model first. We exercise:
- tool registration (the tool appears in `tools/list`)
- description matches the authoring-signal spec
- missing-argument call surfaces `isError: true`
- unknown `model_id` surfaces `ModelNotFoundError` as `isError: true`
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


@pytest.mark.contract
def test_mcp_lists_deprecate_model_tool() -> None:
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
    assert "deprecate_model" in tool_names


@pytest.mark.contract
def test_mcp_deprecate_model_tool_description_matches_authoring_spec() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    tools_by_name = {t["name"]: t for t in body["result"]["tools"]}
    deprecate_model = tools_by_name["deprecate_model"]
    description = deprecate_model["description"]
    assert "vendor-catalog Model" in description
    assert "authoring signal" in description
    assert "Assets" in description


@pytest.mark.contract
def test_mcp_deprecate_model_tool_rejects_missing_argument() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "deprecate_model",
                    "arguments": {},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_deprecate_model_tool_returns_iserror_for_unknown_model() -> None:
    unknown_id = str(uuid4())
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "deprecate_model",
                    "arguments": {
                        "model_id": unknown_id,
                        "reason": "Vendor EOL 2026-Q3",
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
