"""Contract tests for the `get_model` MCP tool.

Mirrors `test_get_family_mcp_tool.py`. Shared MCP helpers live in
`tests/contract/_mcp_helpers.py`. The Model upstream `define_model`
tool enforces a cross-BC `list_all_family_ids` precondition that is
pool-backed and returns `[]` in the in-memory harness; we
monkeypatch the upstream handler's binding so the seed tool call
succeeds.
"""

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data

_FIXED_FAMILY_ID = UUID("01900000-0000-7000-8000-00000000fa01")


@pytest.fixture
def accept_family(monkeypatch: pytest.MonkeyPatch) -> Iterator[UUID]:
    async def _stub(_pool: object) -> list[UUID]:
        return [_FIXED_FAMILY_ID]

    monkeypatch.setattr(
        "cora.equipment.features.define_model.handler.list_all_family_ids",
        _stub,
    )
    yield _FIXED_FAMILY_ID


def _define_model_via_tool(client: TestClient, headers: dict[str, str]) -> UUID:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "define_model",
                "arguments": {
                    "name": "Aerotech ANT130-L",
                    "manufacturer": {"name": "Aerotech"},
                    "part_number": "ANT130-L",
                    "declared_families": [str(_FIXED_FAMILY_ID)],
                },
            },
        },
        headers=headers,
    )
    body = parse_sse_data(response.text)
    return UUID(body["result"]["structuredContent"]["model_id"])


@pytest.mark.contract
def test_mcp_lists_get_model_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "get_model" in tool_names


@pytest.mark.contract
def test_mcp_get_model_tool_returns_structured_model_for_known_id(
    accept_family: UUID,
) -> None:
    _ = accept_family
    with TestClient(create_app()) as client:
        headers = open_session(client)
        model_id = _define_model_via_tool(client, headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "get_model",
                    "arguments": {"model_id": str(model_id)},
                },
            },
            headers=headers,
        )

    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    structured = result["structuredContent"]
    assert structured["model_id"] == str(model_id)
    assert structured["name"] == "Aerotech ANT130-L"
    assert structured["manufacturer"] == {
        "name": "Aerotech",
        "identifier": None,
        "identifier_type": None,
    }
    assert structured["part_number"] == "ANT130-L"
    assert structured["declared_families"] == [str(_FIXED_FAMILY_ID)]
    assert structured["status"] == "Defined"
    # Null until version_model runs (no initial version_tag supplied).
    assert structured["version_tag"] is None


@pytest.mark.contract
def test_mcp_get_model_tool_returns_iserror_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "get_model",
                    "arguments": {"model_id": str(uuid4())},
                },
            },
            headers=headers,
        )

    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()


@pytest.mark.contract
def test_mcp_get_model_tool_rejects_missing_argument() -> None:
    """Calling `get_model` without `model_id` raises Pydantic input
    validation, which FastMCP wraps as `isError: true`."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "get_model",
                    "arguments": {},
                },
            },
            headers=headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
