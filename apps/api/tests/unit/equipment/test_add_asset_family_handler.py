"""Unit tests for the `add_asset_family` application handler.

Mirror of `test_relocate_asset_handler.py` (also a longhand
two-id-arg slice). Covers the strict-not-idempotent re-add guard,
the Decommissioned-asset guard, auth deny, causation_id propagation,
and the wire-equipment smoke.

Also covers the cross-BC subset gate (Model binding): when an Asset
carries a `model_id`, the handler loads the Model stream snapshot,
asserts `Model.declared_families` is a subset of the post-add Asset
families, and raises `AssetModelMismatch` otherwise. The Model load
is monkeypatched per the model-binding design memo precedent (same
shape as `update_asset_settings` Family-stream loads).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment import EquipmentHandlers, UnauthorizedError, wire_equipment
from cora.equipment.aggregates.asset import (
    AssetCannotAddFamilyError,
    AssetLevel,
    AssetModelMismatch,
    AssetNotFoundError,
)
from cora.equipment.aggregates.asset.events import AssetRegistered
from cora.equipment.aggregates.asset.events import (
    event_type_name as asset_event_type_name,
)
from cora.equipment.aggregates.asset.events import to_payload as asset_to_payload
from cora.equipment.aggregates.model import (
    Manufacturer,
    ManufacturerName,
    Model,
    ModelName,
    ModelNotFoundError,
    PartNumber,
)
from cora.equipment.features import (
    add_asset_family,
    decommission_asset,
    register_asset,
)
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.add_asset_family import handler as add_asset_family_handler
from cora.equipment.features.decommission_asset import DecommissionAsset
from cora.equipment.features.register_asset import RegisterAsset
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports.event_store import EventStore
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000000fa01")
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-00000000fa02")
_DECOMMISSION_EVENT_ID = UUID("01900000-0000-7000-8000-00000000fa03")
_ADD_EVENT_ID = UUID("01900000-0000-7000-8000-00000000fa04")
_PARENT_ID = UUID("01900000-0000-7000-8000-00000000a000")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CAP1 = UUID("01900000-0000-7000-8000-000000000111")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    """Thin wrapper preserving this file's ID list + clock."""
    return _build_deps_shared(
        ids=[_NEW_ID, _REGISTER_EVENT_ID, _DECOMMISSION_EVENT_ID, _ADD_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


async def _register_asset_helper(deps: Kernel) -> UUID:
    return await register_asset.bind(deps)(
        RegisterAsset(name="APS-2BM", level=AssetLevel.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.unit
async def test_handler_returns_none_on_success() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    result = await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=_CAP1),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_asset_capability_added_event_with_family_id() -> None:
    """Pinned: payload carries `family_id` (not just asset_id).
    The metadata field should be the canonical command name so log
    queries for the audit trail work end-to-end."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=_CAP1),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Asset", asset_id)
    assert version == 2  # AssetRegistered + AssetFamilyAdded
    assert [e.event_type for e in events] == [
        "AssetRegistered",
        "AssetFamilyAdded",
    ]
    added = events[1]
    # FixedIdGenerator: registered consumes _NEW_ID (asset_id) +
    # _REGISTER_EVENT_ID, then add consumes _DECOMMISSION_EVENT_ID
    # (intended for decommission but skipped here).
    assert added.event_id == _DECOMMISSION_EVENT_ID
    assert added.metadata == {"command": "AddAssetFamily"}
    assert added.payload["family_id"] == str(_CAP1)


@pytest.mark.unit
async def test_handler_raises_asset_not_found_when_asset_does_not_exist() -> None:
    deps = _build_deps()
    handler = add_asset_family.bind(deps)

    with pytest.raises(AssetNotFoundError):
        await handler(
            AddAssetFamily(asset_id=uuid4(), family_id=_CAP1),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_add_when_capability_already_present() -> None:
    """Strict-not-idempotent: re-adding raises."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    handler = add_asset_family.bind(deps)
    await handler(
        AddAssetFamily(asset_id=asset_id, family_id=_CAP1),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    with pytest.raises(AssetCannotAddFamilyError) as exc_info:
        await handler(
            AddAssetFamily(asset_id=asset_id, family_id=_CAP1),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.asset_id == asset_id
    assert exc_info.value.family_id == _CAP1
    assert "already" in exc_info.value.reason


@pytest.mark.unit
async def test_handler_raises_cannot_add_when_asset_is_decommissioned() -> None:
    """Decommissioned guard via the handler path."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    await decommission_asset.bind(deps)(
        DecommissionAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    handler = add_asset_family.bind(deps)
    with pytest.raises(AssetCannotAddFamilyError) as exc_info:
        await handler(
            AddAssetFamily(asset_id=asset_id, family_id=_CAP1),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert "Decommissioned" in exc_info.value.reason


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    deny_deps = _build_deps(event_store=store, deny=True)
    with pytest.raises(UnauthorizedError) as exc_info:
        await add_asset_family.bind(deny_deps)(
            AddAssetFamily(asset_id=asset_id, family_id=_CAP1),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=_CAP1),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Asset", asset_id)
    assert events[1].causation_id == causation


@pytest.mark.unit
def test_wire_equipment_includes_add_asset_family() -> None:
    deps = _build_deps()
    handlers = wire_equipment(deps)
    assert isinstance(handlers, EquipmentHandlers)
    assert callable(handlers.add_asset_family)


# ---------------------------------------------------------------------------
# Cross-BC subset gate (Asset.model_id binding).
#
# The handler loads the bound Model (when `state.model_id is not None`)
# and asserts `Model.declared_families` is a subset of the post-add
# `state.family_ids | {command.family_id}`. The four scenarios below
# cover: (a) bound+satisfied success, (b) bound+violated mismatch,
# (c) bound+Model-stream-missing raises ModelNotFoundError,
# (d) unbound (model_id=None) proceeds with no Model load.
# ---------------------------------------------------------------------------


_MODEL_ID = UUID("01900000-0000-7000-8000-0000000c0d01")
_CAP_DECLARED = UUID("01900000-0000-7000-8000-0000000c0d02")
_CAP_EXTRA = UUID("01900000-0000-7000-8000-0000000c0d03")
_PRIOR = datetime(2026, 5, 10, 11, 0, 0, tzinfo=UTC)


def _make_model(
    *,
    model_id: UUID = _MODEL_ID,
    declared_families: frozenset[UUID] | None = None,
) -> Model:
    """Build a Model state aggregate for monkeypatched load_model."""
    return Model(
        id=model_id,
        name=ModelName("Aerotech ANT130-L"),
        manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
        part_number=PartNumber("ANT130-L"),
        declared_families=declared_families
        if declared_families is not None
        else frozenset({_CAP_DECLARED}),
    )


async def _seed_asset_with_model_id(
    store: InMemoryEventStore,
    asset_id: UUID,
    *,
    model_id: UUID | None,
) -> None:
    """Append an `AssetRegistered` event carrying `model_id` directly.

    The current `register_asset` slice does not yet accept a
    `model_id` argument, so handler tests that need to fold an Asset
    state with `model_id` set seed the genesis event directly via the
    event store. The payload-shape round-trip is exercised by the
    PG integration test.
    """
    registered = AssetRegistered(
        asset_id=asset_id,
        name="APS-2BM",
        level=AssetLevel.UNIT,
        parent_id=_PARENT_ID,
        occurred_at=_PRIOR,
        model_id=model_id,
    )
    new_event = to_new_event(
        event_type=asset_event_type_name(registered),
        payload=asset_to_payload(registered),
        occurred_at=_PRIOR,
        event_id=uuid4(),
        command_name="RegisterAsset",
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
    )
    await store.append(
        stream_type="Asset",
        stream_id=asset_id,
        expected_version=0,
        events=[new_event],
    )


@pytest.mark.unit
async def test_handler_succeeds_when_bound_model_subset_is_satisfied_post_add(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Asset bound to Model; post-add family set is a superset of
    `Model.declared_families` (the family being added is the only
    declared family). Subset gate passes; event is appended as usual."""
    asset_id = UUID("01900000-0000-7000-8000-0000000c0d10")
    store = InMemoryEventStore()
    await _seed_asset_with_model_id(store, asset_id, model_id=_MODEL_ID)
    deps = _build_deps(event_store=store)

    captured: dict[str, UUID] = {}

    async def fake_load_model(event_store: EventStore, model_id: UUID) -> Model | None:
        _ = event_store
        captured["model_id"] = model_id
        return _make_model(declared_families=frozenset({_CAP_DECLARED}))

    monkeypatch.setattr(add_asset_family_handler, "load_model", fake_load_model)

    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=_CAP_DECLARED),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert captured["model_id"] == _MODEL_ID
    events, version = await store.load("Asset", asset_id)
    assert version == 2
    assert [e.event_type for e in events] == ["AssetRegistered", "AssetFamilyAdded"]


@pytest.mark.unit
async def test_handler_raises_asset_model_mismatch_when_subset_is_violated_post_add(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Asset bound to Model; post-add family set still missing one of
    `Model.declared_families`. Subset gate fails; AssetModelMismatch
    raised, no event appended, Asset stream stays at version 1."""
    asset_id = UUID("01900000-0000-7000-8000-0000000c0d11")
    store = InMemoryEventStore()
    await _seed_asset_with_model_id(store, asset_id, model_id=_MODEL_ID)
    deps = _build_deps(event_store=store)

    # Model declares TWO families; the add provides only one of them
    # and the Asset has no families yet, so the post-add set is
    # {_CAP_EXTRA} which is not a superset of {_CAP_DECLARED, _CAP_EXTRA}.
    async def fake_load_model(event_store: EventStore, model_id: UUID) -> Model | None:
        _ = (event_store, model_id)
        return _make_model(declared_families=frozenset({_CAP_DECLARED, _CAP_EXTRA}))

    monkeypatch.setattr(add_asset_family_handler, "load_model", fake_load_model)

    with pytest.raises(AssetModelMismatch) as exc_info:
        await add_asset_family.bind(deps)(
            AddAssetFamily(asset_id=asset_id, family_id=_CAP_EXTRA),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    assert exc_info.value.asset_id == asset_id
    assert exc_info.value.model_id == _MODEL_ID
    assert exc_info.value.declared_families == frozenset({_CAP_DECLARED, _CAP_EXTRA})
    assert exc_info.value.asset_family_ids == frozenset({_CAP_EXTRA})

    _, version = await store.load("Asset", asset_id)
    assert version == 1


@pytest.mark.unit
async def test_handler_raises_model_not_found_when_bound_model_stream_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Asset bound to Model but the Model stream cannot be loaded
    (returns None). The handler raises ModelNotFoundError; no Asset
    event is appended."""
    asset_id = UUID("01900000-0000-7000-8000-0000000c0d12")
    store = InMemoryEventStore()
    await _seed_asset_with_model_id(store, asset_id, model_id=_MODEL_ID)
    deps = _build_deps(event_store=store)

    async def fake_load_model(event_store: EventStore, model_id: UUID) -> Model | None:
        _ = (event_store, model_id)
        return None

    monkeypatch.setattr(add_asset_family_handler, "load_model", fake_load_model)

    with pytest.raises(ModelNotFoundError) as exc_info:
        await add_asset_family.bind(deps)(
            AddAssetFamily(asset_id=asset_id, family_id=_CAP_DECLARED),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    assert exc_info.value.model_id == _MODEL_ID
    _, version = await store.load("Asset", asset_id)
    assert version == 1


@pytest.mark.unit
async def test_handler_skips_model_load_when_asset_is_unbound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Asset has `model_id=None`. The handler does not call
    load_model and proceeds straight to decide+append. Verified by
    monkeypatching load_model to a sentinel that raises if called."""
    asset_id = UUID("01900000-0000-7000-8000-0000000c0d13")
    store = InMemoryEventStore()
    await _seed_asset_with_model_id(store, asset_id, model_id=None)
    deps = _build_deps(event_store=store)

    async def sentinel_load_model(event_store: EventStore, model_id: UUID) -> Model | None:
        _ = (event_store, model_id)
        pytest.fail("load_model should not be called for an unbound Asset")

    monkeypatch.setattr(add_asset_family_handler, "load_model", sentinel_load_model)

    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=_CAP_DECLARED),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Asset", asset_id)
    assert version == 2
    assert [e.event_type for e in events] == ["AssetRegistered", "AssetFamilyAdded"]
