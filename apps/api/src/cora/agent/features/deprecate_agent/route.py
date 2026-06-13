"""HTTP route for the `deprecate_agent` slice.

Action endpoint at `POST /agents/{agent_id}/deprecate`. Body
optionally carries `reason` (1-500 chars after trim). 204 No
Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.agent.features.deprecate_agent.command import DeprecateAgent
from cora.agent.features.deprecate_agent.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH


class DeprecateAgentRequest(BaseModel):
    """Body for `POST /agents/{agent_id}/deprecate`."""

    reason: str | None = Field(
        default=None,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Optional operator-supplied deprecation reason (1-500 chars after "
            "trim). Pass null to omit."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.agent.deprecate_agent
    return handler


router = APIRouter(tags=["agent"])


@router.post(
    "/agents/{agent_id}/deprecate",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Reason is empty / whitespace-only / over-cap after trim.",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No agent exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "Agent is already Deprecated (strict-not-idempotent).",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Request body or path parameter failed schema validation.",
        },
    },
    summary="Deprecate an Agent (Defined | Versioned -> Deprecated; terminal)",
)
async def post_agents_deprecate(
    agent_id: Annotated[UUID, Path(description="Target agent's id.")],
    body: DeprecateAgentRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        DeprecateAgent(agent_id=agent_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
