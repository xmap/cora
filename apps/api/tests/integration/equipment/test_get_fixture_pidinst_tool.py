"""Integration tests for the `get_fixture_pidinst` MCP tool against real Postgres.

Registers the slice's tool on a fresh FastMCP server bound to a
Postgres-backed handler closure, then exercises the registered tool
function directly so the test does not need to stand up a streamable-
http request context. The integration tier owns the end-to-end chain:
MCP tool input parsing through the slice handler through the
event-replay view assembler through the Fixture-tier serializer
against the Postgres event store. The wire-protocol envelope
(SSE / JSON-RPC) is the contract-tier suite's concern.

Mirrors the slice F `test_assign_asset_persistent_id_tool.py` MCP
registration / invocation pattern and the slice F
`test_get_asset_pidinst_with_persistent_id.py` Fixture-style seeding
(define_family + define_model + register_asset + add_asset_family +
add_asset_owner + define_assembly + register_fixture). Read-side
slice of project_fixture_pidinst_design Section 15.5: MCP tool
integration coverage.
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
    AssetLevel,
    AssetOwner,
    AssetOwnerContact,
    AssetOwnerIdentifier,
    AssetOwnerIdentifierType,
    AssetOwnerName,
)
from cora.equipment.aggregates.fixture import FixtureNotFoundError, SlotAssetBinding
from cora.equipment.aggregates.model import (
    Manufacturer,
    ManufacturerIdentifier,
    ManufacturerIdentifierType,
    ManufacturerName,
)
from cora.equipment.features import (
    add_asset_family,
    add_asset_owner,
    define_assembly,
    define_family,
    define_model,
    get_fixture_pidinst,
    register_asset,
    register_fixture,
)
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.add_asset_owner import AddAssetOwner
from cora.equipment.features.define_assembly import DefineAssembly
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_model import DefineModel
from cora.equipment.features.get_fixture_pidinst.handler import Handler
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.register_fixture import RegisterFixture
from cora.infrastructure.kernel import Kernel
from tests.integration._equipment_helpers import (
    drain_equipment_projections,
    install_existing_asset_into_fresh_mount,
)
from tests.integration._helpers import build_postgres_deps

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
    mcp = FastMCP("get-fixture-pidinst-integration")
    get_fixture_pidinst.tool.register(mcp, get_handler=lambda: handler)
    tools = mcp._tool_manager._tools  # pyright: ignore[reportPrivateUsage]
    return tools["get_fixture_pidinst"].fn


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


async def _seed_minted_fixture(db_pool: asyncpg.Pool) -> UUID:
    """Seed a Fixture with one bound Asset that satisfies the PIDINST cardinality.

    The bound Asset carries an owner and references a Model whose
    Manufacturer cascades into the Fixture-tier Manufacturers union,
    so `to_fixture_pidinst_record` returns a serialized record without
    raising any `Fixture*StateNotAvailableError`.
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
            level=AssetLevel.DEVICE,
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
            name="MCTOptics",
            presents_as_family_id=family_id,
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
async def test_get_fixture_pidinst_tool_with_minted_fixture_returns_pidinst_record_payload(
    db_pool: asyncpg.Pool,
) -> None:
    fixture_id = await _seed_minted_fixture(db_pool)
    handler_deps = _build_deps(db_pool, ids=[])
    tool_fn = _registered_tool_fn(get_fixture_pidinst.bind(handler_deps))

    output = await tool_fn(_StubMcpContext(), fixture_id=fixture_id)

    assert output.fixture_id == fixture_id
    assert output.name == f"Fixture {fixture_id}"
    assert output.schema_version == "1.0"
    assert output.identifier.scheme == "URN"
    assert output.identifier.value == f"urn:uuid:{fixture_id}"
    assert output.landing_page_url == f"https://cora.local/fixtures/{fixture_id}/landing"
    assert len(output.owners) == 1
    assert output.owners[0].name == "Helmholtz-Zentrum Berlin"
    assert output.owners[0].identifier == "https://ror.org/02aj13c28"
    assert output.owners[0].identifier_type == "ROR"
    assert output.publisher == "CORA"
    assert output.publication_year == _NOW.year


@pytest.mark.integration
async def test_get_fixture_pidinst_tool_with_unknown_fixture_raises_fixture_not_found(
    db_pool: asyncpg.Pool,
) -> None:
    handler_deps = _build_deps(db_pool, ids=[])
    tool_fn = _registered_tool_fn(get_fixture_pidinst.bind(handler_deps))

    with pytest.raises(FixtureNotFoundError):
        await tool_fn(_StubMcpContext(), fixture_id=uuid4())
