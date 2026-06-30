"""HTTP route for the `set_agent_target_plan` slice.

Action endpoint at `POST /agents/{agent_id}/target-plan`. Body carries
`target_plan_id` (nullable). PUT-semantics: the supplied value IS the
post-set target; null clears it.

204 No Content on success (including the idempotent no-op case).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.agent.features.set_agent_target_plan.command import SetAgentTargetPlan
from cora.agent.features.set_agent_target_plan.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class SetAgentTargetPlanRequest(BaseModel):
    """Body for `POST /agents/{agent_id}/target-plan`."""

    target_plan_id: UUID | None = Field(
        default=None,
        description=(
            "The recipe Plan this autonomous agent starts for each ready "
            "Subject. Pass null to clear the target (the agent initiates "
            "nothing until a Plan is set again)."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.agent.set_agent_target_plan
    return handler


router = APIRouter(tags=["agent"])


@router.post(
    "/agents/{agent_id}/target-plan",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
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
            "description": "Agent is `Deprecated` (only blocking source state).",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Request body or path parameter failed schema validation.",
        },
    },
    summary="Set or clear an autonomous Agent's target Plan (PUT semantics; null clears)",
)
async def post_agents_set_target_plan(
    agent_id: Annotated[UUID, Path(description="Target agent's id.")],
    body: SetAgentTargetPlanRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        SetAgentTargetPlan(
            agent_id=agent_id,
            target_plan_id=body.target_plan_id,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
