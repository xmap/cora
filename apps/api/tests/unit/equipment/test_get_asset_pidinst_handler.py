"""Unit tests for the `get_asset_pidinst` query handler.

Five tests covering the handler's success + the four propagation
paths per section 10 of project_asset_persistent_id_design:

  - Returns a `PidinstRecord` for a fully populated asset.
  - Propagates `AssetNotFoundError` to the caller (route maps 404).
  - Propagates `OwnerStateNotAvailableError` (route maps 409).
  - Propagates `ManufacturerStateNotAvailableError` (route maps 409).
  - Logs + re-raises `PidinstRecordInvariantError` (route maps 500
    via FastAPI default per L11; the handler closes the observability
    gap that the bare-500 path would otherwise leave because L22
    forbids logging inside the serializer).

The handler is thin (assemble + serialize); these tests pin the
propagation behavior so the route's exception-handler tuples are
exercised end-to-end at the integration tier.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment._pidinst_types import PidinstRecord
from cora.equipment.aggregates.asset import AssetNotFoundError
from cora.equipment.aggregates.asset.events import (
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
from cora.equipment.errors import (
    ManufacturerStateNotAvailableError,
    OwnerStateNotAvailableError,
    PidinstRecordInvariantError,
)
from cora.equipment.features import get_asset_pidinst
from cora.equipment.features.get_asset_pidinst import GetAssetPidinst
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps as _build_deps_shared

_TEST_ACTOR_ID = ActorId(UUID("00000000-0000-0000-0000-000000000001"))


_NOW = datetime(2025, 4, 15, 9, 30, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(event_store: InMemoryEventStore | None = None) -> Kernel:
    return _build_deps_shared(ids=[], now=_NOW, event_store=event_store)


def _owner() -> AssetOwner:
    return AssetOwner(
        name=AssetOwnerName("Helmholtz-Zentrum Berlin"),
        contact=AssetOwnerContact("instrument-data@hzb.de"),
        identifier=AssetOwnerIdentifier("https://ror.org/02aj13c28"),
        identifier_type=AssetOwnerIdentifierType("ROR"),
    )


def _manufacturer() -> Manufacturer:
    return Manufacturer(
        name=ManufacturerName("Aerotech"),
        identifier=ManufacturerIdentifier("https://ror.org/04bw7nh07"),
        identifier_type=ManufacturerIdentifierType.ROR,
    )


async def _seed_asset_registered(
    store: InMemoryEventStore,
    *,
    asset_id: UUID,
    model_id: UUID | None,
    owners: frozenset[AssetOwner],
) -> None:
    registered = AssetRegistered(
        asset_id=asset_id,
        name="Rotary Stage A",
        level="Device",
        parent_id=uuid4(),
        occurred_at=_NOW,
        model_id=model_id,
        owners=owners,
        commissioned_by=_TEST_ACTOR_ID,
    )
    new_event = to_new_event(
        event_type=event_type_name(registered),
        payload=to_payload(registered),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="RegisterAsset",
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await store.append("Asset", asset_id, 0, [new_event])


async def _seed_model_defined(
    store: InMemoryEventStore,
    *,
    model_id: UUID,
) -> None:
    defined = ModelDefined(
        model_id=model_id,
        name="ANT130-L",
        part_number="ANT130-L-RM",
        manufacturer=_manufacturer(),
        declared_family_ids=frozenset(),
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
async def test_handler_returns_pidinst_record_for_populated_asset() -> None:
    store = InMemoryEventStore()
    asset_id = uuid4()
    model_id = uuid4()
    await _seed_model_defined(store, model_id=model_id)
    await _seed_asset_registered(
        store,
        asset_id=asset_id,
        model_id=model_id,
        owners=frozenset({_owner()}),
    )
    deps = _build_deps(event_store=store)
    handler = get_asset_pidinst.bind(deps)
    record = await handler(
        GetAssetPidinst(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert isinstance(record, PidinstRecord)
    assert record.name == "Rotary Stage A"
    assert len(record.owners) == 1
    assert record.owners[0].name == "Helmholtz-Zentrum Berlin"


@pytest.mark.unit
@pytest.mark.timeout(60, method="thread")
async def test_handler_propagates_asset_not_found_error_for_unknown_asset() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = get_asset_pidinst.bind(deps)
    missing_id = uuid4()
    with pytest.raises(AssetNotFoundError) as exc_info:
        await handler(
            GetAssetPidinst(asset_id=missing_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.asset_id == missing_id


@pytest.mark.unit
@pytest.mark.timeout(60, method="thread")
async def test_handler_propagates_owner_state_not_available_for_asset_without_owners() -> None:
    store = InMemoryEventStore()
    asset_id = uuid4()
    model_id = uuid4()
    await _seed_model_defined(store, model_id=model_id)
    await _seed_asset_registered(
        store,
        asset_id=asset_id,
        model_id=model_id,
        owners=frozenset(),
    )
    deps = _build_deps(event_store=store)
    handler = get_asset_pidinst.bind(deps)
    with pytest.raises(OwnerStateNotAvailableError) as exc_info:
        await handler(
            GetAssetPidinst(asset_id=asset_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.asset_id == asset_id


@pytest.mark.unit
@pytest.mark.timeout(60, method="thread")
async def test_handler_propagates_manufacturer_unavailable_for_asset_without_model() -> None:
    store = InMemoryEventStore()
    asset_id = uuid4()
    await _seed_asset_registered(
        store,
        asset_id=asset_id,
        model_id=None,
        owners=frozenset({_owner()}),
    )
    deps = _build_deps(event_store=store)
    handler = get_asset_pidinst.bind(deps)
    with pytest.raises(ManufacturerStateNotAvailableError) as exc_info:
        await handler(
            GetAssetPidinst(asset_id=asset_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.asset_id == asset_id


@pytest.mark.unit
@pytest.mark.timeout(60, method="thread")
async def test_handler_logs_and_reraises_on_pidinst_record_invariant_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`PidinstRecordInvariantError` from `to_pidinst_record` is a
    CORA bug class (server-side defect; the four pre-construction
    validators should have caught it earlier). Lock 11 of
    project_asset_persistent_id_design forbids wiring it to a custom
    HTTP handler, so FastAPI's default 500 fires. The query handler
    is the observability site: it emits a structured
    `get_asset_pidinst.pidinst_record_invariant` log entry with
    asset_id, principal_id, correlation_id, and the invariant
    `reason`, then re-raises. The serializer cannot log directly
    per L22 purity.
    """
    import structlog.testing

    from cora.equipment.features.get_asset_pidinst import handler as handler_module

    store = InMemoryEventStore()
    asset_id = uuid4()
    model_id = uuid4()
    await _seed_model_defined(store, model_id=model_id)
    await _seed_asset_registered(
        store,
        asset_id=asset_id,
        model_id=model_id,
        owners=frozenset({_owner()}),
    )

    raised_reason = "owners must contain at least one Owner"

    def fake_to_pidinst_record(_view: object) -> PidinstRecord:
        raise PidinstRecordInvariantError(raised_reason)

    monkeypatch.setattr(handler_module, "to_pidinst_record", fake_to_pidinst_record)

    deps = _build_deps(event_store=store)
    handler = get_asset_pidinst.bind(deps)
    with (
        structlog.testing.capture_logs() as captured,
        pytest.raises(PidinstRecordInvariantError) as exc_info,
    ):
        await handler(
            GetAssetPidinst(asset_id=asset_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == raised_reason

    invariant_logs = [
        e for e in captured if e.get("event") == "get_asset_pidinst.pidinst_record_invariant"
    ]
    assert len(invariant_logs) == 1
    entry = invariant_logs[0]
    assert entry["asset_id"] == str(asset_id)
    assert entry["principal_id"] == str(_PRINCIPAL_ID)
    assert entry["correlation_id"] == str(_CORRELATION_ID)
    assert entry["reason"] == raised_reason
    assert entry["log_level"] == "error"
