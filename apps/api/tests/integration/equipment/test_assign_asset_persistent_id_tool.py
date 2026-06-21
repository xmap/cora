"""Integration tests for the `assign_asset_persistent_id` MCP tool against real Postgres.

Registers the slice's tool on a fresh FastMCP server bound to a
Postgres-backed handler closure, then exercises the registered tool
function directly so the test does not need to stand up a streamable-
http request context. The integration tier owns the end-to-end chain:
MCP tool input parsing through the slice handler through the PersistentIdentifierMinter
port through the Postgres event store. The happy-path and domain-
error mappings are covered here; the wire-protocol envelope (SSE /
JSON-RPC) is the contract-tier suite's concern.

Mirrors the slice E.1 get_asset_pidinst integration suite shape for
seeding (register_asset.bind(deps) + Kernel construction) and the
slice F conftest's `raising_persistent_identifier_minter` fixture for the upstream
mint-failure path.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest
from mcp.server.fastmcp import FastMCP

from cora.equipment.aggregates.asset import (
    AssetNotFoundError,
    AssetPersistentIdAlreadyAssignedError,
    AssetPersistentIdAssignmentForbiddenError,
    AssetTier,
)
from cora.equipment.features import (
    assign_asset_persistent_id,
    decommission_asset,
    register_asset,
)
from cora.equipment.features.assign_asset_persistent_id import AssignAssetPersistentId
from cora.equipment.features.assign_asset_persistent_id.handler import Handler
from cora.equipment.features.decommission_asset import DecommissionAsset
from cora.equipment.features.register_asset import RegisterAsset
from cora.infrastructure.adapters.stub_persistent_identifier_minter import (
    StubPersistentIdentifierMinter,
)
from cora.infrastructure.kernel import Kernel
from cora.shared.identifier import (
    PersistentIdentifier,
    PersistentIdentifierScheme,
)
from cora.shared.ports.persistent_identifier_minter import PersistentIdentifierMintError
from tests.integration._helpers import build_postgres_deps
from tests.integration.equipment.conftest import RaisingPersistentIdentifierMinter

pytestmark = pytest.mark.timeout(60, method="thread")

_NOW = datetime(2026, 6, 5, 12, 0, 0, tzinfo=UTC)
_LATER = datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC)
_PARENT_ID = UUID("01900000-0000-7000-8000-0000ee010000")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    db_pool: asyncpg.Pool,
    *,
    ids: list[UUID] | None = None,
    now: datetime = _NOW,
) -> Kernel:
    return build_postgres_deps(db_pool, ids=ids or [], now=now)


def _attach_persistent_identifier_minter(deps: Kernel, minter: object) -> Kernel:
    """Replicate `wire_equipment`'s BC-local namespace stamp.

    The slice handler reads `deps.equipment.persistent_identifier_minter`; the
    integration helper does not run `wire_equipment`, so the test
    stamps the namespace directly to keep the handler bind path
    Postgres-only without dragging the full Equipment handler bundle
    into the test.
    """
    from types import SimpleNamespace

    object.__setattr__(deps, "equipment", SimpleNamespace(persistent_identifier_minter=minter))
    return deps


class _StubMcpContext:
    """Minimal FastMCP-Context stand-in for outside-request invocation.

    The slice tool's body calls `get_mcp_principal_id(ctx)`, which
    walks `ctx.request_context.request`; raising AttributeError on
    the descriptor makes the helper fall through to
    `SYSTEM_PRINCIPAL_ID`, matching the stdio-transport behavior the
    helper documents.
    """

    @property
    def request_context(self) -> Any:
        raise AttributeError("no request context outside streamable-http")


def _registered_tool_fn(handler: Handler) -> Any:
    mcp = FastMCP("assign-persistent-id-integration")
    assign_asset_persistent_id.tool.register(mcp, get_handler=lambda: handler)
    tools = mcp._tool_manager._tools  # pyright: ignore[reportPrivateUsage]
    return tools["assign_asset_persistent_id"].fn


async def _register_seed_asset(db_pool: asyncpg.Pool, *, asset_id: UUID) -> None:
    deps = _build_deps(db_pool, ids=[asset_id, uuid4()])
    await register_asset.bind(deps)(
        RegisterAsset(
            name="Rotary Stage A",
            tier=AssetTier.DEVICE,
            parent_id=_PARENT_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _decommission_seed_asset(db_pool: asyncpg.Pool, *, asset_id: UUID) -> None:
    deps = _build_deps(db_pool, ids=[uuid4()], now=_LATER)
    await decommission_asset.bind(deps)(
        DecommissionAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.integration
async def test_assign_persistent_id_tool_with_doi_scheme_returns_scheme_and_value(
    db_pool: asyncpg.Pool,
) -> None:
    asset_id = uuid4()
    await _register_seed_asset(db_pool, asset_id=asset_id)
    handler_deps = _attach_persistent_identifier_minter(
        _build_deps(db_pool, ids=[uuid4()]), StubPersistentIdentifierMinter()
    )
    tool_fn = _registered_tool_fn(assign_asset_persistent_id.bind(handler_deps))

    body = await tool_fn(
        _StubMcpContext(),
        asset_id=asset_id,
        scheme=PersistentIdentifierScheme.DOI,
        suffix="APS-2BM-CAM-001",
    )
    assert body == {"scheme": "DOI", "value": "10.0000/cora-stub/APS-2BM-CAM-001"}


@pytest.mark.integration
async def test_assign_persistent_id_tool_with_handle_scheme_returns_handle_prefix(
    db_pool: asyncpg.Pool,
) -> None:
    asset_id = uuid4()
    await _register_seed_asset(db_pool, asset_id=asset_id)
    handler_deps = _attach_persistent_identifier_minter(
        _build_deps(db_pool, ids=[uuid4()]), StubPersistentIdentifierMinter()
    )
    tool_fn = _registered_tool_fn(assign_asset_persistent_id.bind(handler_deps))

    body = await tool_fn(
        _StubMcpContext(),
        asset_id=asset_id,
        scheme=PersistentIdentifierScheme.HANDLE,
        suffix="HZB-rotary-001",
    )
    assert body == {
        "scheme": "Handle",
        "value": "20.500.0000/cora-stub/HZB-rotary-001",
    }


@pytest.mark.integration
async def test_assign_persistent_id_tool_with_no_suffix_creates_uuid_suffix(
    db_pool: asyncpg.Pool,
) -> None:
    asset_id = uuid4()
    await _register_seed_asset(db_pool, asset_id=asset_id)
    handler_deps = _attach_persistent_identifier_minter(
        _build_deps(db_pool, ids=[uuid4()]), StubPersistentIdentifierMinter()
    )
    tool_fn = _registered_tool_fn(assign_asset_persistent_id.bind(handler_deps))

    body = await tool_fn(
        _StubMcpContext(),
        asset_id=asset_id,
        scheme=PersistentIdentifierScheme.DOI,
    )
    assert body["scheme"] == "DOI"
    assert body["value"].startswith("10.0000/cora-stub/")
    # UUID4 string is 36 chars after the trailing slash
    assert len(body["value"].split("/")[-1]) == 36


@pytest.mark.integration
async def test_assign_persistent_id_tool_with_unknown_asset_raises_not_found(
    db_pool: asyncpg.Pool,
) -> None:
    handler_deps = _attach_persistent_identifier_minter(
        _build_deps(db_pool, ids=[uuid4()]), StubPersistentIdentifierMinter()
    )
    tool_fn = _registered_tool_fn(assign_asset_persistent_id.bind(handler_deps))

    with pytest.raises(AssetNotFoundError):
        await tool_fn(
            _StubMcpContext(),
            asset_id=uuid4(),
            scheme=PersistentIdentifierScheme.DOI,
            suffix="ghost-asset",
        )


@pytest.mark.integration
async def test_assign_persistent_id_tool_on_already_assigned_asset_raises_already_assigned(
    db_pool: asyncpg.Pool,
) -> None:
    asset_id = uuid4()
    await _register_seed_asset(db_pool, asset_id=asset_id)
    first_deps = _attach_persistent_identifier_minter(
        _build_deps(db_pool, ids=[uuid4()]), StubPersistentIdentifierMinter()
    )
    first_handler = assign_asset_persistent_id.bind(first_deps)
    await first_handler(
        AssignAssetPersistentId(
            asset_id=asset_id,
            scheme=PersistentIdentifierScheme.DOI,
            suffix="first-mint",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    second_deps = _attach_persistent_identifier_minter(
        _build_deps(db_pool, ids=[uuid4()]), StubPersistentIdentifierMinter()
    )
    tool_fn = _registered_tool_fn(assign_asset_persistent_id.bind(second_deps))
    with pytest.raises(AssetPersistentIdAlreadyAssignedError):
        await tool_fn(
            _StubMcpContext(),
            asset_id=asset_id,
            scheme=PersistentIdentifierScheme.DOI,
            suffix="second-mint",
        )


@pytest.mark.integration
async def test_assign_persistent_id_tool_on_decommissioned_asset_raises_forbidden(
    db_pool: asyncpg.Pool,
) -> None:
    asset_id = uuid4()
    await _register_seed_asset(db_pool, asset_id=asset_id)
    await _decommission_seed_asset(db_pool, asset_id=asset_id)
    handler_deps = _attach_persistent_identifier_minter(
        _build_deps(db_pool, ids=[uuid4()]), StubPersistentIdentifierMinter()
    )
    tool_fn = _registered_tool_fn(assign_asset_persistent_id.bind(handler_deps))

    with pytest.raises(AssetPersistentIdAssignmentForbiddenError):
        await tool_fn(
            _StubMcpContext(),
            asset_id=asset_id,
            scheme=PersistentIdentifierScheme.DOI,
            suffix="retired-asset",
        )


@pytest.mark.integration
async def test_assign_persistent_id_tool_with_raising_minter_raises_mint_error(
    db_pool: asyncpg.Pool,
    raising_persistent_identifier_minter: RaisingPersistentIdentifierMinter,
) -> None:
    asset_id = uuid4()
    await _register_seed_asset(db_pool, asset_id=asset_id)
    handler_deps = _attach_persistent_identifier_minter(
        _build_deps(db_pool, ids=[uuid4()]), raising_persistent_identifier_minter
    )
    tool_fn = _registered_tool_fn(assign_asset_persistent_id.bind(handler_deps))

    with pytest.raises(PersistentIdentifierMintError):
        await tool_fn(
            _StubMcpContext(),
            asset_id=asset_id,
            scheme=PersistentIdentifierScheme.DOI,
            suffix="upstream-fails",
        )


@pytest.mark.integration
async def test_assign_persistent_id_tool_persists_assigned_event_to_event_store(
    db_pool: asyncpg.Pool,
) -> None:
    asset_id = uuid4()
    await _register_seed_asset(db_pool, asset_id=asset_id)
    handler_deps = _attach_persistent_identifier_minter(
        _build_deps(db_pool, ids=[uuid4()]), StubPersistentIdentifierMinter()
    )
    tool_fn = _registered_tool_fn(assign_asset_persistent_id.bind(handler_deps))

    await tool_fn(
        _StubMcpContext(),
        asset_id=asset_id,
        scheme=PersistentIdentifierScheme.DOI,
        suffix="persisted-doi",
    )

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT event_type, payload FROM events "
            "WHERE stream_type = 'Asset' AND stream_id = $1 "
            "ORDER BY version ASC",
            asset_id,
        )
    event_types = [row["event_type"] for row in rows]
    assert "AssetPersistentIdAssigned" in event_types
    import json as _json

    assigned = next(
        _json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"]
        for row in rows
        if row["event_type"] == "AssetPersistentIdAssigned"
    )
    assert assigned["persistent_id_scheme"] == "DOI"
    assert assigned["persistent_id_value"] == "10.0000/cora-stub/persisted-doi"


@pytest.mark.integration
async def test_assign_persistent_id_tool_returned_value_round_trips_through_state(
    db_pool: asyncpg.Pool,
) -> None:
    from cora.equipment.aggregates.asset import load_asset

    asset_id = uuid4()
    await _register_seed_asset(db_pool, asset_id=asset_id)
    handler_deps = _attach_persistent_identifier_minter(
        _build_deps(db_pool, ids=[uuid4()]), StubPersistentIdentifierMinter()
    )
    tool_fn = _registered_tool_fn(assign_asset_persistent_id.bind(handler_deps))

    body = await tool_fn(
        _StubMcpContext(),
        asset_id=asset_id,
        scheme=PersistentIdentifierScheme.DOI,
        suffix="round-trip",
    )

    state = await load_asset(handler_deps.event_store, asset_id)
    assert state is not None
    assert state.persistent_id == PersistentIdentifier(
        scheme=PersistentIdentifierScheme(body["scheme"]),
        value=body["value"],
    )
