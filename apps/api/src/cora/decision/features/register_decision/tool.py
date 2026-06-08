"""MCP tool for the `register_decision` slice.

Surfaces the same handler the REST route uses.

The MCP tool exposes the same flat parameter set as the REST body
(no flattening needed since the body is already mostly flat;
`alternatives` and `inputs` pass through as JSON-native
list/dict types).
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.decision.aggregates.decision import (
    DECISION_ALTERNATIVES_MAX_ENTRIES,
    DECISION_CHOICE_MAX_LENGTH,
    DECISION_CONTEXT_MAX_LENGTH,
    DECISION_REASONING_MAX_LENGTH,
    DECISION_REASONING_SIGNATURE_MAX_LENGTH,
    DECISION_RULE_MAX_LENGTH,
    DecisionConfidenceSource,
    DecisionOverrideKind,
)
from cora.decision.features.register_decision.command import RegisterDecision
from cora.decision.features.register_decision.handler import IdempotentHandler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.identity import ActorId


class RegisterDecisionOutput(BaseModel):
    """Structured output of the `register_decision` MCP tool."""

    decision_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `register_decision` tool on the given MCP server."""

    @mcp.tool(
        name="register_decision",
        description=(
            "Register a new Decision (structured-audit record of a "
            "consequential choice). Same aggregate handles human and AI "
            "deciders; decided_by distinguishes them. Use parent_id + "
            "override_kind for corrections / exceptions / appeals / "
            "supersessions. Use rule + inputs for "
            "ISO 17025 Clause 7.1.3 conformance. Use confidence + "
            "confidence_source for AI-decider audit (pair by convention; "
            "self_reported confidence has the lowest audit weight)."
        ),
    )
    async def register_decision_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        decided_by: Annotated[UUID, Field(description="WHO made the decision (Actor.id).")],
        context: Annotated[
            str,
            Field(
                min_length=1,
                max_length=DECISION_CONTEXT_MAX_LENGTH,
                description=(
                    "Decision discriminator. Well-known values: "
                    "RecipeApproval, RunAbort, RunStop, RunTruncate, "
                    "ResourceAllocation, PolicyGrant, ProcedureExecution, "
                    "DatasetDiscard."
                ),
            ),
        ],
        choice: Annotated[
            str,
            Field(
                min_length=1,
                max_length=DECISION_CHOICE_MAX_LENGTH,
                description="What was decided (1-500 chars after trim).",
            ),
        ],
        parent_id: Annotated[
            UUID | None,
            Field(default=None, description="Prior Decision being overridden."),
        ] = None,
        override_kind: Annotated[
            DecisionOverrideKind | None,
            Field(
                default=None,
                description=(
                    "Why this overrides the prior Decision (correction / "
                    "exception / appeal / supersession). Required when "
                    "parent_id is set."
                ),
            ),
        ] = None,
        rule: Annotated[
            str | None,
            Field(
                default=None,
                max_length=DECISION_RULE_MAX_LENGTH,
                description=(
                    "Rule citation per ISO 17025 Clause 7.1.3 (for example, "
                    "'iso17025:7.1.3:simple_acceptance')."
                ),
            ),
        ] = None,
        reasoning: Annotated[
            str | None,
            Field(
                default=None,
                max_length=DECISION_REASONING_MAX_LENGTH,
                description="Human-readable summary of the decision rationale.",
            ),
        ] = None,
        confidence: Annotated[
            float | None,
            Field(
                default=None,
                ge=0.0,
                le=1.0,
                description="Confidence in [0, 1]. Always pair with confidence_source.",
            ),
        ] = None,
        confidence_source: Annotated[
            DecisionConfidenceSource | None,
            Field(
                default=None,
                description=(
                    "How confidence was computed: self_reported / logprob / ensemble / human."
                ),
            ),
        ] = None,
        alternatives: Annotated[
            list[str] | None,
            Field(
                default=None,
                max_length=DECISION_ALTERNATIVES_MAX_ENTRIES,
                description=(
                    "Options considered (order preserved). For PolicyGrant "
                    "context: determining policy IDs."
                ),
            ),
        ] = None,
        inputs: Annotated[
            dict[str, Any] | None,
            Field(default=None, description="Inputs the rule was applied to."),
        ] = None,
        reasoning_signature: Annotated[
            str | None,
            Field(
                default=None,
                max_length=DECISION_REASONING_SIGNATURE_MAX_LENGTH,
                description=(
                    "Optional opaque blob (typically sha256 of the full "
                    "reasoning trace) for tamper-evidence."
                ),
            ),
        ] = None,
    ) -> RegisterDecisionOutput:
        handler = get_handler()
        decision_id = await handler(
            RegisterDecision(
                decided_by=ActorId(decided_by),
                context=context,
                choice=choice,
                parent_id=parent_id,
                override_kind=override_kind,
                rule=rule,
                reasoning=reasoning,
                confidence=confidence,
                confidence_source=confidence_source,
                alternatives=tuple(alternatives or []),
                inputs=inputs,
                reasoning_signature=reasoning_signature,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RegisterDecisionOutput(decision_id=decision_id)
