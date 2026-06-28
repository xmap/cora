"""MCP tool for the `conduct_until_advised` slice (steered loop wire).

Mirrors the REST route: accepts the steering objective + search space + the
objective captures-slot name + the brain-selection config, returns a structured
ConductUntilAdvisedResult summary. Failures (a pass / brain fault or the
absolute ceiling) land in the return value (not raised); the LLM caller
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
from cora.operation.features.conduct_until_advised.handler import Handler
from cora.operation.features.conduct_until_advised.route import (
    ConductUntilAdvisedRequest,
    ConductUntilAdvisedResponse,
    command_from_wire,
    result_to_wire,
)


class _ToolResult(BaseModel):
    """MCP-shape mirror of `ConductUntilAdvisedResponse` for tool-output validation."""

    procedure_id: UUID
    completed_count: int
    succeeded: bool
    failure: dict[str, Any] | None = None
    actuation_kind: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `conduct_until_advised` tool on the given MCP server."""

    @mcp.tool(
        name="conduct_until_advised",
        description=(
            "Conduct an existing recipe-driven Procedure as a STEERED loop: start "
            "it, then repeatedly walk one pass block, hand the accumulated "
            "evidence to an in-CORA brain (grid_walk by default), and follow its "
            "advice on where to measure next until it advises Stop. Completes on "
            "Stop, aborts on a pass fault, a brain fault, or the absolute "
            "iteration ceiling. Returns a structured summary; failures DO NOT raise."
        ),
    )
    async def conduct_until_advised_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        procedure_id: Annotated[
            UUID,
            Field(description="Target procedure's id."),
        ],
        body: Annotated[
            ConductUntilAdvisedRequest,
            Field(description="Steering objective + search space + brain config."),
        ],
    ) -> _ToolResult:
        handler = get_handler()
        result = await handler(
            command_from_wire(procedure_id, body),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        wire: ConductUntilAdvisedResponse = result_to_wire(result)
        return _ToolResult(
            procedure_id=wire.procedure_id,
            completed_count=wire.completed_count,
            succeeded=wire.succeeded,
            failure=wire.failure.model_dump() if wire.failure is not None else None,
            actuation_kind=wire.actuation_kind,
        )
