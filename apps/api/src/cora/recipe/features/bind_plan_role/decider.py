"""Pure decider for the `BindPlanRole` command.

Mirrors the cross-aggregate-read pattern from `add_plan_wire`. The
context object is constructed by the handler from `load_method` +
`load_asset` (plus, for the 3D role_kind path, `RoleLookup.lookup`
and a `FamilyLookup.lookup` batch over `asset.family_ids`); tests
pass it directly to bypass the I/O. Fail-fast order is the same as
the Invariants list below.

## Bifurcation (Layer 3 sub-slice 3D)

`RoleRequirement` carries either `role_kind` (federation-portable;
Layer 3) OR `family_id` (anatomical escape hatch; slice-1) per the
XOR invariant enforced by the VO. The satisfaction check splits:

  - family_id path: existing slice-1 check
    `role.family_id in asset.family_ids` -> PlanRoleFamilyMismatchError
  - role_kind path: ANY-single-family disjunction per Lock 17, OR-ed
    with the composed-Assembly branch. For each family_id in
    `asset.family_ids` the handler must have loaded a
    `FamilyLookupResult`; the decider walks the dict and accepts
    iff AT LEAST ONE Family both (a) declares `role_kind` in its
    `presents_as` AND (b) has `affordances` superset
    `Role.required_affordances`. None-on-lookup raises
    `PlanRoleFamilyNotResolvableError`. If no Family satisfies but
    the Asset carries `fixture_id` AND the handler-loaded
    `AssemblyLookupResult.presents_as` contains `role_kind`, the
    Assembly satisfaction path accepts the binding (Assembly
    affordance-superset is enforced at register_fixture time, not
    at template time per 3C state docstring). If neither path
    succeeds, `PlanRoleAssetCannotPresentError` fires.

Invariants:
  - State must not be None -> PlanNotFoundError
  - Plan must be in Defined status -> PlanCannotMutateRoleBindingsError
  - command.asset_id must be in state.asset_ids ->
    PlanRoleAssetNotBoundError
  - role_name must not already be in state.role_bindings (strict-not-
    idempotent) -> PlanRoleAlreadyBoundError
  - Method must be loaded via state.method_id -> MethodNotFoundError
  - role_name must match a RoleRequirement on method.required_roles
    -> PlanRoleNameNotDeclaredError
  - Asset must be loaded -> AssetNotFoundError
  - Family-path satisfaction OR role_kind-path satisfaction (see above)
  - Port coverage + wire-graph consistency (unchanged from slice-2)
"""

from datetime import datetime

from cora.equipment.aggregates.asset import AssetNotFoundError, PortDirection
from cora.recipe.aggregates.method import MethodNotFoundError, RoleRequirement
from cora.recipe.aggregates.plan import (
    Plan,
    PlanCannotMutateRoleBindingsError,
    PlanNotFoundError,
    PlanRoleAlreadyBoundError,
    PlanRoleAssetCannotPresentError,
    PlanRoleAssetNotBoundError,
    PlanRoleBound,
    PlanRoleFamilyMismatchError,
    PlanRoleFamilyNotResolvableError,
    PlanRoleNameNotDeclaredError,
    PlanRolePortCoverageNotSatisfiedError,
    PlanStatus,
    PlanWireRoleEndpointMismatchError,
)
from cora.recipe.features.bind_plan_role.command import BindPlanRole
from cora.recipe.features.bind_plan_role.context import BindPlanRoleContext


