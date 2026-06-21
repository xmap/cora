"""MCP tool for the `reconduct_procedure` slice.

Mirrors the REST route: resumes a Held Procedure and replays its pinned
step-list tail, returning a structured summary. Replay outcomes (a step
failure, an acquisition halt) land in the return value, not raised; the
LLM caller inspects `succeeded` / `acquisition_halt` / `failure`.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.operation.features.reconduct_procedure.command import ReconductProcedure
from cora.operation.features.reconduct_procedure.handler import Handler
from cora.operation.features.reconduct_procedure.route import (
    ReconductProcedureResponse,
    result_to_wire,
)


class _ToolResult(BaseModel):
    """MCP-shape mirror of `ReconductProcedureResponse` for tool-output validation."""

    procedure_id: UUID
    completed_count: int
    succeeded: bool
    re_establishment_boundary: int
    acquisition_halt: bool
    failure: dict[str, Any] | None = None
    actuation_kind: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `reconduct_procedure` tool on the given MCP server."""

    @mcp.tool(
        name="reconduct_procedure",
        description=(
            "Resume a Held Procedure and replay its pinned step-list tail from "
            "re_establishment_boundary: re-drive setpoints, re-run checks, and "
            "HALT for an operator decision at an acquisition. On a clean tail "
            "the Procedure auto-completes; on an acquisition halt it stays "
            "Running (acquisition_halt=True); on a genuine step failure it "
            "aborts. Returns a structured summary; outcomes DO NOT raise. "
            "Requires the Procedure to be Held (and, for a Phase-of-Run "
            "Procedure, its parent Run not Held)."
        ),
    )
    async def reconduct_procedure_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        procedure_id: Annotated[
            UUID,
            Field(description="Target procedure's id."),
        ],
        re_establishment_boundary: Annotated[
            int,
            Field(
                ge=0,
                description=(
                    "Step-list index the resume re-drives setpoints / re-runs "
                    "checks from (>= 0; 0 = from the first step)."
                ),
            ),
        ],
    ) -> _ToolResult:
        handler = get_handler()
        result = await handler(
            ReconductProcedure(
                procedure_id=procedure_id,
                re_establishment_boundary=re_establishment_boundary,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        wire: ReconductProcedureResponse = result_to_wire(result)
        return _ToolResult(
            procedure_id=wire.procedure_id,
            completed_count=wire.completed_count,
            succeeded=wire.succeeded,
            re_establishment_boundary=wire.re_establishment_boundary,
            acquisition_halt=wire.acquisition_halt,
            failure=wire.failure.model_dump() if wire.failure is not None else None,
            actuation_kind=wire.actuation_kind,
        )
