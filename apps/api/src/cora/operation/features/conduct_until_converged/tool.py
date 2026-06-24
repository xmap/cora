"""MCP tool for the `conduct_until_converged` slice (slice 6c).

Mirrors the REST route: accepts the convergence predicate (captures-slot name
+ criterion) plus an optional per-pass step list, returns a structured
ConductUntilConvergedResult summary. Failures (a never-converged cap-abort or
an in-pass fault) land in the return value (not raised); the LLM caller
inspects `succeeded` + `failure` to decide retry / escalation.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.operation._conduct_wire import criterion_from_wire, step_from_wire
from cora.operation.features.conduct_until_converged.command import ConductUntilConverged
from cora.operation.features.conduct_until_converged.handler import Handler
from cora.operation.features.conduct_until_converged.route import (
    ConductUntilConvergedRequest,
    ConductUntilConvergedResponse,
    result_to_wire,
)


class _ToolResult(BaseModel):
    """MCP-shape mirror of `ConductUntilConvergedResponse` for tool-output validation."""

    procedure_id: UUID
    completed_count: int
    succeeded: bool
    failure: dict[str, Any] | None = None
    actuation_kind: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `conduct_until_converged` tool on the given MCP server."""

    @mcp.tool(
        name="conduct_until_converged",
        description=(
            "Conduct an existing Procedure as an AUTO convergence loop: start "
            "it, then repeatedly walk one measure-correct pass block until the "
            "deposited value satisfies the supplied criterion (equals or "
            "within_tolerance) OR the patience cap trips. Completes on "
            "convergence, aborts on the cap or a pass fault. Returns a "
            "structured summary; failures DO NOT raise."
        ),
    )
    async def conduct_until_converged_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        procedure_id: Annotated[
            UUID,
            Field(description="Target procedure's id."),
        ],
        body: Annotated[
            ConductUntilConvergedRequest,
            Field(description="Convergence predicate + per-pass step block."),
        ],
    ) -> _ToolResult:
        handler = get_handler()
        command = ConductUntilConverged(
            procedure_id=procedure_id,
            convergence_capture_name=body.convergence_capture_name,
            criterion=criterion_from_wire(body.criterion),
            steps=tuple(step_from_wire(s) for s in body.steps),
            max_consecutive_unconverged_iterations=body.max_consecutive_unconverged_iterations,
        )
        result = await handler(
            command,
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        wire: ConductUntilConvergedResponse = result_to_wire(result)
        return _ToolResult(
            procedure_id=wire.procedure_id,
            completed_count=wire.completed_count,
            succeeded=wire.succeeded,
            failure=wire.failure.model_dump() if wire.failure is not None else None,
            actuation_kind=wire.actuation_kind,
        )
