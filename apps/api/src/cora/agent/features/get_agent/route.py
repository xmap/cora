"""HTTP route for the `get_agent` query slice.

`GET /agents/{agent_id}` returns 200 + AgentResponse on hit, 404
on miss. The handler returns `AgentView | None`; the route maps None
to 404 via HTTPException.

`defined_at` / `versioned_at` / `deprecated_at` are sourced from the
`proj_agent_summary` projection (Path C),
NOT from aggregate state (previously they lived on Agent state at
8f-a; the audit moved them to the projection so the Agent BC follows
the same pattern as Method/Plan/Practice/Family/Capability). Null
semantics under eventual consistency: read together with `status`.
A 200 with a populated `status` but null timestamp means projection
lag, never a missing transition. A 404 means the Agent aggregate
itself does not exist.

Suspended/Resumed timestamps + reason stay state-sourced (the
`suspension_reason` field is invariant-bearing — deciders read it).
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel

from cora.agent.aggregates.agent import AgentStatus
from cora.agent.features.get_agent.handler import AgentView, Handler
from cora.agent.features.get_agent.query import GetAgent
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.deprecation import DeprecationReason


class ModelRefResponse(BaseModel):
    """Sub-DTO for the typed ModelRef VO."""

    provider: str
    model: str
    snapshot_pin: str | None = None


class AgentResponse(BaseModel):
    """Read-side DTO at the API boundary.

    Carries primitives, not domain VOs. Decouples the wire format
    from the domain model so the two can evolve independently.

    `defined_at` / `versioned_at` / `deprecated_at` are projection-
    sourced lifecycle timestamps (Path C);
    see module docstring for null-semantics. `defined_at` is
    nullable (changed from required during lifecycle widening) because
    the projection can lag; once the projection has folded
    `AgentDefined`, `defined_at` is non-null on every response.
    """

    id: UUID
    kind: str
    name: str
    version: str
    model_ref: ModelRefResponse
    status: AgentStatus
    defined_at: datetime | None = None
    description: str | None = None
    canonical_uri: str | None = None
    prompt_template_id: UUID | None = None
    capabilities: list[str]
    versioned_at: datetime | None = None
    deprecated_at: datetime | None = None
    deprecation_reason: DeprecationReason | None = None


def _response_from_view(view: AgentView) -> AgentResponse:
    agent = view.agent
    timestamps = view.timestamps
    return AgentResponse(
        id=agent.id,
        kind=agent.kind.value,
        name=agent.name.value,
        version=agent.version.value,
        model_ref=ModelRefResponse(
            provider=agent.model_ref.provider,
            model=agent.model_ref.model,
            snapshot_pin=agent.model_ref.snapshot_pin,
        ),
        status=agent.status,
        defined_at=timestamps.created_at if timestamps is not None else None,
        description=agent.description.value if agent.description is not None else None,
        canonical_uri=agent.canonical_uri.value if agent.canonical_uri is not None else None,
        prompt_template_id=agent.prompt_template_id,
        capabilities=sorted(c.value for c in agent.capabilities),
        versioned_at=timestamps.versioned_at if timestamps is not None else None,
        deprecated_at=timestamps.deprecated_at if timestamps is not None else None,
        deprecation_reason=agent.deprecation_reason,
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.agent.get_agent
    return handler


router = APIRouter(tags=["agent"])


@router.get(
    "/agents/{agent_id}",
    status_code=status.HTTP_200_OK,
    response_model=AgentResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No agent exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Get an agent by id",
)
async def get_agents(
    agent_id: Annotated[UUID, Path(description="Target agent's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> AgentResponse:
    view = await handler(
        GetAgent(agent_id=agent_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    if view is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found",
        )
    return _response_from_view(view)
