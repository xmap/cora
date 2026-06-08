"""Pure decider for the `DecommissionAsset` command.

Multi-source-state transition: `Commissioned | Active | Maintenance
-> Decommissioned`. Each source state is valid:

  - Commissioned: asset never went into service (operator changed
    mind, decommissioning before activation).
  - Active: asset retired from service (typical case).
  - Maintenance: asset retired during a maintenance window
    (operator decided not to bring it back into service).

## Cross-aggregate guards (run BEFORE the lifecycle check)

Two guards prevent decommission from stranding back-references on
sibling aggregates:

  - `state.fixture_id` must be None -> `AssetHasFixtureBindingError`
    (operator must `detach_asset_from_fixture` first; mirrors
    `decommission_mount`'s `MountHasAssetInstalled` guard).
  - `context.currently_installed_at_mount_id` must be None ->
    `AssetIsInstalledError` (operator must `uninstall_asset` first;
    mirrors `decommission_mount`'s `MountHasAssetInstalled` on the
    inverse axis).

Source-state guard uses tuple-membership rather than a
match-statement: the check is "is in {Commissioned, Active,
Maintenance}", which is naturally a set-membership test. Matches
the precedent locked by Subject's `remove_subject` decider.

Invariants:
  - State must not be None -> AssetNotFoundError
  - State.fixture_id must be None -> AssetHasFixtureBindingError(fixture_id=...)
  - context.currently_installed_at_mount_id must be None
    -> AssetIsInstalledError(mount_id=...)
  - State.lifecycle must be in {Commissioned, Active, Maintenance}
    -> AssetCannotDecommissionError(current_lifecycle=...)
"""

from datetime import datetime

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCannotDecommissionError,
    AssetDecommissioned,
    AssetHasFixtureBindingError,
    AssetIsInstalledError,
    AssetLifecycle,
    AssetNotFoundError,
)
from cora.equipment.features.decommission_asset.command import DecommissionAsset
from cora.equipment.features.decommission_asset.context import DecommissionAssetContext
from cora.shared.identity import ActorId

_DECOMMISSIONABLE_LIFECYCLES: tuple[AssetLifecycle, ...] = (
    AssetLifecycle.COMMISSIONED,
    AssetLifecycle.ACTIVE,
    AssetLifecycle.MAINTENANCE,
)


def decide(
    state: Asset | None,
    command: DecommissionAsset,
    *,
    context: DecommissionAssetContext,
    now: datetime,
    decommissioned_by: ActorId,
) -> list[AssetDecommissioned]:
    """Decide the events produced by decommissioning an existing asset."""
    if state is None:
        raise AssetNotFoundError(command.asset_id)
    if state.fixture_id is not None:
        raise AssetHasFixtureBindingError(state.id, state.fixture_id)
    if context.currently_installed_at_mount_id is not None:
        raise AssetIsInstalledError(state.id, context.currently_installed_at_mount_id)
    if state.lifecycle not in _DECOMMISSIONABLE_LIFECYCLES:
        raise AssetCannotDecommissionError(state.id, current_lifecycle=state.lifecycle)
    return [
        AssetDecommissioned(
            asset_id=state.id,
            occurred_at=now,
            decommissioned_by=decommissioned_by,
        )
    ]
