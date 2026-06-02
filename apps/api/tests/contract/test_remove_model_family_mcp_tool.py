"""Contract tests for the `remove_model_family` MCP tool.

Shared MCP helpers live in `tests/contract/_mcp_helpers.py`.

Unlike `add_model_family`, this slice performs NO cross-BC Family
lookup, so the failure shapes pinned at the MCP wire are:

  - missing argument -> isError: true (Pydantic schema validation)
  - present model + absent family -> isError: true ("does not declare")
  - missing model stream -> isError: true ("not found")

The seeding `define_model` call still needs `list_all_family_ids`
stubbed so we can seed a real model via REST in the same TestClient
before invoking the MCP tool.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data

_FIXED_FAMILY_ID = UUID("01900000-0000-7000-8000-00000000fe01")


def _stub_define_model_family_lookup(
    monkeypatch: pytest.MonkeyPatch,
    family_ids: list[UUID],
) -> None:
    async def _stub(_pool: object) -> list[UUID]:
        return list(family_ids)

    monkeypatch.setattr(
        "cora.equipment.features.define_model.handler.list_all_family_ids",
        _stub,
    )


def _seed_model_via_rest(client: TestClient) -> UUID:
    response = client.post(
        "/models",
        json={
            "name": "ANT130-L",
            "manufacturer": {"name": "Aerotech"},
            "part_number": "ANT130-L",
            "declared_families": [str(_FIXED_FAMILY_ID)],
        },
    )
    assert response.status_code == 201
    return UUID(response.json()["model_id"])


@pytest.mark.contract
def test_mcp_lists_remove_model_family_tool() -> None:
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
    assert "remove_model_family" in tool_names


@pytest.mark.contract
def test_mcp_remove_model_family_tool_description_matches_spec() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    tools_by_name = {t["name"]: t for t in body["result"]["tools"]}
    remove_model_family = tools_by_name["remove_model_family"]
    description = remove_model_family["description"]
    assert "Family" in description
    assert "vendor-catalog Model" in description
    assert "declared_families" in description
    assert "Strict-not-idempotent" in description


@pytest.mark.contract
def test_mcp_remove_model_family_tool_rejects_missing_argument() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "remove_model_family",
                    "arguments": {"model_id": str(uuid4())},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_remove_model_family_tool_returns_iserror_on_absent_family(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Strict-not-idempotent: removing a family not in declared_families
    raises ModelFamilyNotPresentError, which FastMCP wraps as
    isError: true with a 'does not declare' diagnostic."""
    _stub_define_model_family_lookup(monkeypatch, [_FIXED_FAMILY_ID])
    absent_family_id = uuid4()
    with TestClient(create_app()) as client:
        model_id = _seed_model_via_rest(client)
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "remove_model_family",
                    "arguments": {
                        "model_id": str(model_id),
                        "family_id": str(absent_family_id),
                    },
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is True
    assert "does not declare" in result["content"][0]["text"]


@pytest.mark.contract
def test_mcp_remove_model_family_tool_returns_iserror_on_unknown_model() -> None:
    """Missing model stream surfaces ModelNotFoundError, which FastMCP
    wraps as isError: true with a 'not found' diagnostic. No cross-BC
    lookup runs, so no stub is needed."""
    missing_model_id = uuid4()
    missing_family_id = uuid4()
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "remove_model_family",
                    "arguments": {
                        "model_id": str(missing_model_id),
                        "family_id": str(missing_family_id),
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
