"""MCP tool for the `append_outcomes` slice.

Exposes the SAME contract as the HTTP route: a batch of steered-pass outcome
entries, lazy open-on-first-write, dedup via Postgres PK on event_id.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.operation.features.append_outcomes.command import (
    AppendProcedureOutcomes,
    OutcomeInput,
)
from cora.operation.features.append_outcomes.handler import Handler


class _ProcedureOutcomeEntry(BaseModel):
    """One outcome entry's input payload (mirrors HTTP route shape)."""

    event_id: UUID
    iteration_index: int
    point: dict[str, Any]
    measurements: list[dict[str, Any]]
    succeeded: bool
    actuation_kind: str | None = None
    sampled_at: datetime
    occurred_at: datetime | None = None

    model_config = {"extra": "forbid"}


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `append_outcomes` tool on the given MCP server."""

    @mcp.tool(
        name="append_outcomes",
        description=(
            "Append a batch of steered-pass outcomes (the measured values a "
            "steering brain fit against, one row per iteration) to a Procedure's "
            "outcome logbook. Requires the Procedure to be `Running`. Lazy "
            "open-on-first-write; dedup via UUIDv7 event_id."
        ),
    )
    async def append_outcomes_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        procedure_id: Annotated[
            UUID,
            Field(description="Target procedure's id."),
        ],
        entries: Annotated[
            list[_ProcedureOutcomeEntry],
            Field(
                min_length=1,
                max_length=500,
                description="Batch of outcome entries to append (1-500).",
            ),
        ],
    ) -> int:
        handler = get_handler()
        return await handler(
            AppendProcedureOutcomes(
                procedure_id=procedure_id,
                entries=tuple(
                    OutcomeInput(
                        event_id=e.event_id,
                        iteration_index=e.iteration_index,
                        point=dict(e.point),
                        measurements=list(e.measurements),
                        succeeded=e.succeeded,
                        actuation_kind=e.actuation_kind,
                        sampled_at=e.sampled_at,
                        occurred_at=e.occurred_at,
                    )
                    for e in entries
                ),
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
