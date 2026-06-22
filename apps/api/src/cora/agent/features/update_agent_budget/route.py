"""HTTP route for the `update_agent_budget` slice.

Action endpoint at `POST /agents/{agent_id}/budget`. Body
carries `monthly_usd_cap` and `daily_token_cap`, both
independently nullable. PUT-semantics: the supplied caps ARE
the post-update budget. Both None clears the budget.

204 No Content on success (including the idempotent no-op case).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.agent.features.update_agent_budget.command import UpdateAgentBudget
from cora.agent.features.update_agent_budget.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class UpdateAgentBudgetRequest(BaseModel):
    """Body for `POST /agents/{agent_id}/budget`."""

    monthly_usd_cap: float | None = Field(
        default=None,
        ge=0.0,
        description=(
            "Monthly USD cap. Pass null to clear this field. Setting both "
            "caps to null clears the entire budget."
        ),
    )
    daily_token_cap: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Daily token cap. Pass null to clear this field. Setting both "
            "caps to null clears the entire budget."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.agent.update_agent_budget
    return handler


router = APIRouter(tags=["agent"])


@router.post(
    "/agents/{agent_id}/budget",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Cap value invalid (negative).",
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
            "description": "Agent is `Deprecated` (only blocking source state).",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Request body or path parameter failed schema validation.",
        },
    },
    summary="Update an Agent's declarative budget caps (PUT semantics; both null clears)",
)
async def post_agents_update_budget(
    agent_id: Annotated[UUID, Path(description="Target agent's id.")],
    body: UpdateAgentBudgetRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        UpdateAgentBudget(
            agent_id=agent_id,
            monthly_usd_cap=body.monthly_usd_cap,
            daily_token_cap=body.daily_token_cap,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
