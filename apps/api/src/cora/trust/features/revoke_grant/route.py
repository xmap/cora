"""HTTP route for the `revoke_grant` slice.

Action endpoint at `POST /policies/{policy_id}/revoke-grant`. Required
JSON body: the `principal_id` grant to remove and a `reason`. 204 No
Content on success (including the silently-idempotent no-op when the
principal is already absent). Mirrors the lifecycle-terminal action
endpoints (`/supplies/{id}/deregister`,
`/federation/credentials/{id}/revoke`): a state-changing gesture sits
under the resource via verb, not as a DELETE, so the audit gesture
(revoke a grant) is distinguishable from a resource-delete semantic.

`reason` is required and bounded (1-`REASON_MAX_LENGTH`) at the boundary
so a malformed reason is a 422 before the handler runs; the decider
re-checks defensively for non-HTTP callers.
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
from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.trust.features.revoke_grant.command import RevokeGrant
from cora.trust.features.revoke_grant.handler import Handler


class RevokeGrantBody(BaseModel):
    """Required revoke-grant request body."""

    principal_id: Annotated[
        UUID,
        Field(description="The principal whose grant is removed from the policy."),
    ]
    reason: Annotated[
        str,
        Field(
            min_length=1,
            max_length=REASON_MAX_LENGTH,
            description=(
                "Operator-supplied reason for revoking the grant "
                "(audit-log breadcrumb). Flows onto the PolicyGrantRevoked "
                "event payload and the downstream compensation Decision."
            ),
        ),
    ]


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.trust.revoke_grant
    return handler


router = APIRouter(tags=["trust"])


@router.post(
    "/policies/{policy_id}/revoke-grant",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Reason failed the defensive decider bound (InvalidPolicyGrantRevokeReasonError)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No policy exists with the given id.",
        },
    },
    summary="Revoke one principal's grant from a Policy (silently idempotent)",
)
async def post_policies_revoke_grant(
    policy_id: Annotated[UUID, Path(description="Target policy's id.")],
    body: RevokeGrantBody,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        RevokeGrant(
            policy_id=policy_id,
            principal_id=body.principal_id,
            reason=body.reason,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
