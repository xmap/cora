"""HTTP route for the `regenerate_run_debrief` slice.

`POST /agents/run-debriefer/runs/{run_id}/regenerate-debrief` with
optional body `{parent_decision_id?}`. Returns 201 + `{decision_id}`
on success (including the `DebriefDeferred` path, which still produces
a Decision -- operators distinguish via the `choice` field on the
returned Decision).

Idempotency-Key header (per Stripe / Adyen / PayPal convention)
makes the operator's retry safe: a second call with the same key
replays the cached `decision_id`.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Request, status
from pydantic import BaseModel, Field

from cora.agent.build_llm import llm_unwired_reason
from cora.agent.features.regenerate_run_debrief.command import RegenerateRunDebrief
from cora.agent.features.regenerate_run_debrief.handler import IdempotentHandler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class RegenerateRunDebriefRequest(BaseModel):
    """Body for `POST /agents/run-debriefer/runs/{run_id}/regenerate-debrief`."""

    parent_decision_id: UUID | None = Field(
        default=None,
        description=(
            "Optional ref to the prior RunDebrief Decision being re-evaluated. "
            "When supplied, the new Decision's `parent_id` is set, forming a "
            "PROV-O `wasInformedBy` chain. Must reference the same Run as the "
            "path's `run_id`."
        ),
    )


class RegenerateRunDebriefResponse(BaseModel):
    """Response body for `POST /agents/run-debriefer/runs/{run_id}/regenerate-debrief`."""

    decision_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler | None = request.app.state.agent.regenerate_run_debrief
    if handler is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"regenerate_run_debrief is unavailable: kernel.llm is not wired. "
                f"{llm_unwired_reason(request.app.state.deps.settings)}"
            ),
        )
    return handler


router = APIRouter(tags=["agent"])


@router.post(
    "/agents/run-debriefer/runs/{run_id}/regenerate-debrief",
    status_code=status.HTTP_201_CREATED,
    response_model=RegenerateRunDebriefResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Cross-aggregate invariant violated: Run missing, agent not "
                "seeded / deactivated, parent_decision missing, or parent "
                "Decision references a different Run."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation, OR Idempotency-Key "
                "was reused with a different request body."
            ),
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ErrorResponse,
            "description": (
                "RunDebriefer is not wired (LLM_ENABLED off, the default, or no "
                "ANTHROPIC_API_KEY). The body names which."
            ),
        },
    },
    summary="Re-invoke RunDebriefer on demand against a specific Run.",
)
async def post_regenerate_run_debrief(
    run_id: Annotated[UUID, Path(description="The Run to regenerate the debrief for.")],
    handler: Annotated[IdempotentHandler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
    body: RegenerateRunDebriefRequest | None = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> RegenerateRunDebriefResponse:
    parent_decision_id = body.parent_decision_id if body is not None else None
    decision_id = await handler(
        RegenerateRunDebrief(
            run_id=run_id,
            parent_decision_id=parent_decision_id,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return RegenerateRunDebriefResponse(decision_id=decision_id)
