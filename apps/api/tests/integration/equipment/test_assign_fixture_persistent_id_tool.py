"""Integration tests for the `assign_fixture_persistent_id` MCP tool against real Postgres.

Registers the slice's tool on a fresh FastMCP server bound to a
Postgres-backed handler closure, then exercises the registered tool
function directly so the test does not need to stand up a streamable-
http request context. The integration tier owns the end-to-end chain:
MCP tool input parsing through the slice handler through the DoiMinter
port through the Postgres event store. The happy-path and domain-
error mappings are covered here; the wire-protocol envelope (SSE /
JSON-RPC) is the contract-tier suite's concern.

Mirrors the Asset slice F `test_assign_asset_persistent_id_tool.py`
MCP registration / invocation pattern. Reuses the Fixture seeding
recipe from `test_get_fixture_pidinst_tool.py` (define_family +
define_model + register_asset + add_asset_family + add_asset_owner +
define_assembly + register_fixture). Reuses the `raising_doi_minter`
fixture from `tests/integration/equipment/conftest.py` for the
upstream mint-failure path.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest
from mcp.server.fastmcp import FastMCP

from cora.equipment.aggregates.assembly import SlotCardinality, SlotName, TemplateSlot
from cora.equipment.aggregates.asset import (
    AssetOwner,
    AssetOwnerContact,
    AssetOwnerIdentifier,
    AssetOwnerIdentifierType,
    AssetOwnerName,
    AssetTier,
)
from cora.equipment.aggregates.fixture import (
    FixtureNotFoundError,
    FixturePersistentIdAlreadyAssignedError,
    SlotAssetBinding,
)
from cora.equipment.aggregates.model import (
    Manufacturer,
    ManufacturerIdentifier,
    ManufacturerIdentifierType,
    ManufacturerName,
)
from cora.equipment.features import (
    add_asset_family,
    add_asset_owner,
    assign_fixture_persistent_id,
    define_assembly,
    define_family,
    define_model,
    register_asset,
    register_fixture,
)
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.add_asset_owner import AddAssetOwner
from cora.equipment.features.assign_fixture_persistent_id import AssignFixturePersistentId
from cora.equipment.features.assign_fixture_persistent_id.handler import Handler
from cora.equipment.features.define_assembly import DefineAssembly
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_model import DefineModel
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.register_fixture import RegisterFixture
from cora.infrastructure.adapters.stub_doi_minter import StubDoiMinter
from cora.infrastructure.kernel import Kernel
from cora.shared.identifier import (
    PersistentIdentifier,
    PersistentIdentifierScheme,
)
from cora.shared.ports.doi_minter import PersistentIdentifierMintError
from tests.integration._equipment_helpers import (
    drain_equipment_projections,
    install_existing_asset_into_fresh_mount,
)
from tests.integration._helpers import build_postgres_deps
from tests.integration.equipment.conftest import RaisingDoiMinter

pytestmark = pytest.mark.timeout(60, method="thread")

_NOW = datetime(2026, 6, 5, 12, 0, 0, tzinfo=UTC)
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


def _attach_doi_minter(deps: Kernel, minter: object) -> Kernel:
    """Replicate `wire_equipment`'s BC-local namespace stamp.

    The slice handler reads `deps.equipment.doi_minter`; the
    integration helper does not run `wire_equipment`, so the test
    stamps the namespace directly to keep the handler bind path
    Postgres-only without dragging the full Equipment handler bundle
    into the test.
    """
    from types import SimpleNamespace

    object.__setattr__(deps, "equipment", SimpleNamespace(doi_minter=minter))
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
    mcp = FastMCP("assign-fixture-persistent-id-integration")
    assign_fixture_persistent_id.tool.register(mcp, get_handler=lambda: handler)
    tools = mcp._tool_manager._tools  # pyright: ignore[reportPrivateUsage]
    return tools["assign_fixture_persistent_id"].fn


def _hzb_owner() -> AssetOwner:
    return AssetOwner(
        name=AssetOwnerName("Helmholtz-Zentrum Berlin"),
        contact=AssetOwnerContact("instrument-data@hzb.de"),
        identifier=AssetOwnerIdentifier("https://ror.org/02aj13c28"),
        identifier_type=AssetOwnerIdentifierType("ROR"),
    )


def _aerotech_manufacturer() -> Manufacturer:
    return Manufacturer(
        name=ManufacturerName("Aerotech"),
        identifier=ManufacturerIdentifier("https://ror.org/04bw7nh07"),
        identifier_type=ManufacturerIdentifierType.ROR,
    )


async def _seed_fixture(db_pool: asyncpg.Pool) -> UUID:
    """Seed a Fixture with one bound Asset carrying owner + model.

    Mirrors `test_get_fixture_pidinst_tool.py::_seed_minted_fixture`
    so the Fixture is in a shape the read-side serializer can publish,
    even though this suite only exercises the write-side assign tool.
    """
    family_deps = _build_deps(db_pool, ids=[uuid4(), uuid4()])
    family_id = await define_family.bind(family_deps)(
        DefineFamily(name="Camera", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)
    deps = _build_deps(
        db_pool,
        ids=[uuid4() for _ in range(20)],
    )
    model_id = await define_model.bind(deps)(
        DefineModel(
            name="ANT130-L",
            manufacturer=_aerotech_manufacturer(),
            part_number="ANT130-L-RM",
            declared_family_ids=frozenset({family_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    asset_id = await register_asset.bind(deps)(
        RegisterAsset(
            name="Camera-1",
            tier=AssetTier.DEVICE,
            parent_id=_PARENT_ID,
            model_id=model_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # INV-4: a Fixture's bindings must be installed in a Mount.
    # Activate + install before the later register_fixture call.
    await install_existing_asset_into_fresh_mount(
        db_pool, now=_NOW, asset_id=asset_id, slot_code=f"02-BM-pidinst-{asset_id}"
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_owner.bind(deps)(
        AddAssetOwner(asset_id=asset_id, owner=_hzb_owner()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assembly_id = await define_assembly.bind(deps)(
        DefineAssembly(
            name="Microscope",
            presents_as=frozenset(),
            required_slots=frozenset(
                {
                    TemplateSlot(
                        slot_name=SlotName("camera"),
                        required_family_ids=frozenset({family_id}),
                        cardinality=SlotCardinality.EXACTLY_1,
                    )
                }
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    fixture_id = await register_fixture.bind(deps)(
        RegisterFixture(
            assembly_id=assembly_id,
            slot_asset_bindings=frozenset(
                {SlotAssetBinding(slot_name="camera", asset_id=asset_id)}
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return fixture_id


@pytest.mark.integration
async def test_assign_fixture_persistent_id_tool_with_doi_scheme_returns_scheme_and_value(
    db_pool: asyncpg.Pool,
) -> None:
    fixture_id = await _seed_fixture(db_pool)
    handler_deps = _attach_doi_minter(_build_deps(db_pool, ids=[uuid4()]), StubDoiMinter())
    tool_fn = _registered_tool_fn(assign_fixture_persistent_id.bind(handler_deps))

    body = await tool_fn(
        _StubMcpContext(),
        fixture_id=fixture_id,
        scheme=PersistentIdentifierScheme.DOI,
        suffix="APS-2BM-FIX-001",
    )
    assert body == {"scheme": "DOI", "value": "10.0000/cora-stub/APS-2BM-FIX-001"}


@pytest.mark.integration
async def test_assign_fixture_persistent_id_tool_with_handle_scheme_returns_handle_prefix(
    db_pool: asyncpg.Pool,
) -> None:
    fixture_id = await _seed_fixture(db_pool)
    handler_deps = _attach_doi_minter(_build_deps(db_pool, ids=[uuid4()]), StubDoiMinter())
    tool_fn = _registered_tool_fn(assign_fixture_persistent_id.bind(handler_deps))

    body = await tool_fn(
        _StubMcpContext(),
        fixture_id=fixture_id,
        scheme=PersistentIdentifierScheme.HANDLE,
        suffix="HZB-fixture-001",
    )
    assert body == {
        "scheme": "Handle",
        "value": "20.500.0000/cora-stub/HZB-fixture-001",
    }


@pytest.mark.integration
async def test_assign_fixture_persistent_id_tool_with_no_suffix_creates_uuid_suffix(
    db_pool: asyncpg.Pool,
) -> None:
    fixture_id = await _seed_fixture(db_pool)
    handler_deps = _attach_doi_minter(_build_deps(db_pool, ids=[uuid4()]), StubDoiMinter())
    tool_fn = _registered_tool_fn(assign_fixture_persistent_id.bind(handler_deps))

    body = await tool_fn(
        _StubMcpContext(),
        fixture_id=fixture_id,
        scheme=PersistentIdentifierScheme.DOI,
    )
    assert body["scheme"] == "DOI"
    assert body["value"].startswith("10.0000/cora-stub/")
    # UUID4 string is 36 chars after the trailing slash
    assert len(body["value"].split("/")[-1]) == 36


@pytest.mark.integration
async def test_assign_fixture_persistent_id_tool_with_unknown_fixture_raises_not_found(
    db_pool: asyncpg.Pool,
) -> None:
    handler_deps = _attach_doi_minter(_build_deps(db_pool, ids=[uuid4()]), StubDoiMinter())
    tool_fn = _registered_tool_fn(assign_fixture_persistent_id.bind(handler_deps))

    with pytest.raises(FixtureNotFoundError):
        await tool_fn(
            _StubMcpContext(),
            fixture_id=uuid4(),
            scheme=PersistentIdentifierScheme.DOI,
            suffix="ghost-fixture",
        )


@pytest.mark.integration
async def test_assign_fixture_pid_tool_on_already_assigned_fixture_raises_already_assigned(
    db_pool: asyncpg.Pool,
) -> None:
    fixture_id = await _seed_fixture(db_pool)
    first_deps = _attach_doi_minter(_build_deps(db_pool, ids=[uuid4()]), StubDoiMinter())
    first_handler = assign_fixture_persistent_id.bind(first_deps)
    await first_handler(
        AssignFixturePersistentId(
            fixture_id=fixture_id,
            scheme=PersistentIdentifierScheme.DOI,
            suffix="first-mint",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    second_deps = _attach_doi_minter(_build_deps(db_pool, ids=[uuid4()]), StubDoiMinter())
    tool_fn = _registered_tool_fn(assign_fixture_persistent_id.bind(second_deps))
    with pytest.raises(FixturePersistentIdAlreadyAssignedError):
        await tool_fn(
            _StubMcpContext(),
            fixture_id=fixture_id,
            scheme=PersistentIdentifierScheme.DOI,
            suffix="second-mint",
        )


@pytest.mark.integration
async def test_assign_fixture_persistent_id_tool_with_raising_minter_raises_mint_error(
    db_pool: asyncpg.Pool,
    raising_doi_minter: RaisingDoiMinter,
) -> None:
    fixture_id = await _seed_fixture(db_pool)
    handler_deps = _attach_doi_minter(_build_deps(db_pool, ids=[uuid4()]), raising_doi_minter)
    tool_fn = _registered_tool_fn(assign_fixture_persistent_id.bind(handler_deps))

    with pytest.raises(PersistentIdentifierMintError):
        await tool_fn(
            _StubMcpContext(),
            fixture_id=fixture_id,
            scheme=PersistentIdentifierScheme.DOI,
            suffix="upstream-fails",
        )


@pytest.mark.integration
async def test_assign_fixture_persistent_id_tool_persists_assigned_event_to_event_store(
    db_pool: asyncpg.Pool,
) -> None:
    fixture_id = await _seed_fixture(db_pool)
    handler_deps = _attach_doi_minter(_build_deps(db_pool, ids=[uuid4()]), StubDoiMinter())
    tool_fn = _registered_tool_fn(assign_fixture_persistent_id.bind(handler_deps))

    await tool_fn(
        _StubMcpContext(),
        fixture_id=fixture_id,
        scheme=PersistentIdentifierScheme.DOI,
        suffix="persisted-doi",
    )

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT event_type, payload FROM events "
            "WHERE stream_type = 'Fixture' AND stream_id = $1 "
            "ORDER BY version ASC",
            fixture_id,
        )
    event_types = [row["event_type"] for row in rows]
    assert "FixturePersistentIdAssigned" in event_types
    import json as _json

    assigned = next(
        _json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"]
        for row in rows
        if row["event_type"] == "FixturePersistentIdAssigned"
    )
    assert assigned["persistent_id_scheme"] == "DOI"
    assert assigned["persistent_id_value"] == "10.0000/cora-stub/persisted-doi"


@pytest.mark.integration
async def test_assign_fixture_persistent_id_tool_returned_value_round_trips_through_state(
    db_pool: asyncpg.Pool,
) -> None:
    from cora.equipment.aggregates.fixture import load_fixture

    fixture_id = await _seed_fixture(db_pool)
    handler_deps = _attach_doi_minter(_build_deps(db_pool, ids=[uuid4()]), StubDoiMinter())
    tool_fn = _registered_tool_fn(assign_fixture_persistent_id.bind(handler_deps))

    body = await tool_fn(
        _StubMcpContext(),
        fixture_id=fixture_id,
        scheme=PersistentIdentifierScheme.DOI,
        suffix="round-trip",
    )

    state = await load_fixture(handler_deps.event_store, fixture_id)
    assert state is not None
    assert state.persistent_id == PersistentIdentifier(
        scheme=PersistentIdentifierScheme(body["scheme"]),
        value=body["value"],
    )
