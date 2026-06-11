"""HTTP route for `add_method_required_role`.

Action endpoint at `POST /methods/{method_id}/add-required-role`.
Body carries the `RoleRequirement` block (role_name + family_id +
required_ports + optional). 201 Created on success, mirroring the
Method BC's POST-style targeted-mutation convention; no DELETE verb
on the Method aggregate's mutation slices (the sibling mutation is
`remove_method_required_role` via POST).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.recipe._role_requirement_body import RoleRequirementBody
from cora.recipe.features.add_method_required_role.command import AddMethodRequiredRole
from cora.recipe.features.add_method_required_role.handler import Handler


class AddMethodRequiredRoleRequest(BaseModel):
    """Body for `POST /methods/{method_id}/add-required-role`."""

    requirement: RoleRequirementBody = Field(
        ...,
        description=(
            "The positional role slot to declare. Uniqueness keyed on "
            "`role_name` within the Method scope. The Method aggregate "
            "owns the role vocabulary only; Plan-side binding and "
            "port-coverage validation are enforced by the Plan "
            "aggregate (bind_plan_role + add_plan_wire)."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.recipe.add_method_required_role
    return handler


router = APIRouter(tags=["recipe"])


@router.post(
    "/methods/{method_id}/add-required-role",
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Role requirement VO validation failed: empty / "
                "whitespace-only role_name, empty / too-long port "
                "fields, or other shape-level VO constructor failure."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize policy denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": (
                "No Method exists with the given id, OR the supplied "
                "role_kind does not resolve to a registered Role "
                "(handler-side RoleLookup precondition; Layer 3 3D)."
            ),
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Method cannot accept the role under current "
                "conditions: the method is Versioned or Deprecated "
                "(MethodCannotMutateRequiredRolesError), OR a role "
                "with the same role_name already exists on the method "
                "(MethodRoleNameAlreadyDeclaredError), OR a concurrent "
                "write to the same method stream conflicted "
                "(optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Path parameter or request body failed schema "
                "validation (missing field, malformed UUID, length "
                "out of bounds at the wire layer)."
            ),
        },
    },
    summary="Declare a positional role slot on an existing Method",
)
async def post_methods_add_required_role(
    method_id: Annotated[UUID, Path(description="Target method's id.")],
    body: AddMethodRequiredRoleRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        AddMethodRequiredRole(
            method_id=method_id,
            requirement=body.requirement.to_domain(),
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
