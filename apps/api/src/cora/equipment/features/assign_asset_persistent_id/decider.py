"""Pure decider for the `AssignAssetPersistentId` command.

The decider sees `(state, command)` with the resolved
`PersistentIdentifier` passed as a keyword-only argument (Lock 12
server-mint posture: the handler resolves the minter call and forwards
the resolved VO here). The decider is PURE: it does NOT call the
DoiMinter, does NOT read the wall clock (caller injects `now`), and
does NOT touch any I/O. Non-determinism is captured in the handler
closure per [[project-non-determinism-principle]].

Three disqualifying conditions surface as dedicated error classes:

  - state is None (no Asset exists with the given id) ->
    `AssetNotFoundError`
  - Asset is `Decommissioned` (retired; no further PID assignment) ->
    `AssetPersistentIdAssignmentForbiddenError`
  - `state.persistent_id is not None` (set-once; rejects same OR
    different value) -> `AssetPersistentIdAlreadyAssignedError`

P2-17 fitness pin: this module MUST NOT import from
`cora.equipment.ports` or `cora.equipment.adapters`. Any future
refactor that quietly moves the mint into the decider will fail the
architecture test.
"""

from datetime import datetime

from cora.equipment.aggregates.asset import (
    Asset,
    AssetLifecycle,
    AssetNotFoundError,
    AssetPersistentIdAlreadyAssignedError,
    AssetPersistentIdAssigned,
    AssetPersistentIdAssignmentForbiddenError,
)
from cora.equipment.features.assign_asset_persistent_id.command import AssignAssetPersistentId
from cora.shared.identifier import PersistentIdentifier


def decide(
    state: Asset | None,
    command: AssignAssetPersistentId,
    *,
    persistent_id: PersistentIdentifier,
    now: datetime,
) -> list[AssetPersistentIdAssigned]:
    """Decide the events produced by assigning a persistent identifier.

    Invariants:
      - State must not be None -> AssetNotFoundError
      - Asset must not be Decommissioned ->
        AssetPersistentIdAssignmentForbiddenError
      - state.persistent_id must be None (set-once) ->
        AssetPersistentIdAlreadyAssignedError
    """
    if state is None:
        raise AssetNotFoundError(command.asset_id)

    if state.lifecycle is AssetLifecycle.DECOMMISSIONED:
        raise AssetPersistentIdAssignmentForbiddenError(
            state.id,
            persistent_id,
            reason=(
                f"asset is currently {AssetLifecycle.DECOMMISSIONED.value} "
                "(retired from service; persistent identifier assignment is not allowed)"
            ),
        )

    if state.persistent_id is not None:
        raise AssetPersistentIdAlreadyAssignedError(
            state.id,
            current=state.persistent_id,
            attempted=persistent_id,
        )

    return [
        AssetPersistentIdAssigned(
            asset_id=state.id,
            persistent_id_scheme=persistent_id.scheme.value,
            persistent_id_value=persistent_id.value,
            occurred_at=now,
        )
    ]
