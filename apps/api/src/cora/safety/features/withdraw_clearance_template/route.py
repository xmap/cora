"""HTTP route for the `withdraw_clearance_template` slice.

Action endpoint at `POST /clearance-templates/{template_id}/withdraw`. Body carries a
required free-text `reason`. No
body fields. 204 No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.safety.features.withdraw_clearance_template.command import (
    WithdrawClearanceTemplate,
)
from cora.safety.features.withdraw_clearance_template.handler import Handler
from cora.shared.text_bounds import REASON_MAX_LENGTH


class WithdrawClearanceTemplateRequest(BaseModel):
    """Body for `POST /clearance-templates/{template_id}/withdraw`."""

    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Why the template is being withdrawn. Free text: withdrawal "
            "causes are open-ended (superseded by a facility policy "
            "change, drafted in error, the hazard class no longer "
            "applies), unlike deprecation, where the reason decides "
            "whether prior data is trustworthy and the set is closed."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.safety.withdraw_clearance_template
    return handler


router = APIRouter(tags=["safety"])


@router.post(
    "/clearance-templates/{template_id}/withdraw",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No clearance template exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Clearance template is already Withdrawn "
                "(withdraw_clearance_template is strict-not-idempotent at the terminal)."
            ),
        },
    },
    summary="Withdraw a clearance template (any non-terminal -> Withdrawn; terminal)",
)
async def post_clearance_templates_withdraw(
    body: Annotated[WithdrawClearanceTemplateRequest, Body()],
    template_id: Annotated[UUID, Path(description="Target clearance template's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        WithdrawClearanceTemplate(template_id=template_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
