"""Pure decider for the `RelocateAsset` command.

Hierarchy mutation, not a lifecycle transition. Caller supplies the
target parent and a reason; decider reads the source parent from
state and emits an `AssetRelocated` event carrying both.

## Disqualifying conditions (collapsed into one error class)

  - state is None                                  -> AssetNotFoundError
  - asset is a root (parent_id=None)                -> AssetCannotRelocateError("...")
    (a root is facility-anchored; it has no parent to move from.
    Allowing relocate would break the root-anchoring invariant.)
  - asset is `Decommissioned`                      -> AssetCannotRelocateError("...")
    (retired from service; no further hierarchy changes.)
  - target_parent_id == asset_id                   -> AssetCannotRelocateError("...")
    (single-parent-tree self-loop; the trivial cycle case.)
  - target_parent_id == current parent_id          -> AssetCannotRelocateError("...")
    (no-op; strict semantics, not idempotent — same precedent as
    Subject's mount/measure/remove "second call raises" pattern.)

## Cycle detection deferred

The trivial self-loop (target == asset_id) is checked here. Full
cycle detection — walking the target's ancestor chain to ensure
the asset isn't already an ancestor of its own would-be parent —
requires loading the parent chain via additional event-store
queries. Deferred to projection-worker era when the
parent-tree-as-projection becomes available; documented as a known
gap.

## Active-Run gate deferred (BC-map watch item)

This decider does NOT verify that the Asset is free of active Run
membership. Operators MUST avoid relocating Assets that are bound
to a Running or Held Run via Plan.asset_ids — doing so silently
leaves the Run's bind-time snapshot stale (the Asset moved out
from under it) and can corrupt the Run's audit story.

The enforcement gate is deferred per Track-A audit (2026-05-16):
the principled cross-BC adapter would be an `AssetActiveRunLookup`
port over `proj_run_summary` joined with the Plan's asset_ids
denorm (mirrors `ClearanceLookup` / `CautionLookup`). Ship when
the first concrete incident OR pilot
operator request fires the trigger.

Until then: relocation during an active Run is the operator's
responsibility to avoid (UI guidance + operator-guide note carry
the burden).

## Eventual-consistency stance for the target ref

Same as `register_asset`: the decider does NOT verify the target
parent Asset exists in the event store. Precedent locked by Trust's
Conduit zone refs (3b).
"""

from datetime import datetime

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCannotRelocateError,
    AssetLifecycle,
    AssetNotFoundError,
    AssetRelocated,
)
from cora.equipment.features.relocate_asset.command import RelocateAsset


def decide(
    state: Asset | None,
    command: RelocateAsset,
    *,
    now: datetime,
) -> list[AssetRelocated]:
    """Decide the events produced by relocating an existing asset.

    Invariants:
      - State must not be None -> AssetNotFoundError
      - Asset must not be a root (parent_id=None, facility-anchored)
        -> AssetCannotRelocateError
      - Asset must not be Decommissioned
        -> AssetCannotRelocateError
      - to_parent_id must not equal the asset itself (self-loop)
        -> AssetCannotRelocateError
      - to_parent_id must not equal the current parent (no-op)
        -> AssetCannotRelocateError
    """
    if state is None:
        raise AssetNotFoundError(command.asset_id)

    if state.parent_id is None:
        raise AssetCannotRelocateError(
            state.id,
            reason=(
                "Root Assets (parent_id=None) are facility-anchored and cannot "
                "be relocated (would violate the root-anchoring invariant)"
            ),
        )

    if state.lifecycle is AssetLifecycle.DECOMMISSIONED:
        raise AssetCannotRelocateError(
            state.id,
            reason=(
                f"asset is currently {AssetLifecycle.DECOMMISSIONED.value} "
                "(retired from service; hierarchy changes are not allowed)"
            ),
        )

    if command.to_parent_id == state.id:
        raise AssetCannotRelocateError(
            state.id,
            reason="target parent equals the asset itself (self-loop)",
        )

    if command.to_parent_id == state.parent_id:
        raise AssetCannotRelocateError(
            state.id,
            reason=f"target parent {command.to_parent_id} is already the current parent (no-op)",
        )

    # state.parent_id is non-null per registration invariant + the
    # root guard above; assert narrows the type for pyright.
    assert state.parent_id is not None
    return [
        AssetRelocated(
            asset_id=state.id,
            from_parent_id=state.parent_id,
            to_parent_id=command.to_parent_id,
            reason=command.reason,
            occurred_at=now,
        )
    ]
