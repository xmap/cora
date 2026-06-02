"""Pure decider for the `AddAssetAlternateIdentifier` command.

Two disqualifying conditions surface as dedicated error classes:

  - asset is `Decommissioned` (retired; no further identifier
    changes) -> `AssetCannotAddAlternateIdentifierError`
  - `(kind, value)` pair already in `state.alternate_identifiers`
    (strict-not-idempotent; mirrors the `add_model_family`
    add-vs-already-present split rather than the older
    `add_asset_port` collapsed-class pattern) ->
    `AssetAlternateIdentifierAlreadyPresentError`

The lifecycle guard mirrors `add_asset_port` exactly: a
Decommissioned asset is out of inventory, and identifier changes
are not permitted. Symmetric with
`remove_asset_alternate_identifier`. The `routes.py` 409 mapping
covers both the AlreadyPresent class and the lifecycle-guard
class.

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
    AssetCannotAddAlternateIdentifierError,
    AssetLifecycle,
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
      - Asset must not be Decommissioned
        -> AssetCannotAddAlternateIdentifierError
      - `(kind, value)` pair must not already be in
        state.alternate_identifiers (strict-not-idempotent)
        -> AssetAlternateIdentifierAlreadyPresentError
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

    if identifier in state.alternate_identifiers:
        raise AssetAlternateIdentifierAlreadyPresentError(state.id, identifier)

    return [
        AssetAlternateIdentifierAdded(
            asset_id=state.id,
            alternate_identifier=identifier,
            occurred_at=now,
        )
    ]
