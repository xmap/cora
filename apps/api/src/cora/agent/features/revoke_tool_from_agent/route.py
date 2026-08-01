"""HTTP route for the `revoke_tool_from_agent` slice.

Action endpoint at `POST /agents/{agent_id}/tools/revoke`. Body
carries REQUIRED `tool_name`. 204 No Content on success (including
the idempotent revoke-of-non-granted case).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.agent.aggregates.agent import AGENT_TOOL_NAME_MAX_LENGTH
from cora.agent.features.revoke_tool_from_agent.command import RevokeToolFromAgent
from cora.agent.features.revoke_tool_from_agent.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH


class RevokeToolFromAgentRequest(BaseModel):
    """Body for `POST /agents/{agent_id}/tools/revoke`."""

    tool_name: str = Field(
        min_length=1,
        max_length=AGENT_TOOL_NAME_MAX_LENGTH,
        description="MCP tool name to remove from the Agent's allowlist (1-100 chars).",
    )
    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Operator-supplied reason for the revocation (audit-log "
            "breadcrumb; no PII). Taking a tool away narrows what an "
            "autonomous Agent may do mid-campaign, so the record "
            "should say why."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.agent.revoke_tool_from_agent
    return handler


router = APIRouter(tags=["agent"])


@router.post(
    "/agents/{agent_id}/tools/revoke",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Tool name is empty / whitespace-only / over-cap after trim.",
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
    summary="Revoke one MCP tool from an Agent (idempotent revoke-of-non-granted emits no event)",
)
async def post_agents_revoke_tool(
    agent_id: Annotated[UUID, Path(description="Target agent's id.")],
    body: RevokeToolFromAgentRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        RevokeToolFromAgent(agent_id=agent_id, tool_name=body.tool_name, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
