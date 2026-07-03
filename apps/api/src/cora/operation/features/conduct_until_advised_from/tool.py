"""MCP tool for the `conduct_until_advised_from` slice (steered RESUME wire).

Mirrors the REST route: accepts the steering objective + search space + the
objective captures-slot name + the brain-selection config, resumes a Held
GP-steered Procedure from its recorded closed passes, and returns a structured
summary. Loop failures (a pass / brain fault or the absolute ceiling) land in the
return value (not raised); the LLM caller inspects `succeeded` + `failure`.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.operation.features.conduct_until_advised_from.handler import Handler
from cora.operation.features.conduct_until_advised_from.route import (
    ConductUntilAdvisedFromRequest,
    ConductUntilAdvisedFromResponse,
    command_from_wire,
    result_to_wire,
)


class _ToolResult(BaseModel):
    """MCP-shape mirror of `ConductUntilAdvisedFromResponse` for tool-output validation."""

    procedure_id: UUID
    completed_count: int
    succeeded: bool
    re_establishment_boundary: int
    failure: dict[str, Any] | None = None
    actuation_kind: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `conduct_until_advised_from` tool on the given MCP server."""

    @mcp.tool(
        name="conduct_until_advised_from",
        description=(
            "Resume a Held recipe-driven STEERED Procedure: re-seed the in-CORA "
            "brain from the recorded closed passes (their measured values + advised "
            "coordinates) WITHOUT re-driving or re-measuring them, then continue the "
            "measure-then-advise loop at the open frontier until the brain advises "
            "Stop. Completes on Stop, aborts on a pass / brain fault or the absolute "
            "ceiling. Returns a structured summary; loop failures DO NOT raise."
        ),
    )
    async def conduct_until_advised_from_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        procedure_id: Annotated[
            UUID,
            Field(description="Target procedure's id."),
        ],
        body: Annotated[
            ConductUntilAdvisedFromRequest,
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
        wire: ConductUntilAdvisedFromResponse = result_to_wire(result)
        return _ToolResult(
            procedure_id=wire.procedure_id,
            completed_count=wire.completed_count,
            succeeded=wire.succeeded,
            re_establishment_boundary=wire.re_establishment_boundary,
            failure=wire.failure.model_dump() if wire.failure is not None else None,
            actuation_kind=wire.actuation_kind,
        )
