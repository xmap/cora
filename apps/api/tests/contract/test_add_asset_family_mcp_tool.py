"""Contract tests for the `add_asset_family` MCP tool.

Mirrors `test_relocate_asset_mcp_tool.py` (also two-id-arg).
"""

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.aggregates.asset.events import AssetRegistered
from cora.equipment.aggregates.asset.events import (
    event_type_name as asset_event_type_name,
)
from cora.equipment.aggregates.asset.events import to_payload as asset_to_payload
from cora.equipment.aggregates.model.events import ModelDefined
from cora.equipment.aggregates.model.events import (
    event_type_name as model_event_type_name,
)
from cora.equipment.aggregates.model.events import to_payload as model_to_payload
from cora.equipment.aggregates.model.state import (
    Manufacturer,
    ManufacturerName,
)
from cora.infrastructure.event_envelope import to_new_event
from cora.shared.identity import ActorId
from tests.contract._mcp_helpers import open_session, parse_sse_data

_SEED_NOW = datetime(2026, 5, 10, 11, 0, 0, tzinfo=UTC)
_SEED_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_SEED_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")


async def _seed_model_with_declared_family_ids(
    app: FastAPI,
    *,
    model_id: UUID,
    declared_family_ids: frozenset[UUID],
) -> None:
    """Append a `ModelDefined` event with `declared_family_ids` set
    directly via the app's wired kernel; mirrors the REST endpoint
    test's seeder."""
    deps = app.state.deps
    event = ModelDefined(
        model_id=model_id,
        name="Aerotech ANT130-L",
        manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
        part_number="ANT130-L",
        declared_family_ids=declared_family_ids,
        occurred_at=_SEED_NOW,
    )
    new_event = to_new_event(
        event_type=model_event_type_name(event),
        payload=model_to_payload(event),
        occurred_at=_SEED_NOW,
        event_id=uuid4(),
        command_name="DefineModel",
        correlation_id=_SEED_CORRELATION_ID,
        principal_id=_SEED_PRINCIPAL_ID,
    )
    await deps.event_store.append(
        stream_type="Model",
        stream_id=model_id,
        expected_version=0,
        events=[new_event],
    )


async def _seed_asset_bound_to_model(
    app: FastAPI,
    *,
    asset_id: UUID,
    model_id: UUID,
) -> None:
    """Append an `AssetRegistered` event with `model_id` set directly.

    The current `register_asset` tool does not yet accept `model_id`;
    the MCP contract test for the cross-BC subset gate seeds the
    Asset's genesis event via the event store, same shape as the
    REST endpoint test."""
    deps = app.state.deps
    registered = AssetRegistered(
        asset_id=asset_id,
        name="APS-2BM",
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        occurred_at=_SEED_NOW,
        model_id=model_id,
        commissioned_by=ActorId(uuid4()),
    )
    new_event = to_new_event(
        event_type=asset_event_type_name(registered),
        payload=asset_to_payload(registered),
        occurred_at=_SEED_NOW,
        event_id=uuid4(),
        command_name="RegisterAsset",
        correlation_id=_SEED_CORRELATION_ID,
        principal_id=_SEED_PRINCIPAL_ID,
    )
    await deps.event_store.append(
        stream_type="Asset",
        stream_id=asset_id,
        expected_version=0,
        events=[new_event],
    )


def _register_asset_via_tool(
    client: TestClient,
    headers: dict[str, str],
) -> UUID:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "register_asset",
                "arguments": {
                    "name": "APS-2BM",
                    "tier": "Unit",
                    "parent_id": str(uuid4()),
                },
            },
        },
        headers=headers,
    )
    body = parse_sse_data(response.text)
    return UUID(body["result"]["structuredContent"]["asset_id"])


@pytest.mark.contract
def test_mcp_lists_add_asset_family_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "add_asset_family" in tool_names


@pytest.mark.contract
def test_mcp_add_asset_family_tool_succeeds_on_happy_path() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        asset_id = _register_asset_via_tool(client, headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "add_asset_family",
                    "arguments": {
                        "asset_id": str(asset_id),
                        "family_id": str(uuid4()),
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_add_asset_family_tool_returns_iserror_for_unknown_asset() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "add_asset_family",
                    "arguments": {
                        "asset_id": str(uuid4()),
                        "family_id": str(uuid4()),
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()


@pytest.mark.contract
def test_mcp_add_asset_family_tool_returns_iserror_when_already_present() -> None:
    cap = str(uuid4())
    with TestClient(create_app()) as client:
        headers = open_session(client)
        asset_id = _register_asset_via_tool(client, headers)
        first = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "add_asset_family",
                    "arguments": {"asset_id": str(asset_id), "family_id": cap},
                },
            },
            headers=headers,
        )
        assert parse_sse_data(first.text)["result"]["isError"] is False
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {
                    "name": "add_asset_family",
                    "arguments": {"asset_id": str(asset_id), "family_id": cap},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "already" in body["result"]["content"][0]["text"]


@pytest.mark.contract
def test_mcp_add_asset_family_tool_returns_iserror_when_asset_model_mismatch() -> None:
    """Cross-BC subset gate: an Asset bound to a Model whose
    `declared_family_ids` are not satisfied by the post-add Asset
    family set raises `AssetModelMismatchError`, surfaced as
    `isError: true` with the bound model_id in the error text."""
    asset_id = UUID("01900000-0000-7000-8000-0000000e0e01")
    model_id = UUID("01900000-0000-7000-8000-0000000e0e02")
    declared_a = UUID("01900000-0000-7000-8000-0000000e0e03")
    declared_b = UUID("01900000-0000-7000-8000-0000000e0e04")
    family_to_add = declared_a

    app = create_app()
    with TestClient(app) as client:
        asyncio.run(
            _seed_model_with_declared_family_ids(
                app,
                model_id=model_id,
                declared_family_ids=frozenset({declared_a, declared_b}),
            )
        )
        asyncio.run(_seed_asset_bound_to_model(app, asset_id=asset_id, model_id=model_id))

        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 8,
                "method": "tools/call",
                "params": {
                    "name": "add_asset_family",
                    "arguments": {
                        "asset_id": str(asset_id),
                        "family_id": str(family_to_add),
                    },
                },
            },
            headers=headers,
        )

    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    text = body["result"]["content"][0]["text"]
    assert str(model_id) in text
    assert str(asset_id) in text
