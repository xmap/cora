"""HTTP route for the `register_decision` slice.

`POST /decisions` returns 201 + `RegisterDecisionResponse`. Body
shape mirrors the on-the-wire event payload (so the client-facing
API and the persisted event are byte-aligned).
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.decision.aggregates.decision import (
    DECISION_ALTERNATIVE_ENTRY_MAX_LENGTH,
    DECISION_ALTERNATIVES_MAX_ENTRIES,
    DECISION_CHOICE_MAX_LENGTH,
    DECISION_CONTEXT_MAX_LENGTH,
    DECISION_INPUTS_MAX_ENTRIES,
    DECISION_REASONING_MAX_LENGTH,
    DECISION_REASONING_SIGNATURE_MAX_LENGTH,
    DECISION_RULE_MAX_LENGTH,
    DecisionConfidenceSource,
    DecisionOverrideKind,
)
from cora.decision.features.register_decision.command import RegisterDecision
from cora.decision.features.register_decision.handler import IdempotentHandler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.identity import ActorId


class RegisterDecisionRequest(BaseModel):
    """Body for `POST /decisions`."""

    decided_by: UUID = Field(
        ...,
        description=(
            "WHO made the decision (Actor.id). Existence-checked; 404 if "
            "the Actor doesn't exist. Decision can be made by any Actor "
            "including Deactivated (historical fact still holds)."
        ),
    )
    context: str = Field(
        ...,
        min_length=1,
        max_length=DECISION_CONTEXT_MAX_LENGTH,
        description=(
            "Decision discriminator. Open-ended string; well-known values "
            "include RecipeApproval, RunAbort, RunStop, RunTruncate, "
            "ResourceAllocation, PolicyGrant, ProcedureExecution, "
            "DatasetDiscard."
        ),
    )
    choice: str = Field(
        ...,
        min_length=1,
        max_length=DECISION_CHOICE_MAX_LENGTH,
        description="Free-form text capturing what was decided (1-500 chars after trim).",
    )
    parent_id: UUID | None = Field(
        default=None,
        description=(
            "Optional ref to a prior Decision being overridden / corrected "
            "/ appealed / superseded. Existence-checked; 404 if missing."
        ),
    )
    override_kind: DecisionOverrideKind | None = Field(
        default=None,
        description=(
            "When parent_id is set: WHY this Decision overrides the prior "
            "one. correction = we got it wrong; exception = explicit "
            "deviation; appeal = formal challenge; supersession = newer "
            "context replaces older. Required-with-parent invariant: "
            "set both or neither (400 otherwise)."
        ),
    )
    rule: str | None = Field(
        default=None,
        min_length=1,
        max_length=DECISION_RULE_MAX_LENGTH,
        description=(
            "Optional rule citation per ISO 17025 Clause 7.1.3. Convention "
            "encourages prefixed identifiers like "
            "'iso17025:7.1.3:simple_acceptance' or "
            "'cora:policy:recipe_approval:v1'."
        ),
    )
    reasoning: str | None = Field(
        default=None,
        max_length=DECISION_REASONING_MAX_LENGTH,
        description=(
            "Free-form prose explaining the decision (human-readable "
            "summary). AI token-by-token traces go to a separate logbook "
            "on the Decision aggregate (8c)."
        ),
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Confidence in the decision, in [0.0, 1.0]. Pair with "
            "confidence_source by convention so consumers can audit how "
            "the value was computed (BC does not enforce pairing; either "
            "field can be set independently)."
        ),
    )
    confidence_source: DecisionConfidenceSource | None = Field(
        default=None,
        description=(
            "How confidence was computed. self_reported = AI claim "
            "(lowest audit weight); logprob = derived from token "
            "log-probabilities; ensemble = aggregated over multiple "
            "deciders; human = subjective rating."
        ),
    )
    alternatives: list[str] = Field(
        default_factory=list[str],
        max_length=DECISION_ALTERNATIVES_MAX_ENTRIES,
        description=(
            "Options considered (ORDER PRESERVED for AI top-k). For "
            "PolicyGrant context, carries the determining policy IDs "
            "(Cedar-style)."
        ),
    )
    inputs: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Optional dict carrying the values the rule was "
            "applied to (per ILAC-G8:09/2019: a rule without its inputs "
            "is unauditable). Cap 64 keys."
        ),
    )
    reasoning_signature: str | None = Field(
        default=None,
        min_length=1,
        max_length=DECISION_REASONING_SIGNATURE_MAX_LENGTH,
        description=(
            "Optional opaque blob for tamper-evidence beyond row-level "
            "INSERT-only (typically sha256 of the full reasoning trace, "
            "or vendor-supplied encrypted summary)."
        ),
    )

    model_config = {"extra": "forbid"}


class RegisterDecisionResponse(BaseModel):
    """Response body for `POST /decisions`."""

    decision_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.decision.register_decision
    return handler


router = APIRouter(tags=["decision"])


# Per-entry alternatives length cap reference (enforced at the
# domain VO, mapped to 400 if violated).
_ = DECISION_ALTERNATIVE_ENTRY_MAX_LENGTH
_ = DECISION_INPUTS_MAX_ENTRIES


@router.post(
    "/decisions",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterDecisionResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated: whitespace-only choice / "
                "context, malformed alternatives entry, malformed "
                "inputs key, or override_kind without parent_id."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": ("Cross-aggregate reference does not exist: decided_by or parent_id."),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation OR Idempotency-"
                "Key was reused with a different request body."
            ),
        },
    },
    summary="Register a new Decision",
)
async def post_decisions(
    body: RegisterDecisionRequest,
    handler: Annotated[IdempotentHandler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description=(
                "Optional client-supplied unique key. Retries with the "
                "same key + same body return the cached response instead "
                "of re-creating the Decision."
            ),
        ),
    ] = None,
) -> RegisterDecisionResponse:
    decision_id = await handler(
        RegisterDecision(
            decided_by=ActorId(body.decided_by),
            context=body.context,
            choice=body.choice,
            parent_id=body.parent_id,
            override_kind=body.override_kind,
            rule=body.rule,
            reasoning=body.reasoning,
            confidence=body.confidence,
            confidence_source=body.confidence_source,
            alternatives=tuple(body.alternatives),
            inputs=body.inputs,
            reasoning_signature=body.reasoning_signature,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return RegisterDecisionResponse(decision_id=decision_id)
