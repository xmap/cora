"""HTTP route for the `revoke_permit` slice.

Action endpoint at `POST /federation/permits/{permit_id}/revoke`.
Optional `reason` body field flows through to the emitted
`PermitRevoked` event payload so operator context survives on the
immutable event log. 204 No Content on success. The supply BC's
lifecycle-terminal `POST /supplies/{supply_id}/deregister` is the
precedent: lifecycle-state transitions sit under the resource via
verb, not as a DELETE, so the audit gesture (revoke) is
distinguishable from a resource-delete semantic.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.federation.features.revoke_permit.command import RevokePermit
from cora.federation.features.revoke_permit.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH


class RevokePermitRequest(BaseModel):
    """Body for `POST /federation/permits/{permit_id}/revoke`.

    `reason` is operator-supplied free text (audit-log breadcrumb)
    explaining why the Permit is being revoked. Examples: "peer
    facility decommissioned", "credential compromise", "policy
    change ended sharing agreement".
    """

    reason: str | None = Field(
        default=None,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Optional operator-supplied reason for revoking the permit (audit-log breadcrumb)."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.federation.revoke_permit
    return handler


router = APIRouter(tags=["federation"])


@router.post(
    "/federation/permits/{permit_id}/revoke",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No permit exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Permit is already Revoked (revoke_permit is strict-not-idempotent; "
                "Revoked is terminal)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": ("Request body failed schema validation (reason exceeds 500 chars)."),
        },
    },
    summary="Revoke a Permit (terminal: any non-Revoked -> Revoked)",
)
async def post_federation_permits_revoke(
    permit_id: Annotated[UUID, Path(description="Target permit's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
    body: Annotated[RevokePermitRequest | None, Body()] = None,
) -> None:
    reason = body.reason if body is not None else None
    await handler(
        RevokePermit(permit_id=permit_id, reason=reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
