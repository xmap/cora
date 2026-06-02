"""Unit tests for the `register_asset` application handler."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.equipment import EquipmentHandlers, UnauthorizedError, wire_equipment
from cora.equipment.aggregates.asset import (
    AssetLevel,
    InvalidAssetNameError,
    InvalidAssetParentError,
)
from cora.equipment.aggregates.model import (
    Manufacturer,
    ManufacturerName,
    Model,
    ModelName,
    ModelNotFoundError,
    PartNumber,
)
from cora.equipment.features import register_asset
from cora.equipment.features.register_asset import RegisterAsset
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000007ab1")
_EVENT_ID = UUID("01900000-0000-7000-8000-000000007be1")
_PARENT_ID = UUID("01900000-0000-7000-8000-00000000a000")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    """Thin wrapper preserving this file's ID list + clock."""
    return _build_deps_shared(
        ids=[_NEW_ID, _EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


@pytest.mark.unit
async def test_handler_returns_generated_asset_id() -> None:
    deps = _build_deps()
    handler = register_asset.bind(deps)

    result = await handler(
        RegisterAsset(name="APS-2BM", level=AssetLevel.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert result == _NEW_ID


@pytest.mark.unit
async def test_handler_appends_asset_registered_event_to_store() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_asset.bind(deps)

    await handler(
        RegisterAsset(name="APS-2BM", level=AssetLevel.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Asset", _NEW_ID)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "AssetRegistered"
    assert stored.schema_version == 1
    assert stored.payload == {
        "asset_id": str(_NEW_ID),
        "name": "APS-2BM",
        "level": "Unit",
        "parent_id": str(_PARENT_ID),
        "occurred_at": _NOW.isoformat(),
    }
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.event_id == _EVENT_ID
    assert stored.metadata == {"command": "RegisterAsset"}
    assert stored.occurred_at == _NOW


@pytest.mark.unit
async def test_handler_appends_enterprise_asset_with_null_parent() -> None:
    """The other genesis path: Enterprise root, parent_id=None. Pinned
    because the payload's null serialization is one of two paths the
    evolver round-trip relies on."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_asset.bind(deps)

    await handler(
        RegisterAsset(name="ANL", level=AssetLevel.ENTERPRISE, parent_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Asset", _NEW_ID)
    assert events[0].payload["parent_id"] is None
    assert events[0].payload["level"] == "Enterprise"


@pytest.mark.unit
async def test_handler_trims_asset_name_via_value_object() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_asset.bind(deps)

    await handler(
        RegisterAsset(name="  APS-2BM  ", level=AssetLevel.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Asset", _NEW_ID)
    assert events[0].payload["name"] == "APS-2BM"


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = _build_deps(deny=True)
    handler = register_asset.bind(deps)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            RegisterAsset(name="APS-2BM", level=AssetLevel.UNIT, parent_id=_PARENT_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_does_not_append_when_denied() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store, deny=True)
    handler = register_asset.bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            RegisterAsset(name="APS-2BM", level=AssetLevel.UNIT, parent_id=_PARENT_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, version = await store.load("Asset", _NEW_ID)
    assert events == []
    assert version == 0


@pytest.mark.unit
async def test_handler_propagates_invalid_asset_name_error() -> None:
    deps = _build_deps()
    handler = register_asset.bind(deps)

    with pytest.raises(InvalidAssetNameError):
        await handler(
            RegisterAsset(name="   ", level=AssetLevel.SITE, parent_id=_PARENT_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_propagates_invalid_asset_parent_error_for_enterprise() -> None:
    """Hierarchy rule violation surfaces as InvalidAssetParentError;
    the route maps it to 400. Pinned because authz happens before
    decider, so a denied request never reaches this path — the test
    confirms the decider error propagates through the handler chain
    when authz allows."""
    deps = _build_deps()
    handler = register_asset.bind(deps)

    with pytest.raises(InvalidAssetParentError):
        await handler(
            RegisterAsset(name="Federated", level=AssetLevel.ENTERPRISE, parent_id=_PARENT_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_propagates_invalid_asset_parent_error_for_non_enterprise() -> None:
    deps = _build_deps()
    handler = register_asset.bind(deps)

    with pytest.raises(InvalidAssetParentError):
        await handler(
            RegisterAsset(name="Orphan", level=AssetLevel.UNIT, parent_id=None),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_asset.bind(deps)

    await handler(
        RegisterAsset(name="APS-2BM", level=AssetLevel.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Asset", _NEW_ID)
    assert events[0].causation_id == causation


@pytest.mark.unit
def test_wire_equipment_includes_register_asset() -> None:
    deps = _build_deps()
    handlers = wire_equipment(deps)
    assert isinstance(handlers, EquipmentHandlers)
    assert callable(handlers.register_asset)
    # earlier-phase handlers still wired (regression guards)
    assert callable(handlers.define_family)
    assert callable(handlers.get_family)


@pytest.mark.unit
async def test_handler_raises_model_not_found_when_model_stream_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When command.model_id is supplied but the Model stream returns
    None, the handler raises ModelNotFoundError BEFORE appending the
    AssetRegistered event. The 404 mapping is wired at the BC route
    layer (`_handle_not_found`)."""
    unknown_model_id = UUID("01900000-0000-7000-8000-000000def001")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)

    async def _load_none(event_store: object, model_id: UUID) -> Model | None:
        _ = (event_store, model_id)
        return None

    monkeypatch.setattr("cora.equipment.features.register_asset.handler.load_model", _load_none)

    handler = register_asset.bind(deps)
    with pytest.raises(ModelNotFoundError) as exc_info:
        await handler(
            RegisterAsset(
                name="APS-2BM",
                level=AssetLevel.UNIT,
                parent_id=_PARENT_ID,
                model_id=unknown_model_id,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.model_id == unknown_model_id

    events, version = await store.load("Asset", _NEW_ID)
    assert events == []
    assert version == 0


@pytest.mark.unit
async def test_handler_proceeds_when_model_id_resolves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Happy path: when load_model returns a Model snapshot, the
    handler appends AssetRegistered carrying the model_id verbatim."""
    model_id = UUID("01900000-0000-7000-8000-000000ade001")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)

    async def _load_model(event_store: object, requested_id: UUID) -> Model | None:
        _ = event_store
        assert requested_id == model_id
        return Model(
            id=requested_id,
            name=ModelName("EigerX-9M"),
            manufacturer=Manufacturer(name=ManufacturerName("Dectris")),
            part_number=PartNumber("EX9M-001"),
            declared_families=frozenset({UUID("01900000-0000-7000-8000-000000fa1001")}),
        )

    monkeypatch.setattr("cora.equipment.features.register_asset.handler.load_model", _load_model)

    handler = register_asset.bind(deps)
    await handler(
        RegisterAsset(
            name="APS-2BM-Det",
            level=AssetLevel.DEVICE,
            parent_id=_PARENT_ID,
            model_id=model_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Asset", _NEW_ID)
    assert version == 1
    assert events[0].event_type == "AssetRegistered"
    assert events[0].payload["model_id"] == str(model_id)


@pytest.mark.unit
async def test_handler_omits_model_id_payload_key_when_command_has_none() -> None:
    """When command.model_id is None the handler must NOT attempt a
    Model load (no monkeypatch needed) and the emitted payload must
    omit the `model_id` key entirely (mirrors the `drawing` omit-when-
    None convention locked in events.py)."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)

    handler = register_asset.bind(deps)
    await handler(
        RegisterAsset(
            name="APS-2BM",
            level=AssetLevel.UNIT,
            parent_id=_PARENT_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Asset", _NEW_ID)
    assert "model_id" not in events[0].payload


@pytest.mark.unit
async def test_wired_handler_propagates_causation_id_through_full_composition() -> None:
    """End-to-end check that causation_id survives the
    `with_tracing(with_idempotency(bare))` chain in wire.py."""
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handlers = wire_equipment(deps)

    await handlers.register_asset(
        RegisterAsset(name="APS-2BM", level=AssetLevel.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Asset", _NEW_ID)
    assert events[0].causation_id == causation
