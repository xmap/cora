"""Pure decider for the `RemoveAssetAlternateIdentifier` command.

Mirror of `add_asset_alternate_identifier.decide`. Two
disqualifying conditions surface as dedicated error classes:

  - asset is `Decommissioned` (retired; no further identifier
    changes) -> `AssetCannotAddAlternateIdentifierError`
    (the shared lifecycle-guard class is used by BOTH add and
    remove deciders, mirroring the symmetry of the guard)
  - no exact `(kind, value)` pair in `state.alternate_identifiers`
    (strict-not-idempotent; symmetric with add) ->
    `AssetAlternateIdentifierNotPresentError`

The lifecycle guard mirrors `remove_asset_port` exactly: a
Decommissioned asset is out of inventory, and identifier changes
are not permitted. The `routes.py` 409 mapping covers the
NotPresent and lifecycle-guard classes.
"""

from datetime import datetime

from cora.equipment.aggregates.asset import (
    Asset,
    AssetAlternateIdentifierNotPresentError,
    AssetAlternateIdentifierRemoved,
    AssetCannotAddAlternateIdentifierError,
    AssetLifecycle,
    AssetNotFoundError,
)
from cora.equipment.features.remove_asset_alternate_identifier.command import (
    RemoveAssetAlternateIdentifier,
)


def decide(
    state: Asset | None,
    command: RemoveAssetAlternateIdentifier,
    *,
    now: datetime,
) -> list[AssetAlternateIdentifierRemoved]:
    """Decide the events produced by removing an alternate identifier.

    Invariants:
      - State must not be None -> AssetNotFoundError
      - Asset must not be Decommissioned
        -> AssetCannotAddAlternateIdentifierError (shared lifecycle
        guard class; used by BOTH add and remove deciders)
      - `(kind, value)` pair must be in state.alternate_identifiers
        (strict-not-idempotent)
        -> AssetAlternateIdentifierNotPresentError
    """
    if state is None:
        raise AssetNotFoundError(command.asset_id)

    identifier = command.alternate_identifier

    if state.lifecycle is AssetLifecycle.DECOMMISSIONED:
        raise AssetCannotAddAlternateIdentifierError(
            state.id,
            identifier.kind,
            identifier.value,
            reason=(
                f"asset is currently {AssetLifecycle.DECOMMISSIONED.value} "
                "(retired from service; alternate identifier changes are not allowed)"
            ),
        )

    if identifier not in state.alternate_identifiers:
        raise AssetAlternateIdentifierNotPresentError(state.id, identifier)

    return [
        AssetAlternateIdentifierRemoved(
            asset_id=state.id,
            alternate_identifier=identifier,
            occurred_at=now,
        )
    ]
