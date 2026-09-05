"""MCP tool for the `define_agent` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool. MCP tools currently bypass header extraction
"""

from collections.abc import Callable
from typing import Annotated, Any, Literal, assert_never
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

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
    BrainKind,
    BrainRef,
    InvalidBrainRefError,
    ModelRef,
)
from cora.agent.features.define_agent.command import DefineAgent
from cora.agent.features.define_agent.handler import IdempotentHandler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class BrainInput(BaseModel):
    """Sub-input for the typed BrainRef VO: what this Agent thinks with."""

    kind: Literal["LanguageModel", "Rule"] = Field(
        ...,
        description=(
            "`LanguageModel` carries model_ref and is gated against the "
            "approved catalog; `Rule` carries rule and needs no approval."
        ),
    )
    model_ref: "ModelRefInput | None" = Field(
        default=None, description="Required when kind is LanguageModel."
    )
    rule: str | None = Field(
        default=None,
        min_length=1,
        max_length=BRAIN_RULE_MAX_LENGTH,
        description="Required when kind is Rule (convention: `ExperimentSteerer:v1`).",
    )


class ModelRefInput(BaseModel):
    """Sub-input for the typed ModelRef VO."""

    provider: str = Field(
        ...,
        min_length=1,
        max_length=MODEL_REF_PROVIDER_MAX_LENGTH,
        description="LLM provider name.",
    )
    model: str = Field(
        ...,
        min_length=1,
        max_length=MODEL_REF_MODEL_MAX_LENGTH,
        description="Provider-specific model identifier.",
    )
    snapshot_pin: str | None = Field(
        default=None,
        max_length=MODEL_REF_SNAPSHOT_PIN_MAX_LENGTH,
        description="Optional snapshot pin.",
    )


class DefineAgentOutput(BaseModel):
    """Structured output of the `define_agent` MCP tool."""

    agent_id: UUID


def _model_ref_from(value: ModelRefInput | None) -> ModelRef | None:
    if value is None:
        return None
    return ModelRef(provider=value.provider, model=value.model, snapshot_pin=value.snapshot_pin)


def _brain_from(value: BrainInput | None) -> BrainRef | None:
    """Build the typed BrainRef, letting the VO enforce kind consistency.

    Mirrors the route helper: one home for the invariant, so a body whose
    payload disagrees with its kind surfaces as `InvalidBrainRefError` rather
    than being coerced into something the caller did not ask for.
    """
    if value is None:
        return None
    match value.kind:
        case "LanguageModel":
            model_ref = _model_ref_from(value.model_ref)
            if model_ref is None:
                raise InvalidBrainRefError("a LanguageModel brain carries model_ref and no rule")
            return BrainRef(kind=BrainKind.LANGUAGE_MODEL, model_ref=model_ref, rule=value.rule)
        case "Rule":
            return BrainRef(
                kind=BrainKind.RULE, rule=value.rule, model_ref=_model_ref_from(value.model_ref)
            )
        case _:  # pragma: no cover - exhaustive over the Literal
            assert_never(value.kind)


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `define_agent` tool on the given MCP server."""

    @mcp.tool(
        name="define_agent",
        description=(
            "Define a new Agent (lands in Defined; co-registers an Actor with "
            "kind=agent atomically). Required: kind, name, version, model_ref. "
            "Optional: description, canonical_uri (https only), "
            "prompt_template_id, capabilities. The new agent_id is the same "
            "UUID as the co-registered Actor's id."
        ),
    )
    async def define_agent_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        kind: Annotated[
            str,
            Field(
                min_length=1,
                max_length=AGENT_KIND_MAX_LENGTH,
                description="Agent kind discriminator (`RunDebriefer`, etc.).",
            ),
        ],
        name: Annotated[
            str,
            Field(min_length=1, max_length=AGENT_NAME_MAX_LENGTH, description="Display name."),
        ],
        version: Annotated[
            str,
            Field(
                min_length=1,
                max_length=AGENT_VERSION_MAX_LENGTH,
                description="Version identifier.",
            ),
        ],
        model_ref: Annotated[
            ModelRefInput | None,
            Field(
                default=None,
                description=(
                    "Model identity: provider, model name, and an optional snapshot "
                    "pin. The legacy way to name a LanguageModel brain. Supply "
                    "exactly one of model_ref or brain."
                ),
            ),
        ] = None,
        brain: Annotated[
            BrainInput | None,
            Field(
                default=None,
                description=(
                    "What this Agent thinks with. Supply exactly one of model_ref "
                    "or brain; brain is the only way to define an Agent whose "
                    "brain is not a language model."
                ),
            ),
        ] = None,
        description: Annotated[
            str | None,
            Field(
                default=None,
                min_length=1,
                max_length=AGENT_DESCRIPTION_MAX_LENGTH,
                description="Optional description.",
            ),
        ] = None,
        canonical_uri: Annotated[
            str | None,
            Field(
                default=None,
                min_length=1,
                max_length=AGENT_CANONICAL_URI_MAX_LENGTH,
                description="Optional https canonical URI.",
            ),
        ] = None,
        prompt_template_id: Annotated[
            UUID | None,
            Field(default=None, description="Optional UUID into the prompt registry."),
        ] = None,
        capabilities: Annotated[
            list[str] | None,
            Field(
                default=None,
                max_length=AGENT_CAPABILITIES_MAX_COUNT,
                description=(
                    f"Optional capability claims (each 1-{AGENT_CAPABILITY_MAX_LENGTH} chars). "
                    "Null is treated as an empty set."
                ),
            ),
        ] = None,
    ) -> DefineAgentOutput:
        if (model_ref is None) == (brain is None):
            msg = "supply exactly one of model_ref or brain"
            raise ValueError(msg)
        handler = get_handler()
        agent_id = await handler(
            DefineAgent(
                kind=kind,
                name=name,
                version=version,
                model_ref=_model_ref_from(model_ref),
                brain=_brain_from(brain),
                description=description,
                canonical_uri=canonical_uri,
                prompt_template_id=prompt_template_id,
                capabilities=frozenset(capabilities or []),
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return DefineAgentOutput(agent_id=agent_id)