def decide(
    state: Plan | None,
    command: BindPlanRole,
    *,
    context: BindPlanRoleContext,
    now: datetime,
) -> list[PlanRoleBound]:
    """Decide the events produced by binding a role to an Asset.

    Invariants:
      - State must not be None -> PlanNotFoundError
      - Plan status must be Defined -> PlanCannotMutateRoleBindingsError
      - asset_id must be in state.asset_ids -> PlanRoleAssetNotBoundError
      - role_name must not already be bound (strict-not-idempotent) ->
        PlanRoleAlreadyBoundError
      - Method must be loaded -> MethodNotFoundError
      - role_name must match a RoleRequirement on method.required_roles
        -> PlanRoleNameNotDeclaredError
      - Asset must be loaded -> AssetNotFoundError
      - Family-path (slice-1): asset.family_ids must include
        role.family_id -> PlanRoleFamilyMismatchError
      - Role-kind path (3D): every family_id in asset.family_ids
        must resolve via FamilyLookup ->
        PlanRoleFamilyNotResolvableError; at least one of those
        Families must declare role_kind in presents_as AND have
        affordances superset role.required_affordances (Lock 17
        ANY-single-family disjunction), OR (if the Asset is in a
        Fixture) the loaded Assembly's presents_as must contain
        role_kind ->
        PlanRoleAssetCannotPresentError
      - Asset.ports must cover every role.required_ports triple
        exactly -> PlanRolePortCoverageNotSatisfiedError
      - No existing wire's endpoint port may claim a role's
        required_port at an Asset other than the candidate bound
        Asset -> PlanWireRoleEndpointMismatchError
    """
    if state is None:
        raise PlanNotFoundError(command.plan_id)

    if state.status is not PlanStatus.DEFINED:
        raise PlanCannotMutateRoleBindingsError(state.id, state.status)

    if command.asset_id not in state.asset_ids:
        raise PlanRoleAssetNotBoundError(state.id, command.role_name, command.asset_id)

    if any(b.role_name == command.role_name for b in state.role_bindings):
        raise PlanRoleAlreadyBoundError(state.id, command.role_name)

    method = context.method
    if method is None:
        # Unlike `add_plan_wire`, this decider CANNOT proceed without a
        # Method: the role_name must be validated against
        # method.required_roles, and there is no fallback semantic that
        # could justify silently binding to an unknown role. The
        # asymmetry with add_plan_wire (which silently skips the role
        # check when method is None) is principled and documented in
        # the add_plan_wire decider. `state.method_id or command.plan_id`
        # surfaces the better sentinel: prefer the genuine method_id when
        # the Plan declares one, otherwise echo plan_id so the operator
        # sees the offending Plan.
        raise MethodNotFoundError(state.method_id or command.plan_id)

    matching_role: RoleRequirement | None = None
    for role in method.required_roles:
        if role.role_name == command.role_name:
            matching_role = role
            break
    if matching_role is None:
        raise PlanRoleNameNotDeclaredError(state.id, method.id, command.role_name)

    asset = context.asset
    if asset is None:
        raise AssetNotFoundError(command.asset_id)

    # Bifurcated satisfaction check per memo Lock 17.
    if matching_role.role_kind is not None:
        # 3D role_kind path: ANY-single-family disjunction. Walk
        # asset.family_ids, lookup each in context.family_lookups,
        # accept iff AT LEAST ONE Family advertises role_kind in
        # presents_as AND has affordances superset
        # role.required_affordances.
        # Handler contract: role_lookup_result MUST be populated when
        # matching_role.role_kind is set. Mirror the symmetric XOR
        # guard at line 178 below: assert (not a domain error) so a
        # buggy handler / test fails loud rather than silently mis-
        # binding. Operators never see this; only callers that
        # bypass the handler can trigger it.
        assert context.role_lookup_result is not None, (
            "handler contract violation: role_lookup_result must be populated "
            f"when matching_role.role_kind is set (role_kind={matching_role.role_kind})"
        )
        role_lookup = context.role_lookup_result
        required_affordances = role_lookup.required_affordances
        satisfied_by: bool = False
        for family_id in asset.family_ids:
            family_row = context.family_lookups.get(family_id)
            if family_row is None:
                raise PlanRoleFamilyNotResolvableError(
                    state.id,
                    command.role_name,
                    command.asset_id,
                    family_id,
                )
            if matching_role.role_kind in family_row.presents_as and (
                required_affordances <= family_row.affordances
            ):
                satisfied_by = True
                break
        # Assembly satisfaction OR-branch: when no Family satisfied
        # and the Asset is part of a materialized Assembly (via
        # fixture_id), accept the binding iff the loaded Assembly's
        # presents_as contains role_kind. Affordance-superset is NOT
        # checked here -- Assembly affordances derive from the
        # constituent Family union at register_fixture time per
        # the 3C state.py docstring, so the check belongs at the
        # fixture-registration layer, not the bind-time layer.
        if not satisfied_by and asset.fixture_id is not None:
            assembly_row = context.assembly_lookup_result
            if assembly_row is not None and matching_role.role_kind in assembly_row.presents_as:
                satisfied_by = True
        if not satisfied_by:
            raise PlanRoleAssetCannotPresentError(
                state.id,
                command.role_name,
                command.asset_id,
                matching_role.role_kind,
                asset.family_ids,
            )
    else:
        # Slice-1 family_id path: anatomical escape hatch unchanged.
        # XOR invariant guarantees family_id is non-None here.
        assert matching_role.family_id is not None, (
            "RoleRequirement.__post_init__ invariant violated: neither role_kind nor family_id set"
        )
        if matching_role.family_id not in asset.family_ids:
            raise PlanRoleFamilyMismatchError(
                state.id,
                command.role_name,
                command.asset_id,
                matching_role.family_id,
                asset.family_ids,
            )

    # Port coverage: each required (port_name, direction, signal_type)
    # triple must match an existing Asset.port triple exactly.
    asset_port_triples = {(p.name, p.direction, p.signal_type) for p in asset.ports}
    missing: list[tuple[str, str, str]] = []
    for required in matching_role.required_ports:
        triple = (required.port_name, required.direction, required.signal_type)
        if triple not in asset_port_triples:
            missing.append((triple[0], triple[1].value, triple[2]))
    if missing:
        raise PlanRolePortCoverageNotSatisfiedError(
            state.id,
            command.role_name,
            command.asset_id,
            missing,
        )

    # Wire-graph consistency: scan existing wires for any endpoint
    # that already claims this role's port (by name + side) at a
    # different Asset than the candidate binding. Without this scan,
    # the wire-then-bind temporal ordering (operator adds a wire
    # before binding the role) and the unbind-rebind ordering
    # (operator unbinds a role while wires still reference its
    # port, then rebinds to a different Asset) would silently
    # produce role-table-vs-wire-graph divergence. The add_plan_wire
    # decider already enforces the bind-then-wire ordering; this
    # branch closes the bind ordering symmetrically. Mirrors the
    # add_plan_wire role-endpoint check exactly: OUTPUT required_ports
    # constrain wire SOURCE endpoints, INPUT required_ports constrain
    # wire TARGET endpoints.
    for required in matching_role.required_ports:
        if required.direction is PortDirection.OUTPUT:
            for wire in state.wires:
                if (
                    wire.source_port_name == required.port_name
                    and wire.source_asset_id != command.asset_id
                ):
                    raise PlanWireRoleEndpointMismatchError(
                        state.id,
                        wire,
                        command.role_name,
                        "source",
                        command.asset_id,
                        wire.source_asset_id,
                    )
        if required.direction is PortDirection.INPUT:
            for wire in state.wires:
                if (
                    wire.target_port_name == required.port_name
                    and wire.target_asset_id != command.asset_id
                ):
                    raise PlanWireRoleEndpointMismatchError(
                        state.id,
                        wire,
                        command.role_name,
                        "target",
                        command.asset_id,
                        wire.target_asset_id,
                    )

    return [
        PlanRoleBound(
            plan_id=state.id,
            role_name=command.role_name.value,
            asset_id=command.asset_id,
            occurred_at=now,
        )
    ]
