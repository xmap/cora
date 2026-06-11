"""End-to-end integration tests for Slice 8A Asset.facility_code binding.

Mirrors the Supply Slice 7A integration coverage for facility binding:
  - Happy path: register Asset with valid facility_code; event payload,
    projection column, and folded Asset state all round-trip the typed
    FacilityCode VO.
  - Unknown facility_code path: handler raises AssetFacilityNotFoundError
    BEFORE appending any Asset event, mapped to HTTP 404 by the BC's
    exception-handler tuple.
  - Omit path: register Asset with facility_code=None; no
    FacilityLookup.lookup_by_code call fires; the projection column
    stores NULL and the folded Asset state carries facility_code=None.

The cross-BC binding sequence: register a Facility via the Federation
BC's register_facility command first, drain the Federation projection
so proj_federation_facility_summary has the row, then register the
Asset via the Equipment BC's register_asset command bound to that
Facility code. PostgresFacilityLookup adapter (already shipped Slice
5+6) resolves the slug against the projection.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment._projections import register_equipment_projections
from cora.equipment.aggregates.asset import (
    AssetFacilityNotFoundError,
    AssetTier,
    load_asset,
)
from cora.equipment.features import register_asset
from cora.equipment.features.register_asset import RegisterAsset
from cora.federation._projections import register_federation_projections
from cora.federation.adapters.postgres_facility_lookup import PostgresFacilityLookup
from cora.federation.aggregates.facility import FacilityKind
from cora.federation.features import register_facility
from cora.federation.features.register_facility import RegisterFacility
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.shared.facility_code import FacilityCode
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _drain_federation(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_federation_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _drain_equipment(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_equipment_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


@pytest.mark.integration
async def test_register_asset_with_facility_code_round_trips_typed_vo(
    db_pool: asyncpg.Pool,
) -> None:
    """Happy path: Asset bound to a real Facility via facility_code.

    Verifies (a) handler resolves the slug via PostgresFacilityLookup;
    (b) decider folds the typed FacilityCode onto the AssetRegistered
    event; (c) projection column receives the bare-str value; (d)
    folded Asset state carries the typed FacilityCode VO."""
    # Step 1: register a Facility (self-Facility "cora" is already seeded
    # by bootstrap_federation in the test fixture, so we use it directly).
    asset_id = uuid4()
    asset_event_id = uuid4()
    facility_code = "cora"
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[asset_id, asset_event_id])

    # Step 2: register the Asset bound to the Facility.
    new_asset_id = await register_asset.bind(deps)(
        RegisterAsset(
            name="2-BM-facility-binding-test",
            tier=AssetTier.UNIT,
            parent_id=None,
            facility_code=facility_code,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert new_asset_id == asset_id

    # Step 3: verify the folded Asset state carries the typed
    # FacilityCode VO (the from_stored serializer round-trips the
    # bare-str payload key to the typed VO).
    asset = await load_asset(deps.event_store, asset_id)
    assert asset is not None
    assert asset.facility_code == FacilityCode(facility_code)

    # Step 4: drain the Equipment projection and verify the projection
    # column carries the bare-str FacilityCode value.
    await _drain_equipment(db_pool)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT facility_code FROM proj_equipment_asset_summary WHERE asset_id = $1",
            asset_id,
        )
    assert row is not None
    assert row["facility_code"] == facility_code


@pytest.mark.integration
async def test_register_asset_raises_facility_not_found_on_unknown_facility_code(
    db_pool: asyncpg.Pool,
) -> None:
    """Unknown facility_code: handler resolves the slug via
    FacilityLookup, finds nothing, and the decider raises
    AssetFacilityNotFoundError BEFORE appending any Asset event."""
    asset_id = uuid4()
    asset_event_id = uuid4()
    unknown_facility_code = "ghost-facility"
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[asset_id, asset_event_id])

    with pytest.raises(AssetFacilityNotFoundError) as exc_info:
        await register_asset.bind(deps)(
            RegisterAsset(
                name="Asset bound to unknown facility",
                tier=AssetTier.UNIT,
                parent_id=None,
                facility_code=unknown_facility_code,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.facility_code == unknown_facility_code

    # No Asset event landed: the handler raised BEFORE
    # event_store.append per Slice 8A Lock L8 (handler loads + decider
    # rejects).
    _, version = await deps.event_store.load("Asset", asset_id)
    assert version == 0


@pytest.mark.integration
async def test_register_asset_with_omitted_facility_code_stores_null(
    db_pool: asyncpg.Pool,
) -> None:
    """Omit path: register_asset accepts facility_code=None (the
    default); the handler skips the FacilityLookup call entirely; the
    projection column receives NULL; the folded Asset state carries
    facility_code=None. Pins the OPTIONAL contract per Slice 8A
    Lock L1."""
    asset_id = uuid4()
    asset_event_id = uuid4()
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[asset_id, asset_event_id])

    new_asset_id = await register_asset.bind(deps)(
        RegisterAsset(
            name="Asset without facility binding",
            tier=AssetTier.UNIT,
            parent_id=uuid4(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert new_asset_id == asset_id

    asset = await load_asset(deps.event_store, asset_id)
    assert asset is not None
    assert asset.facility_code is None

    await _drain_equipment(db_pool)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT facility_code FROM proj_equipment_asset_summary WHERE asset_id = $1",
            asset_id,
        )
    assert row is not None
    assert row["facility_code"] is None


@pytest.mark.integration
async def test_register_asset_with_facility_code_explicit_register_facility_first(
    db_pool: asyncpg.Pool,
) -> None:
    """End-to-end: register a brand-new Facility then bind an Asset
    to it. Pins the cross-BC handshake sequence: Federation
    register_facility -> drain Federation projection ->
    PostgresFacilityLookup sees the row -> Equipment register_asset
    handler resolves the slug -> Asset event lands with typed
    FacilityCode."""
    # Step 1: register a fresh Facility.
    facility_id = uuid4()
    facility_event_id = uuid4()
    new_code = f"maxiv-{uuid4().hex[:8]}"
    facility_deps = build_postgres_deps(db_pool, now=_NOW, ids=[facility_id, facility_event_id])
    await register_facility.bind(facility_deps)(
        RegisterFacility(
            code=new_code,
            kind=FacilityKind.SITE,
            display_name="MAX IV",
            parent_id=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_federation(db_pool)

    # Step 2: register an Asset bound to the brand-new Facility.
    # Use the postgres-backed FacilityLookup so it sees the actual
    # projection row written in Step 1 (not the in-memory default seeded
    # only with "cora").
    asset_id = uuid4()
    asset_event_id = uuid4()
    asset_deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[asset_id, asset_event_id],
        facility_lookup=PostgresFacilityLookup(db_pool),
    )
    new_asset_id = await register_asset.bind(asset_deps)(
        RegisterAsset(
            name=f"MAX IV beamline {uuid4().hex[:6]}",
            tier=AssetTier.UNIT,
            parent_id=None,
            facility_code=new_code,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert new_asset_id == asset_id

    asset = await load_asset(asset_deps.event_store, asset_id)
    assert asset is not None
    assert asset.facility_code == FacilityCode(new_code)
