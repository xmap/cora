"""HTTP route for the `define_agent` slice.

`POST /agents` with body carrying kind / name / version / model_ref +
optional description / canonical_uri / prompt_template_id /
capabilities. Returns 201 + `{agent_id}` on success.
"""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from cora.agent._brain_wire import brain_from_body, model_ref_from_body
from cora.agent.aggregates.agent import (
    AGENT_CANONICAL_URI_MAX_LENGTH,
    AGENT_CAPABILITIES_MAX_COUNT,
    AGENT_CAPABILITY_MAX_LENGTH,
    AGENT_DESCRIPTION_MAX_LENGTH,
    AGENT_KIND_MAX_LENGTH,
    AGENT_NAME_MAX_LENGTH,
    AGENT_VERSION_MAX_LENGTH,
    BRAIN_RULE_MAX_LENGTH,
    MODEL_REF_MODEL_MAX_LENGTH,
    MODEL_REF_PROVIDER_MAX_LENGTH,
    MODEL_REF_SNAPSHOT_PIN_MAX_LENGTH,
)
from cora.agent.features.define_agent.command import DefineAgent
from cora.agent.features.define_agent.handler import IdempotentHandler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class ModelRefRequest(BaseModel):
    """Sub-body for the typed ModelRef VO."""

    provider: str = Field(
        ...,
        min_length=1,
        max_length=MODEL_REF_PROVIDER_MAX_LENGTH,
        description="LLM provider name (`anthropic`, `openai`, `google`, etc.).",
    )
    model: str = Field(
        ...,
        min_length=1,
        max_length=MODEL_REF_MODEL_MAX_LENGTH,
        description="Provider-specific model identifier (`claude-sonnet-4-6`, etc.).",
    )
    snapshot_pin: str | None = Field(
        default=None,
        max_length=MODEL_REF_SNAPSHOT_PIN_MAX_LENGTH,
        description=(
            "Optional provider-specific snapshot identifier (Anthropic snapshot "
            "string, OpenAI fingerprint, etc.) for reproducibility. Pass null "
            "to leave unpinned."
        ),
    )


class BrainRequest(BaseModel):
    """Sub-body for the typed BrainRef VO: what this Agent thinks with.

    Discriminated by `kind`; exactly the payload belonging to that kind may
    be set. A flat body carrying every possible field could disagree with
    itself, which is the shape `BrainRef` exists to make unrepresentable.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["LanguageModel", "Rule"] = Field(
        ...,
        description=(
            "Which kind of brain. `LanguageModel` carries `model_ref` and is "
            "gated against the approved LanguageModel catalog. `Rule` carries "
            "`rule` and needs no approval: it runs no external model and "
            "spends nothing."
        ),
    )
    model_ref: ModelRefRequest | None = Field(
        default=None,
        description="Required when `kind` is `LanguageModel`, forbidden otherwise.",
    )
    rule: str | None = Field(
        default=None,
        min_length=1,
        max_length=BRAIN_RULE_MAX_LENGTH,
        description=(
            "Required when `kind` is `Rule`, forbidden otherwise. Names and "
            "versions the decision rule (convention: `ExperimentCoordinator:v1`)."
        ),
    )


class DefineAgentRequest(BaseModel):
    """Body for `POST /agents`."""

    kind: str = Field(
        ...,
        min_length=1,
        max_length=AGENT_KIND_MAX_LENGTH,
        description=(
            "Free-form agent kind discriminator (bare-str at MVP per Supply.kind "
            "precedent). Day-1 example: `RunDebriefer`."
        ),
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=AGENT_NAME_MAX_LENGTH,
        description="Human-readable display name.",
    )
    version: str = Field(
        ...,
        min_length=1,
        max_length=AGENT_VERSION_MAX_LENGTH,
        description="Semver-like version identifier (`v1`, `1.0.0`, etc.).",
    )
    model_ref: ModelRefRequest | None = Field(
        default=None,
        description=(
            "Model identity (provider + model + optional snapshot pin). The "
            "legacy way to name a LanguageModel brain, kept for callers that "
            "predate `brain`. Supply exactly one of `model_ref` or `brain`."
        ),
    )
    brain: BrainRequest | None = Field(
        default=None,
        description=(
            "What this Agent thinks with. Supply exactly one of `model_ref` or "
            "`brain`; `brain` is the only way to define an Agent whose brain is "
            "not a language model."
        ),
    )
    description: str | None = Field(
        default=None,
        min_length=1,
        max_length=AGENT_DESCRIPTION_MAX_LENGTH,
        description="Optional free-form description.",
    )
    canonical_uri: str | None = Field(
        default=None,
        min_length=1,
        max_length=AGENT_CANONICAL_URI_MAX_LENGTH,
        description=(
            "Optional canonical https URI for A2A forward-compat. Must start "
            "with `https://` and contain no fragment."
        ),
    )
    prompt_template_id: UUID | None = Field(
        default=None,
        description=(
            "Optional UUID into the Python module registry at "
            "`cora.agent.prompts`. Required by the RunDebriefer subscriber; "
            "may be null until the registry ships its first template."
        ),
    )
    capabilities: list[str] = Field(
        default_factory=list,
        max_length=AGENT_CAPABILITIES_MAX_COUNT,
        description=(
            f"Optional capability claims. Each entry 1-{AGENT_CAPABILITY_MAX_LENGTH} "
            "chars after trim. Empty list IS allowed."
        ),
    )

    @model_validator(mode="after")
    def _exactly_one_brain_declaration(self) -> "DefineAgentRequest":
        """Reject a body that names both a brain and a legacy model_ref.

        Not "brain wins": two declarations that disagree mean the caller
        believes something the record would not say, and picking one silently
        makes the wire lie about what was asked for. Rejecting is cheap, and a
        caller that meant a LanguageModel brain can say so either way.
        """
        if (self.model_ref is None) == (self.brain is None):
            msg = "supply exactly one of `model_ref` or `brain`"
            raise ValueError(msg)
        return self


class DefineAgentResponse(BaseModel):
    """Response body for `POST /agents`."""

    agent_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.agent.define_agent
    return handler


router = APIRouter(tags=["agent"])


@router.post(
    "/agents",
    status_code=status.HTTP_201_CREATED,
    response_model=DefineAgentResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated (whitespace-only kind / name / version, "
                "over-cap capabilities, malformed canonical_uri, or invalid ModelRef)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Defensive guard: the target Agent or co-written Actor stream "
                "already has events. Essentially impossible in production with "
                "UUIDv7 ids."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (missing field, length "
                "out of bounds, invalid UUID), OR Idempotency-Key was reused "
                "with a different request body."
            ),
        },
    },
    summary="Define a new Agent (cross-BC atomic; co-registers an Actor with kind=agent)",
)
async def post_agents(
    body: DefineAgentRequest,
    handler: Annotated[IdempotentHandler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> DefineAgentResponse:
    agent_id = await handler(
        DefineAgent(
            kind=body.kind,
            name=body.name,
            version=body.version,
            # Recorded as the caller named it. A legacy `model_ref` body is
            # NOT translated to a brain here: the decider keeps the event a
            # faithful record of what was asked, and the evolver derives the
            # effective brain when folding.
            model_ref=model_ref_from_body(body.model_ref),
            brain=brain_from_body(body.brain),
            description=body.description,
            canonical_uri=body.canonical_uri,
            prompt_template_id=body.prompt_template_id,
            capabilities=frozenset(body.capabilities),
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return DefineAgentResponse(agent_id=agent_id)
