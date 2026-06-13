"""HTTP route for the `decommission_enclosure` slice.

Action endpoint at `POST /enclosures/{enclosure_id}/decommission`.
JSON body with a required free-text `reason` field; 204 No Content on
success. Mirrors the Facility `decommission_facility` precedent
(lifecycle-state transitions sit under the resource via verb, not as
a DELETE, so the audit gesture is distinguishable from a
resource-delete semantic).

The `reason` body field is required and flows through to the emitted
`EnclosureDecommissioned` event payload so operator context survives
on the immutable event log. Pydantic length bounds match the
`EnclosureReason` value object (1-500 chars after trimming);
whitespace-only payloads pass the schema gate and are rejected at
the decider via `InvalidEnclosureReasonError` (HTTP 400).

`permit_status` is preserved as audit trail across this terminal
transition: the decommission slice mutates `lifecycle` only and the
last-observed `permit_status` rides forward on the aggregate fold
unchanged.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.enclosure.aggregates._value_types import EnclosureId
from cora.enclosure.features.decommission_enclosure.command import DecommissionEnclosure
from cora.enclosure.features.decommission_enclosure.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH


class DecommissionEnclosureRequest(BaseModel):
    """Body for `POST /enclosures/{enclosure_id}/decommission`.

    `reason` is operator-supplied free text (audit-log breadcrumb)
    explaining why the enclosure is being decommissioned. Examples:
    "hutch retired", "interlock chain replaced; re-registering",
    "duplicate of enclosure <id>".
    """

    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Operator-supplied reason for the decommission transition "
            "(audit-log breadcrumb). Flows onto the "
            "EnclosureDecommissioned event payload."
        ),
    )

    model_config = {"extra": "forbid"}


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.enclosure.decommission_enclosure
    return handler


router = APIRouter(tags=["enclosure"])


@router.post(
    "/enclosures/{enclosure_id}/decommission",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated (for example whitespace-only "
                "reason rejected by the EnclosureReason value object "
                "past the Pydantic length bounds)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No enclosure exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Enclosure is already Decommissioned "
                "(decommission_enclosure is strict-not-idempotent; "
                "Decommissioned is terminal). The address tuple "
                "(containing_asset_id, name) is freed for "
                "re-registration once the projection arm advances."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (missing reason, "
                "empty reason, or reason exceeds 500 chars), OR the "
                "path enclosure_id is not a well-formed UUID."
            ),
        },
    },
    summary="Decommission an Enclosure (terminal: Active -> Decommissioned)",
)
async def post_enclosures_decommission(
    enclosure_id: Annotated[UUID, Path(description="Target enclosure's id.")],
    body: DecommissionEnclosureRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        DecommissionEnclosure(
            enclosure_id=EnclosureId(enclosure_id),
            reason=body.reason,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
