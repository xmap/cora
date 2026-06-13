"""HTTP route for the `abort_credential_rotation` slice.

Action endpoint at
`POST /federation/credentials/{credential_id}/rotation/abort`.
Optional `reason` body field flows through to the emitted
`CredentialRotationAborted` event payload so operator context
survives on the immutable event log. 204 No Content on success.

The `aborted_by` command field is supplied verbatim by
the route from the request envelope's `principal_id` (same actor
the handler also stamps onto the emitted event's
`rotation_aborted_by` denorm).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.federation.features.abort_credential_rotation.command import (
    AbortCredentialRotation,
)
from cora.federation.features.abort_credential_rotation.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH


class AbortCredentialRotationRequest(BaseModel):
    """Body for `POST /federation/credentials/{credential_id}/rotation/abort`.

    `reason` is operator-supplied free text (audit-log breadcrumb)
    explaining why the rotation is being aborted. Examples: "peer
    refused new material", "SecretStore generation failed mid-flight",
    "operator changed their mind".
    """

    reason: str | None = Field(
        default=None,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Optional operator-supplied reason for aborting the rotation (audit-log breadcrumb)."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.federation.abort_credential_rotation
    return handler


router = APIRouter(tags=["federation"])


@router.post(
    "/federation/credentials/{credential_id}/rotation/abort",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No credential exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Credential is not in `Rotating` status "
                "(abort_credential_rotation requires Rotating; "
                "Active / Revoked credentials are rejected)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (reason exceeds 500 chars) "
                "or path parameter is not a UUID."
            ),
        },
    },
    summary="Abort an in-flight credential rotation (Rotating -> Active)",
)
async def post_credentials_rotation_abort(
    credential_id: Annotated[UUID, Path(description="Target credential's id.")],
    body: AbortCredentialRotationRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        AbortCredentialRotation(
            credential_id=credential_id,
            aborted_by=principal_id,
            reason=body.reason,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
