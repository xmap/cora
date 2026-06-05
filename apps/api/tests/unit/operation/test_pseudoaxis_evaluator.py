"""Unit tests for `resolve_pseudoaxis_command`.

Pure-function tests for the PseudoAxis runtime evaluator. The evaluator
loads the target Asset, verifies it carries a PseudoAxis Family id,
verifies a partition rule is set, dispatches on the rule's kind, and
returns a `ResolvedSetpoints` record while emitting one structlog
`pseudoaxis.resolved` event.

Mirrors the InMemoryEventStore + define_family + register_asset +
add_asset_family + update_asset_partition_rule fixture pattern from
`tests/unit/equipment/test_update_asset_partition_rule_handler.py`.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest
import structlog.testing

from cora.equipment.aggregates._partition_rule import (
    Affine,
    InvalidPartitionRuleError,
    LookupTable,
    PartitionRuleKind,
)
from cora.equipment.aggregates.asset import AssetLevel
from cora.equipment.aggregates.asset.state import AssetNotFoundError
from cora.equipment.features import (
    add_asset_family,
    define_family,
    register_asset,
    update_asset_partition_rule,
)
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.update_asset_partition_rule import (
    UpdateAssetPartitionRule,
)
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from cora.operation._pseudoaxis_evaluator import (
    ResolvedSetpoints,
    resolve_pseudoaxis_command,
)
from cora.operation.errors import (
    AssetNotPseudoAxisError,
    PartitionRuleNotFoundError,
)
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)

_FAMILY_ID = UUID("01900000-0000-7000-8000-00000000c001")
_FAMILY_DEFINED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000c002")
_ASSET_ID = UUID("01900000-0000-7000-8000-00000000c003")
_ASSET_REGISTERED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000c004")
_FAMILY_ADDED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000c005")
_PARTITION_EVENT_ID = UUID("01900000-0000-7000-8000-00000000c006")
_NON_PA_FAMILY_ID = UUID("01900000-0000-7000-8000-00000000c011")
_NON_PA_FAMILY_DEFINED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000c012")
_NON_PA_ASSET_ID = UUID("01900000-0000-7000-8000-00000000c013")
_NON_PA_ASSET_REGISTERED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000c014")
_NON_PA_FAMILY_ADDED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000c015")
_MISSING_ASSET_ID = UUID("01900000-0000-7000-8000-00000000c0ff")
_PARENT_ID = UUID("01900000-0000-7000-8000-00000000c000")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_LOOKUP_CALIBRATION_REVISION_ID = UUID("01900000-0000-7000-8000-00000000d001")
_CONSTITUENT_ID_A = UUID("01900000-0000-7000-8000-00000000e001")
_CONSTITUENT_ID_B = UUID("01900000-0000-7000-8000-00000000e002")

_AFFINE_RULE = Affine(gain=2.0, offset=1.0, unit_in="deg", unit_out="mm")
_LOOKUP_RULE = LookupTable(calibration_revision_id=_LOOKUP_CALIBRATION_REVISION_ID)


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
) -> Kernel:
    """Build a Kernel with a queued id list large enough for the
    PseudoAxis + non-PseudoAxis setup paths used across this file."""
    return _build_deps_shared(
        ids=[
            _FAMILY_ID,
            _FAMILY_DEFINED_EVENT_ID,
            _ASSET_ID,
            _ASSET_REGISTERED_EVENT_ID,
            _FAMILY_ADDED_EVENT_ID,
            _PARTITION_EVENT_ID,
            _NON_PA_FAMILY_ID,
            _NON_PA_FAMILY_DEFINED_EVENT_ID,
            _NON_PA_ASSET_ID,
            _NON_PA_ASSET_REGISTERED_EVENT_ID,
            _NON_PA_FAMILY_ADDED_EVENT_ID,
        ],
        now=_NOW,
        event_store=event_store,
    )


async def _define_family_named(deps: Kernel, *, name: str) -> UUID:
    return await define_family.bind(deps)(
        DefineFamily(name=name, affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _setup_pseudoaxis_asset(
    deps: Kernel,
    *,
    rule: object | None = _AFFINE_RULE,
) -> tuple[UUID, UUID]:
    """Seed a PseudoAxis Family + Asset + optional partition rule.

    Returns `(asset_id, family_id)`. Pass `rule=None` to skip the
    partition-rule assignment (used by the no-rule scenario).
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
    if rule is not None:
        await update_asset_partition_rule.bind(deps)(
            UpdateAssetPartitionRule(asset_id=asset_id, partition_rule=rule),  # type: ignore[arg-type]
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    return asset_id, family_id


async def _setup_non_pseudoaxis_asset(deps: Kernel) -> UUID:
    """Seed an Asset whose Family is NOT named PseudoAxis."""
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
async def test_resolve_pseudoaxis_command_raises_asset_not_found_on_missing_asset() -> None:
    store = InMemoryEventStore()
    _ = _build_deps(event_store=store)

    with pytest.raises(AssetNotFoundError):
        await resolve_pseudoaxis_command(
            event_store=store,
            asset_id=_MISSING_ASSET_ID,
            commanded_value=1.0,
            constituent_asset_ids=(_CONSTITUENT_ID_A,),
            correlation_id=_CORRELATION_ID,
            pseudoaxis_family_ids=frozenset({_FAMILY_ID}),
        )


@pytest.mark.unit
async def test_resolve_pseudoaxis_command_raises_not_pseudoaxis_on_unrelated_family() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    _pa_asset_id, _pa_family_id = await _setup_pseudoaxis_asset(deps, rule=None)
    non_pa_asset_id = await _setup_non_pseudoaxis_asset(deps)

    with pytest.raises(AssetNotPseudoAxisError) as exc_info:
        await resolve_pseudoaxis_command(
            event_store=store,
            asset_id=non_pa_asset_id,
            commanded_value=1.0,
            constituent_asset_ids=(_CONSTITUENT_ID_A,),
            correlation_id=_CORRELATION_ID,
            pseudoaxis_family_ids=frozenset({_FAMILY_ID}),
        )
    assert exc_info.value.asset_id == non_pa_asset_id


@pytest.mark.unit
async def test_resolve_pseudoaxis_command_raises_partition_rule_not_found_when_unset() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id, family_id = await _setup_pseudoaxis_asset(deps, rule=None)

    with pytest.raises(PartitionRuleNotFoundError) as exc_info:
        await resolve_pseudoaxis_command(
            event_store=store,
            asset_id=asset_id,
            commanded_value=1.0,
            constituent_asset_ids=(_CONSTITUENT_ID_A,),
            correlation_id=_CORRELATION_ID,
            pseudoaxis_family_ids=frozenset({family_id}),
        )
    assert exc_info.value.asset_id == asset_id


@pytest.mark.unit
async def test_resolve_pseudoaxis_command_returns_resolved_setpoints_for_affine_rule() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id, family_id = await _setup_pseudoaxis_asset(deps, rule=_AFFINE_RULE)

    resolved = await resolve_pseudoaxis_command(
        event_store=store,
        asset_id=asset_id,
        commanded_value=3.0,
        constituent_asset_ids=(_CONSTITUENT_ID_A,),
        correlation_id=_CORRELATION_ID,
        pseudoaxis_family_ids=frozenset({family_id}),
    )

    assert isinstance(resolved, ResolvedSetpoints)
    assert resolved.constituent_asset_ids == (_CONSTITUENT_ID_A,)
    assert resolved.constituent_values == (7.0,)
    assert resolved.evaluator_kind is PartitionRuleKind.AFFINE
    assert resolved.residual == 0.0
    assert resolved.correlation_id == _CORRELATION_ID
    assert resolved.evaluator_latency_ms >= 0.0


@pytest.mark.unit
async def test_resolve_raises_invalid_rule_when_calibration_revision_none() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id, family_id = await _setup_pseudoaxis_asset(deps, rule=_LOOKUP_RULE)

    with pytest.raises(InvalidPartitionRuleError) as exc_info:
        await resolve_pseudoaxis_command(
            event_store=store,
            asset_id=asset_id,
            commanded_value=1.0,
            constituent_asset_ids=(_CONSTITUENT_ID_A,),
            correlation_id=_CORRELATION_ID,
            pseudoaxis_family_ids=frozenset({family_id}),
            calibration_revision=None,
        )
    assert exc_info.value.sub_code == "calibration_revision_retracted"


@pytest.mark.unit
async def test_resolve_pseudoaxis_command_emits_resolved_log_exactly_once() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id, family_id = await _setup_pseudoaxis_asset(deps, rule=_AFFINE_RULE)

    with structlog.testing.capture_logs() as logs:
        await resolve_pseudoaxis_command(
            event_store=store,
            asset_id=asset_id,
            commanded_value=3.0,
            constituent_asset_ids=(_CONSTITUENT_ID_A,),
            correlation_id=_CORRELATION_ID,
            pseudoaxis_family_ids=frozenset({family_id}),
        )

    resolved_events = [e for e in logs if e.get("event") == "pseudoaxis.resolved"]
    assert len(resolved_events) == 1
    entry = resolved_events[0]
    assert entry["asset_id"] == str(asset_id)
    assert entry["commanded_value"] == 3.0
    assert entry["partition_rule_kind"] == PartitionRuleKind.AFFINE.value
    assert entry["resolved_setpoints"] == [7.0]
    assert entry["status"] == "ok"
    assert entry["correlation_id"] == str(_CORRELATION_ID)
    assert entry["residual"] == 0.0
