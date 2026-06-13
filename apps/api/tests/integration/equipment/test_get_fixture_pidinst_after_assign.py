"""Closure-proof integration suite: get_fixture_pidinst observes Fixture.persistent_id end-to-end.

Pins the URN-fallback to DOI / Handle swap (Section 15.2 + Lock 16 of
[[project-fixture-pidinst-design]]) that the
`_pidinst_serializer._build_fixture_identifier` extension performs when
`view.persistent_id` is populated. The Fixture stream is mutated by
`assign_fixture_persistent_id` (server-mint via the inert
`StubDoiMinter` wired by `wire_equipment`), then `get_fixture_pidinst`
reads the stream + folds + the route runs `to_fixture_pidinst_record`;
the resulting `PidinstIdentifier` should carry the DOI or Handle
scheme byte-for-byte rather than the URN fallback emitted before any
persistent identifier is assigned.

The without-assign baseline test pins the URN fallback path on the
same fixture shape, defending the pre-assign serializer contract
against silent regression now that assign wiring is live.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment._pidinst import to_fixture_pidinst_record
from cora.equipment.aggregates.assembly import SlotCardinality, SlotName, TemplateSlot
from cora.equipment.aggregates.asset import (
    AssetOwner,
    AssetOwnerContact,
    AssetOwnerIdentifier,
    AssetOwnerIdentifierType,
    AssetOwnerName,
    AssetTier,
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
    assign_fixture_persistent_id,
    define_assembly,
    define_family,
    define_model,
    get_fixture_pidinst,
    register_asset,
    register_fixture,
)
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.add_asset_owner import AddAssetOwner
from cora.equipment.features.assign_fixture_persistent_id import AssignFixturePersistentId
from cora.equipment.features.define_assembly import DefineAssembly
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_model import DefineModel
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.register_fixture import RegisterFixture
from cora.infrastructure.adapters.stub_doi_minter import StubDoiMinter
from cora.infrastructure.config import Settings
from cora.infrastructure.kernel import Kernel
from cora.shared.identifier import (
    PersistentIdentifierScheme,
)
from tests.integration._equipment_helpers import (
    drain_equipment_projections,
    install_existing_asset_into_fresh_mount,
)
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
    # The assign_fixture_persistent_id handler reads `deps.equipment.doi_minter`;
    # mirror what `wire_equipment` registers when no DataCite credentials are
    # present (parity with test_get_fixture_pidinst_handler_postgres.py).
    object.__setattr__(deps, "equipment", SimpleNamespace(doi_minter=StubDoiMinter()))
    return deps


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
    # define_family derives the stream id from the name; return the
    # handler's deterministic id, not a pre-minted random one.
    define_event_id = uuid4()
    deps = _build_deps(db_pool, ids=[define_event_id])
    family_id = await define_family.bind(deps)(
        DefineFamily(name=name, affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)
    return family_id


async def _seed_model(db_pool: asyncpg.Pool, *, declared_family_ids: frozenset[UUID]) -> UUID:
    # define_model pops a random fallback (unused for a real part number)
    # then the event id; the handler returns the derived stream id.
    fallback_id = uuid4()
    define_event_id = uuid4()
    deps = _build_deps(db_pool, ids=[fallback_id, define_event_id])
    return await define_model.bind(deps)(
        DefineModel(
            name="ANT130-L",
            manufacturer=_aerotech_manufacturer(),
            part_number="ANT130-L-RM",
            declared_family_ids=declared_family_ids,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


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
    await _add_family_to_asset(db_pool, asset_id=asset_id, family_id=family_id)
    owner_event_id = uuid4()
    owner_deps = _build_deps(db_pool, ids=[owner_event_id])
    await add_asset_owner.bind(owner_deps)(
        AddAssetOwner(asset_id=asset_id, owner=owner),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return asset_id


async def _seed_assembly_one_slot(
    db_pool: asyncpg.Pool, *, family_id: UUID, name: str = "MCTOptics"
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
                        cardinality=SlotCardinality.EXACTLY_1,
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
    asset_id: UUID,
) -> UUID:
    fixture_id = uuid4()
    fixture_event_id = uuid4()
    deps = _build_deps(db_pool, ids=[fixture_id, fixture_event_id])
    return await register_fixture.bind(deps)(
        RegisterFixture(
            assembly_id=assembly_id,
            slot_asset_bindings=frozenset(
                {SlotAssetBinding(slot_name="camera", asset_id=asset_id)}
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _seed_fixture_with_owners_and_model(db_pool: asyncpg.Pool) -> UUID:
    family_id = await _seed_family(db_pool, name="Camera")
    model_id = await _seed_model(db_pool, declared_family_ids=frozenset({family_id}))
    asset_id = await _seed_asset_with_owner_and_model(
        db_pool,
        family_id=family_id,
        model_id=model_id,
        name="Camera-A",
        owner=_hzb_owner(),
    )
    assembly_id = await _seed_assembly_one_slot(db_pool, family_id=family_id)
    return await _seed_fixture(db_pool, assembly_id=assembly_id, asset_id=asset_id)


async def _assign_fixture_persistent_id(
    db_pool: asyncpg.Pool,
    *,
    fixture_id: UUID,
    scheme: PersistentIdentifierScheme,
    suffix: str,
) -> None:
    event_id = uuid4()
    deps = _build_deps(db_pool, ids=[event_id])
    await assign_fixture_persistent_id.bind(deps)(
        AssignFixturePersistentId(fixture_id=fixture_id, scheme=scheme, suffix=suffix),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


def _pidinst_handler(deps: Kernel) -> get_fixture_pidinst.Handler:
    return get_fixture_pidinst.bind(deps)


def _landing_page_url(fixture_id: UUID) -> str:
    return f"https://cora.example/fixtures/{fixture_id}/landing"


@pytest.mark.integration
async def test_get_fixture_pidinst_after_assign_emits_doi_identifier_not_urn(
    db_pool: asyncpg.Pool,
) -> None:
    fixture_id = await _seed_fixture_with_owners_and_model(db_pool)
    await _assign_fixture_persistent_id(
        db_pool,
        fixture_id=fixture_id,
        scheme=PersistentIdentifierScheme.DOI,
        suffix="APS-2BM-FIX-001",
    )
    handler = _pidinst_handler(_build_deps(db_pool, ids=[]))
    view = await handler(
        fixture_id,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert view is not None
    record = to_fixture_pidinst_record(
        view,
        landing_page_url=_landing_page_url(fixture_id),
        publisher=_PUBLISHER,
    )
    assert record.identifier.scheme.value == "DOI"
    assert record.identifier.value == "10.0000/cora-stub/APS-2BM-FIX-001"
    assert not record.identifier.value.startswith("urn:uuid:")


@pytest.mark.integration
async def test_get_fixture_pidinst_without_assign_still_emits_urn_fallback(
    db_pool: asyncpg.Pool,
) -> None:
    fixture_id = await _seed_fixture_with_owners_and_model(db_pool)
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
        landing_page_url=_landing_page_url(fixture_id),
        publisher=_PUBLISHER,
    )
    assert record.identifier.scheme.value == "URN"
    assert record.identifier.value == f"urn:uuid:{fixture_id}"


@pytest.mark.integration
async def test_get_fixture_pidinst_with_handle_scheme_after_assign_emits_handle_identifier(
    db_pool: asyncpg.Pool,
) -> None:
    fixture_id = await _seed_fixture_with_owners_and_model(db_pool)
    await _assign_fixture_persistent_id(
        db_pool,
        fixture_id=fixture_id,
        scheme=PersistentIdentifierScheme.HANDLE,
        suffix="12345",
    )
    handler = _pidinst_handler(_build_deps(db_pool, ids=[]))
    view = await handler(
        fixture_id,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert view is not None
    record = to_fixture_pidinst_record(
        view,
        landing_page_url=_landing_page_url(fixture_id),
        publisher=_PUBLISHER,
    )
    assert record.identifier.scheme.value == "Handle"
    assert record.identifier.value == "20.500.0000/cora-stub/12345"
    assert not record.identifier.value.startswith("urn:uuid:")
