"""HTTP route for the `list_permissions` query slice.

`GET /policies/{policy_id}/permissions` with `evaluated_principal_id`
and `evaluated_conduit_id` as query parameters. No body — matches the
GET convention of the other Trust BC list/query slices
(`evaluate_policy`, `list_policies`, etc.).

Returns 200 with `{"policy_id", "evaluated_principal_id",
"evaluated_conduit_id", "permitted_commands", "incomplete"}`.
Only a missing Policy maps to 404.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.trust.features.list_permissions.handler import Handler
from cora.trust.features.list_permissions.query import ListPermissions


class ListPermissionsResponse(BaseModel):
    """Read-side DTO at the API boundary.

    `incomplete` is always False at v1, required from day 1 per the
    design lock's anti-hook to forward-compat with future ABAC
    policies that may make enumeration lossy.
    """

    policy_id: UUID
    evaluated_principal_id: UUID
    evaluated_conduit_id: UUID
    surface_id: Annotated[
        UUID,
        Field(
            description=(
                "Arrival surface the listing is scoped to. The Policy matches its surface by "
                "strict equality, so it permits nothing on any other surface and "
                "`permitted_commands` must not be read as holding everywhere."
            ),
        ),
    ]
    permitted_commands: list[str]
    incomplete: bool = Field(
        description=("True if some permissions could not be enumerated (always False at v1)."),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.trust.list_permissions
    return handler


router = APIRouter(tags=["trust"])


@router.get(
    "/policies/{policy_id}/permissions",
    status_code=status.HTTP_200_OK,
    response_model=ListPermissionsResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No policy exists with the given id.",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the query.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path or query parameter failed schema validation.",
        },
    },
    summary="List a Policy's permitted commands for (principal, conduit)",
    description=(
        "Enumerates the commands a principal can execute against a Policy via a conduit. "
        "Returns the sorted set, the `surface_id` that set is scoped to, plus the "
        "`incomplete: bool` flag (always False at v1; future ABAC may flip it). The Policy "
        "matches its surface by strict equality, so the commands are permitted on that "
        "surface and on no other; read the two fields together. "
        "**Do NOT use the returned set to drive authorization decisions**: "
        "this is for UX / debugging only; only `Kernel.authorize` (the PEP) authorizes. "
        "On-behalf queries (evaluated_principal_id != caller) require a separate "
        "`ListPermissionsOfOthers` permission, denied by default."
    ),
)
async def get_policies_permissions(
    policy_id: Annotated[UUID, Path(description="Target policy's id.")],
    evaluated_principal_id: Annotated[
        UUID,
        Query(description="Principal whose permissions are being enumerated."),
    ],
    evaluated_conduit_id: Annotated[
        UUID,
        Query(description="Conduit through which the commands would be issued."),
    ],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> ListPermissionsResponse:
    result = await handler(
        ListPermissions(
            policy_id=policy_id,
            evaluated_principal_id=evaluated_principal_id,
            evaluated_conduit_id=evaluated_conduit_id,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy {policy_id} not found",
        )
    return ListPermissionsResponse(
        policy_id=result.policy_id,
        evaluated_principal_id=result.evaluated_principal_id,
        evaluated_conduit_id=result.evaluated_conduit_id,
        surface_id=result.surface_id,
        permitted_commands=result.permitted_commands,
        incomplete=result.incomplete,
    )
