"""MCP tool for the `try_conduct_procedure` slice.

Mirrors the REST route: accepts a discriminated step list, returns a
structured summary. On a recoverable step failure the Procedure is PAUSED to
`Held` (resumable) instead of aborted; `held` in the return value flags that.
Failures land in the return value (not raised); the LLM caller inspects
`succeeded` + `held` + `failure` to decide reconduct / abort / escalation.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.operation._conduct_wire import step_from_wire
from cora.operation.features.try_conduct_procedure.command import TryConductProcedure
from cora.operation.features.try_conduct_procedure.handler import Handler
from cora.operation.features.try_conduct_procedure.route import (
    TryConductProcedureRequest,
    TryConductProcedureResponse,
    result_to_wire,
)


class _ToolResult(BaseModel):
    """MCP-shape mirror of `TryConductProcedureResponse` for tool-output validation."""

    procedure_id: UUID
    completed_count: int
    succeeded: bool
    held: bool = False
    failure: dict[str, Any] | None = None
    actuation_kind: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `try_conduct_procedure` tool on the given MCP server."""

    @mcp.tool(
        name="try_conduct_procedure",
        description=(
            "Conduct an existing Procedure end-to-end like conduct_procedure, "
            "but on a RECOVERABLE step failure (a setpoint write or read-back "
            "check) PAUSE the Procedure to Held (resumable via "
            "reconduct_procedure) instead of aborting it. An acquisition "
            "(action) failure still aborts. Returns a structured summary; "
            "`held` is True when the Procedure was paused (resumable). "
            "Failures DO NOT raise."
        ),
    )
    async def try_conduct_procedure_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        procedure_id: Annotated[
            UUID,
            Field(description="Target procedure's id."),
        ],
        body: Annotated[
            TryConductProcedureRequest,
            Field(description="Step list the Conductor walks in order."),
        ],
    ) -> _ToolResult:
        handler = get_handler()
        command = TryConductProcedure(
            procedure_id=procedure_id,
            steps=tuple(step_from_wire(s) for s in body.steps),
        )
        result = await handler(
            command,
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        wire: TryConductProcedureResponse = result_to_wire(result)
        return _ToolResult(
            procedure_id=wire.procedure_id,
            completed_count=wire.completed_count,
            succeeded=wire.succeeded,
            held=wire.held,
            failure=wire.failure.model_dump() if wire.failure is not None else None,
            actuation_kind=wire.actuation_kind,
        )
