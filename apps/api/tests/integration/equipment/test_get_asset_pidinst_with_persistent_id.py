"""Closure-proof integration suite: get_asset_pidinst observes Asset.persistent_id end-to-end.

Slice F (Section 13.2). Three tests pin the URN-fallback to DOI/Handle
swap that the `_pidinst_serializer._build_identifier` extension makes
when `view.persistent_id` is populated. The Asset stream is mutated by
`assign_asset_persistent_id` (server-mint via the inert `StubDoiMinter` wired
by `wire_equipment`), then `get_asset_pidinst` reads the stream + folds
+ serializes; the resulting `PidinstIdentifier` should carry the DOI or
Handle scheme byte-for-byte rather than the URN fallback from slice C.

The without-assign baseline test pins the URN fallback path on the same
asset shape, defending the slice C contract against silent regression
when slice F's swap lands.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment.adapters.stub_doi_minter import StubDoiMinter
from cora.equipment.aggregates.asset import (
    AssetLevel,
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
from cora.equipment.features import (
    add_asset_family,
    add_asset_owner,
    assign_asset_persistent_id,
    define_family,
    define_model,
    get_asset_pidinst,
    register_asset,
)
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.add_asset_owner import AddAssetOwner
from cora.equipment.features.assign_asset_persistent_id import AssignAssetPersistentId
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_model import DefineModel
from cora.equipment.features.get_asset_pidinst import GetAssetPidinst
from cora.equipment.features.register_asset import RegisterAsset
from cora.infrastructure.config import Settings
from cora.infrastructure.kernel import Kernel
from cora.shared.identifier import (
    PersistentIdentifierScheme,
)
from tests.integration._equipment_helpers import drain_equipment_projections
from tests.integration._helpers import build_postgres_deps

pytestmark = pytest.mark.timeout(60, method="thread")

_NOW = datetime(2024, 7, 4, 12, 0, 0, tzinfo=UTC)
_PARENT_ID = UUID("01900000-0000-7000-8000-0000ee010000")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_LANDING_TEMPLATE = "https://cora.example/assets/{asset_id}/landing"
_PUBLISHER = "Argonne National Laboratory"


def _build_deps(
    db_pool: asyncpg.Pool,
    *,
    ids: list[UUID],
    now: datetime = _NOW,
) -> Kernel:
    deps = build_postgres_deps(
        db_pool,
        ids=ids,
        now=now,
    )
    deps = _override_settings(
        deps,
        facility_publisher=_PUBLISHER,
        landing_page_template=_LANDING_TEMPLATE,
    )
    # Attach the BC-local equipment namespace the assign_asset_persistent_id
    # handler reads (`deps.equipment.doi_minter`). The Stub mirrors what
    # `wire_equipment` registers when no DataCite credentials are present.
    object.__setattr__(deps, "equipment", SimpleNamespace(doi_minter=StubDoiMinter()))
    return deps


def _override_settings(deps: Kernel, **overrides: object) -> Kernel:
    """Construct a sibling Kernel sharing every dep except settings."""
    settings_data = deps.settings.model_dump()
    settings_data.update(overrides)
    new_settings = Settings(**settings_data)  # type: ignore[arg-type]
    from dataclasses import replace

    return replace(deps, settings=new_settings)


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


async def _seed_family(db_pool: asyncpg.Pool, *, name: str) -> UUID:
    family_id = uuid4()
    define_event_id = uuid4()
    deps = _build_deps(db_pool, ids=[family_id, define_event_id])
    await define_family.bind(deps)(
        DefineFamily(name=name, affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)
    return family_id


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


async def _add_family_to_asset(db_pool: asyncpg.Pool, *, asset_id: UUID, family_id: UUID) -> None:
    event_id = uuid4()
    deps = _build_deps(db_pool, ids=[event_id])
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _seed_asset_with_owner_and_model(db_pool: asyncpg.Pool) -> UUID:
    """Seed a minimal owner-and-model-bound asset suitable for PIDINST emission."""
    family_id = await _seed_family(db_pool, name="AnchorFamily")
    model_id = await _seed_model(db_pool, declared_family_ids=frozenset({family_id}))
    asset_id = uuid4()
    register_event_id = uuid4()
    deps = _build_deps(db_pool, ids=[asset_id, register_event_id])
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
    await _add_family_to_asset(db_pool, asset_id=asset_id, family_id=family_id)
    owner_event_id = uuid4()
    owner_deps = _build_deps(db_pool, ids=[owner_event_id])
    await add_asset_owner.bind(owner_deps)(
        AddAssetOwner(asset_id=asset_id, owner=_hzb_owner()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return asset_id


async def _assign_asset_persistent_id(
    db_pool: asyncpg.Pool,
    *,
    asset_id: UUID,
    scheme: PersistentIdentifierScheme,
    suffix: str,
) -> None:
    event_id = uuid4()
    deps = _build_deps(db_pool, ids=[event_id])
    await assign_asset_persistent_id.bind(deps)(
        AssignAssetPersistentId(asset_id=asset_id, scheme=scheme, suffix=suffix),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


def _pidinst_handler(deps: Kernel) -> get_asset_pidinst.Handler:
    return get_asset_pidinst.bind(deps)


@pytest.mark.integration
async def test_get_pidinst_after_assign_emits_doi_identifier_not_urn(
    db_pool: asyncpg.Pool,
) -> None:
    asset_id = await _seed_asset_with_owner_and_model(db_pool)
    await _assign_asset_persistent_id(
        db_pool,
        asset_id=asset_id,
        scheme=PersistentIdentifierScheme.DOI,
        suffix="zenodo.7654321",
    )
    handler = _pidinst_handler(_build_deps(db_pool, ids=[]))
    record = await handler(
        GetAssetPidinst(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert record.identifier.scheme.value == "DOI"
    assert record.identifier.value == "10.0000/cora-stub/zenodo.7654321"
    assert not record.identifier.value.startswith("urn:uuid:")


@pytest.mark.integration
async def test_get_pidinst_without_assign_still_emits_urn_fallback(
    db_pool: asyncpg.Pool,
) -> None:
    asset_id = await _seed_asset_with_owner_and_model(db_pool)
    handler = _pidinst_handler(_build_deps(db_pool, ids=[]))
    record = await handler(
        GetAssetPidinst(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert record.identifier.scheme.value == "URN"
    assert record.identifier.value == f"urn:uuid:{asset_id}"


@pytest.mark.integration
async def test_get_pidinst_with_handle_scheme_after_assign_emits_handle_identifier(
    db_pool: asyncpg.Pool,
) -> None:
    asset_id = await _seed_asset_with_owner_and_model(db_pool)
    await _assign_asset_persistent_id(
        db_pool,
        asset_id=asset_id,
        scheme=PersistentIdentifierScheme.HANDLE,
        suffix="12345",
    )
    handler = _pidinst_handler(_build_deps(db_pool, ids=[]))
    record = await handler(
        GetAssetPidinst(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert record.identifier.scheme.value == "Handle"
    assert record.identifier.value == "20.500.0000/cora-stub/12345"
    assert not record.identifier.value.startswith("urn:uuid:")
