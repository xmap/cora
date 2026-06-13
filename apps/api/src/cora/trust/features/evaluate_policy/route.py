"""HTTP route for the `evaluate_policy` query slice.

`GET /policies/{policy_id}/evaluate` with three required query
parameters describing what's being evaluated against the policy:
`evaluated_principal_id`, `evaluated_command_name`,
`evaluated_conduit_id`. (The `evaluated_` prefix disambiguates
from the Subject BC; in 2026-05 these were renamed from
`subject_*` to remove the BC-name overload.)

Returns 200 with `{"decision": "Allow"|"Deny", "reason": str|null}`.
Both Allow and Deny are normal results — only a missing Policy
(handler returns None) maps to 404 via `HTTPException`.

Verbose `subject_*` query-param names mirror the EvaluatePolicy
dataclass fields for unambiguous separation from the caller's
`principal_id` (which arrives via `get_principal_id` Depends).
"""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from pydantic import BaseModel

from cora.infrastructure.ports import Allow
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.trust.features.evaluate_policy.handler import Handler
from cora.trust.features.evaluate_policy.query import EvaluatePolicy


class EvaluatePolicyResponse(BaseModel):
    """Read-side DTO at the API boundary.

    `reason` is populated only when `decision == "Deny"`. The Allow
    branch leaves `reason` null (omitted on the wire when
    `model_dump(exclude_none=True)` is used; FastAPI default keeps
    the field present as null which is also fine).
    """

    decision: Literal["Allow", "Deny"]
    reason: str | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.trust.evaluate_policy
    return handler


router = APIRouter(tags=["trust"])


@router.get(
    "/policies/{policy_id}/evaluate",
    status_code=status.HTTP_200_OK,
    response_model=EvaluatePolicyResponse,
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
    summary="Evaluate a Policy against a (principal, command, conduit, surface) tuple",
)
async def get_policies_evaluate(
    policy_id: Annotated[UUID, Path(description="Target policy's id.")],
    evaluated_principal_id: Annotated[
        UUID,
        Query(description="Principal whose authorization is being checked."),
    ],
    evaluated_command_name: Annotated[
        str,
        Query(
            min_length=1,
            max_length=200,
            description="Command name being evaluated (for example 'RegisterActor').",
        ),
    ],
    evaluated_conduit_id: Annotated[
        UUID,
        Query(description="Conduit through which the command would be issued."),
    ],
    evaluated_surface_id: Annotated[
        UUID,
        Query(description="Arrival Surface the command would enter through."),
    ],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> EvaluatePolicyResponse:
    result = await handler(
        EvaluatePolicy(
            policy_id=policy_id,
            evaluated_principal_id=evaluated_principal_id,
            evaluated_command_name=evaluated_command_name,
            evaluated_conduit_id=evaluated_conduit_id,
            evaluated_surface_id=evaluated_surface_id,
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
    if isinstance(result, Allow):
        return EvaluatePolicyResponse(decision="Allow")
    # Narrowed to Deny via the Allow|Deny union exhaustiveness.
    return EvaluatePolicyResponse(decision="Deny", reason=result.reason)
