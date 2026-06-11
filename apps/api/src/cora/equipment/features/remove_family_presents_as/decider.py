"""Pure decider for the `RemoveFamilyPresentsAs` command."""

from datetime import datetime

from cora.equipment.aggregates._value_types import RoleId
from cora.equipment.aggregates.family import (
    Family,
    FamilyNotFoundError,
    FamilyPresentsAsRemoved,
    FamilyRolePresentsAsNotPresentError,
)
from cora.equipment.features.remove_family_presents_as.command import (
    RemoveFamilyPresentsAs,
)


def decide(
    state: Family | None,
    command: RemoveFamilyPresentsAs,
    *,
    now: datetime,
) -> list[FamilyPresentsAsRemoved]:
    """Decide the events produced by removing a Role from a Family's presents_as set.

    Invariants:
      - State must not be None -> FamilyNotFoundError
      - role_id must be in state.presents_as
        (strict-not-idempotent) -> FamilyRolePresentsAsNotPresentError
    """
    if state is None:
        raise FamilyNotFoundError(command.family_id)

    if RoleId(command.role_id) not in state.presents_as:
        raise FamilyRolePresentsAsNotPresentError(state.id, command.role_id)

    return [
        FamilyPresentsAsRemoved(
            family_id=state.id,
            role_id=command.role_id,
            occurred_at=now,
        )
    ]


__all__ = ["decide"]
