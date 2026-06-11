"""Unit tests for the add_plan_wire / remove_plan_wire handlers.

Consolidated file (mirror of 5h's `test_port_slices_handlers.py`):
both wire slices share the load+fold+decide+append shape, so per-slice
files would duplicate setup.

Coverage per slice:
  - happy path appends the right event
  - authorize-deny -> UnauthorizedError; no event appended
  - causation_id propagates onto the appended event
  - wire_recipe exposes the handler on the bundle

Plus add_plan_wire-specific:
  - dedup of asset_ids_to_load when source == target asset_id (the
    handler's `set` literal at handler.py:127 dedupes one load away)
  - silent-drop when load_asset returns None for an unknown asset
    stream (PlanWireAssetNotBoundError surfaces from the decider via
    state.asset_ids check, NOT from the load itself; the handler's
    silent-drop is a defensive shape, not a behavioral path)
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.asset.events import (
    AssetPortAdded,
    AssetRegistered,
)
from cora.equipment.aggregates.asset.events import event_type_name as asset_event_type_name
from cora.equipment.aggregates.asset.events import to_payload as asset_to_payload
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.recipe import RecipeHandlers, UnauthorizedError, wire_recipe
from cora.recipe.aggregates.plan import PlanWireAssetNotBoundError
from cora.recipe.aggregates.plan.events import (
    PlanDefined,
    event_type_name,
    to_payload,
)
from cora.recipe.features import add_plan_wire, remove_plan_wire
from cora.recipe.features.add_plan_wire import AddPlanWire
from cora.recipe.features.remove_plan_wire import RemovePlanWire
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_PLAN_ID = UUID("01900000-0000-7000-8000-0000000d6e01")
_SRC_ASSET_ID = UUID("01900000-0000-7000-8000-0000000d6e02")
_TGT_ASSET_ID = UUID("01900000-0000-7000-8000-0000000d6e03")
_PRACTICE_ID = UUID("01900000-0000-7000-8000-0000000d6e04")
_METHOD_ID = UUID("01900000-0000-7000-8000-0000000d6e05")
_WIRE_EVENT_ID_1 = UUID("01900000-0000-7000-8000-0000000d6e06")
_WIRE_EVENT_ID_2 = UUID("01900000-0000-7000-8000-0000000d6e07")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000000d6e08")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000d6e09")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_WIRE_EVENT_ID_1, _WIRE_EVENT_ID_2],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


async def _seed_asset_with_port(
    store: InMemoryEventStore,
    asset_id: UUID,
    *,
    name: str,
    port_name: str,
    direction: str,
    signal_type: str,
) -> None:
    """Seed an Asset with one port directly into the event store."""
    register = AssetRegistered(
        asset_id=asset_id,
        name=name,
        tier="Device",
        parent_id=None,
        occurred_at=_NOW,
        commissioned_by=ActorId(uuid4()),
    )
    add_port = AssetPortAdded(
        asset_id=asset_id,
        port_name=port_name,
        direction=direction,
        signal_type=signal_type,
        occurred_at=_NOW,
    )
    events = [
        to_new_event(
            event_type=asset_event_type_name(ev),
            payload=asset_to_payload(ev),
            occurred_at=_NOW,
            event_id=uuid4(),
            command_name="Seed",
            correlation_id=_CORRELATION_ID,
            principal_id=uuid4(),
        )
        for ev in (register, add_port)
    ]
    await store.append(stream_type="Asset", stream_id=asset_id, expected_version=0, events=events)


async def _seed_plan(
    store: InMemoryEventStore,
    *,
    asset_ids: tuple[UUID, ...],
) -> None:
    """Seed a Plan binding the given Asset ids."""
    event = PlanDefined(
        plan_id=_PLAN_ID,
        name="32-ID Triggered Acquisition",
        practice_id=_PRACTICE_ID,
        asset_ids=asset_ids,
        method_id=_METHOD_ID,
        method_needed_family_ids_snapshot=(),
        asset_families_snapshot={a: () for a in asset_ids},
        occurred_at=_NOW,
    )
    await store.append(
        stream_type="Plan",
        stream_id=_PLAN_ID,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="DefinePlan",
                correlation_id=_CORRELATION_ID,
                principal_id=uuid4(),
            )
        ],
    )


async def _setup_two_asset_plan(store: InMemoryEventStore) -> None:
    """Standard 2-Asset Plan setup: source has trigger_out (OUTPUT TTL),
    target has trigger_in (INPUT TTL), Plan binds both."""
    await _seed_asset_with_port(
        store,
        _SRC_ASSET_ID,
        name="PandABox",
        port_name="trigger_out",
        direction="Output",
        signal_type="TTL",
    )
    await _seed_asset_with_port(
        store,
        _TGT_ASSET_ID,
        name="Camera",
        port_name="trigger_in",
        direction="Input",
        signal_type="TTL",
    )
    await _seed_plan(store, asset_ids=(_SRC_ASSET_ID, _TGT_ASSET_ID))


# ---------- add_plan_wire handler ----------


@pytest.mark.unit
async def test_add_plan_wire_handler_appends_event() -> None:
    store = InMemoryEventStore()
    await _setup_two_asset_plan(store)
    deps = _build_deps(event_store=store)

    await add_plan_wire.bind(deps)(
        AddPlanWire(
            plan_id=_PLAN_ID,
            source_asset_id=_SRC_ASSET_ID,
            source_port_name="trigger_out",
            target_asset_id=_TGT_ASSET_ID,
            target_port_name="trigger_in",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Plan", _PLAN_ID)
    assert version == 2
    appended = events[1]
    assert appended.event_type == "PlanWireAdded"
    assert appended.event_id == _WIRE_EVENT_ID_1
    assert appended.metadata == {"command": "AddPlanWire"}
    assert appended.payload["source_asset_id"] == str(_SRC_ASSET_ID)
    assert appended.payload["source_port_name"] == "trigger_out"
    assert appended.payload["target_asset_id"] == str(_TGT_ASSET_ID)
    assert appended.payload["target_port_name"] == "trigger_in"


@pytest.mark.unit
async def test_add_plan_wire_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _setup_two_asset_plan(store)
    deny_deps = _build_deps(event_store=store, deny=True)

    with pytest.raises(UnauthorizedError):
        await add_plan_wire.bind(deny_deps)(
            AddPlanWire(
                plan_id=_PLAN_ID,
                source_asset_id=_SRC_ASSET_ID,
                source_port_name="trigger_out",
                target_asset_id=_TGT_ASSET_ID,
                target_port_name="trigger_in",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # Plan stream untouched: only the seeded PlanDefined event.
    _, version = await store.load("Plan", _PLAN_ID)
    assert version == 1


@pytest.mark.unit
async def test_add_plan_wire_handler_propagates_causation_id() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000d6ebb")
    store = InMemoryEventStore()
    await _setup_two_asset_plan(store)
    deps = _build_deps(event_store=store)

    await add_plan_wire.bind(deps)(
        AddPlanWire(
            plan_id=_PLAN_ID,
            source_asset_id=_SRC_ASSET_ID,
            source_port_name="trigger_out",
            target_asset_id=_TGT_ASSET_ID,
            target_port_name="trigger_in",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Plan", _PLAN_ID)
    assert events[1].causation_id == causation


@pytest.mark.unit
async def test_add_plan_wire_handler_dedupes_loads_when_source_equals_target() -> None:
    """Self-loop on different ports of the SAME Asset: the handler's
    `set` literal at add_plan_wire/handler.py:127 dedupes the load
    set so we issue ONE Asset load, not two. Verify the handler still
    succeeds when source_asset_id == target_asset_id."""
    store = InMemoryEventStore()
    # One Asset with TWO ports for the self-loop pattern.
    register = AssetRegistered(
        asset_id=_SRC_ASSET_ID,
        name="LUT",
        tier="Device",
        parent_id=None,
        occurred_at=_NOW,
        commissioned_by=ActorId(uuid4()),
    )
    out_port = AssetPortAdded(
        asset_id=_SRC_ASSET_ID,
        port_name="lut_out",
        direction="Output",
        signal_type="TTL",
        occurred_at=_NOW,
    )
    in_port = AssetPortAdded(
        asset_id=_SRC_ASSET_ID,
        port_name="lut_feedback_in",
        direction="Input",
        signal_type="TTL",
        occurred_at=_NOW,
    )
    events = [
        to_new_event(
            event_type=asset_event_type_name(ev),
            payload=asset_to_payload(ev),
            occurred_at=_NOW,
            event_id=uuid4(),
            command_name="Seed",
            correlation_id=_CORRELATION_ID,
            principal_id=uuid4(),
        )
        for ev in (register, out_port, in_port)
    ]
    await store.append(
        stream_type="Asset", stream_id=_SRC_ASSET_ID, expected_version=0, events=events
    )
    await _seed_plan(store, asset_ids=(_SRC_ASSET_ID,))
    deps = _build_deps(event_store=store)

    await add_plan_wire.bind(deps)(
        AddPlanWire(
            plan_id=_PLAN_ID,
            source_asset_id=_SRC_ASSET_ID,
            source_port_name="lut_out",
            target_asset_id=_SRC_ASSET_ID,
            target_port_name="lut_feedback_in",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events_out, _ = await store.load("Plan", _PLAN_ID)
    assert events_out[1].event_type == "PlanWireAdded"
    assert events_out[1].payload["source_asset_id"] == str(_SRC_ASSET_ID)
    assert events_out[1].payload["target_asset_id"] == str(_SRC_ASSET_ID)


@pytest.mark.unit
async def test_add_plan_wire_handler_surfaces_asset_not_bound_for_unbound_target() -> None:
    """Operator references an Asset that's NOT in Plan.asset_ids → handler
    loads what the COMMAND references (not what the Plan binds), the load
    succeeds (the Asset stream exists), but the decider rejects with
    PlanWireAssetNotBoundError because the asset isn't bound by this Plan.

    Pinned because the handler's load-from-command shape (handler.py:127-135)
    bypasses Plan.asset_ids — the bound-set check happens in the decider,
    not the handler."""
    store = InMemoryEventStore()
    # Plan binds ONLY the source. An "extra" Asset exists with a port,
    # but isn't bound by this Plan.
    extra_asset_id = uuid4()
    await _seed_asset_with_port(
        store,
        _SRC_ASSET_ID,
        name="PandABox",
        port_name="trigger_out",
        direction="Output",
        signal_type="TTL",
    )
    await _seed_asset_with_port(
        store,
        extra_asset_id,
        name="UnboundCamera",
        port_name="trigger_in",
        direction="Input",
        signal_type="TTL",
    )
    # Plan binds source only — extra_asset_id is NOT in asset_ids.
    await _seed_plan(store, asset_ids=(_SRC_ASSET_ID,))
    deps = _build_deps(event_store=store)

    with pytest.raises(PlanWireAssetNotBoundError) as exc_info:
        await add_plan_wire.bind(deps)(
            AddPlanWire(
                plan_id=_PLAN_ID,
                source_asset_id=_SRC_ASSET_ID,
                source_port_name="trigger_out",
                target_asset_id=extra_asset_id,
                target_port_name="trigger_in",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert extra_asset_id in exc_info.value.missing_asset_ids


# ---------- remove_plan_wire handler ----------


async def _add_one_wire(store: InMemoryEventStore, deps: Kernel) -> None:
    """Helper: add a wire to seed the remove tests."""
    await add_plan_wire.bind(deps)(
        AddPlanWire(
            plan_id=_PLAN_ID,
            source_asset_id=_SRC_ASSET_ID,
            source_port_name="trigger_out",
            target_asset_id=_TGT_ASSET_ID,
            target_port_name="trigger_in",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.unit
async def test_remove_plan_wire_handler_appends_event() -> None:
    store = InMemoryEventStore()
    await _setup_two_asset_plan(store)
    deps = _build_deps(event_store=store)
    await _add_one_wire(store, deps)

    await remove_plan_wire.bind(deps)(
        RemovePlanWire(
            plan_id=_PLAN_ID,
            source_asset_id=_SRC_ASSET_ID,
            source_port_name="trigger_out",
            target_asset_id=_TGT_ASSET_ID,
            target_port_name="trigger_in",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Plan", _PLAN_ID)
    assert version == 3  # define + add + remove
    removed = events[2]
    assert removed.event_type == "PlanWireRemoved"
    assert removed.event_id == _WIRE_EVENT_ID_2
    assert removed.metadata == {"command": "RemovePlanWire"}
    assert removed.payload["source_asset_id"] == str(_SRC_ASSET_ID)
    assert removed.payload["target_port_name"] == "trigger_in"


@pytest.mark.unit
async def test_remove_plan_wire_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _setup_two_asset_plan(store)
    deps = _build_deps(event_store=store)
    await _add_one_wire(store, deps)

    deny_deps = _build_deps(event_store=store, deny=True)
    with pytest.raises(UnauthorizedError):
        await remove_plan_wire.bind(deny_deps)(
            RemovePlanWire(
                plan_id=_PLAN_ID,
                source_asset_id=_SRC_ASSET_ID,
                source_port_name="trigger_out",
                target_asset_id=_TGT_ASSET_ID,
                target_port_name="trigger_in",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # Plan stream still has the prior add but no remove event.
    _, version = await store.load("Plan", _PLAN_ID)
    assert version == 2


@pytest.mark.unit
async def test_remove_plan_wire_handler_propagates_causation_id() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000d6ebc")
    store = InMemoryEventStore()
    await _setup_two_asset_plan(store)
    deps = _build_deps(event_store=store)
    await _add_one_wire(store, deps)

    await remove_plan_wire.bind(deps)(
        RemovePlanWire(
            plan_id=_PLAN_ID,
            source_asset_id=_SRC_ASSET_ID,
            source_port_name="trigger_out",
            target_asset_id=_TGT_ASSET_ID,
            target_port_name="trigger_in",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Plan", _PLAN_ID)
    assert events[2].causation_id == causation


@pytest.mark.unit
async def test_remove_plan_wire_handler_succeeds_after_referenced_port_removed() -> None:
    """Hot-swap path: remove the wire AFTER the referenced port has been
    removed from the Asset. The remove decider doesn't cross-validate
    Asset.ports (per remove_plan_wire/decider.py:14 docstring), so the
    wire can still be removed cleanly."""
    store = InMemoryEventStore()
    await _setup_two_asset_plan(store)
    deps = _build_deps(event_store=store)
    await _add_one_wire(store, deps)

    # Remove the target port from the Asset. We bypass the slice (the
    # 5h remove_asset_port slice would also work but adds dependency
    # surface to this test); append the AssetPortRemoved event directly.
    from cora.equipment.aggregates.asset.events import AssetPortRemoved

    removed_port = AssetPortRemoved(
        asset_id=_TGT_ASSET_ID,
        port_name="trigger_in",
        occurred_at=_NOW,
    )
    await store.append(
        stream_type="Asset",
        stream_id=_TGT_ASSET_ID,
        expected_version=2,  # register + add_port
        events=[
            to_new_event(
                event_type=asset_event_type_name(removed_port),
                payload=asset_to_payload(removed_port),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="RemoveAssetPort",
                correlation_id=_CORRELATION_ID,
                principal_id=uuid4(),
            )
        ],
    )

    # Remove the wire: should still succeed because remove_plan_wire
    # decider does not consult Asset state.
    await remove_plan_wire.bind(deps)(
        RemovePlanWire(
            plan_id=_PLAN_ID,
            source_asset_id=_SRC_ASSET_ID,
            source_port_name="trigger_out",
            target_asset_id=_TGT_ASSET_ID,
            target_port_name="trigger_in",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    plan_events, _ = await store.load("Plan", _PLAN_ID)
    assert plan_events[-1].event_type == "PlanWireRemoved"


# ---------- wire_recipe wiring ----------


@pytest.mark.unit
@pytest.mark.parametrize("handler_field", ["add_plan_wire", "remove_plan_wire"])
def test_wire_recipe_exposes_wire_handlers(handler_field: str) -> None:
    deps = _build_deps_shared(ids=[_WIRE_EVENT_ID_1, _WIRE_EVENT_ID_2], now=_NOW)
    handlers = wire_recipe(deps)
    assert isinstance(handlers, RecipeHandlers)
    assert callable(getattr(handlers, handler_field))
