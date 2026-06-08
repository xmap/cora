"""Application-handler tests for `start_procedure` slice.

Custom handler with cross-aggregate context: pre-loads the Procedure
stream then each target Asset (via Equipment's `load_asset`) before
reaching the decider. Tests seed events directly into the in-memory
store via helpers, mirroring `test_start_run_handler.py`.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.asset import AssetLevel, AssetNotFoundError
from cora.equipment.aggregates.asset.events import (
    AssetDecommissioned,
    AssetRegistered,
)
from cora.equipment.aggregates.asset.events import (
    event_type_name as asset_event_type_name,
)
from cora.equipment.aggregates.asset.events import to_payload as asset_to_payload
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.operation.aggregates.procedure import (
    ProcedureCannotStartError,
    ProcedureNotFoundError,
    ProcedurePlanAssetDecommissionedError,
    ProcedureRegistered,
)
from cora.operation.aggregates.procedure import event_type_name as procedure_event_type_name
from cora.operation.aggregates.procedure import to_payload as procedure_to_payload
from cora.operation.errors import UnauthorizedError
from cora.operation.features import start_procedure
from cora.operation.features.start_procedure import StartProcedure
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_PRIOR = datetime(2026, 5, 15, 11, 0, 0, tzinfo=UTC)
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-0000000c0b01")
_TRANSITION_EVENT_ID = UUID("01900000-0000-7000-8000-0000000c0b02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _append(
    store: InMemoryEventStore,
    *,
    stream_type: str,
    stream_id: UUID,
    expected_version: int,
    event_type: str,
    payload: dict[str, object],
    command_name: str,
) -> None:
    new_event = to_new_event(
        event_type=event_type,
        payload=payload,
        occurred_at=_PRIOR,
        event_id=uuid4(),
        command_name=command_name,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
    )
    await store.append(
        stream_type=stream_type,
        stream_id=stream_id,
        expected_version=expected_version,
        events=[new_event],
    )


async def _seed_procedure(
    store: InMemoryEventStore,
    *,
    procedure_id: UUID = _PROCEDURE_ID,
    target_asset_ids: tuple[UUID, ...] | None = None,
) -> None:
    """Seed a registered (Defined) Procedure into the store."""
    event = ProcedureRegistered(
        procedure_id=procedure_id,
        name="Vessel-A bakeout",
        kind="bakeout",
        target_asset_ids=target_asset_ids or (),
        parent_run_id=None,
        occurred_at=_PRIOR,
    )
    await _append(
        store,
        stream_type="Procedure",
        stream_id=procedure_id,
        expected_version=0,
        event_type=procedure_event_type_name(event),
        payload=procedure_to_payload(event),
        command_name="RegisterProcedure",
    )


async def _seed_asset(
    store: InMemoryEventStore, asset_id: UUID, *, decommissioned: bool = False
) -> None:
    """Seed an Active (or Decommissioned) Asset into the store."""
    register_event = AssetRegistered(
        asset_id=asset_id,
        name="TestAsset",
        level=AssetLevel.DEVICE,
        parent_id=uuid4(),
        occurred_at=_PRIOR,
        commissioned_by=ActorId(uuid4()),
    )
    await _append(
        store,
        stream_type="Asset",
        stream_id=asset_id,
        expected_version=0,
        event_type=asset_event_type_name(register_event),
        payload=asset_to_payload(register_event),
        command_name="RegisterAsset",
    )
    if decommissioned:
        dc_event = AssetDecommissioned(
            asset_id=asset_id, occurred_at=_PRIOR, decommissioned_by=ActorId(uuid4())
        )
        await _append(
            store,
            stream_type="Asset",
            stream_id=asset_id,
            expected_version=1,
            event_type=asset_event_type_name(dc_event),
            payload=asset_to_payload(dc_event),
            command_name="DecommissionAsset",
        )


@pytest.mark.unit
async def test_handler_appends_procedure_started_event_for_facility_envelope() -> None:
    """Procedure with no target assets (beam-mode change) starts cleanly."""
    store = InMemoryEventStore()
    await _seed_procedure(store)
    deps = _build_deps_shared(ids=[_TRANSITION_EVENT_ID], now=_NOW, event_store=store)
    handler = start_procedure.bind(deps)

    await handler(
        StartProcedure(procedure_id=_PROCEDURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Procedure", _PROCEDURE_ID)
    assert version == 2
    assert events[1].event_type == "ProcedureStarted"
    assert events[1].payload == {
        "procedure_id": str(_PROCEDURE_ID),
        "occurred_at": _NOW.isoformat(),
    }
    assert events[1].principal_id == _PRINCIPAL_ID
    assert events[1].correlation_id == _CORRELATION_ID


@pytest.mark.unit
async def test_handler_loads_target_assets_and_starts_with_active_assets() -> None:
    asset_id = UUID("01900000-0000-7000-8000-0000000c0b11")
    store = InMemoryEventStore()
    await _seed_asset(store, asset_id)
    await _seed_procedure(store, target_asset_ids=(asset_id,))
    deps = _build_deps_shared(ids=[_TRANSITION_EVENT_ID], now=_NOW, event_store=store)
    handler = start_procedure.bind(deps)

    await handler(
        StartProcedure(procedure_id=_PROCEDURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    _, version = await store.load("Procedure", _PROCEDURE_ID)
    assert version == 2


@pytest.mark.unit
async def test_handler_raises_when_procedure_not_found() -> None:
    store = InMemoryEventStore()  # empty
    deps = _build_deps_shared(ids=[_TRANSITION_EVENT_ID], now=_NOW, event_store=store)
    handler = start_procedure.bind(deps)
    with pytest.raises(ProcedureNotFoundError):
        await handler(
            StartProcedure(procedure_id=_PROCEDURE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_when_target_asset_not_found() -> None:
    asset_id = UUID("01900000-0000-7000-8000-0000000c0b21")
    store = InMemoryEventStore()
    # Procedure references asset_id but Asset stream is missing.
    await _seed_procedure(store, target_asset_ids=(asset_id,))
    deps = _build_deps_shared(ids=[_TRANSITION_EVENT_ID], now=_NOW, event_store=store)
    handler = start_procedure.bind(deps)
    with pytest.raises(AssetNotFoundError):
        await handler(
            StartProcedure(procedure_id=_PROCEDURE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_when_target_asset_decommissioned() -> None:
    asset_id = UUID("01900000-0000-7000-8000-0000000c0b31")
    store = InMemoryEventStore()
    await _seed_asset(store, asset_id, decommissioned=True)
    await _seed_procedure(store, target_asset_ids=(asset_id,))
    deps = _build_deps_shared(ids=[_TRANSITION_EVENT_ID], now=_NOW, event_store=store)
    handler = start_procedure.bind(deps)
    with pytest.raises(ProcedurePlanAssetDecommissionedError) as exc:
        await handler(
            StartProcedure(procedure_id=_PROCEDURE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc.value.asset_ids == [asset_id]


@pytest.mark.unit
async def test_handler_raises_cannot_start_when_already_running() -> None:
    """Strict-not-idempotent: re-starting a Running procedure raises."""
    store = InMemoryEventStore()
    await _seed_procedure(store)
    # First start lands cleanly.
    deps1 = _build_deps_shared(
        ids=[UUID("01900000-0000-7000-8000-0000000c0b41")], now=_NOW, event_store=store
    )
    await start_procedure.bind(deps1)(
        StartProcedure(procedure_id=_PROCEDURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Second start must raise.
    deps2 = _build_deps_shared(
        ids=[UUID("01900000-0000-7000-8000-0000000c0b42")], now=_NOW, event_store=store
    )
    with pytest.raises(ProcedureCannotStartError):
        await start_procedure.bind(deps2)(
            StartProcedure(procedure_id=_PROCEDURE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_procedure(store)
    deps = _build_deps_shared(ids=[_TRANSITION_EVENT_ID], now=_NOW, event_store=store, deny=True)
    handler = start_procedure.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            StartProcedure(procedure_id=_PROCEDURE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_does_not_append_when_denied() -> None:
    store = InMemoryEventStore()
    await _seed_procedure(store)
    deps = _build_deps_shared(ids=[_TRANSITION_EVENT_ID], now=_NOW, event_store=store, deny=True)
    handler = start_procedure.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            StartProcedure(procedure_id=_PROCEDURE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version = await store.load("Procedure", _PROCEDURE_ID)
    assert version == 1  # only the genesis from _seed_procedure


@pytest.mark.unit
async def test_handler_propagates_causation_id() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    await _seed_procedure(store)
    deps = _build_deps_shared(ids=[_TRANSITION_EVENT_ID], now=_NOW, event_store=store)
    handler = start_procedure.bind(deps)
    await handler(
        StartProcedure(procedure_id=_PROCEDURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )
    events, _ = await store.load("Procedure", _PROCEDURE_ID)
    assert events[1].causation_id == causation
