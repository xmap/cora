"""Unit tests for the degrade_asset / fault_asset / restore_asset
application handlers.

Consolidated file for the three condition slices: their
handlers are identical-shape `make_asset_update_handler` factory
binds with different (command_name, log_prefix, decide_fn) tuples,
so the per-slice tests are byte-parallel. Consolidating into one
file lets the bind-correctness + authorize-deny + causation-id +
no-op-on-unchanged invariants stay parametrized across the three
slices, surfacing any one-slice regression immediately.

Coverage per slice (parametrized):
  - bind() returns a callable
  - happy path appends the right event with reason carried through
  - authorize-deny -> UnauthorizedError; no event appended
  - no-op-on-unchanged: second call to the same target condition
    appends NO additional event
  - causation_id propagates onto the appended event
  - wire_equipment exposes the handler on the bundle
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

import pytest

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

from cora.equipment import EquipmentHandlers, UnauthorizedError, wire_equipment
from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.features import (
    degrade_asset,
    fault_asset,
    register_asset,
    restore_asset,
)
from cora.equipment.features.degrade_asset import DegradeAsset
from cora.equipment.features.fault_asset import FaultAsset
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.restore_asset import RestoreAsset
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 13, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-0000000c0d01")
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-0000000c0d02")
_FIRST_TRANSITION_EVENT_ID = UUID("01900000-0000-7000-8000-0000000c0d03")
_SECOND_TRANSITION_EVENT_ID = UUID("01900000-0000-7000-8000-0000000c0d04")
_PARENT_ID = UUID("01900000-0000-7000-8000-0000000c0d05")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000000c0d06")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000c0d07")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_NEW_ID, _REGISTER_EVENT_ID, _FIRST_TRANSITION_EVENT_ID, _SECOND_TRANSITION_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


async def _register_asset_helper(deps: Kernel) -> UUID:
    return await register_asset.bind(deps)(
        RegisterAsset(name="Detector-X", tier=AssetTier.DEVICE, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


# Each row: (slice_name, slice_module, command_class, expected_event_type, handler_field_name)
_CONDITION_SLICES: list[tuple[str, Any, Any, str, str]] = [
    ("degrade", degrade_asset, DegradeAsset, "AssetDegraded", "degrade_asset"),
    ("fault", fault_asset, FaultAsset, "AssetFaulted", "fault_asset"),
    ("restore", restore_asset, RestoreAsset, "AssetRestored", "restore_asset"),
]


def _make_command(command_class: Any, asset_id: UUID, *, reason: str) -> Any:
    return command_class(asset_id=asset_id, reason=reason)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "slice_mod", "command_class", "event_type", "handler_field"),
    _CONDITION_SLICES,
)
async def test_handler_appends_event_with_reason(
    name: str,
    slice_mod: Any,
    command_class: Any,
    event_type: str,
    handler_field: str,
) -> None:
    """For restore: the asset must NOT already be Nominal or it'd no-op,
    so we degrade it first when testing restore. Otherwise we go
    straight from Nominal -> target."""
    _ = name, handler_field
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    if command_class is RestoreAsset:
        # Move out of Nominal first so restore has work to do.
        await degrade_asset.bind(deps)(
            DegradeAsset(asset_id=asset_id, reason="setup"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        expected_position = 2
    else:
        expected_position = 1

    handler: Callable[..., Awaitable[None]] = slice_mod.bind(deps)
    await handler(
        _make_command(command_class, asset_id, reason="canonical reason"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Asset", asset_id)
    appended = events[expected_position]
    assert appended.event_type == event_type
    assert appended.payload["reason"] == "canonical reason"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "slice_mod", "command_class", "event_type", "handler_field"),
    _CONDITION_SLICES,
)
async def test_handler_raises_unauthorized_on_deny(
    name: str,
    slice_mod: Any,
    command_class: Any,
    event_type: str,
    handler_field: str,
) -> None:
    _ = name, event_type, handler_field
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    deny_deps = _build_deps(event_store=store, deny=True)
    handler: Callable[..., Awaitable[None]] = slice_mod.bind(deny_deps)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            _make_command(command_class, asset_id, reason="should be denied"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"

    # Stream still only has AssetRegistered.
    events, version = await store.load("Asset", asset_id)
    assert version == 1
    assert events[0].event_type == "AssetRegistered"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "slice_mod", "command_class", "event_type", "handler_field"),
    _CONDITION_SLICES,
)
async def test_handler_no_op_on_unchanged_appends_no_second_event(
    name: str,
    slice_mod: Any,
    command_class: Any,
    event_type: str,
    handler_field: str,
) -> None:
    """Second call to the same target condition appends NO additional
    event (decider returns []). Pin against the in-memory store."""
    _ = name, event_type, handler_field
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    if command_class is RestoreAsset:
        # Restore -> Nominal is a no-op when asset is already Nominal
        # (which it is, fresh from registration).
        baseline_version = 1
    else:
        # Degrade / Fault: first call lands an event.
        await slice_mod.bind(deps)(
            _make_command(command_class, asset_id, reason="first"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        baseline_version = 2

    # Second call with DIFFERENT reason — still no-op because target
    # condition is already current.
    await slice_mod.bind(deps)(
        _make_command(command_class, asset_id, reason="second"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    _events, version = await store.load("Asset", asset_id)
    assert version == baseline_version


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "slice_mod", "command_class", "event_type", "handler_field"),
    _CONDITION_SLICES,
)
async def test_handler_propagates_causation_id_to_appended_event(
    name: str,
    slice_mod: Any,
    command_class: Any,
    event_type: str,
    handler_field: str,
) -> None:
    _ = name, event_type, handler_field
    causation = UUID("01900000-0000-7000-8000-0000000c0dbb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_asset_helper(deps)

    if command_class is RestoreAsset:
        # Need to be in non-Nominal for restore to fire an event.
        await degrade_asset.bind(deps)(
            DegradeAsset(asset_id=asset_id, reason="setup"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        appended_index = 2
    else:
        appended_index = 1

    await slice_mod.bind(deps)(
        _make_command(command_class, asset_id, reason="x"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Asset", asset_id)
    assert events[appended_index].causation_id == causation


@pytest.mark.unit
@pytest.mark.parametrize(
    ("handler_field"),
    ["degrade_asset", "fault_asset", "restore_asset"],
)
def test_wire_equipment_includes_condition_slice(handler_field: str) -> None:
    deps = _build_deps()
    handlers = wire_equipment(deps)
    assert isinstance(handlers, EquipmentHandlers)
    assert callable(getattr(handlers, handler_field))
