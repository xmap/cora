"""Pure decider for the `RemoveAssemblyPresentsAs` command."""

from datetime import datetime

from cora.equipment.aggregates._value_types import RoleId
from cora.equipment.aggregates.assembly import (
    Assembly,
    AssemblyNotFoundError,
    AssemblyPresentsAsRemoved,
    AssemblyRolePresentsAsNotPresentError,
)
from cora.equipment.features.remove_assembly_presents_as.command import (
    RemoveAssemblyPresentsAs,
)


def decide(
    state: Assembly | None,
    command: RemoveAssemblyPresentsAs,
    *,
    now: datetime,
) -> list[AssemblyPresentsAsRemoved]:
    """Decide the events produced by removing a Role from an Assembly's presents_as set.

    Invariants:
      - State must not be None -> AssemblyNotFoundError
      - role_id must be in state.presents_as
        (strict-not-idempotent) -> AssemblyRolePresentsAsNotPresentError
    """
    if state is None:
        raise AssemblyNotFoundError(command.assembly_id)

    if RoleId(command.role_id) not in state.presents_as:
        raise AssemblyRolePresentsAsNotPresentError(state.id, command.role_id)

    return [
        AssemblyPresentsAsRemoved(
            assembly_id=state.id,
            role_id=command.role_id,
            occurred_at=now,
        )
    ]


__all__ = ["decide"]
