"""MCP tool for the `list_at_risk_results` query slice.

Surfaces the same handler the REST route uses. A missing entry raises
`LanguageModelNotFoundError` from the handler, which FastMCP wraps as
`isError: true` (the query-tool convention).
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.agent.aggregates.language_model import ArchivabilityTier, LanguageModelStatus
from cora.agent.features.list_at_risk_results.handler import Handler
from cora.agent.features.list_at_risk_results.query import ListAtRiskResults
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class AtRiskResultOutput(BaseModel):
    """One Decision whose recorded LLM calls touched the entry's model."""

    decision_id: UUID
    occurred_at: datetime
    request_model: str
    response_model: str | None = None
    agent_id: str | None = None


class AtRiskResultsOutput(BaseModel):
    """Structured output of the `list_at_risk_results` MCP tool.

    `reproducibility_grade` is `ReExecutable` (Pinned weights) or
    `AttributableOnly` (Alias identity); `at_risk` is true only when
    the grade is `AttributableOnly` AND the entry's status is
    RetirementAnnounced or Retired. `results` is populated for any
    status so callers can triage exposure before an announcement.
    """

    language_model_id: UUID
    status: LanguageModelStatus
    archivability: ArchivabilityTier
    reproducibility_grade: str
    at_risk: bool
    results: list[AtRiskResultOutput]


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `list_at_risk_results` tool on the given MCP server."""

    @mcp.tool(
        name="list_at_risk_results",
        description=(
            "List the Decisions whose recorded LLM calls touched a "
            "LanguageModel catalog entry's model identity, graded for "
            "reproducibility: ReExecutable when the entry is Pinned "
            "(facility-held weights), AttributableOnly when it is an "
            "Alias the provider may retire. `at_risk` is true only for "
            "an AttributableOnly entry whose status is "
            "RetirementAnnounced or Retired; the list itself answers "
            "for any status so exposure can be triaged before an "
            "announcement."
        ),
    )
    async def list_at_risk_results_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        language_model_id: Annotated[
            UUID,
            Field(description="Identifier of the LanguageModel catalog entry to grade."),
        ],
    ) -> AtRiskResultsOutput:
        handler = get_handler()
        view = await handler(
            ListAtRiskResults(language_model_id=language_model_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return AtRiskResultsOutput(
            language_model_id=view.language_model_id,
            status=view.status,
            archivability=view.archivability,
            reproducibility_grade=view.reproducibility_grade,
            at_risk=view.at_risk,
            results=[
                AtRiskResultOutput(
                    decision_id=result.decision_id,
                    occurred_at=result.occurred_at,
                    request_model=result.request_model,
                    response_model=result.response_model,
                    agent_id=result.agent_id,
                )
                for result in view.results
            ],
        )
