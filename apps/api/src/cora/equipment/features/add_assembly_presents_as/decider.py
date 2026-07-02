"""Pure decider for the `AddAssemblyPresentsAs` command.

The handler verifies the Role exists via `RoleLookup` at the edge
(RoleNotFoundError on miss). This decider only enforces the
state-side strict-not-idempotent guard; the affordance-superset
gate from 3B's Family decider is not replicated here because an
Assembly's affordances are constituent-derived and unknown at
template time. The gate is enforced instead at register_fixture time,
once concrete Assets fill the slots, via FixtureCannotPresentRoleError.
"""

from datetime import datetime

from cora.equipment.aggregates._value_types import RoleId
from cora.equipment.aggregates.assembly import (
    Assembly,
    AssemblyNotFoundError,
    AssemblyPresentsAsAdded,
    AssemblyRolePresentsAsAlreadyError,
)
from cora.equipment.features.add_assembly_presents_as.command import AddAssemblyPresentsAs


def decide(
    state: Assembly | None,
    command: AddAssemblyPresentsAs,
    *,
    now: datetime,
) -> list[AssemblyPresentsAsAdded]:
    """Decide the events produced by adding a Role to an Assembly's presents_as set.

    Invariants:
      - State must not be None -> AssemblyNotFoundError
      - role_id must not already be in state.presents_as
        (strict-not-idempotent) -> AssemblyRolePresentsAsAlreadyError
    """
    if state is None:
        raise AssemblyNotFoundError(command.assembly_id)

    if RoleId(command.role_id) in state.presents_as:
        raise AssemblyRolePresentsAsAlreadyError(state.id, command.role_id)

    return [
        AssemblyPresentsAsAdded(
            assembly_id=state.id,
            role_id=command.role_id,
            occurred_at=now,
        )
    ]


__all__ = ["decide"]
