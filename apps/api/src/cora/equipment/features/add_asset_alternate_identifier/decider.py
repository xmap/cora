"""Pure decider for the `AddAssetAlternateIdentifier` command.

One disqualifying condition surfaces a dedicated error class:

  - `(kind, value)` pair already in `state.alternate_identifiers`
    (strict-not-idempotent; mirrors the `add_model_family`
    add-vs-already-present split rather than the older
    `add_asset_port` collapsed-class pattern) ->
    `AssetAlternateIdentifierAlreadyPresentError`

Unlike `add_asset_port`, alternate-identifier mutation is allowed
in EVERY Asset lifecycle including Decommissioned: inventory tags
and serial numbers may be reconciled even after retirement (audit
correction, vendor RMA, etc.). The `routes.py` 409 mapping covers
only the AlreadyPresent class; no lifecycle-guard error is
registered. Symmetric with `remove_asset_alternate_identifier`.

`AlternateIdentifier` VO construction at command time validates
the `value` length / non-empty invariant and raises
`InvalidAlternateIdentifierValueError` (mapped to 400 by the BC's
exception handler); the closed `AlternateIdentifierKind` StrEnum
makes invalid `kind` values impossible to construct (Pydantic
catches strings at the route boundary).
"""

from datetime import datetime

from cora.equipment.aggregates.asset import (
    Asset,
    AssetAlternateIdentifierAdded,
    AssetAlternateIdentifierAlreadyPresentError,
    AssetNotFoundError,
)
from cora.equipment.features.add_asset_alternate_identifier.command import (
    AddAssetAlternateIdentifier,
)


def decide(
    state: Asset | None,
    command: AddAssetAlternateIdentifier,
    *,
    now: datetime,
) -> list[AssetAlternateIdentifierAdded]:
    """Decide the events produced by adding an alternate identifier.

    Invariants:
      - State must not be None -> AssetNotFoundError
      - `(kind, value)` pair must not already be in
        state.alternate_identifiers (strict-not-idempotent)
        -> AssetAlternateIdentifierAlreadyPresentError
    """
    if state is None:
        raise AssetNotFoundError(command.asset_id)

    identifier = command.alternate_identifier

    if identifier in state.alternate_identifiers:
        raise AssetAlternateIdentifierAlreadyPresentError(state.id, identifier)

    return [
        AssetAlternateIdentifierAdded(
            asset_id=state.id,
            alternate_identifier=identifier,
            occurred_at=now,
        )
    ]
