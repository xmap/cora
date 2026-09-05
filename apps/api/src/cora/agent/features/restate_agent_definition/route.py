"""HTTP route for the `restate_agent_definition` slice.

Action endpoint at `POST /agents/{agent_id}/restate-definition`. Body
carries an optional `name`, an optional `brain`, and a required `reason`.

Not PUT semantics, unlike the target-plan sibling: an omitted field means
UNCHANGED, not cleared. Neither a name nor a brain has a meaningful empty
value, so a clear would have nothing to mean, and the endpoint refuses a body
that supplies neither rather than accepting a no-op governance write.

204 No Content on success (including the idempotent no-op case, where every
supplied field already holds the value asked for).
"""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from cora.agent._brain_wire import brain_from_body
from cora.agent.aggregates.agent import (
    AGENT_NAME_MAX_LENGTH,
    BRAIN_RULE_MAX_LENGTH,
)
from cora.agent.features.restate_agent_definition.command import RestateAgentDefinition
from cora.agent.features.restate_agent_definition.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH


class RestatedModelRefRequest(BaseModel):
    """Sub-body for the typed ModelRef VO."""

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(..., min_length=1, max_length=100)
    model: str = Field(..., min_length=1, max_length=200)
    snapshot_pin: str | None = Field(default=None, max_length=100)


class RestatedBrainRequest(BaseModel):
    """Sub-body for the typed BrainRef VO, discriminated by `kind`."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["LanguageModel", "Rule"] = Field(
        ..., description="`LanguageModel` carries model_ref; `Rule` carries rule."
    )
    model_ref: RestatedModelRefRequest | None = Field(default=None)
    rule: str | None = Field(default=None, min_length=1, max_length=BRAIN_RULE_MAX_LENGTH)


class RestateAgentDefinitionRequest(BaseModel):
    """Body for `POST /agents/{agent_id}/restate-definition`."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Why this restatement is being appended. Required: writing to an "
            "append-only governance record is an act someone chooses, and the "
            "record should say why they chose it."
        ),
    )
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=AGENT_NAME_MAX_LENGTH,
        description="New display name. Omit to leave the name unchanged.",
    )
    brain: RestatedBrainRequest | None = Field(
        default=None,
        description="What this Agent thinks with. Omit to leave the brain unchanged.",
    )

    @model_validator(mode="after")
    def _restates_something(self) -> "RestateAgentDefinitionRequest":
        if self.name is None and self.brain is None:
            msg = "supply a `name`, a `brain`, or both"
            raise ValueError(msg)
        return self


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.agent.restate_agent_definition
    return handler


router = APIRouter(tags=["agent"])


@router.post(
    "/agents/{agent_id}/restate-definition",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated (whitespace-only name or reason, or a "
                "brain whose payload disagrees with its kind)."
            ),
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
            "description": (
                "Request body or path parameter failed schema validation, "
                "including a body that restates neither a name nor a brain."
            ),
        },
    },
    summary="Restate an existing Agent's name and/or brain (omitted fields stay unchanged)",
)
async def post_agents_restate_definition(
    agent_id: Annotated[UUID, Path(description="Target agent's id.")],
    body: RestateAgentDefinitionRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        RestateAgentDefinition(
            agent_id=agent_id,
            reason=body.reason,
            name=body.name,
            brain=brain_from_body(body.brain),
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
