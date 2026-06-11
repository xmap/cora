"""Pure decider for the `AddFamilyPresentsAs` command.

The handler resolves the Role via `RoleLookup` at the edge and
threads the result into the decider as `role_lookup_result`. This
keeps the decider pure (no I/O, no awaits) while making the
affordance-superset gate explicit at the decision boundary.
"""

from datetime import datetime

from cora.equipment.aggregates._value_types import RoleId
from cora.equipment.aggregates.family import (
    Affordance,
    Family,
    FamilyCannotPresentAsError,
    FamilyNotFoundError,
    FamilyPresentsAsAdded,
    FamilyRolePresentsAsAlreadyError,
)
from cora.equipment.features.add_family_presents_as.command import AddFamilyPresentsAs
from cora.infrastructure.ports.role_lookup import RoleLookupResult


def decide(
    state: Family | None,
    command: AddFamilyPresentsAs,
    *,
    now: datetime,
    role_lookup_result: RoleLookupResult,
) -> list[FamilyPresentsAsAdded]:
    """Decide the events produced by adding a Role to a Family's presents_as set.

    Invariants:
      - State must not be None -> FamilyNotFoundError
      - role_id must not already be in state.presents_as
        (strict-not-idempotent) -> FamilyRolePresentsAsAlreadyError
      - role_lookup_result.id must equal command.role_id (handler
        contract; defensive check, never user-driven)
      - Family.affordances must superset role_lookup_result
        .required_affordances -> FamilyCannotPresentAsError
    """
    if state is None:
        raise FamilyNotFoundError(command.family_id)

    if RoleId(command.role_id) in state.presents_as:
        raise FamilyRolePresentsAsAlreadyError(state.id, command.role_id)

    assert role_lookup_result.id == command.role_id, (
        f"handler contract violation: role_lookup_result.id "
        f"{role_lookup_result.id} != command.role_id {command.role_id}"
    )

    family_affordance_values = {a.value for a in state.affordances}
    missing_value_strings = role_lookup_result.required_affordances - family_affordance_values
    if missing_value_strings:
        missing_affordances = frozenset(Affordance(s) for s in missing_value_strings)
        raise FamilyCannotPresentAsError(
            family_id=state.id,
            role_id=command.role_id,
            missing_affordances=missing_affordances,
        )

    return [
        FamilyPresentsAsAdded(
            family_id=state.id,
            role_id=command.role_id,
            occurred_at=now,
        )
    ]


__all__ = ["decide"]
