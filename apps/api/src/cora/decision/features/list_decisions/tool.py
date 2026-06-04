"""MCP tool for the `list_decisions` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.decision.features.list_decisions.handler import Handler
from cora.decision.features.list_decisions.query import ConfidenceBandFilter, ListDecisions
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class DecisionSummaryRow(BaseModel):
    decision_id: UUID
    actor_id: UUID
    rule: str | None
    parent_id: UUID | None
    confidence: float | None
    confidence_band: ConfidenceBandFilter | None
    choice: str
    created_at: datetime


class DecisionListOutput(BaseModel):
    """Structured output of the `list_decisions` MCP tool."""

    items: list[DecisionSummaryRow]
    next_cursor: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `list_decisions` tool on the given MCP server."""

    @mcp.tool(
        name="list_decisions",
        description=(
            "Cursor-paginated list of decisions. Optional "
            "`confidence_band` filter accepts: Low, Medium, High, "
            "Certain. Optional `rule` filter narrows by "
            "categorical rule label. Optional `actor_id` filter "
            "narrows to Decisions made by one Actor. Optional "
            "`choice` filter narrows to one DecisionChoice value "
            "(e.g. NominalCompletion). Optional `exclude_choices` "
            "list drops named choices, commonly the audit-only "
            "DebriefConflicted / CautionDraftConflicted rows from "
            "the cross-agent debrief lease. Pass `cursor` "
            "from a previous page's `next_cursor`."
        ),
    )
    async def list_decisions_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        cursor: Annotated[
            str | None,
            Field(description="Opaque cursor from a previous response."),
        ] = None,
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Page size cap (max 100)."),
        ] = 50,
        confidence_band: Annotated[
            ConfidenceBandFilter | None,
            Field(description="Optional confidence-band filter; omit to list all."),
        ] = None,
        rule: Annotated[
            str | None,
            Field(description="Optional decision-rule label filter."),
        ] = None,
        actor_id: Annotated[
            UUID | None,
            Field(description="Optional Actor-id filter."),
        ] = None,
        choice: Annotated[
            str | None,
            Field(description="Optional DecisionChoice filter (one value)."),
        ] = None,
        exclude_choices: Annotated[
            list[str] | None,
            Field(
                description=(
                    "Optional DecisionChoice exclusion list. Drops named "
                    "choices; commonly used to omit DebriefConflicted / "
                    "CautionDraftConflicted audit rows."
                ),
            ),
        ] = None,
    ) -> DecisionListOutput:
        handler = get_handler()
        page = await handler(
            ListDecisions(
                cursor=cursor,
                limit=limit,
                confidence_band=confidence_band,
                rule=rule,
                actor_id=actor_id,
                choice=choice,
                exclude_choices=tuple(exclude_choices) if exclude_choices else None,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return DecisionListOutput(
            items=[
                DecisionSummaryRow(
                    decision_id=item.decision_id,
                    actor_id=item.actor_id,
                    rule=item.rule,
                    parent_id=item.parent_id,
                    confidence=item.confidence,
                    confidence_band=item.confidence_band,
                    choice=item.choice,
                    created_at=item.created_at,
                )
                for item in page.items
            ],
            next_cursor=page.next_cursor,
        )
