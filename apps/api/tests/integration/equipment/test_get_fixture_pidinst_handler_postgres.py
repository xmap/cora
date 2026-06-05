"""Closure-proof integration suite: get_fixture_pidinst against real Postgres.

Read-side slice of project_fixture_pidinst_design (Section 15.2).
The view assembler composes a `FixturePidinstView` from the Fixture
aggregate plus its bound Assets (one level deep per L24); the route
then runs the view through `to_fixture_pidinst_record` to produce
the `PidinstRecord`. This suite pins the handler-tier closure:
register the upstream chain (Family -> Model -> Asset + owner +
family -> Assembly -> Fixture), optionally assign each bound Asset a
persistent_id via the inert `StubDoiMinter`, then load through
`get_fixture_pidinst.bind(deps)` and assert against the assembled
view (and through `to_fixture_pidinst_record` for the URN-fallback
identifier shape).

The read-side slice has no `assign_fixture_persistent_id` write
sibling yet, so the Fixture's own `persistent_id` is always None and
the serializer always emits the `urn:uuid:<fixture_id>` fallback per
L28.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment._pidinst_serializer import to_fixture_pidinst_record
from cora.equipment.adapters.stub_doi_minter import StubDoiMinter
from cora.equipment.aggregates.assembly import SlotCardinality, SlotName, TemplateSlot
from cora.equipment.aggregates.asset import (
    AssetLevel,
    AssetOwner,
    AssetOwnerContact,
    AssetOwnerIdentifier,
    AssetOwnerIdentifierType,
    AssetOwnerName,
    PersistentIdentifierScheme,
)
from cora.equipment.aggregates.fixture import SlotAssetBinding
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
    define_assembly,
    define_family,
    define_model,
    get_fixture_pidinst,
    register_asset,
    register_fixture,
)
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.add_asset_owner import AddAssetOwner
from cora.equipment.features.assign_asset_persistent_id import AssignAssetPersistentId
from cora.equipment.features.define_assembly import DefineAssembly
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_model import DefineModel
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.register_fixture import RegisterFixture
from cora.infrastructure.config import Settings
from cora.infrastructure.kernel import Kernel
from tests.integration._equipment_helpers import drain_equipment_projections
from tests.integration._helpers import build_postgres_deps

pytestmark = pytest.mark.timeout(60, method="thread")

_NOW = datetime(2024, 7, 4, 12, 0, 0, tzinfo=UTC)
_PARENT_ID = UUID("01900000-0000-7000-8000-0000ee010000")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_LANDING_TEMPLATE = "https://cora.example/assets/{asset_id}/landing"
_PUBLISHER = "Argonne National Laboratory"


def _override_settings(deps: Kernel, **overrides: object) -> Kernel:
    """Construct a sibling Kernel sharing every dep except settings."""
    settings_data = deps.settings.model_dump()
    settings_data.update(overrides)
    new_settings = Settings(**settings_data)  # type: ignore[arg-type]
    from dataclasses import replace

    return replace(deps, settings=new_settings)


def _build_deps(
    db_pool: asyncpg.Pool,
    *,
    ids: list[UUID],
    now: datetime = _NOW,
) -> Kernel:
    deps = build_postgres_deps(db_pool, ids=ids, now=now)
    deps = _override_settings(
        deps,
        facility_publisher=_PUBLISHER,
        landing_page_template=_LANDING_TEMPLATE,
    )
    # The assign_asset_persistent_id handler reads `deps.equipment.doi_minter`;
    # mirror what `wire_equipment` registers when no DataCite credentials are
    # present (parity with test_get_asset_pidinst_with_persistent_id.py).
    object.__setattr__(deps, "equipment", SimpleNamespace(doi_minter=StubDoiMinter()))
    return deps


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
    # define_model + register_fixture read proj_equipment_family_summary;
    # drain so the lookup the next handler call performs sees this row.
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


async def _seed_asset_with_owner_and_model(
    db_pool: asyncpg.Pool,
    *,
    family_id: UUID,
    model_id: UUID,
    name: str,
    owner: AssetOwner,
) -> UUID:
    asset_id = uuid4()
    register_event_id = uuid4()
    deps = _build_deps(db_pool, ids=[asset_id, register_event_id])
    await register_asset.bind(deps)(
        RegisterAsset(
            name=name,
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
        AddAssetOwner(asset_id=asset_id, owner=owner),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return asset_id


async def _assign_asset_persistent_id(
    db_pool: asyncpg.Pool,
    *,
    asset_id: UUID,
    suffix: str,
) -> None:
    event_id = uuid4()
    deps = _build_deps(db_pool, ids=[event_id])
    await assign_asset_persistent_id.bind(deps)(
        AssignAssetPersistentId(
            asset_id=asset_id,
            scheme=PersistentIdentifierScheme.DOI,
            suffix=suffix,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _seed_assembly_one_slot(
    db_pool: asyncpg.Pool,
    *,
    family_id: UUID,
    cardinality: SlotCardinality,
    name: str = "MCTOptics",
) -> UUID:
    assembly_id = uuid4()
    define_event_id = uuid4()
    deps = _build_deps(db_pool, ids=[assembly_id, define_event_id])
    return await define_assembly.bind(deps)(
        DefineAssembly(
            name=name,
            presents_as_family_id=family_id,
            required_slots=frozenset(
                {
                    TemplateSlot(
                        slot_name=SlotName("camera"),
                        required_family_ids=frozenset({family_id}),
                        cardinality=cardinality,
                    )
                }
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _seed_fixture(
    db_pool: asyncpg.Pool,
    *,
    assembly_id: UUID,
    slot_asset_bindings: frozenset[SlotAssetBinding],
) -> UUID:
    fixture_id = uuid4()
    fixture_event_id = uuid4()
    deps = _build_deps(db_pool, ids=[fixture_id, fixture_event_id])
    return await register_fixture.bind(deps)(
        RegisterFixture(
            assembly_id=assembly_id,
            slot_asset_bindings=slot_asset_bindings,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


def _pidinst_handler(deps: Kernel) -> get_fixture_pidinst.Handler:
    return get_fixture_pidinst.bind(deps)


@pytest.mark.integration
async def test_get_fixture_pidinst_for_minted_fixture_with_bound_minted_assets_returns_pidinst_view(
    db_pool: asyncpg.Pool,
) -> None:
    family_id = await _seed_family(db_pool, name="Camera")
    model_id = await _seed_model(db_pool, declared_family_ids=frozenset({family_id}))
    asset_a = await _seed_asset_with_owner_and_model(
        db_pool,
        family_id=family_id,
        model_id=model_id,
        name="Camera-A",
        owner=_hzb_owner(),
    )
    asset_b = await _seed_asset_with_owner_and_model(
        db_pool,
        family_id=family_id,
        model_id=model_id,
        name="Camera-B",
        owner=_aps_owner(),
    )
    await _assign_asset_persistent_id(db_pool, asset_id=asset_a, suffix="CAM-A")
    await _assign_asset_persistent_id(db_pool, asset_id=asset_b, suffix="CAM-B")
    assembly_id = await _seed_assembly_one_slot(
        db_pool,
        family_id=family_id,
        cardinality=SlotCardinality.ONE_OR_MORE,
    )
    fixture_id = await _seed_fixture(
        db_pool,
        assembly_id=assembly_id,
        slot_asset_bindings=frozenset(
            {
                SlotAssetBinding(slot_name="camera", asset_id=asset_a),
                SlotAssetBinding(slot_name="camera", asset_id=asset_b),
            }
        ),
    )

    handler = _pidinst_handler(_build_deps(db_pool, ids=[]))
    view = await handler(
        fixture_id,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is not None
    assert view.fixture_id == fixture_id
    assert view.persistent_id is None
    owner_names = {owner.name.value for owner in view.owners}
    assert owner_names == {"Advanced Photon Source", "Helmholtz-Zentrum Berlin"}
    manufacturer_names = {m.name for m in view.manufacturers}
    assert manufacturer_names == {"Aerotech"}
    component_ids = {component.component_id for component in view.components}
    assert component_ids == {asset_a, asset_b}
    for component in view.components:
        assert component.scheme is PersistentIdentifierScheme.DOI
        assert component.value is not None
        assert component.value.startswith("10.0000/cora-stub/")
    assert view.publication_year == _NOW.year


@pytest.mark.integration
async def test_get_fixture_pidinst_no_bound_assets_returns_view_empty_owners_manufacturers(
    db_pool: asyncpg.Pool,
) -> None:
    family_id = await _seed_family(db_pool, name="Camera")
    assembly_id = await _seed_assembly_one_slot(
        db_pool,
        family_id=family_id,
        cardinality=SlotCardinality.ZERO_OR_MORE,
    )
    fixture_id = await _seed_fixture(
        db_pool,
        assembly_id=assembly_id,
        slot_asset_bindings=frozenset(),
    )

    handler = _pidinst_handler(_build_deps(db_pool, ids=[]))
    view = await handler(
        fixture_id,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is not None
    assert view.fixture_id == fixture_id
    assert view.owners == ()
    assert view.manufacturers == ()
    assert view.components == ()
    assert view.persistent_id is None


@pytest.mark.integration
async def test_get_fixture_pidinst_with_unminted_fixture_returns_urn_identifier(
    db_pool: asyncpg.Pool,
) -> None:
    family_id = await _seed_family(db_pool, name="Camera")
    model_id = await _seed_model(db_pool, declared_family_ids=frozenset({family_id}))
    asset_id = await _seed_asset_with_owner_and_model(
        db_pool,
        family_id=family_id,
        model_id=model_id,
        name="Camera-Solo",
        owner=_hzb_owner(),
    )
    assembly_id = await _seed_assembly_one_slot(
        db_pool,
        family_id=family_id,
        cardinality=SlotCardinality.EXACTLY_1,
    )
    fixture_id = await _seed_fixture(
        db_pool,
        assembly_id=assembly_id,
        slot_asset_bindings=frozenset({SlotAssetBinding(slot_name="camera", asset_id=asset_id)}),
    )

    handler = _pidinst_handler(_build_deps(db_pool, ids=[]))
    view = await handler(
        fixture_id,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is not None
    assert view.persistent_id is None
    record = to_fixture_pidinst_record(
        view,
        landing_page_url=f"https://cora.example/fixtures/{fixture_id}/landing",
        publisher=_PUBLISHER,
    )
    assert record.identifier.scheme.value == "URN"
    assert record.identifier.value == f"urn:uuid:{fixture_id}"


@pytest.mark.integration
async def test_get_fixture_pidinst_with_unknown_fixture_returns_none(
    db_pool: asyncpg.Pool,
) -> None:
    handler = _pidinst_handler(_build_deps(db_pool, ids=[]))
    view = await handler(
        uuid4(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert view is None
