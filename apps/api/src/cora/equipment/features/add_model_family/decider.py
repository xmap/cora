"""Pure decider for the `AddModelFamily` command.

Targeted mutation of `Model.declared_families`, not a lifecycle
transition. Status is preserved (`Defined` stays `Defined`,
`Versioned` stays `Versioned`); only `Deprecated` is rejected, on
the same "deprecated catalog entry is frozen" rationale that drives
`ModelVersioned` and `ModelFamilyRemoved` rejection from
`Deprecated` in the events module.

There is no dedicated `ModelCannotAddFamilyError` in the Model
aggregate; the Model aggregate carries `ModelCannotVersionError`
as its general "cannot mutate from Deprecated" gate (add and remove
are conceptually version-like mutations of the declared-families
set), so this slice reuses it. The diagnostic message stays
accurate because `ModelCannotVersionError` already enumerates the
allowed `Defined | Versioned` source states.

The decider does NOT verify the referenced Family id resolves to a
real Family stream; the handler performs that cross-BC lookup
upstream (mirroring `define_model`) and raises `FamilyNotFoundError`
before the command reaches the decider.

Strict-not-idempotent: re-adding a present family raises
`ModelFamilyAlreadyPresentError` (mirrors `add_asset_family`).

Invariants:
  - State must not be None -> ModelNotFoundError
  - State.status must not be Deprecated -> ModelCannotVersionError
  - family_id must not already be in state.declared_families
    (strict-not-idempotent) -> ModelFamilyAlreadyPresentError
"""

from datetime import datetime

from cora.equipment.aggregates.model import (
    Model,
    ModelCannotVersionError,
    ModelFamilyAdded,
    ModelFamilyAlreadyPresentError,
    ModelNotFoundError,
    ModelStatus,
)
from cora.equipment.features.add_model_family.command import AddModelFamily


def decide(
    state: Model | None,
    command: AddModelFamily,
    *,
    now: datetime,
) -> list[ModelFamilyAdded]:
    """Decide the events produced by adding a family to an existing model."""
    if state is None:
        raise ModelNotFoundError(command.model_id)
    if state.status is ModelStatus.DEPRECATED:
        raise ModelCannotVersionError(state.id, current_status=state.status)
    if command.family_id in state.declared_families:
        raise ModelFamilyAlreadyPresentError(state.id, command.family_id)
    return [
        ModelFamilyAdded(
            model_id=state.id,
            family_id=command.family_id,
            occurred_at=now,
        )
    ]
