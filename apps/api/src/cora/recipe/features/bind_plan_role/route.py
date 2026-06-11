"""HTTP route for the `bind_plan_role` slice.

Action endpoint at `POST /plans/{plan_id}/bind-role`. Body carries
the `role_name` (a string scoped to the Plan's Method) and the
`asset_id` filling the role. 201 Created on success.
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
from cora.recipe.aggregates.method import ROLE_NAME_MAX_LENGTH, RoleName
from cora.recipe.features.bind_plan_role.command import BindPlanRole
from cora.recipe.features.bind_plan_role.handler import Handler


class BindPlanRoleRequest(BaseModel):
    """Body for `POST /plans/{plan_id}/bind-role`."""

    role_name: str = Field(
        ...,
        min_length=1,
        max_length=ROLE_NAME_MAX_LENGTH,
        description=(
            "Method-local role label matching a RoleRequirement on "
            "Method.required_roles. Strict-not-idempotent within the "
            "Plan: a duplicate binding returns 409."
        ),
    )
    asset_id: UUID = Field(
        ...,
        description=(
            "Asset filling the role. Must be in Plan.asset_ids; must "
            "carry the role's required Family; must expose the role's "
            "required_ports."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.recipe.bind_plan_role
    return handler


router = APIRouter(tags=["recipe"])


@router.post(
    "/plans/{plan_id}/bind-role",
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Role name VO validation failed (empty / whitespace-only or too-long string)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize policy denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": (
                "No plan, method, or asset exists with the given id, "
                "OR the matching RoleRequirement's role_kind does not "
                "resolve to a registered Role (Layer 3 3D edge-load)."
            ),
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Plan cannot bind the role under current conditions: "
                "Plan is Versioned/Deprecated, role_name already "
                "bound, role_name not declared on the bound Method, "
                "asset_id not in Plan.asset_ids, Asset missing the "
                "role's required Family (family_id path), OR for the "
                "3D role_kind path: no Family on the Asset advertises "
                "the Role with covering affordances "
                "(PlanRoleAssetCannotPresentError), or a Family "
                "id on the Asset does not resolve via FamilyLookup "
                "(PlanRoleFamilyNotResolvableError), OR Asset missing "
                "one or more of the role's required port triples."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": ("Path parameter or request body failed schema validation."),
        },
    },
    summary="Bind a Method.required_role to a specific Asset on an existing Plan",
)
async def post_plans_bind_role(
    plan_id: Annotated[UUID, Path(description="Target plan's id.")],
    body: BindPlanRoleRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        BindPlanRole(
            plan_id=plan_id,
            role_name=RoleName(body.role_name),
            asset_id=body.asset_id,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
