"""Unit tests for the `decommission_asset` slice's pure decider.

Multi-source-state guard in Equipment (`Commissioned | Active |
Maintenance -> Decommissioned`) plus two cross-aggregate guards that
run BEFORE the lifecycle check:

  - `AssetHasFixtureBindingError`: state.fixture_id is non-None
    (operator must detach_asset_from_fixture first).
  - `AssetIsInstalledError`: context.currently_installed_at_mount_id
    is non-None (operator must uninstall_asset first).

Both guards mirror the `MountHasAssetInstalledError` precedent on
the sibling Mount aggregate.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCannotDecommissionError,
    AssetDecommissioned,
    AssetHasFixtureBindingError,
    AssetIsInstalledError,
    AssetLifecycle,
    AssetName,
    AssetNotFoundError,
    AssetTier,
)
from cora.equipment.features import decommission_asset
from cora.equipment.features.decommission_asset import (
    DecommissionAsset,
    DecommissionAssetContext,
)
from cora.shared.identity import ActorId

_TEST_ACTOR_ID = ActorId(UUID("00000000-0000-0000-0000-000000000001"))

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_EMPTY_CONTEXT = DecommissionAssetContext(currently_installed_at_mount_id=None)


def _asset(
    *,
    lifecycle: AssetLifecycle = AssetLifecycle.COMMISSIONED,
    fixture_id: UUID | None = None,
) -> Asset:
    return Asset(
        id=uuid4(),
        name=AssetName("APS-2BM"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        lifecycle=lifecycle,
        fixture_id=fixture_id,
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "source",
    [
        AssetLifecycle.COMMISSIONED,
        AssetLifecycle.ACTIVE,
        AssetLifecycle.MAINTENANCE,
    ],
)
def test_decide_emits_asset_decommissioned_for_each_allowed_source_lifecycle(
    source: AssetLifecycle,
) -> None:
    """Decommission emits an identical event from any valid source lifecycle.

    Commissioned, Active, and Maintenance are all valid sources;
    the emitted event is identical regardless of which one preceded
    — no `from_lifecycle` on the event payload. (5e widened the
    source set from the original 5c {Commissioned, Active} to add
    Maintenance.)
    """
    state = _asset(lifecycle=source)
    events = decommission_asset.decide(
        state=state,
        command=DecommissionAsset(asset_id=state.id),
        context=_EMPTY_CONTEXT,
        now=_NOW,
        decommissioned_by=_TEST_ACTOR_ID,
    )
    assert events == [
        AssetDecommissioned(asset_id=state.id, occurred_at=_NOW, decommissioned_by=_TEST_ACTOR_ID)
    ]


@pytest.mark.unit
def test_decide_raises_asset_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(AssetNotFoundError) as exc_info:
        decommission_asset.decide(
            state=None,
            command=DecommissionAsset(asset_id=target_id),
            context=_EMPTY_CONTEXT,
            now=_NOW,
            decommissioned_by=_TEST_ACTOR_ID,
        )
    assert exc_info.value.asset_id == target_id


@pytest.mark.unit
@pytest.mark.parametrize(
    "current",
    [
        AssetLifecycle.DECOMMISSIONED,
    ],
)
def test_decide_raises_cannot_decommission_for_every_disallowed_source(
    current: AssetLifecycle,
) -> None:
    """Strict semantics, not idempotent: re-decommissioning an
    already-`Decommissioned` asset raises. After 5e widened the
    source set to {Commissioned, Active, Maintenance}, Decommissioned
    is the only state left from which decommission is disallowed
    (the parametrize stays for shape symmetry with allowed-source
    test above; future state additions outside the allowed set go
    here)."""
    state = _asset(lifecycle=current)
    with pytest.raises(AssetCannotDecommissionError) as exc_info:
        decommission_asset.decide(
            state=state,
            command=DecommissionAsset(asset_id=state.id),
            context=_EMPTY_CONTEXT,
            now=_NOW,
            decommissioned_by=_TEST_ACTOR_ID,
        )
    assert exc_info.value.asset_id == state.id
    assert exc_info.value.current_lifecycle is current


@pytest.mark.unit
def test_decide_error_message_lists_all_three_allowed_source_lifecycles() -> None:
    """Pinned because the route's 409 body surfaces this string and
    the operator needs to see ALL THREE allowed source states (after
    5e widened to include Maintenance) to diagnose 'why can't I
    decommission'."""
    state = _asset(lifecycle=AssetLifecycle.DECOMMISSIONED)
    with pytest.raises(AssetCannotDecommissionError) as exc_info:
        decommission_asset.decide(
            state=state,
            command=DecommissionAsset(asset_id=state.id),
            context=_EMPTY_CONTEXT,
            now=_NOW,
            decommissioned_by=_TEST_ACTOR_ID,
        )
    msg = str(exc_info.value)
    assert "Decommissioned" in msg
    assert "Commissioned" in msg
    assert "Active" in msg
    assert "Maintenance" in msg


