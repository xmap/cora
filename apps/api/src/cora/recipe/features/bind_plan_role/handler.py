"""Application handler for the `bind_plan_role` slice.

Custom (non-factory) update-style handler: loads Plan + Method +
Asset + (for the 3D role_kind path) RoleLookup +
FamilyLookup batch before reaching the pure decider, so the
decider stays I/O-free.

NOT idempotency-wrapped: bind is strict-not-idempotent at the
decider (`PlanRoleAlreadyBoundError`).

## Edge-loaded RoleLookup + FamilyLookup batch (Layer 3 3D)

When the matching RoleRequirement (looked up by role_name in
method.required_roles) carries `role_kind` rather than `family_id`,
the handler additionally:
  - resolves `role_kind` via `Kernel.role_lookup.lookup` ->
    role_lookup_result on the context (decider walks
    required_affordances for the superset check)
  - loads a `FamilyLookupResult` for each family_id in
    `asset.family_ids` via `Kernel.family_lookup.lookup` ->
    `family_lookups` dict on the context (decider walks for the
    ANY-single-family disjunction per Lock 17)
  - if the candidate Asset carries `fixture_id`, loads the
    Fixture (via `load_fixture`) and then the referenced Assembly
    via `Kernel.assembly_lookup.lookup` ->
    `assembly_lookup_result` on the context (decider ORs-in
    `role_kind in assembly.presents_as` on the Family disjunction
    so a composed Assembly like MCTOptics can satisfy the Role
    when no individual Family declares it)

Slice-1 family_id-only RoleRequirements skip all extra loads:
the context's optional fields default to None / empty dict and
the decider takes the existing family_id-equality branch.
"""

import asyncio
from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.asset import AssetNotFoundError
from cora.equipment.aggregates.asset.read import load_asset
from cora.equipment.aggregates.fixture.read import load_fixture
from cora.equipment.aggregates.role import RoleNotFoundError
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import AssemblyLookupResult, Deny, FamilyLookupResult
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.recipe.aggregates.method import MethodNotFoundError, RoleRequirement
from cora.recipe.aggregates.method.read import load_method
from cora.recipe.aggregates.plan import (
    PlanEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.recipe.errors import UnauthorizedError
from cora.recipe.features.bind_plan_role.command import BindPlanRole
from cora.recipe.features.bind_plan_role.context import BindPlanRoleContext
from cora.recipe.features.bind_plan_role.decider import decide

_STREAM_TYPE = "Plan"
_COMMAND_NAME = "BindPlanRole"
_LOG_PREFIX = "bind_plan_role"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every bind_plan_role handler implements."""

    async def __call__(
        self,
        command: BindPlanRole,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a bind_plan_role handler closed over the shared deps."""

    async def handler(
        command: BindPlanRole,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            f"{_LOG_PREFIX}.start",
            command_name=_COMMAND_NAME,
            plan_id=str(command.plan_id),
            role_name=command.role_name.value,
            asset_id=str(command.asset_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                f"{_LOG_PREFIX}.denied",
                command_name=_COMMAND_NAME,
                plan_id=str(command.plan_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.plan_id,
        )
        history: list[PlanEvent] = [from_stored(s) for s in stored]
        state = fold(history)

        # Cross-aggregate loads: Method (via Plan.state.method_id) and
        # the candidate Asset. Both surface their respective NotFound
        # errors when the streams are empty.
        method = None
        if state is not None and state.method_id is not None:
            method = await load_method(deps.event_store, state.method_id)
            if method is None:
                raise MethodNotFoundError(state.method_id)

        asset = await load_asset(deps.event_store, command.asset_id)
        if asset is None:
            raise AssetNotFoundError(command.asset_id)

        # Layer 3 sub-slice 3D: when the matching RoleRequirement
        # carries role_kind, edge-load the Role + a FamilyLookup
        # batch over asset.family_ids so the decider has everything
        # it needs to evaluate the ANY-single-family disjunction.
        # Skip the extra loads when matching_role is family_id-only
        # (slice-1 path) or when there is no matching role
        # (PlanRoleNameNotDeclaredError will surface in the decider).
        matching_role: RoleRequirement | None = None
        if method is not None:
            for role in method.required_roles:
                if role.role_name == command.role_name:
                    matching_role = role
                    break

        role_lookup_result = None
        family_lookups: dict[UUID, FamilyLookupResult] = {}
        assembly_lookup_result: AssemblyLookupResult | None = None
        if matching_role is not None and matching_role.role_kind is not None:
            role_lookup_result = await deps.role_lookup.lookup(matching_role.role_kind)
            if role_lookup_result is None:
                # Mid-flight Role-projection miss: surface
                # RoleNotFoundError at the handler edge so the
                # operator sees a 404 with the offending role_kind
                # rather than a satisfaction-side mis-bind.
                raise RoleNotFoundError(matching_role.role_kind)
            # Parallel batch lookup of every family on the Asset.
            family_ids = list(asset.family_ids)
            results = await asyncio.gather(*(deps.family_lookup.lookup(fid) for fid in family_ids))
            family_lookups = {
                fid: row for fid, row in zip(family_ids, results, strict=True) if row is not None
            }
            # Assembly satisfaction branch: when the Asset carries a
            # fixture_id, load the Fixture (one event-store hop) and
            # then the referenced Assembly's projection row. The
            # decider ORs-in role_kind membership in
            # assembly.presents_as on top of the Family disjunction.
            # Missed Fixture / Assembly silently fall through to the
            # Family-only path; the decider raises
            # PlanRoleAssetCannotPresentError if no path
            # satisfies.
            if asset.fixture_id is not None:
                fixture = await load_fixture(deps.event_store, asset.fixture_id)
                if fixture is not None:
                    assembly_lookup_result = await deps.assembly_lookup.lookup(fixture.assembly_id)

        context = BindPlanRoleContext(
            method=method,
            asset=asset,
            role_lookup_result=role_lookup_result,
            family_lookups=family_lookups,
            assembly_lookup_result=assembly_lookup_result,
        )

        domain_events = decide(
            state=state,
            command=command,
            context=context,
            now=now,
        )

        new_events = [
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=event.occurred_at,
                event_id=deps.id_generator.new_id(),
                command_name=_COMMAND_NAME,
                correlation_id=correlation_id,
                causation_id=causation_id,
                principal_id=principal_id,
            )
            for event in domain_events
        ]
        await deps.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=command.plan_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            f"{_LOG_PREFIX}.success",
            command_name=_COMMAND_NAME,
            plan_id=str(command.plan_id),
            role_name=command.role_name.value,
            asset_id=str(command.asset_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
