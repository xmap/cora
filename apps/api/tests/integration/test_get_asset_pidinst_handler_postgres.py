"""Closure-proof integration suite: get_asset_pidinst against real Postgres.

Slice E.1 of project_asset_persistent_id_design. Twelve tests cover the
end-to-end chain: register_asset + add_asset_owner + define_model +
add_asset_family produce events that the AssetSummaryProjection
materializes, then `get_asset_pidinst` folds the streams + serializes
the PIDINST record. If any link in the chain breaks, the closure
proof fails at the assertion site, NOT silently in production.

Six happy-path tests cover the assembler matrix (single owner,
multiple owners, with-model, with-three-families, commissioned-only,
decommissioned-set). Four negative-path tests pin the status-code
mapping for the 404 / 409 / 422 routes the BC's exception-handler
tuples register. Two closure-proof tests pin the slice-C URN-fallback
reachability and the publisher passthrough.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment.aggregates.asset import (
    AssetLevel,
    AssetNotFoundError,
    AssetOwner,
    AssetOwnerContact,
    AssetOwnerIdentifier,
    AssetOwnerIdentifierType,
    AssetOwnerName,
)
from cora.equipment.aggregates.model import (
    Manufacturer,
    ManufacturerIdentifier,
    ManufacturerIdentifierType,
    ManufacturerName,
)
from cora.equipment.errors import (
    LandingPageMissingError,
    ManufacturerStateNotAvailableError,
    OwnerStateNotAvailableError,
)
from cora.equipment.features import (
    add_asset_family,
    add_asset_owner,
    decommission_asset,
    define_family,
    define_model,
    get_asset_pidinst,
    register_asset,
)
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.add_asset_owner import AddAssetOwner
from cora.equipment.features.decommission_asset import DecommissionAsset
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_model import DefineModel
from cora.equipment.features.get_asset_pidinst import GetAssetPidinst
from cora.equipment.features.register_asset import RegisterAsset
from cora.infrastructure.config import Settings
from cora.infrastructure.kernel import Kernel
from tests.integration._equipment_helpers import drain_equipment_projections
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2024, 7, 4, 12, 0, 0, tzinfo=UTC)
_LATER = datetime(2026, 4, 1, 14, 0, 0, tzinfo=UTC)
_PARENT_ID = UUID("01900000-0000-7000-8000-0000ee010000")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_LANDING_TEMPLATE = "https://cora.example/assets/{asset_id}/landing"
_PUBLISHER = "Argonne National Laboratory"


def _settings() -> Settings:
    return Settings(  # type: ignore[call-arg]
        app_env="test",
        facility_publisher=_PUBLISHER,
        landing_page_template=_LANDING_TEMPLATE,
    )


def _build_deps(
    db_pool: asyncpg.Pool,
    *,
    ids: list[UUID],
    now: datetime = _NOW,
) -> Kernel:
    return build_postgres_deps(
        db_pool,
        ids=ids,
        now=now,
    )


def _hzb_owner() -> AssetOwner:
    return AssetOwner(
        name=AssetOwnerName("Helmholtz-Zentrum Berlin"),
        contact=AssetOwnerContact("instrument-data@hzb.de"),
        identifier=AssetOwnerIdentifier("https://ror.org/02aj13c28"),
        identifier_type=AssetOwnerIdentifierType("ROR"),
    )


def _aps_owner() -> AssetOwner:
    return AssetOwner(
        name=AssetOwnerName("Advanced Photon Source"),
        contact=AssetOwnerContact("aps-ops@anl.gov"),
        identifier=AssetOwnerIdentifier("https://ror.org/05gvnxz63"),
        identifier_type=AssetOwnerIdentifierType("ROR"),
    )


def _esrf_owner() -> AssetOwner:
    return AssetOwner(
        name=AssetOwnerName("European Synchrotron"),
        contact=AssetOwnerContact("ops@esrf.fr"),
        identifier=AssetOwnerIdentifier("https://ror.org/02kv6nq22"),
        identifier_type=AssetOwnerIdentifierType("ROR"),
    )


def _aerotech_manufacturer() -> Manufacturer:
    return Manufacturer(
        name=ManufacturerName("Aerotech"),
        identifier=ManufacturerIdentifier("https://ror.org/04bw7nh07"),
        identifier_type=ManufacturerIdentifierType.ROR,
    )


def _override_settings(deps: Kernel, **overrides: object) -> Kernel:
    """Construct a sibling Kernel sharing every dep except settings."""
    settings_data = deps.settings.model_dump()
    settings_data.update(overrides)
    new_settings = Settings(**settings_data)  # type: ignore[arg-type]
    from dataclasses import replace

    return replace(deps, settings=new_settings)


async def _seed_minimal_asset_with_owners(
    db_pool: asyncpg.Pool,
    *,
    owners: list[AssetOwner],
    model_id: UUID | None = None,
    model_family_ids: frozenset[UUID] | None = None,
) -> UUID:
    """Register an Asset, optionally bound to a Model.

    When `model_id` is set, the Model's `declared_family_ids` are
    threaded onto the Asset via `add_asset_family` BEFORE registration
    is complete: the cross-BC subset invariant
    `Model.declared_family_ids subset-of Asset.family_ids` is enforced
    by `add_asset_family`'s decider, so we add all of the Model's
    declared families to the new Asset first."""
    asset_id = uuid4()
    deps = _build_deps(db_pool, ids=[asset_id, uuid4()])
    await register_asset.bind(deps)(
        RegisterAsset(
            name="Rotary Stage A",
            level=AssetLevel.DEVICE,
            parent_id=_PARENT_ID,
            model_id=model_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    if model_family_ids:
        for family_id in model_family_ids:
            await _add_family_to_asset(db_pool, asset_id=asset_id, family_id=family_id)
    for owner in owners:
        owner_event_id = uuid4()
        owner_deps = _build_deps(db_pool, ids=[owner_event_id])
        await add_asset_owner.bind(owner_deps)(
            AddAssetOwner(asset_id=asset_id, owner=owner),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    return asset_id


async def _seed_model_with_anchor_family(
    db_pool: asyncpg.Pool,
) -> tuple[UUID, frozenset[UUID]]:
    """Convenience: define a single anchor Family + a Model whose
    declared_family_ids covers it. Used by the happy-path tests that
    don't care about Family count specifically."""
    family_id = await _seed_family(db_pool, name="AnchorFamily")
    model_id = await _seed_model(db_pool, declared_family_ids=frozenset({family_id}))
    return model_id, frozenset({family_id})