@pytest.mark.unit
def test_decide_raises_has_fixture_binding_when_fixture_id_non_none() -> None:
    """Cross-aggregate guard: an Asset bound into a Fixture cannot
    be decommissioned; operator must detach_asset_from_fixture first.

    Fires BEFORE the lifecycle check, so a still-bound Active Asset
    surfaces the binding dependency rather than passing through to
    AssetDecommissioned.
    """
    fixture_id = uuid4()
    state = _asset(lifecycle=AssetLifecycle.ACTIVE, fixture_id=fixture_id)
    with pytest.raises(AssetHasFixtureBindingError) as exc_info:
        decommission_asset.decide(
            state=state,
            command=DecommissionAsset(asset_id=state.id),
            context=_EMPTY_CONTEXT,
            now=_NOW,
            decommissioned_by=_TEST_ACTOR_ID,
        )
    assert exc_info.value.asset_id == state.id
    assert exc_info.value.fixture_id == fixture_id


@pytest.mark.unit
def test_decide_raises_is_installed_when_currently_at_mount_non_none() -> None:
    """Cross-aggregate guard: an Asset installed in a Mount cannot
    be decommissioned; operator must uninstall_asset first.

    Fires BEFORE the lifecycle check.
    """
    mount_id = uuid4()
    state = _asset(lifecycle=AssetLifecycle.ACTIVE)
    context = DecommissionAssetContext(currently_installed_at_mount_id=mount_id)
    with pytest.raises(AssetIsInstalledError) as exc_info:
        decommission_asset.decide(
            state=state,
            command=DecommissionAsset(asset_id=state.id),
            context=context,
            now=_NOW,
            decommissioned_by=_TEST_ACTOR_ID,
        )
    assert exc_info.value.asset_id == state.id
    assert exc_info.value.mount_id == mount_id


@pytest.mark.unit
def test_decide_fixture_binding_guard_fires_before_mount_installed_guard() -> None:
    """When BOTH cross-aggregate guards would apply, fixture-binding
    fires first (deterministic order: detach is the inner step of
    the choreography, uninstall the outer).
    """
    fixture_id = uuid4()
    mount_id = uuid4()
    state = _asset(lifecycle=AssetLifecycle.ACTIVE, fixture_id=fixture_id)
    context = DecommissionAssetContext(currently_installed_at_mount_id=mount_id)
    with pytest.raises(AssetHasFixtureBindingError):
        decommission_asset.decide(
            state=state,
            command=DecommissionAsset(asset_id=state.id),
            context=context,
            now=_NOW,
            decommissioned_by=_TEST_ACTOR_ID,
        )


@pytest.mark.unit
def test_decide_cross_aggregate_guards_fire_before_lifecycle_guard() -> None:
    """A Decommissioned Asset that is somehow still fixture-bound
    surfaces the binding error, not the lifecycle error. Diagnostic
    clarity: 'detach first' is the more actionable message than
    'already decommissioned'.
    """
    fixture_id = uuid4()
    state = _asset(lifecycle=AssetLifecycle.DECOMMISSIONED, fixture_id=fixture_id)
    with pytest.raises(AssetHasFixtureBindingError):
        decommission_asset.decide(
            state=state,
            command=DecommissionAsset(asset_id=state.id),
            context=_EMPTY_CONTEXT,
            now=_NOW,
            decommissioned_by=_TEST_ACTOR_ID,
        )


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _asset(lifecycle=AssetLifecycle.ACTIVE)
    command = DecommissionAsset(asset_id=state.id)
    first = decommission_asset.decide(
        state=state,
        command=command,
        context=_EMPTY_CONTEXT,
        now=_NOW,
        decommissioned_by=_TEST_ACTOR_ID,
    )
    second = decommission_asset.decide(
        state=state,
        command=command,
        context=_EMPTY_CONTEXT,
        now=_NOW,
        decommissioned_by=_TEST_ACTOR_ID,
    )
    assert first == second
