"""Pure decider for the `RemoveAssetOwner` command.

Mirror of `add_asset_owner.decide`. Two disqualifying conditions
surface as dedicated error classes:

  - asset is `Decommissioned` (retired; no further owner changes)
    -> `AssetCannotAddOwnerError` (the shared lifecycle-guard class
    is used by BOTH add and remove deciders)
  - `command.owner_name` not present in state.owners (strict-not-
    idempotent; symmetric with add) -> `AssetOwnerNotPresentError`

Removing the last owner is allowed (Lock 7): an Asset can exist
registered with owner not yet captured; the PIDINST emission gate
at the serializer raises `OwnerStateNotAvailableError` on empty.
"""

from datetime import datetime

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCannotAddOwnerError,
    AssetLifecycle,
    AssetNotFoundError,
    AssetOwnerNotPresentError,
    AssetOwnerRemoved,
)
from cora.equipment.features.remove_asset_owner.command import RemoveAssetOwner


def decide(
    state: Asset | None,
    command: RemoveAssetOwner,
    *,
    now: datetime,
) -> list[AssetOwnerRemoved]:
    """Decide the events produced by removing an owner.

    Invariants:
      - State must not be None -> AssetNotFoundError
      - Asset must not be Decommissioned -> AssetCannotAddOwnerError
        (shared lifecycle guard with the add slice)
      - `command.owner_name` must be present in state.owners
        (strict-not-idempotent) -> AssetOwnerNotPresentError
      - Removing the last owner is allowed (Lock 7); no error
    """
    if state is None:
        raise AssetNotFoundError(command.asset_id)

    name = command.owner_name

    if state.lifecycle is AssetLifecycle.DECOMMISSIONED:
        raise AssetCannotAddOwnerError(
            state.id,
            name,
            reason=(
                f"asset is currently {AssetLifecycle.DECOMMISSIONED.value} "
                "(retired from service; owner changes are not allowed)"
            ),
        )

    if not any(existing.name == name for existing in state.owners):
        raise AssetOwnerNotPresentError(state.id, name)

    return [
        AssetOwnerRemoved(
            asset_id=state.id,
            owner_name=name,
            occurred_at=now,
        )
    ]
