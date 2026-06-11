"""Unit tests for `assemble_pidinst_view`.

Eight tests covering the assembler's composition matrix per section 10
of project_asset_persistent_id_design. Each test pre-seeds an
`InMemoryEventStore` with the canonical event stream(s) the assembler
will fold, then asserts the resulting `AssetPidinstView` carries the
expected shape.

Patterns reused from `test_get_asset_handler.py` (InMemoryEventStore
+ FakeClock) and `_helpers.py` builder VOs.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment._pidinst_types import AssetPidinstView, ModelPidinstView
from cora.equipment.aggregates._partition_rule import Affine
from cora.equipment.aggregates.asset import AssetNotFoundError
from cora.equipment.aggregates.asset.events import (
    AssetFamilyAdded,
    AssetPartitionRuleUpdated,
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
from cora.equipment.aggregates.family.events import (
    FamilyDefined,
)
from cora.equipment.aggregates.family.events import (
    event_type_name as family_event_type_name,
)
from cora.equipment.aggregates.family.events import (
    to_payload as family_to_payload,
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
from cora.equipment.errors import VirtualAxisNotPidinstableError
from cora.equipment.features.get_asset_pidinst._view_assembler import assemble_pidinst_view
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.shared.identity import ActorId

_TEST_ACTOR_ID = ActorId(UUID("00000000-0000-0000-0000-000000000001"))


_NOW = datetime(2025, 4, 15, 9, 30, 0, tzinfo=UTC)
_PUBLISHER = "Argonne National Laboratory"
_LANDING_TEMPLATE = "https://cora.example/assets/{asset_id}/landing"
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


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


async def _seed_asset(
    store: InMemoryEventStore,
    *,
    asset_id: UUID,
    name: str = "Rotary Stage A",
    model_id: UUID | None = None,
    owners: frozenset[AssetOwner] = frozenset(),
    family_ids: tuple[UUID, ...] = (),
    occurred_at: datetime | None = None,
) -> None:
    when = occurred_at or _NOW
    registered = AssetRegistered(
        asset_id=asset_id,
        name=name,
        tier="Device",
        parent_id=uuid4(),
        occurred_at=when,
        model_id=model_id,
        owners=owners,
        commissioned_by=_TEST_ACTOR_ID,
    )
    new_event = to_new_event(
        event_type=event_type_name(registered),
        payload=to_payload(registered),
        occurred_at=when,
        event_id=uuid4(),
        command_name="RegisterAsset",
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await store.append("Asset", asset_id, 0, [new_event])
    for family_id in family_ids:
        added = AssetFamilyAdded(
            asset_id=asset_id,
            family_id=family_id,
            occurred_at=when,
        )
        added_event = to_new_event(
            event_type=event_type_name(added),
            payload=to_payload(added),
            occurred_at=when,
            event_id=uuid4(),
            command_name="AddAssetFamily",
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        version = (await store.load("Asset", asset_id))[1]
        await store.append("Asset", asset_id, version, [added_event])


async def _seed_family(
    store: InMemoryEventStore,
    *,
    family_id: UUID,
    name: str,
) -> None:
    defined = FamilyDefined(
        family_id=family_id,
        name=name,
        occurred_at=_NOW,
        affordances=frozenset(),
    )
    new_event = to_new_event(
        event_type=family_event_type_name(defined),
        payload=family_to_payload(defined),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="DefineFamily",
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await store.append("Family", family_id, 0, [new_event])


async def _seed_model(
    store: InMemoryEventStore,
    *,
    model_id: UUID,
    family_ids: frozenset[UUID],
    manufacturer: Manufacturer | None = None,
) -> None:
    defined = ModelDefined(
        model_id=model_id,
        name="ANT130-L",
        part_number="ANT130-L-RM",
        manufacturer=manufacturer or _aerotech_manufacturer(),
        declared_family_ids=family_ids,
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


@pytest.mark.unit
@pytest.mark.timeout(60, method="thread")
async def test_assemble_pidinst_view_owner_only_returns_view_no_families_no_model() -> None:
    store = InMemoryEventStore()
    asset_id = uuid4()
    await _seed_asset(store, asset_id=asset_id, owners=frozenset({_hzb_owner()}))
    view = await assemble_pidinst_view(
        store,
        asset_id,
        facility_publisher=_PUBLISHER,
        landing_page_template=_LANDING_TEMPLATE,
    )
    assert isinstance(view, AssetPidinstView)
    assert view.asset_id == asset_id
    assert view.model is None
    assert view.family_names == ()
    assert view.family_ids == ()
    assert len(view.owners) == 1
    assert view.owners[0].name == "Helmholtz-Zentrum Berlin"


@pytest.mark.unit
@pytest.mark.timeout(60, method="thread")
async def test_assemble_pidinst_view_with_model_returns_view_with_manufacturer_subset() -> None:
    store = InMemoryEventStore()
    asset_id = uuid4()
    model_id = uuid4()
    family_id = uuid4()
    await _seed_family(store, family_id=family_id, name="RotaryStage")
    await _seed_model(store, model_id=model_id, family_ids=frozenset({family_id}))
    await _seed_asset(
        store,
        asset_id=asset_id,
        model_id=model_id,
        owners=frozenset({_hzb_owner()}),
        family_ids=(family_id,),
    )
    view = await assemble_pidinst_view(
        store,
        asset_id,
        facility_publisher=_PUBLISHER,
        landing_page_template=_LANDING_TEMPLATE,
    )
    assert view.model == ModelPidinstView(
        name="ANT130-L",
        part_number="ANT130-L-RM",
        manufacturer_name="Aerotech",
        manufacturer_identifier="https://ror.org/04bw7nh07",
        manufacturer_identifier_type=ManufacturerIdentifierType.ROR,
    )


@pytest.mark.unit
@pytest.mark.timeout(60, method="thread")
async def test_assemble_pidinst_view_with_single_family_returns_view_with_one_family() -> None:
    store = InMemoryEventStore()
    asset_id = uuid4()
    family_id = uuid4()
    await _seed_family(store, family_id=family_id, name="RotaryStage")
    await _seed_asset(
        store,
        asset_id=asset_id,
        owners=frozenset({_hzb_owner()}),
        family_ids=(family_id,),
    )
    view = await assemble_pidinst_view(
        store,
        asset_id,
        facility_publisher=_PUBLISHER,
        landing_page_template=_LANDING_TEMPLATE,
    )
    assert view.family_names == ("RotaryStage",)
    assert view.family_ids == (family_id,)


@pytest.mark.unit
@pytest.mark.timeout(60, method="thread")
async def test_assemble_pidinst_view_with_three_families_sorts_by_name_asc() -> None:
    store = InMemoryEventStore()
    asset_id = uuid4()
    family_ids: list[UUID] = [uuid4(), uuid4(), uuid4()]
    await _seed_family(store, family_id=family_ids[0], name="Zeta")
    await _seed_family(store, family_id=family_ids[1], name="Alpha")
    await _seed_family(store, family_id=family_ids[2], name="Mu")
    await _seed_asset(
        store,
        asset_id=asset_id,
        owners=frozenset({_hzb_owner()}),
        family_ids=tuple(family_ids),
    )
    view = await assemble_pidinst_view(
        store,
        asset_id,
        facility_publisher=_PUBLISHER,
        landing_page_template=_LANDING_TEMPLATE,
    )
    assert view.family_names == ("Alpha", "Mu", "Zeta")


@pytest.mark.unit
@pytest.mark.timeout(60, method="thread")
async def test_assemble_pidinst_view_with_no_asset_raises_asset_not_found() -> None:
    store = InMemoryEventStore()
    missing_id = uuid4()
    with pytest.raises(AssetNotFoundError) as exc_info:
        await assemble_pidinst_view(
            store,
            missing_id,
            facility_publisher=_PUBLISHER,
            landing_page_template=_LANDING_TEMPLATE,
        )
    assert exc_info.value.asset_id == missing_id


@pytest.mark.unit
@pytest.mark.timeout(60, method="thread")
async def test_assemble_pidinst_view_landing_page_template_passes_through_substitution() -> None:
    store = InMemoryEventStore()
    asset_id = uuid4()
    await _seed_asset(store, asset_id=asset_id, owners=frozenset({_hzb_owner()}))
    view = await assemble_pidinst_view(
        store,
        asset_id,
        facility_publisher=_PUBLISHER,
        landing_page_template="https://other.example/instruments/{asset_id}",
    )
    assert view.landing_page_url == f"https://other.example/instruments/{asset_id}"


@pytest.mark.unit
@pytest.mark.timeout(60, method="thread")
async def test_assemble_pidinst_view_facility_publisher_passes_through_to_view() -> None:
    store = InMemoryEventStore()
    asset_id = uuid4()
    await _seed_asset(store, asset_id=asset_id, owners=frozenset({_hzb_owner()}))
    view = await assemble_pidinst_view(
        store,
        asset_id,
        facility_publisher="HZB BESSY II",
        landing_page_template=_LANDING_TEMPLATE,
    )
    assert view.publisher == "HZB BESSY II"


@pytest.mark.unit
@pytest.mark.timeout(60, method="thread")
async def test_assemble_pidinst_view_publication_year_derives_from_commissioned_at() -> None:
    store = InMemoryEventStore()
    asset_id = uuid4()
    await _seed_asset(
        store,
        asset_id=asset_id,
        owners=frozenset({_hzb_owner()}),
        occurred_at=datetime(2024, 7, 4, 10, 0, 0, tzinfo=UTC),
    )
    view = await assemble_pidinst_view(
        store,
        asset_id,
        facility_publisher=_PUBLISHER,
        landing_page_template=_LANDING_TEMPLATE,
    )
    assert view.commissioned_at == datetime(2024, 7, 4, 10, 0, 0, tzinfo=UTC)
    assert view.publication_year == 2024


@pytest.mark.unit
@pytest.mark.timeout(60, method="thread")
async def test_assemble_pidinst_view_with_virtual_axis_raises_not_pidinstable() -> None:
    """Assets carrying a non-None partition_rule are virtual axes and
    PIDINST-ineligible per PIDINST v1.0's Manufacturer + Owner mandate.
    The assembler rejects them BEFORE any Model / Family load so the
    route returns 404 (resource not applicable), not 409 (which would
    mis-signal "fix this by adding a Manufacturer").
    """
    store = InMemoryEventStore()
    asset_id = uuid4()
    await _seed_asset(store, asset_id=asset_id, owners=frozenset({_hzb_owner()}))
    rule_updated = AssetPartitionRuleUpdated(
        asset_id=asset_id,
        partition_rule=Affine(gain=2.0, offset=1.0),
        occurred_at=_NOW,
    )
    rule_event = to_new_event(
        event_type=event_type_name(rule_updated),
        payload=to_payload(rule_updated),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="UpdateAssetPartitionRule",
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    version = (await store.load("Asset", asset_id))[1]
    await store.append("Asset", asset_id, version, [rule_event])

    with pytest.raises(VirtualAxisNotPidinstableError) as exc_info:
        await assemble_pidinst_view(
            store,
            asset_id,
            facility_publisher=_PUBLISHER,
            landing_page_template=_LANDING_TEMPLATE,
        )
    assert exc_info.value.asset_id == asset_id
