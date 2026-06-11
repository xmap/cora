"""Pure decider for the `AddMethodRequiredRole` command.

Three disqualifying conditions surface as dedicated error classes:

  - Method stream has no events -> `MethodNotFoundError` (404)
  - Method status is not `Defined` (i.e. `Versioned` or `Deprecated`)
    -> `MethodCannotMutateRequiredRolesError` (409). A `Versioned`
    Method has an attested content_hash that covers required_roles,
    and a `Deprecated` Method is out of use entirely.
  - `command.requirement.role_name` already in `state.required_roles`
    -> `MethodRoleNameAlreadyDeclaredError` (409, strict-not-
    idempotent; uniqueness keyed on role_name within the Method
    scope)

Eventual-consistency on `family_id`: the decider does NOT verify the
referenced Family stream exists. Same precedent as
`Method.needed_family_ids` and `Method.needed_assembly_ids`. Mismatch
surfaces at Plan binding (`bind_plan_role`) when the role cannot be
filled by an Asset carrying that Family.

Fail-fast on `role_kind`: handler-side `RoleLookup` precondition
fires before this decider runs (Layer 3 sub-slice 3D); a missing
Role surfaces as `RoleNotFoundError` at the handler edge, not as a
silent satisfaction-side failure later at Plan binding.

`RoleRequirement` + `PortRequirement` + `RoleName` VOs validate their
own bounded text in `__post_init__`; reaching the decider means the
VO is already shape-valid.
"""

from datetime import datetime

from cora.recipe.aggregates.method import (
    Method,
    MethodCannotMutateRequiredRolesError,
    MethodNotFoundError,
    MethodRequiredRoleAdded,
    MethodRoleNameAlreadyDeclaredError,
    MethodStatus,
)
from cora.recipe.features.add_method_required_role.command import AddMethodRequiredRole


def decide(
    state: Method | None,
    command: AddMethodRequiredRole,
    *,
    now: datetime,
) -> list[MethodRequiredRoleAdded]:
    """Decide the events produced by adding a required role.

    Invariants:
      - State must not be None -> MethodNotFoundError
      - State.status must be Defined -> MethodCannotMutateRequiredRolesError
      - command.requirement.role_name must not already be present in
        state.required_roles (keyed on role_name; strict-not-
        idempotent) -> MethodRoleNameAlreadyDeclaredError
    """
    if state is None:
        raise MethodNotFoundError(command.method_id)

    if state.status is not MethodStatus.DEFINED:
        raise MethodCannotMutateRequiredRolesError(state.id, state.status)

    requirement = command.requirement
    if any(existing.role_name == requirement.role_name for existing in state.required_roles):
        raise MethodRoleNameAlreadyDeclaredError(state.id, requirement.role_name)

    # required_ports flattens to a tuple[dict, ...] for the event
    # payload. Each PortRequirement materializes as a plain dict so
    # the persisted JSON is operator-readable without VO-aware tooling.
    # The evolver re-hydrates the PortRequirement VOs when folding.
    required_ports_payload = tuple(
        {
            "port_name": port.port_name,
            "direction": port.direction.value,
            "signal_type": port.signal_type,
        }
        for port in requirement.required_ports
    )

    return [
        MethodRequiredRoleAdded(
            method_id=state.id,
            role_name=requirement.role_name.value,
            family_id=requirement.family_id,
            required_ports=required_ports_payload,
            optional=requirement.optional,
            occurred_at=now,
            # Layer 3 sub-slice 3D: role_kind threads through the
            # event payload as additive evolution. XOR with family_id
            # is enforced by RoleRequirement.__post_init__ before the
            # decider sees the requirement, so exactly one of the two
            # is non-None here.
            role_kind=requirement.role_kind,
        )
    ]
