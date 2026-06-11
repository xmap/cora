"""Unit tests for the `relocate_asset` slice's pure decider.

Hierarchy mutation, not a lifecycle transition. The decider has FOUR
disqualifying conditions collapsed into one error class
(`AssetCannotRelocateError`) plus the standard `AssetNotFoundError`
guard:

  - root (parent_id=None; facility-anchored, cannot be relocated)
  - Decommissioned lifecycle (retired)
  - target == asset_id (self-loop; trivial cycle case)
  - target == current parent_id (no-op; strict semantics)

Cycle detection beyond the trivial self-loop case is deferred to
projection-worker era.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCannotRelocateError,
    AssetLifecycle,
    AssetName,
    AssetNotFoundError,
    AssetRelocated,
    AssetTier,
)
from cora.equipment.features import relocate_asset
from cora.equipment.features.relocate_asset import RelocateAsset

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


def _asset(
    *,
    tier: AssetTier = AssetTier.DEVICE,
    lifecycle: AssetLifecycle = AssetLifecycle.COMMISSIONED,
    parent_id: object = "auto",
) -> Asset:
    """Build an Asset with sensible defaults; parent_id="auto" → fresh uuid."""
    pid = uuid4() if parent_id == "auto" else parent_id  # type: ignore[assignment]
    return Asset(
        id=uuid4(),
        name=AssetName("APS-2BM"),
        tier=tier,
        parent_id=pid,  # type: ignore[arg-type]
        lifecycle=lifecycle,
    )


@pytest.mark.unit
def test_decide_emits_asset_relocated_with_both_parents_and_reason() -> None:
    """Happy path: state's current parent becomes from_parent_id; the
    command's to_parent_id is carried straight through. Reason flows
    from command to event payload unchanged."""
    state = _asset()
    new_parent = uuid4()
    events = relocate_asset.decide(
        state=state,
        command=RelocateAsset(
            asset_id=state.id,
            to_parent_id=new_parent,
            reason="site reorganization",
        ),
        now=_NOW,
    )
    assert events == [
        AssetRelocated(
            asset_id=state.id,
            from_parent_id=state.parent_id,  # type: ignore[arg-type]
            to_parent_id=new_parent,
            reason="site reorganization",
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_raises_asset_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(AssetNotFoundError) as exc_info:
        relocate_asset.decide(
            state=None,
            command=RelocateAsset(
                asset_id=target_id,
                to_parent_id=uuid4(),
                reason="moved",
            ),
            now=_NOW,
        )
    assert exc_info.value.asset_id == target_id


@pytest.mark.unit
def test_decide_raises_cannot_relocate_when_asset_is_root() -> None:
    """A root Asset (parent_id=None) is facility-anchored and has no
    parent to move from; allowing relocate would break the
    root-anchoring invariant."""
    state = _asset(parent_id=None)
    with pytest.raises(AssetCannotRelocateError) as exc_info:
        relocate_asset.decide(
            state=state,
            command=RelocateAsset(
                asset_id=state.id,
                to_parent_id=uuid4(),
                reason="moved",
            ),
            now=_NOW,
        )
    assert exc_info.value.asset_id == state.id
    assert "Root" in exc_info.value.reason


@pytest.mark.unit
def test_decide_raises_cannot_relocate_when_asset_is_decommissioned() -> None:
    """Retired-from-service assets cannot be moved in the hierarchy."""
    state = _asset(lifecycle=AssetLifecycle.DECOMMISSIONED)
    with pytest.raises(AssetCannotRelocateError) as exc_info:
        relocate_asset.decide(
            state=state,
            command=RelocateAsset(
                asset_id=state.id,
                to_parent_id=uuid4(),
                reason="moved",
            ),
            now=_NOW,
        )
    assert exc_info.value.asset_id == state.id
    assert "Decommissioned" in exc_info.value.reason


@pytest.mark.unit
def test_decide_raises_cannot_relocate_for_self_loop() -> None:
    """Target == asset_id is the trivial cycle case (single-parent tree
    cannot allow self-parenthood). Pinned because cycle detection
    beyond this case is deferred to projection-worker era; this is
    the only structural cycle guard that exists."""
    state = _asset()
    with pytest.raises(AssetCannotRelocateError) as exc_info:
        relocate_asset.decide(
            state=state,
            command=RelocateAsset(
                asset_id=state.id,
                to_parent_id=state.id,  # self-loop
                reason="moved",
            ),
            now=_NOW,
        )
    assert exc_info.value.asset_id == state.id
    assert "self-loop" in exc_info.value.reason


@pytest.mark.unit
def test_decide_raises_cannot_relocate_for_no_op_target_equals_current_parent() -> None:
    """Strict semantics, not idempotent: relocating to the current
    parent raises. Same precedent as Subject's mount/measure/remove
    "second call raises" pattern."""
    current_parent = uuid4()
    state = _asset(parent_id=current_parent)
    with pytest.raises(AssetCannotRelocateError) as exc_info:
        relocate_asset.decide(
            state=state,
            command=RelocateAsset(
                asset_id=state.id,
                to_parent_id=current_parent,
                reason="moved",
            ),
            now=_NOW,
        )
    assert exc_info.value.asset_id == state.id
    assert "no-op" in exc_info.value.reason


@pytest.mark.unit
@pytest.mark.parametrize(
    "lifecycle",
    [
        AssetLifecycle.COMMISSIONED,
        AssetLifecycle.ACTIVE,
        AssetLifecycle.MAINTENANCE,
    ],
)
def test_decide_succeeds_for_every_non_decommissioned_lifecycle(
    lifecycle: AssetLifecycle,
) -> None:
    """Relocation is allowed in every lifecycle state EXCEPT
    Decommissioned. Pinned: a future change that narrows the
    allowed-lifecycle set would silently break maintenance-window
    moves."""
    state = _asset(lifecycle=lifecycle)
    new_parent = uuid4()
    events = relocate_asset.decide(
        state=state,
        command=RelocateAsset(
            asset_id=state.id,
            to_parent_id=new_parent,
            reason="moved",
        ),
        now=_NOW,
    )
    assert len(events) == 1
    assert events[0].to_parent_id == new_parent


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _asset()
    command = RelocateAsset(
        asset_id=state.id,
        to_parent_id=uuid4(),
        reason="moved",
    )
    first = relocate_asset.decide(state=state, command=command, now=_NOW)
    second = relocate_asset.decide(state=state, command=command, now=_NOW)
    assert first == second
