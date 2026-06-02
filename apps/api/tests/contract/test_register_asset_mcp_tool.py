"""Contract tests for the `register_asset` MCP tool.

Shared MCP helpers live in `tests/contract/_mcp_helpers.py`.

The `model_id`-arg cases monkeypatch `load_model` in the handler's
namespace so the cross-BC Model existence check resolves without
seeding the upstream Model stream.
"""

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.equipment.aggregates.model import (
    Manufacturer,
    ManufacturerName,
    Model,
    ModelName,
    PartNumber,
)
from tests.contract._mcp_helpers import open_session, parse_sse_data


@pytest.mark.contract
def test_mcp_lists_register_asset_tool() -> None:
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
    assert "register_asset" in tool_names


@pytest.mark.contract
def test_mcp_register_asset_tool_returns_structured_asset_id_for_enterprise_root() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "register_asset",
                    "arguments": {
                        "name": "ANL",
                        "level": "Enterprise",
                        "parent_id": None,
                    },
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    assert "asset_id" in result["structuredContent"]
    UUID(result["structuredContent"]["asset_id"])  # parses


@pytest.mark.contract
def test_mcp_register_asset_tool_returns_structured_asset_id_for_site_with_parent() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "register_asset",
                    "arguments": {
                        "name": "APS",
                        "level": "Site",
                        "parent_id": str(uuid4()),
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_register_asset_tool_returns_iserror_on_invalid_name() -> None:
    """Whitespace-only name passes Pydantic min_length=1 but trips
    the domain VO; FastMCP wraps the raised InvalidAssetNameError as
    isError: true with a text diagnostic."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "register_asset",
                    "arguments": {
                        "name": "   ",
                        "level": "Site",
                        "parent_id": str(uuid4()),
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is True
    assert "Asset name" in result["content"][0]["text"]


@pytest.mark.contract
def test_mcp_register_asset_tool_returns_iserror_on_hierarchy_violation() -> None:
    """Enterprise with non-null parent → InvalidAssetParentError →
    FastMCP isError. Same shape as the REST 400 response."""
    parent_id = str(uuid4())
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "register_asset",
                    "arguments": {
                        "name": "Federated",
                        "level": "Enterprise",
                        "parent_id": parent_id,
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is True
    assert "Enterprise" in result["content"][0]["text"]


@pytest.mark.contract
def test_mcp_register_asset_tool_rejects_unknown_level() -> None:
    """FastMCP's argument schema enforces the StrEnum vocabulary;
    unknown levels surface as isError before the handler runs."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {
                    "name": "register_asset",
                    "arguments": {
                        "name": "X",
                        "level": "Beamline",
                        "parent_id": str(uuid4()),
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_register_asset_tool_rejects_missing_arguments() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 8,
                "method": "tools/call",
                "params": {
                    "name": "register_asset",
                    "arguments": {},
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


# ---------- model_id arg (asset-model binding slice) ----------


_KNOWN_MODEL_ID = UUID("01900000-0000-7000-8000-00000000ad02")
_KNOWN_FAMILY_ID = UUID("01900000-0000-7000-8000-00000000fa22")


@pytest.fixture
def accept_model_mcp(monkeypatch: pytest.MonkeyPatch) -> Iterator[UUID]:
    """Stub `load_model` so `_KNOWN_MODEL_ID` resolves to a real Model."""

    async def _stub(_event_store: object, requested_id: UUID) -> Model | None:
        if requested_id == _KNOWN_MODEL_ID:
            return Model(
                id=requested_id,
                name=ModelName("EigerX-9M"),
                manufacturer=Manufacturer(name=ManufacturerName("Dectris")),
                part_number=PartNumber("EX9M-002"),
                declared_families=frozenset({_KNOWN_FAMILY_ID}),
            )
        return None

    monkeypatch.setattr(
        "cora.equipment.features.register_asset.handler.load_model",
        _stub,
    )
    yield _KNOWN_MODEL_ID


@pytest.mark.contract
def test_mcp_register_asset_tool_accepts_model_id_arg(accept_model_mcp: UUID) -> None:
    """Happy path: model_id arg referencing a real Model returns
    structured asset_id."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 9,
                "method": "tools/call",
                "params": {
                    "name": "register_asset",
                    "arguments": {
                        "name": "APS-2BM-Det",
                        "level": "Device",
                        "parent_id": str(uuid4()),
                        "model_id": str(accept_model_mcp),
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    UUID(result["structuredContent"]["asset_id"])  # parses


@pytest.mark.contract
def test_mcp_register_asset_tool_returns_iserror_on_unknown_model_id(
    accept_model_mcp: UUID,
) -> None:
    """A model_id that does not resolve surfaces ModelNotFoundError;
    FastMCP wraps it as isError: true."""
    _ = accept_model_mcp  # fixture stub returns None for any other id
    unknown_id = UUID("01900000-0000-7000-8000-00000000def2")
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 10,
                "method": "tools/call",
                "params": {
                    "name": "register_asset",
                    "arguments": {
                        "name": "APS-2BM-Det",
                        "level": "Device",
                        "parent_id": str(uuid4()),
                        "model_id": str(unknown_id),
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is True


@pytest.mark.contract
def test_mcp_register_asset_tool_omits_model_id_arg_remains_201_path() -> None:
    """Forward-compat: callers that omit model_id continue to work.
    The arg defaults to None and the handler never invokes load_model."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 11,
                "method": "tools/call",
                "params": {
                    "name": "register_asset",
                    "arguments": {
                        "name": "APS",
                        "level": "Site",
                        "parent_id": str(uuid4()),
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    UUID(result["structuredContent"]["asset_id"])  # parses
