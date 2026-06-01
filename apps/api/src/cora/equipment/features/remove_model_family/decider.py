"""Pure decider for the `RemoveModelFamily` command.

Targeted mutation of `Model.declared_families`, not a lifecycle
transition. Status is preserved (`Defined` stays `Defined`,
`Versioned` stays `Versioned`); only `Deprecated` is rejected, on
the same "deprecated catalog entry is frozen" rationale that drives
`ModelVersioned` and `ModelFamilyAdded` rejection from `Deprecated`
in the events module.

There is no dedicated `ModelCannotRemoveFamilyError` in the Model
aggregate; the Model aggregate carries `ModelCannotVersionError`
as its general "cannot mutate from Deprecated" gate (add and remove
are conceptually version-like mutations of the declared-families
set), so this slice reuses it. The diagnostic message stays
accurate because `ModelCannotVersionError` already enumerates the
allowed `Defined | Versioned` source states.

The decider does NOT verify the referenced Family id resolves to a
real Family stream; removal only requires that the id already sits
in `declared_families`. The Family may have been deprecated or
deleted in the Family registry, and removal still proceeds.

Strict-not-idempotent: removing an absent family raises
`ModelFamilyNotPresentError` (mirrors `add_model_family` and
`remove_asset_family`).

Invariants:
  - State must not be None -> ModelNotFoundError
  - State.status must not be Deprecated -> ModelCannotVersionError
  - family_id must already be in state.declared_families
    (strict-not-idempotent) -> ModelFamilyNotPresentError
"""

from datetime import datetime

from cora.equipment.aggregates.model import (
    Model,
    ModelCannotVersionError,
    ModelFamilyNotPresentError,
    ModelFamilyRemoved,
    ModelNotFoundError,
    ModelStatus,
)
from cora.equipment.features.remove_model_family.command import RemoveModelFamily


def decide(
    state: Model | None,
    command: RemoveModelFamily,
    *,
    now: datetime,
) -> list[ModelFamilyRemoved]:
    """Decide the events produced by removing a family from an existing model."""
    if state is None:
        raise ModelNotFoundError(command.model_id)
    if state.status is ModelStatus.DEPRECATED:
        raise ModelCannotVersionError(state.id, current_status=state.status)
    if command.family_id not in state.declared_families:
        raise ModelFamilyNotPresentError(state.id, command.family_id)
    return [
        ModelFamilyRemoved(
            model_id=state.id,
            family_id=command.family_id,
            occurred_at=now,
        )
    ]
