"""Unit tests for `assemble_fixture_pidinst_view`.

Covers the five view-assembler scenarios called out in section 15.1 of
project_fixture_pidinst_design: empty bindings, overlapping-owner
dedupe, unminted-bound-Asset component skipping, missing-Model raise,
and one-level-depth restriction.

Each test pre-seeds an `InMemoryEventStore` with the canonical event
stream(s) the assembler will fold (Asset + Model + Fixture), then asserts
the resulting `FixturePidinstView` carries the expected shape. Pattern
mirrors `test_asset_pidinst_view_assembler.py` (InMemoryEventStore seed
via `to_new_event`) plus the deps wiring in `test_get_fixture_handler.py`
(`build_deps(event_store=preseeded)`).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.asset.events import (
    AssetPersistentIdAssigned,
    AssetRegistered,
    event_type_name,
    to_payload,
)
from cora.equipment.aggregates.asset.state import (
    AssetOwner,
    AssetOwnerContact,
    AssetOwnerIdentifier,
    AssetOwnerIdentifierType,
    AssetOwnerName,
)
from cora.equipment.aggregates.fixture import SlotAssetBinding
from cora.equipment.aggregates.fixture.events import (
    FixtureRegistered,
)
from cora.equipment.aggregates.fixture.events import (
    event_type_name as fixture_event_type_name,
)
from cora.equipment.aggregates.fixture.events import (
    to_payload as fixture_to_payload,
)
from cora.equipment.aggregates.model.events import (
    ModelDefined,
)
from cora.equipment.aggregates.model.events import (
    event_type_name as model_event_type_name,
)
from cora.equipment.aggregates.model.events import (
    to_payload as model_to_payload,
)
from cora.equipment.aggregates.model.state import (
    Manufacturer,
    ManufacturerIdentifier,
    ManufacturerIdentifierType,
    ManufacturerName,
)
from cora.equipment.errors import FixtureManufacturerStateNotAvailableError
from cora.equipment.features.get_fixture_pidinst._view_assembler import (
    assemble_fixture_pidinst_view,
)
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.shared.identifier import PersistentIdentifier, PersistentIdentifierScheme
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps as _build_deps_shared

_TEST_ACTOR_ID = ActorId(UUID("00000000-0000-0000-0000-000000000001"))


pytestmark = pytest.mark.timeout(60, method="thread")

_NOW = datetime(2026, 6, 5, 9, 30, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _hzb_owner() -> AssetOwner:
    return AssetOwner(
        name=AssetOwnerName("Helmholtz-Zentrum Berlin"),
        contact=AssetOwnerContact("instrument-data@hzb.de"),
        identifier=AssetOwnerIdentifier("https://ror.org/02aj13c28"),
        identifier_type=AssetOwnerIdentifierType("ROR"),
    )


def _anl_owner() -> AssetOwner:
    return AssetOwner(
        name=AssetOwnerName("Argonne National Laboratory"),
        contact=AssetOwnerContact("ops@anl.gov"),
        identifier=AssetOwnerIdentifier("https://ror.org/05gvnxz63"),
        identifier_type=AssetOwnerIdentifierType("ROR"),
    )


def _aerotech_manufacturer() -> Manufacturer:
    return Manufacturer(
        name=ManufacturerName("Aerotech"),
        identifier=ManufacturerIdentifier("https://ror.org/04bw7nh07"),
        identifier_type=ManufacturerIdentifierType.ROR,
    )


def _flir_manufacturer() -> Manufacturer:
    return Manufacturer(
        name=ManufacturerName("FLIR"),
        identifier=ManufacturerIdentifier("https://ror.org/0432n7p17"),
        identifier_type=ManufacturerIdentifierType.ROR,
    )


async def _seed_asset(
    store: InMemoryEventStore,
    *,
    asset_id: UUID,
    name: str = "Rotary Stage A",
    model_id: UUID | None = None,
    owners: frozenset[AssetOwner] = frozenset(),
    persistent_id: PersistentIdentifier | None = None,
    occurred_at: datetime | None = None,
) -> None:
    when = occurred_at or _NOW
    registered = AssetRegistered(
        asset_id=asset_id,
        name=name,
        level="Device",
        parent_id=uuid4(),
        occurred_at=when,
        model_id=model_id,
        owners=owners,
        commissioned_by=_TEST_ACTOR_ID,
    )
    registered_event = to_new_event(
        event_type=event_type_name(registered),
        payload=to_payload(registered),
        occurred_at=when,
        event_id=uuid4(),
        command_name="RegisterAsset",
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await store.append("Asset", asset_id, 0, [registered_event])
    if persistent_id is not None:
        assigned = AssetPersistentIdAssigned(
            asset_id=asset_id,
            persistent_id_scheme=persistent_id.scheme.value,
            persistent_id_value=persistent_id.value,
            occurred_at=when,
        )
        assigned_event = to_new_event(
            event_type=event_type_name(assigned),
            payload=to_payload(assigned),
            occurred_at=when,
            event_id=uuid4(),
            command_name="AssignAssetPersistentId",
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        await store.append("Asset", asset_id, 1, [assigned_event])


async def _seed_model(
    store: InMemoryEventStore,
    *,
    model_id: UUID,
    manufacturer: Manufacturer,
    family_ids: frozenset[UUID] | None = None,
    name: str = "ANT130-L",
    part_number: str = "ANT130-L-RM",
) -> None:
    defined = ModelDefined(
        model_id=model_id,
        name=name,
        part_number=part_number,
        manufacturer=manufacturer,
        declared_family_ids=family_ids or frozenset({uuid4()}),
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=model_event_type_name(defined),
        payload=model_to_payload(defined),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="DefineModel",
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await store.append("Model", model_id, 0, [new_event])


async def _seed_fixture(
    store: InMemoryEventStore,
    *,
    fixture_id: UUID,
    slot_asset_bindings: frozenset[SlotAssetBinding],
    assembly_id: UUID | None = None,
    surface_id: UUID | None = None,
) -> None:
    registered = FixtureRegistered(
        fixture_id=fixture_id,
        assembly_id=assembly_id or uuid4(),
        assembly_content_hash="a" * 64,
        surface_id=surface_id or uuid4(),
        slot_asset_bindings=slot_asset_bindings,
        parameter_overrides={},
        occurred_at=_NOW,
        registered_by=_TEST_ACTOR_ID,
    )
    new_event = to_new_event(
        event_type=fixture_event_type_name(registered),
        payload=fixture_to_payload(registered),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="RegisterFixture",
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await store.append("Fixture", fixture_id, 0, [new_event])


@pytest.mark.unit
async def test_assemble_view_with_no_bound_assets_returns_empty_owners_manufacturers() -> None:
    store = InMemoryEventStore()
    fixture_id = uuid4()
    await _seed_fixture(store, fixture_id=fixture_id, slot_asset_bindings=frozenset())
    deps = _build_deps_shared(ids=[], now=_NOW, event_store=store)

    view = await assemble_fixture_pidinst_view(fixture_id, deps)

    assert view is not None
    assert view.fixture_id == fixture_id
    assert view.owners == ()
    assert view.manufacturers == ()
    assert view.components == ()


@pytest.mark.unit
async def test_assemble_view_with_two_bound_assets_with_overlapping_owners_dedups() -> None:
    store = InMemoryEventStore()
    asset_a_id = UUID("01900000-0000-7000-8000-0000000a0001")
    asset_b_id = UUID("01900000-0000-7000-8000-0000000a0002")
    shared_owner = _hzb_owner()
    await _seed_asset(
        store,
        asset_id=asset_a_id,
        name="Camera A",
        owners=frozenset({shared_owner, _anl_owner()}),
    )
    await _seed_asset(
        store,
        asset_id=asset_b_id,
        name="Stage B",
        owners=frozenset({shared_owner}),
    )
    fixture_id = uuid4()
    await _seed_fixture(
        store,
        fixture_id=fixture_id,
        slot_asset_bindings=frozenset(
            {
                SlotAssetBinding(slot_name="camera", asset_id=asset_a_id),
                SlotAssetBinding(slot_name="stage", asset_id=asset_b_id),
            }
        ),
    )
    deps = _build_deps_shared(ids=[], now=_NOW, event_store=store)

    view = await assemble_fixture_pidinst_view(fixture_id, deps)

    assert view is not None
    assert len(view.owners) == 2
    assert [owner.name.value for owner in view.owners] == [
        "Argonne National Laboratory",
        "Helmholtz-Zentrum Berlin",
    ]


@pytest.mark.unit
async def test_assemble_view_with_unminted_bound_asset_skips_components_surfaces_description() -> (
    None
):
    store = InMemoryEventStore()
    minted_asset_id = UUID("01900000-0000-7000-8000-0000000b0001")
    unminted_asset_id = UUID("01900000-0000-7000-8000-0000000b0002")
    minted_pid = PersistentIdentifier(
        scheme=PersistentIdentifierScheme.DOI,
        value="10.5281/zenodo.minted-asset",
    )
    await _seed_asset(
        store,
        asset_id=minted_asset_id,
        name="Minted Camera",
        owners=frozenset({_hzb_owner()}),
        persistent_id=minted_pid,
    )
    await _seed_asset(
        store,
        asset_id=unminted_asset_id,
        name="Unminted Stage",
        owners=frozenset({_hzb_owner()}),
    )
    fixture_id = uuid4()
    await _seed_fixture(
        store,
        fixture_id=fixture_id,
        slot_asset_bindings=frozenset(
            {
                SlotAssetBinding(slot_name="camera", asset_id=minted_asset_id),
                SlotAssetBinding(slot_name="stage", asset_id=unminted_asset_id),
            }
        ),
    )
    deps = _build_deps_shared(ids=[], now=_NOW, event_store=store)

    view = await assemble_fixture_pidinst_view(fixture_id, deps)

    assert view is not None
    assert len(view.components) == 1
    assert view.components[0].component_id == minted_asset_id
    assert view.components[0].value == minted_pid.value
    assert view.components[0].scheme == PersistentIdentifierScheme.DOI


@pytest.mark.unit
async def test_assemble_view_bound_asset_model_missing_raises_manufacturer_state_unavailable() -> (
    None
):
    store = InMemoryEventStore()
    asset_id = UUID("01900000-0000-7000-8000-0000000c0001")
    missing_model_id = UUID("01900000-0000-7000-8000-0000000c00ff")
    await _seed_asset(
        store,
        asset_id=asset_id,
        name="Camera With Phantom Model",
        model_id=missing_model_id,
        owners=frozenset({_hzb_owner()}),
    )
    fixture_id = uuid4()
    await _seed_fixture(
        store,
        fixture_id=fixture_id,
        slot_asset_bindings=frozenset({SlotAssetBinding(slot_name="camera", asset_id=asset_id)}),
    )
    deps = _build_deps_shared(ids=[], now=_NOW, event_store=store)

    with pytest.raises(FixtureManufacturerStateNotAvailableError) as exc_info:
        await assemble_fixture_pidinst_view(fixture_id, deps)
    assert exc_info.value.fixture_id == fixture_id


@pytest.mark.unit
async def test_assemble_fixture_pidinst_view_respects_one_level_depth_only() -> None:
    store = InMemoryEventStore()
    asset_a_id = UUID("01900000-0000-7000-8000-0000000d0001")
    asset_b_id = UUID("01900000-0000-7000-8000-0000000d0002")
    model_a_id = UUID("01900000-0000-7000-8000-0000000d00a0")
    model_b_id = UUID("01900000-0000-7000-8000-0000000d00b0")
    await _seed_model(
        store,
        model_id=model_a_id,
        manufacturer=_aerotech_manufacturer(),
        name="Aerotech ANT130-L",
        part_number="ANT130-L-AERO",
    )
    await _seed_model(
        store,
        model_id=model_b_id,
        manufacturer=_flir_manufacturer(),
        name="FLIR Blackfly",
        part_number="BFLY-PGE-23S6M",
    )
    await _seed_asset(
        store,
        asset_id=asset_a_id,
        name="Rotary Stage",
        model_id=model_a_id,
        owners=frozenset({_hzb_owner()}),
    )
    await _seed_asset(
        store,
        asset_id=asset_b_id,
        name="Camera",
        model_id=model_b_id,
        owners=frozenset({_anl_owner()}),
    )
    inner_fixture_id = UUID("01900000-0000-7000-8000-0000000d0fff")
    await _seed_fixture(
        store,
        fixture_id=inner_fixture_id,
        slot_asset_bindings=frozenset({SlotAssetBinding(slot_name="inner", asset_id=asset_b_id)}),
    )
    outer_fixture_id = uuid4()
    await _seed_fixture(
        store,
        fixture_id=outer_fixture_id,
        slot_asset_bindings=frozenset({SlotAssetBinding(slot_name="stage", asset_id=asset_a_id)}),
    )
    deps = _build_deps_shared(ids=[], now=_NOW, event_store=store)

    view = await assemble_fixture_pidinst_view(outer_fixture_id, deps)

    assert view is not None
    assert len(view.components) == 0
    assert [m.name for m in view.manufacturers] == ["Aerotech"]
    assert [o.name.value for o in view.owners] == ["Helmholtz-Zentrum Berlin"]
