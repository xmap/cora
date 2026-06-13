"""HTTP route for the `suspend_agent` slice.

Action endpoint at `POST /agents/{agent_id}/suspend`. Body
carries REQUIRED `reason` (1-500 chars after trim). 204 No
Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.agent.features.suspend_agent.command import SuspendAgent
from cora.agent.features.suspend_agent.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH


class SuspendAgentRequest(BaseModel):
    """Body for `POST /agents/{agent_id}/suspend`."""

    reason: str = Field(
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Operator-supplied suspension reason (1-500 chars after trim). "
            "REQUIRED: operator-pause is a high-information signal that the "
            "audit log should always carry context for."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.agent.suspend_agent
    return handler


router = APIRouter(tags=["agent"])


@router.post(
    "/agents/{agent_id}/suspend",
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
            "description": (
                "Agent is not in `Versioned` (strict-not-idempotent: cannot "
                "re-suspend a `Suspended` agent, cannot suspend a `Defined` "
                "or `Deprecated` agent)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Request body or path parameter failed schema validation.",
        },
    },
    summary="Suspend an Agent (Versioned -> Suspended; non-terminal)",
)
async def post_agents_suspend(
    agent_id: Annotated[UUID, Path(description="Target agent's id.")],
    body: SuspendAgentRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        SuspendAgent(agent_id=agent_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
