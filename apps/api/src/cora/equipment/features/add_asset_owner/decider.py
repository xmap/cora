"""Pure decider for the `AddAssetOwner` command.

Two disqualifying conditions surface as dedicated error classes:

  - asset is `Decommissioned` (retired; no further owner changes)
    -> `AssetCannotAddOwnerError`
  - `command.owner.name` already in `state.owners` (strict-not-
    idempotent; uniqueness is keyed on name per Lock 5+6) ->
    `AssetOwnerAlreadyPresentError`

The lifecycle guard mirrors `add_asset_alternate_identifier`
exactly: a Decommissioned asset is out of inventory and owner
changes are not permitted. Symmetric with `remove_asset_owner`.

`AssetOwner` VO construction at command time validates each
bounded-text VO and enforces the identifier/identifier_type pairing
invariant (raises `InvalidAssetOwnerIdentifierPairingError`,
mapped to HTTP 400 by the BC's exception handler); reaching the
decider means the VO is already shape-valid.
"""

from datetime import datetime

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCannotAddOwnerError,
    AssetLifecycle,
    AssetNotFoundError,
    AssetOwnerAdded,
    AssetOwnerAlreadyPresentError,
)
from cora.equipment.features.add_asset_owner.command import AddAssetOwner


def decide(
    state: Asset | None,
    command: AddAssetOwner,
    *,
    now: datetime,
) -> list[AssetOwnerAdded]:
    """Decide the events produced by adding an owner.

    Invariants:
      - State must not be None -> AssetNotFoundError
      - Asset must not be Decommissioned -> AssetCannotAddOwnerError
      - `command.owner.name` must not already be present in
        state.owners (keyed on `name`; strict-not-idempotent) ->
        AssetOwnerAlreadyPresentError
    """
    if state is None:
        raise AssetNotFoundError(command.asset_id)

    owner = command.owner

    if state.lifecycle is AssetLifecycle.DECOMMISSIONED:
        raise AssetCannotAddOwnerError(
            state.id,
            owner.name,
            reason=(
                f"asset is currently {AssetLifecycle.DECOMMISSIONED.value} "
                "(retired from service; owner changes are not allowed)"
            ),
        )

    if any(existing.name == owner.name for existing in state.owners):
        raise AssetOwnerAlreadyPresentError(state.id, owner.name)

    return [
        AssetOwnerAdded(
            asset_id=state.id,
            owner=owner,
            occurred_at=now,
        )
    ]
