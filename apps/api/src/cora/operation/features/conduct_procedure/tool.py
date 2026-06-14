"""MCP tool for the `conduct_procedure` slice.

Mirrors the REST route: accepts a discriminated step list, returns
a structured ConductProcedureResult summary. Failures land in the
return value (not raised); the LLM caller inspects `succeeded` +
`failure` to decide retry / abort / escalation.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.operation.features.conduct_procedure.command import ConductProcedure
from cora.operation.features.conduct_procedure.handler import Handler
from cora.operation.features.conduct_procedure.route import (
    ConductProcedureRequest,
    ConductProcedureResponse,
    result_to_wire,
    step_from_wire,
)


class _ToolResult(BaseModel):
    """MCP-shape mirror of `ConductProcedureResponse` for tool-output validation."""

    procedure_id: UUID
    completed_count: int
    succeeded: bool
    failure: dict[str, Any] | None = None
    actuation_kind: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `conduct_procedure` tool on the given MCP server."""

    @mcp.tool(
        name="conduct_procedure",
        description=(
            "Conduct an existing Procedure end-to-end: start it, walk the "
            "supplied step list via the ControlPort (setpoint writes), "
            "the action registry (named action invocations), and read-back "
            "checks (EqualsCriterion or WithinToleranceCriterion criteria); then complete on "
            "success or abort on the first step failure. Returns a structured "
            "summary; failures DO NOT raise."
        ),
    )
    async def conduct_procedure_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        procedure_id: Annotated[
            UUID,
            Field(description="Target procedure's id."),
        ],
        body: Annotated[
            ConductProcedureRequest,
            Field(description="Step list the Conductor walks in order."),
        ],
    ) -> _ToolResult:
        handler = get_handler()
        command = ConductProcedure(
            procedure_id=procedure_id,
            steps=tuple(step_from_wire(s) for s in body.steps),
        )
        result = await handler(
            command,
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        wire: ConductProcedureResponse = result_to_wire(result)
        return _ToolResult(
            procedure_id=wire.procedure_id,
            completed_count=wire.completed_count,
            succeeded=wire.succeeded,
            failure=wire.failure.model_dump() if wire.failure is not None else None,
            actuation_kind=wire.actuation_kind,
        )
