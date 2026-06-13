"""MCP tool for the `adjust_run` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.run.features.adjust_run.command import AdjustRun
from cora.run.features.adjust_run.handler import IdempotentHandler
from cora.shared.text_bounds import REASON_MAX_LENGTH


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `adjust_run` tool on the given MCP server."""

    @mcp.tool(
        name="adjust_run",
        description=(
            "Adjust an in-progress Run's effective parameters mid-flight. "
            "Requires the Run to currently be in Running or Held; Idle / "
            "terminal Runs are rejected. Patch is RFC 7396 JSON Merge "
            "Patch on top of the Run's current effective_parameters; the "
            "post-merge result is validated against the owning Method's "
            "parameters_schema (when declared). The Run identity, "
            "Subject, Plan, Method, Asset binding, and Campaign "
            "membership are NOT changed: this is parameter steering, "
            "not scientific-frame mutation. Reason is required (1-500 "
            "chars). Optional decided_by_decision_id links the action "
            "to a Decision BC record (PROV-O wasInformedBy at export)."
        ),
    )
    async def adjust_run_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        run_id: Annotated[
            UUID,
            Field(description="Target run's id."),
        ],
        parameters_patch: Annotated[
            dict[str, Any],
            Field(
                description=(
                    "RFC 7396 JSON Merge Patch on the Run's current "
                    "effective_parameters. Non-empty required."
                ),
            ),
        ],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description=(
                    "Free-form justification for the adjustment (1-500 chars after trimming)."
                ),
            ),
        ],
        decided_by_decision_id: Annotated[
            UUID | None,
            Field(
                default=None,
                description=(
                    "Optional Decision id that justified this adjustment. "
                    "Maps to prov:wasInformedBy at the future PROV-O "
                    "export adapter. Not verified at the write path."
                ),
            ),
        ] = None,
    ) -> None:
        handler = get_handler()
        await handler(
            AdjustRun(
                run_id=run_id,
                parameters_patch=parameters_patch,
                reason=reason,
                decided_by_decision_id=decided_by_decision_id,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
