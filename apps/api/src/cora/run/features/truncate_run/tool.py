"""MCP tool for the `truncate_run` slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.run.features.truncate_run.command import TruncateRun
from cora.run.features.truncate_run.handler import Handler
from cora.shared.text_bounds import REASON_MAX_LENGTH


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `truncate_run` tool on the given MCP server."""

    @mcp.tool(
        name="truncate_run",
        description=(
            "Cleanup terminal of an interrupted Run (Running | Held → Truncated). "
            "Use when a Run became de-facto dead through interruption (power "
            "loss, process crash, hardware fault) and is being closed "
            "retroactively. Distinct from stop: stop is a controlled exit "
            "while the system is responsive; truncate is retroactive cleanup. "
            "Truncating a terminal Run raises. Reason is free-form (1-500 "
            "chars), captured verbatim for audit. Optional interrupted_at "
            "(ISO-8601 tz-aware) is the operator's best guess at when the "
            "interruption actually happened; must not be in the future."
        ),
    )
    async def truncate_run_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        run_id: Annotated[
            UUID,
            Field(description="Target run's id."),
        ],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description=("Free-form reason for the truncation (1-500 chars after trimming)."),
            ),
        ],
        interrupted_at: Annotated[
            datetime | None,
            Field(
                default=None,
                description=(
                    "Operator's best guess at when the actual interruption "
                    "happened (ISO-8601, timezone-aware). Optional; null when "
                    "unknown. Must not be in the future."
                ),
            ),
        ] = None,
    ) -> None:
        handler = get_handler()
        await handler(
            TruncateRun(
                run_id=run_id,
                reason=reason,
                interrupted_at=interrupted_at,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
