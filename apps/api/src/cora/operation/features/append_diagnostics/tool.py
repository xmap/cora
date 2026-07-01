"""MCP tool for the `append_diagnostics` slice.

Exposes the SAME contract as the HTTP route: a batch of GP-steering diagnostic
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
from cora.operation.features.append_diagnostics.command import (
    AppendProcedureDiagnostics,
    DiagnosticInput,
)
from cora.operation.features.append_diagnostics.handler import Handler


class _ProcedureDiagnosticEntry(BaseModel):
    """One diagnostic entry's input payload (mirrors HTTP route shape)."""

    event_id: UUID
    iteration_index: int
    model_ref: str
    payload: dict[str, float]
    sampled_at: datetime
    occurred_at: datetime | None = None

    model_config = {"extra": "forbid"}


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `append_diagnostics` tool on the given MCP server."""

    @mcp.tool(
        name="append_diagnostics",
        description=(
            "Append a batch of GP-steering diagnostics (fitted-model summary "
            "scalars: lengthscales, noise, acquisition value) to a Procedure's "
            "diagnostics logbook. Requires the Procedure to be `Running`. Lazy "
            "open-on-first-write; dedup via UUIDv7 event_id."
        ),
    )
    async def append_diagnostics_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        procedure_id: Annotated[
            UUID,
            Field(description="Target procedure's id."),
        ],
        entries: Annotated[
            list[_ProcedureDiagnosticEntry],
            Field(
                min_length=1,
                max_length=500,
                description="Batch of diagnostic entries to append (1-500).",
            ),
        ],
    ) -> int:
        handler = get_handler()
        return await handler(
            AppendProcedureDiagnostics(
                procedure_id=procedure_id,
                entries=tuple(
                    DiagnosticInput(
                        event_id=e.event_id,
                        iteration_index=e.iteration_index,
                        model_ref=e.model_ref,
                        payload=e.payload,
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
