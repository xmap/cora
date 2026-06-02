"""Pure decider for the `RemoveAssetAlternateIdentifier` command.

Mirror of `add_asset_alternate_identifier.decide`. One disqualifying
condition surfaces a dedicated error class:

  - no exact `(kind, value)` pair in `state.alternate_identifiers`
    (strict-not-idempotent; symmetric with add) ->
    `AssetAlternateIdentifierNotPresentError`

Unlike `remove_asset_port`, alternate-identifier mutation is allowed
in EVERY Asset lifecycle including Decommissioned: inventory tags
and serial numbers may be reconciled even after retirement (audit
correction, vendor RMA, etc.). The `routes.py` 409 mapping covers
only the NotPresent and AlreadyPresent classes; no lifecycle-guard
error is registered.
"""

from datetime import datetime

from cora.equipment.aggregates.asset import (
    Asset,
    AssetAlternateIdentifierNotPresentError,
    AssetAlternateIdentifierRemoved,
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
      - `(kind, value)` pair must be in state.alternate_identifiers
        (strict-not-idempotent)
        -> AssetAlternateIdentifierNotPresentError
    """
    if state is None:
        raise AssetNotFoundError(command.asset_id)

    identifier = command.alternate_identifier

    if identifier not in state.alternate_identifiers:
        raise AssetAlternateIdentifierNotPresentError(state.id, identifier)

    return [
        AssetAlternateIdentifierRemoved(
            asset_id=state.id,
            alternate_identifier=identifier,
            occurred_at=now,
        )
    ]
