"""Unit tests for the `update_asset_partition_rule` application handler.

Update-style handler that loads the Asset stream, loads every assigned
Family stream, verifies at least one Family is `PseudoAxis` by name,
and delegates to the pure decider. Tests cover happy path with an
Affine rule on a PseudoAxis Asset, the Family-membership guard,
the Decommissioned lifecycle guard, AssetNotFoundError, auth deny,
clear-rule (None payload), and idempotent re-submission with the
same rule. Mirrors the `update_asset_settings_handler` test shape.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.equipment import EquipmentHandlers, UnauthorizedError, wire_equipment
from cora.equipment.aggregates._partition_rule import Affine, PartitionRule
from cora.equipment.aggregates.asset import (
    AssetCannotUpdatePartitionRuleError,
    AssetLevel,
    AssetNotFoundError,
)
from cora.equipment.features import (
    add_asset_family,
    decommission_asset,
    define_family,
    register_asset,
    update_asset_partition_rule,
)
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.decommission_asset import DecommissionAsset
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.update_asset_partition_rule import (
    UpdateAssetPartitionRule,
)
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_FAMILY_ID = UUID("01900000-0000-7000-8000-00000000b501")
_FAMILY_DEFINED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000b502")
_ASSET_ID = UUID("01900000-0000-7000-8000-00000000b503")
_ASSET_REGISTERED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000b504")
_FAMILY_ADDED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000b505")
_PARTITION_EVENT_ID = UUID("01900000-0000-7000-8000-00000000b506")
_PARTITION_EVENT_ID_2 = UUID("01900000-0000-7000-8000-00000000b507")
_DECOMMISSION_EVENT_ID = UUID("01900000-0000-7000-8000-00000000b508")
_MISSING_ASSET_ID = UUID("01900000-0000-7000-8000-00000000b5ff")
_PARENT_ID = UUID("01900000-0000-7000-8000-00000000b000")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")

_DEFAULT_RULE = Affine(gain=2.0, offset=1.0, unit_in="deg", unit_out="mm")
_OTHER_RULE = Affine(gain=3.0, offset=0.5, unit_in="deg", unit_out="mm")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    """Thin wrapper preserving this file's ID list + clock.

    Order matches the canonical setup: define_family, register_asset,
    add_asset_family, then two update_asset_partition_rule event ids
    for tests that emit twice, followed by a decommission_asset event
    id for the lifecycle-guard scenario.
    """
    return _build_deps_shared(
        ids=[
            _FAMILY_ID,
            _FAMILY_DEFINED_EVENT_ID,
            _ASSET_ID,
            _ASSET_REGISTERED_EVENT_ID,
            _FAMILY_ADDED_EVENT_ID,
            _PARTITION_EVENT_ID,
            _PARTITION_EVENT_ID_2,
            _DECOMMISSION_EVENT_ID,
        ],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


async def _define_family_named(deps: Kernel, *, name: str) -> UUID:
    return await define_family.bind(deps)(
        DefineFamily(name=name, affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _setup_pseudoaxis_asset(deps: Kernel) -> tuple[UUID, UUID]:
    """Define a PseudoAxis Family, register an Asset, and bind them.

    Returns `(asset_id, family_id)`.
    """
    family_id = await _define_family_named(deps, name="PseudoAxis")
    asset_id = await register_asset.bind(deps)(
        RegisterAsset(name="VirtualY", level=AssetLevel.DEVICE, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return asset_id, family_id


async def _setup_non_pseudoaxis_asset(deps: Kernel) -> UUID:
    """Define a Family whose name is NOT `PseudoAxis`, register an Asset,
    and bind them. Returns the Asset id.

    Consumes the same id-queue slots as `_setup_pseudoaxis_asset`; the
    test only cares that the Asset carries no PseudoAxis Family.
    """
    family_id = await _define_family_named(deps, name="LinearStage")
    asset_id = await register_asset.bind(deps)(
        RegisterAsset(name="DetectorY", level=AssetLevel.DEVICE, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return asset_id


@pytest.mark.unit
async def test_handler_returns_none_on_success() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id, _ = await _setup_pseudoaxis_asset(deps)

    result = await update_asset_partition_rule.bind(deps)(
        UpdateAssetPartitionRule(asset_id=asset_id, partition_rule=_DEFAULT_RULE),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_partition_rule_updated_event_with_payload() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id, _ = await _setup_pseudoaxis_asset(deps)

    await update_asset_partition_rule.bind(deps)(
        UpdateAssetPartitionRule(asset_id=asset_id, partition_rule=_DEFAULT_RULE),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Asset", asset_id)
    assert version == 3  # AssetRegistered + AssetFamilyAdded + AssetPartitionRuleUpdated
    assert events[-1].event_type == "AssetPartitionRuleUpdated"
    partition_event = events[-1]
    assert partition_event.event_id == _PARTITION_EVENT_ID
    assert partition_event.metadata == {"command": "UpdateAssetPartitionRule"}
    rule_payload = partition_event.payload["partition_rule"]
    assert isinstance(rule_payload, dict)
    assert rule_payload["kind"] == "Affine"
    assert rule_payload["gain"] == 2.0
    assert rule_payload["offset"] == 1.0


@pytest.mark.unit
async def test_handler_raises_cannot_update_when_asset_is_not_pseudoaxis() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _setup_non_pseudoaxis_asset(deps)

    with pytest.raises(AssetCannotUpdatePartitionRuleError) as exc_info:
        await update_asset_partition_rule.bind(deps)(
            UpdateAssetPartitionRule(asset_id=asset_id, partition_rule=_DEFAULT_RULE),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "Asset is not of Family PseudoAxis"


@pytest.mark.unit
async def test_handler_raises_cannot_update_when_asset_is_decommissioned() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id, _ = await _setup_pseudoaxis_asset(deps)

    await decommission_asset.bind(deps)(
        DecommissionAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    with pytest.raises(AssetCannotUpdatePartitionRuleError) as exc_info:
        await update_asset_partition_rule.bind(deps)(
            UpdateAssetPartitionRule(asset_id=asset_id, partition_rule=_DEFAULT_RULE),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "Asset is Decommissioned (immutable once retired)"


@pytest.mark.unit
async def test_handler_raises_asset_not_found_on_missing_asset() -> None:
    deps = _build_deps()

    with pytest.raises(AssetNotFoundError):
        await update_asset_partition_rule.bind(deps)(
            UpdateAssetPartitionRule(asset_id=_MISSING_ASSET_ID, partition_rule=_DEFAULT_RULE),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id, _ = await _setup_pseudoaxis_asset(deps)

    deny_deps = _build_deps(event_store=store, deny=True)
    with pytest.raises(UnauthorizedError) as exc_info:
        await update_asset_partition_rule.bind(deny_deps)(
            UpdateAssetPartitionRule(asset_id=asset_id, partition_rule=_DEFAULT_RULE),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_clear_rule_emits_event_with_none_payload() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id, _ = await _setup_pseudoaxis_asset(deps)
    handler = update_asset_partition_rule.bind(deps)

    await handler(
        UpdateAssetPartitionRule(asset_id=asset_id, partition_rule=_DEFAULT_RULE),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    clear_command: UpdateAssetPartitionRule = UpdateAssetPartitionRule(
        asset_id=asset_id, partition_rule=None
    )
    await handler(
        clear_command,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Asset", asset_id)
    assert version == 4
    assert events[-1].event_type == "AssetPartitionRuleUpdated"
    assert events[-1].payload["partition_rule"] is None


@pytest.mark.unit
async def test_handler_idempotent_on_unchanged_rule_does_not_append() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id, _ = await _setup_pseudoaxis_asset(deps)
    handler = update_asset_partition_rule.bind(deps)

    await handler(
        UpdateAssetPartitionRule(asset_id=asset_id, partition_rule=_DEFAULT_RULE),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await handler(
        UpdateAssetPartitionRule(asset_id=asset_id, partition_rule=_DEFAULT_RULE),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Asset", asset_id)
    assert version == 3
    assert sum(1 for e in events if e.event_type == "AssetPartitionRuleUpdated") == 1


@pytest.mark.unit
async def test_handler_emits_second_event_when_rule_changes() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id, _ = await _setup_pseudoaxis_asset(deps)
    handler = update_asset_partition_rule.bind(deps)

    await handler(
        UpdateAssetPartitionRule(asset_id=asset_id, partition_rule=_DEFAULT_RULE),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    second_rule: PartitionRule = _OTHER_RULE
    await handler(
        UpdateAssetPartitionRule(asset_id=asset_id, partition_rule=second_rule),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Asset", asset_id)
    assert version == 4
    assert events[-2].payload["partition_rule"]["gain"] == 2.0
    assert events[-1].payload["partition_rule"]["gain"] == 3.0


@pytest.mark.unit
def test_wire_equipment_includes_update_asset_partition_rule() -> None:
    deps = _build_deps()
    handlers = wire_equipment(deps)
    assert isinstance(handlers, EquipmentHandlers)
    assert callable(handlers.update_asset_partition_rule)
