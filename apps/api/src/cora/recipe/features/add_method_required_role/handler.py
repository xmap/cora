"""Application handler for the `add_method_required_role` slice.

Update-style handler. The canonical body lives in
`make_method_update_handler` (load + authorize + fold + decide +
append, with structured logging). 3D adds a handler-side RoleLookup
precondition wrapping the factory-bound inner handler.

Not idempotency-wrapped: required-role mutation is strict-not-
idempotent at the decider (a second add hits
`MethodRoleNameAlreadyDeclaredError`); apply Idempotency-Key
support only when cached-success-on-retry semantics are needed.

## Handler-side RoleLookup precondition (Layer 3 sub-slice 3D)

Per [[project-role-aggregate-design]] 3D critique #1: when the
requirement carries `role_kind`, fail-fast resolve it via
`Kernel.role_lookup.lookup` at the handler edge BEFORE invoking
the factory-bound inner handler. None -> RoleNotFoundError (404
at HTTP). This keeps the decider signature at 3 kwargs (state,
command, now) so `make_update_handler`'s factory contract stays
intact; requirements carrying family_id (slice-1 path) skip the
precondition entirely.
"""

from typing import Any, Protocol
from uuid import UUID

from cora.equipment.aggregates.role import RoleNotFoundError
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.recipe._method_update_handler import make_method_update_handler
from cora.recipe.features.add_method_required_role.command import AddMethodRequiredRole
from cora.recipe.features.add_method_required_role.decider import decide


class Handler(Protocol):
    """Callable interface every add_method_required_role handler implements."""

    async def __call__(
        self,
        command: AddMethodRequiredRole,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def _extra_log_fields(command: AddMethodRequiredRole) -> dict[str, Any]:
    role_kind = command.requirement.role_kind
    family_id = command.requirement.family_id
    return {
        "role_name": command.requirement.role_name.value,
        "role_kind": str(role_kind) if role_kind is not None else None,
        "family_id": str(family_id) if family_id is not None else None,
        "required_ports_count": len(command.requirement.required_ports),
        "optional": command.requirement.optional,
    }


def bind(deps: Kernel) -> Handler:
    """Build an add_method_required_role handler closed over the shared deps.

    Wraps the factory-bound inner handler with a RoleLookup
    precondition: when the requirement carries role_kind, the
    existence check fires before any Method-stream load. Slice-1
    family_id-only requirements skip the precondition.
    """
    inner = make_method_update_handler(
        deps,
        command_name="AddMethodRequiredRole",
        log_prefix="add_method_required_role",
        decide_fn=decide,
        extra_log_fields=_extra_log_fields,
    )

    async def handler(
        command: AddMethodRequiredRole,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        role_kind = command.requirement.role_kind
        if role_kind is not None:
            lookup_result = await deps.role_lookup.lookup(role_kind)
            if lookup_result is None:
                raise RoleNotFoundError(role_kind)
        await inner(
            command,
            principal_id=principal_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            surface_id=surface_id,
        )

    return handler