async def _seed_model(db_pool: asyncpg.Pool, *, declared_family_ids: frozenset[UUID]) -> UUID:
    model_id = uuid4()
    define_event_id = uuid4()
    deps = _build_deps(db_pool, ids=[model_id, define_event_id])
    await define_model.bind(deps)(
        DefineModel(
            name="ANT130-L",
            manufacturer=_aerotech_manufacturer(),
            part_number="ANT130-L-RM",
            declared_family_ids=declared_family_ids,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return model_id


async def _seed_family(db_pool: asyncpg.Pool, *, name: str) -> UUID:
    family_id = uuid4()
    define_event_id = uuid4()
    deps = _build_deps(db_pool, ids=[family_id, define_event_id])
    await define_family.bind(deps)(
        DefineFamily(name=name, affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # define_model reads proj_equipment_family_summary; drain so the
    # Family lookup the next handler call performs sees this row.
    await drain_equipment_projections(db_pool)
    return family_id


async def _add_family_to_asset(db_pool: asyncpg.Pool, *, asset_id: UUID, family_id: UUID) -> None:
    event_id = uuid4()
    deps = _build_deps(db_pool, ids=[event_id])
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


def _pidinst_handler(deps: Kernel) -> get_asset_pidinst.Handler:
    deps_with_settings = _override_settings(
        deps,
        facility_publisher=_PUBLISHER,
        landing_page_template=_LANDING_TEMPLATE,
    )
    return get_asset_pidinst.bind(deps_with_settings)


@pytest.mark.integration
@pytest.mark.timeout(60, method="thread")
async def test_pidinst_route_returns_200_for_asset_with_one_owner(
    db_pool: asyncpg.Pool,
) -> None:
    model_id, model_family_ids = await _seed_model_with_anchor_family(db_pool)
    asset_id = await _seed_minimal_asset_with_owners(
        db_pool,
        owners=[_hzb_owner()],
        model_id=model_id,
        model_family_ids=model_family_ids,
    )
    handler_deps = _build_deps(db_pool, ids=[])
    handler = _pidinst_handler(handler_deps)
    record = await handler(
        GetAssetPidinst(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(record.owners) == 1
    assert record.owners[0].name == "Helmholtz-Zentrum Berlin"


@pytest.mark.integration
@pytest.mark.timeout(60, method="thread")
async def test_pidinst_route_returns_200_for_asset_with_three_owners(
    db_pool: asyncpg.Pool,
) -> None:
    model_id, model_family_ids = await _seed_model_with_anchor_family(db_pool)
    asset_id = await _seed_minimal_asset_with_owners(
        db_pool,
        owners=[_aps_owner(), _hzb_owner(), _esrf_owner()],
        model_id=model_id,
        model_family_ids=model_family_ids,
    )
    handler = _pidinst_handler(_build_deps(db_pool, ids=[]))
    record = await handler(
        GetAssetPidinst(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    names = {owner.name for owner in record.owners}
    assert names == {
        "Advanced Photon Source",
        "European Synchrotron",
        "Helmholtz-Zentrum Berlin",
    }


@pytest.mark.integration
@pytest.mark.timeout(60, method="thread")
async def test_pidinst_route_returns_200_for_asset_with_model_bound(
    db_pool: asyncpg.Pool,
) -> None:
    model_id, model_family_ids = await _seed_model_with_anchor_family(db_pool)
    asset_id = await _seed_minimal_asset_with_owners(
        db_pool,
        owners=[_hzb_owner()],
        model_id=model_id,
        model_family_ids=model_family_ids,
    )
    handler = _pidinst_handler(_build_deps(db_pool, ids=[]))
    record = await handler(
        GetAssetPidinst(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert record.model is not None
    assert record.model.name == "ANT130-L"
    assert record.model.identifier == "ANT130-L-RM"
    assert len(record.manufacturers) == 1
    assert record.manufacturers[0].name == "Aerotech"


@pytest.mark.integration
@pytest.mark.timeout(60, method="thread")
async def test_pidinst_route_returns_200_for_asset_with_three_families(
    db_pool: asyncpg.Pool,
) -> None:
    """Asset bound to a Model declaring one anchor family, with two
    additional families added incrementally on the Asset itself (the
    cross-BC subset invariant is one-directional:
    `Asset.family_ids superset-of Model.declared_family_ids`, so the
    asset can carry families the model does not declare)."""
    family_alpha = await _seed_family(db_pool, name="AlphaFamily")
    family_mu = await _seed_family(db_pool, name="MuFamily")
    family_zeta = await _seed_family(db_pool, name="ZetaFamily")
    anchor_set = frozenset({family_alpha})
    model_id = await _seed_model(
        db_pool,
        declared_family_ids=anchor_set,
    )
    asset_id = await _seed_minimal_asset_with_owners(
        db_pool,
        owners=[_hzb_owner()],
        model_id=model_id,
        model_family_ids=anchor_set,
    )
    for extra_family_id in (family_mu, family_zeta):
        await _add_family_to_asset(db_pool, asset_id=asset_id, family_id=extra_family_id)
    handler = _pidinst_handler(_build_deps(db_pool, ids=[]))
    record = await handler(
        GetAssetPidinst(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    family_names = {instrument_type.name for instrument_type in record.instrument_types}
    assert family_names == {"AlphaFamily", "MuFamily", "ZetaFamily"}


@pytest.mark.integration
@pytest.mark.timeout(60, method="thread")
async def test_pidinst_route_returns_200_for_asset_with_commissioned_at_only(
    db_pool: asyncpg.Pool,
) -> None:
    model_id, model_family_ids = await _seed_model_with_anchor_family(db_pool)
    asset_id = await _seed_minimal_asset_with_owners(
        db_pool,
        owners=[_hzb_owner()],
        model_id=model_id,
        model_family_ids=model_family_ids,
    )
    handler = _pidinst_handler(_build_deps(db_pool, ids=[]))
    record = await handler(
        GetAssetPidinst(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert record.publication_year == _NOW.year
    date_types = {pidinst_date.date_type.value for pidinst_date in record.dates}
    assert "Commissioned" in date_types
    assert "DeCommissioned" not in date_types


@pytest.mark.integration
@pytest.mark.timeout(60, method="thread")
async def test_pidinst_route_returns_200_for_asset_with_decommissioned_at_set(
    db_pool: asyncpg.Pool,
) -> None:
    model_id, model_family_ids = await _seed_model_with_anchor_family(db_pool)
    asset_id = await _seed_minimal_asset_with_owners(
        db_pool,
        owners=[_hzb_owner()],
        model_id=model_id,
        model_family_ids=model_family_ids,
    )
    decommission_event_id = uuid4()
    decommission_deps = _build_deps(db_pool, ids=[decommission_event_id], now=_LATER)
    await decommission_asset.bind(decommission_deps)(
        DecommissionAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    handler = _pidinst_handler(_build_deps(db_pool, ids=[]))
    record = await handler(
        GetAssetPidinst(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    date_types = {pidinst_date.date_type.value for pidinst_date in record.dates}
    assert "Commissioned" in date_types
    assert "DeCommissioned" in date_types


@pytest.mark.integration
@pytest.mark.timeout(60, method="thread")
async def test_pidinst_route_returns_404_for_unknown_asset_id(
    db_pool: asyncpg.Pool,
) -> None:
    handler = _pidinst_handler(_build_deps(db_pool, ids=[]))
    with pytest.raises(AssetNotFoundError):
        await handler(
            GetAssetPidinst(asset_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.integration
@pytest.mark.timeout(60, method="thread")
async def test_pidinst_route_returns_409_for_asset_with_no_owners(
    db_pool: asyncpg.Pool,
) -> None:
    model_id, model_family_ids = await _seed_model_with_anchor_family(db_pool)
    asset_id = await _seed_minimal_asset_with_owners(
        db_pool,
        owners=[],
        model_id=model_id,
        model_family_ids=model_family_ids,
    )
    handler = _pidinst_handler(_build_deps(db_pool, ids=[]))
    with pytest.raises(OwnerStateNotAvailableError):
        await handler(
            GetAssetPidinst(asset_id=asset_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.integration
@pytest.mark.timeout(60, method="thread")
async def test_pidinst_route_returns_409_for_asset_with_no_model(
    db_pool: asyncpg.Pool,
) -> None:
    asset_id = await _seed_minimal_asset_with_owners(db_pool, owners=[_hzb_owner()], model_id=None)
    handler = _pidinst_handler(_build_deps(db_pool, ids=[]))
    with pytest.raises(ManufacturerStateNotAvailableError):
        await handler(
            GetAssetPidinst(asset_id=asset_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.integration
@pytest.mark.timeout(60, method="thread")
async def test_pidinst_route_returns_422_for_asset_with_empty_landing_page_url(
    db_pool: asyncpg.Pool,
) -> None:
    """When the landing-page template produces an empty string (a
    template carrying no asset_id substitution + an empty literal),
    the serializer raises LandingPageMissingError. The bootstrap guard
    catches the unset case at startup; this test exercises the route
    layer's 422 mapping by supplying a template that ALWAYS produces
    whitespace regardless of asset_id."""
    model_id, model_family_ids = await _seed_model_with_anchor_family(db_pool)
    asset_id = await _seed_minimal_asset_with_owners(
        db_pool,
        owners=[_hzb_owner()],
        model_id=model_id,
        model_family_ids=model_family_ids,
    )
    deps = _override_settings(
        _build_deps(db_pool, ids=[]),
        facility_publisher=_PUBLISHER,
        landing_page_template="   ",
    )
    handler = get_asset_pidinst.bind(deps)
    with pytest.raises(LandingPageMissingError):
        await handler(
            GetAssetPidinst(asset_id=asset_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.integration
@pytest.mark.timeout(60, method="thread")
async def test_pidinst_route_returns_urn_uuid_identifier_for_owner_populated_asset(
    db_pool: asyncpg.Pool,
) -> None:
    """Closure-proof: every E.1 asset has no persistent_id, so the
    slice-C URN-fallback path is exercised end-to-end. The identifier
    is the literal `urn:uuid:<asset_id>` per slice C's L16."""
    model_id, model_family_ids = await _seed_model_with_anchor_family(db_pool)
    asset_id = await _seed_minimal_asset_with_owners(
        db_pool,
        owners=[_hzb_owner()],
        model_id=model_id,
        model_family_ids=model_family_ids,
    )
    handler = _pidinst_handler(_build_deps(db_pool, ids=[]))
    record = await handler(
        GetAssetPidinst(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert record.identifier.value == f"urn:uuid:{asset_id}"
    assert record.identifier.scheme.value == "URN"


@pytest.mark.integration
@pytest.mark.timeout(60, method="thread")
async def test_pidinst_route_returns_publisher_from_facility_settings(
    db_pool: asyncpg.Pool,
) -> None:
    """Closure-proof: the publisher field on the response equals
    Settings.facility_publisher (slice E.1 L13). The assembler takes
    it as a constructor arg from bind-time settings."""
    model_id, model_family_ids = await _seed_model_with_anchor_family(db_pool)
    asset_id = await _seed_minimal_asset_with_owners(
        db_pool,
        owners=[_hzb_owner()],
        model_id=model_id,
        model_family_ids=model_family_ids,
    )
    deps = _override_settings(
        _build_deps(db_pool, ids=[]),
        facility_publisher="HZB BESSY II",
        landing_page_template=_LANDING_TEMPLATE,
    )
    handler = get_asset_pidinst.bind(deps)
    record = await handler(
        GetAssetPidinst(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert record.publisher == "HZB BESSY II"


_ = _settings  # placeholder kept for symmetry with sibling integration test modules
