"""HTTP route for the `list_at_risk_results` query slice.

`GET /language-models/{language_model_id}/at-risk-results` returns 200
with the graded Decision list; 404 when no entry exists with the given
id (the handler raises `LanguageModelNotFoundError`, mapped by the
BC-registered exception handler, so no inline HTTPException here).

The endpoint answers for ANY status: an operator may ask what WOULD be
at risk before a vendor announcement (catalog triage), so the response
always carries the Decision list and lets the `at_risk` flag carry the
lifecycle judgment (true only for an Alias entry whose status is
RetirementAnnounced or Retired).
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel

from cora.agent.aggregates.language_model import ArchivabilityTier, LanguageModelStatus
from cora.agent.features.list_at_risk_results.handler import AtRiskResultsView, Handler
from cora.agent.features.list_at_risk_results.query import ListAtRiskResults
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class AtRiskResultResponse(BaseModel):
    """One Decision whose recorded LLM calls touched the entry's model.

    Values come from the Decision's newest touching inference row:
    `request_model` / `response_model` show which arm matched (alias
    asked for vs dated snapshot answered with); `agent_id` is the OTel
    string identity of the recording agent, null for
    operator-attributed rows.
    """

    decision_id: UUID
    occurred_at: datetime
    request_model: str
    response_model: str | None = None
    agent_id: str | None = None


class AtRiskResultsResponse(BaseModel):
    """Read-side DTO at the API boundary.

    Carries primitives, not domain VOs. `reproducibility_grade` is
    `ReExecutable` (Pinned weights the facility can serve indefinitely)
    or `AttributableOnly` (an Alias identity whose retirement leaves
    provenance but not re-execution). `at_risk` is true only when the
    grade is `AttributableOnly` AND the vendor lifecycle has moved
    (RetirementAnnounced or Retired); `results` is populated for any
    status so operators can triage exposure before an announcement.
    """

    language_model_id: UUID
    status: LanguageModelStatus
    archivability: ArchivabilityTier
    reproducibility_grade: str
    at_risk: bool
    results: list[AtRiskResultResponse]


def _response_from_view(view: AtRiskResultsView) -> AtRiskResultsResponse:
    return AtRiskResultsResponse(
        language_model_id=view.language_model_id,
        status=view.status,
        archivability=view.archivability,
        reproducibility_grade=view.reproducibility_grade,
        at_risk=view.at_risk,
        results=[
            AtRiskResultResponse(
                decision_id=result.decision_id,
                occurred_at=result.occurred_at,
                request_model=result.request_model,
                response_model=result.response_model,
                agent_id=result.agent_id,
            )
            for result in view.results
        ],
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.agent.list_at_risk_results
    return handler


router = APIRouter(tags=["agent"])


@router.get(
    "/language-models/{language_model_id}/at-risk-results",
    status_code=status.HTTP_200_OK,
    response_model=AtRiskResultsResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the query.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No LanguageModel exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="List the Decisions whose recorded LLM calls touched this model, graded",
)
async def get_language_models_at_risk_results(
    language_model_id: Annotated[UUID, Path(description="Target LanguageModel's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> AtRiskResultsResponse:
    view = await handler(
        ListAtRiskResults(language_model_id=language_model_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return _response_from_view(view)
