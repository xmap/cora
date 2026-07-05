"""HTTP route for the `request_ratification` slice.

Endpoint at `POST /ratifications`. Caller supplies the `ratification_id`
(genesis collision raises 409 via central `_handle_already_exists`). The
requester is the envelope `principal_id`, threaded into the decider by the
handler, not a body field.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.trust.aggregates.ratification import CONSEQUENCE_CLASS_MAX_LENGTH
from cora.trust.features.request_ratification.command import RequestRatification
from cora.trust.features.request_ratification.handler import Handler


class RequestRatificationRequest(BaseModel):
    """Body for `POST /ratifications`."""

    ratification_id: UUID = Field(
        ...,
        description=(
            "Caller-supplied UUID. A subscriber may mint a deterministic uuid5 "
            "for replay-safe ingest; operator-direct may use uuid4."
        ),
    )
    target_action_id: UUID = Field(
        ...,
        description=(
            "Opaque id of the action being gated (e.g. the run id whose "
            "consequential command is held). Not existence-checked at the decider."
        ),
    )
    command_name: str = Field(..., description="Canonical name of the gated command.")
    consequence_class: str = Field(
        ...,
        min_length=1,
        max_length=CONSEQUENCE_CLASS_MAX_LENGTH,
        description="Declared class that triggered the requirement (bare-str label).",
    )


class RequestRatificationResponse(BaseModel):
    """Response body for `POST /ratifications`."""

    ratification_id: UUID


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.trust.request_ratification
    return handler


router = APIRouter(tags=["trust"])


@router.post(
    "/ratifications",
    status_code=status.HTTP_201_CREATED,
    response_model=RequestRatificationResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Domain invariant violated (e.g. empty consequence_class).",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "Ratification with this id already exists.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Request body failed schema validation.",
        },
    },
    summary="Request a second-principal co-signature for a consequential action",
)
async def post_ratifications(
    body: RequestRatificationRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> RequestRatificationResponse:
    ratification_id = await handler(
        RequestRatification(
            ratification_id=body.ratification_id,
            target_action_id=body.target_action_id,
            command_name=body.command_name,
            consequence_class=body.consequence_class,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return RequestRatificationResponse(ratification_id=ratification_id)
