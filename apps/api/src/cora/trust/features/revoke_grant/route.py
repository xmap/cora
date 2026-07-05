"""HTTP route for the `revoke_grant` slice.

Action endpoint at `POST /policies/{policy_id}/revoke-grant`. Body carries the
`permitted_principal_id` grant to remove plus a required `reason`. 204 on success
(a transition, no content). Silently idempotent: revoking an already-absent
principal still returns 204.

The body's `permitted_principal_id` is the grant being revoked (it names the
Policy's `permitted_principal_ids` entry), distinct from the invoking principal
(supplied by `get_principal_id` and threaded as the handler's `principal_id`
kwarg, stamped on the event as `revoked_by`).
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
from cora.trust.features.revoke_grant.command import RevokePolicyGrant
from cora.trust.features.revoke_grant.handler import Handler


class RevokeGrantRequest(BaseModel):
    """Body for `POST /policies/{policy_id}/revoke-grant`.

    `permitted_principal_id` is the grant to remove from the Policy's allow-list.
    `reason` is operator-supplied free text (audit-log breadcrumb; also
    feeds the downstream mid-run compensation Decision). MUST NOT contain PII.
    """

    permitted_principal_id: UUID = Field(
        ...,
        description="Principal (UUID) whose grant is revoked from the policy.",
    )
    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description="Operator-supplied reason for the revocation (audit-log breadcrumb; no PII).",
    )


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
            "description": "Domain invariant violated (whitespace-only reason).",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No Policy exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Request body failed schema validation.",
        },
    },
    summary="Revoke one principal's grant from a Policy",
)
async def post_policies_revoke_grant(
    policy_id: Annotated[UUID, Path(description="Target Policy's id.")],
    body: RevokeGrantRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        RevokePolicyGrant(
            policy_id=policy_id,
            permitted_principal_id=body.permitted_principal_id,
            reason=body.reason,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
