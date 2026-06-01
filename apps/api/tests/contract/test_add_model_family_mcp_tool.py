"""Contract tests for the `add_model_family` MCP tool.

Shared MCP helpers live in `tests/contract/_mcp_helpers.py`.

In-memory contract harness has no Postgres pool, so the cross-BC
`list_family_ids` lookup returns `[]` and every `add_model_family`
call surfaces `FamilyNotFoundError` before the decider runs. The
happy path is pinned at the integration tier; this file pins the
MCP-wire shape: tool registration, description spec, and the failure
branches reachable without a database.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


@pytest.mark.contract
def test_mcp_lists_add_model_family_tool() -> None:
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
    assert "add_model_family" in tool_names


@pytest.mark.contract
def test_mcp_add_model_family_tool_description_matches_spec() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    tools_by_name = {t["name"]: t for t in body["result"]["tools"]}
    add_model_family = tools_by_name["add_model_family"]
    description = add_model_family["description"]
    assert "Family" in description
    assert "vendor-catalog Model" in description
    assert "declared_families" in description
    assert "Strict-not-idempotent" in description


@pytest.mark.contract
def test_mcp_add_model_family_tool_rejects_missing_argument() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "add_model_family",
                    "arguments": {"model_id": str(uuid4())},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_add_model_family_tool_returns_iserror_on_unregistered_family() -> None:
    """Cross-BC check: family_id must resolve to a registered Family.
    In-memory harness has no Family registry, so any family_id surfaces
    FamilyNotFoundError, which FastMCP wraps as isError: true with a
    'not found' diagnostic (same shape as the REST 404)."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "add_model_family",
                    "arguments": {
                        "model_id": str(uuid4()),
                        "family_id": str(uuid4()),
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


@pytest.mark.contract
def test_mcp_add_model_family_tool_returns_iserror_on_unknown_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Family is registered but the model stream is missing; the handler
    raises ModelNotFoundError after the cross-BC lookup succeeds. FastMCP
    wraps that as isError: true with a 'not found' diagnostic."""
    fake_family_id = uuid4()

    async def _stub(_pool: object) -> list[UUID]:
        return [fake_family_id]

    monkeypatch.setattr(
        "cora.equipment.features.add_model_family.handler.list_family_ids",
        _stub,
    )
    missing_model_id = uuid4()
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "add_model_family",
                    "arguments": {
                        "model_id": str(missing_model_id),
                        "family_id": str(fake_family_id),
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
