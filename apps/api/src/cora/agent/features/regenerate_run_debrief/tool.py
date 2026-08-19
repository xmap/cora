"""MCP tool for the regenerate_run_debrief slice.

Surfaces the same handler the REST route uses. MCP tools currently
bypass header-based idempotency, so idempotency_key defaults to None
and each MCP invocation is a fresh attempt.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.agent.features.regenerate_run_debrief.command import RegenerateRunDebrief
from cora.agent.features.regenerate_run_debrief.handler import IdempotentHandler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class RegenerateRunDebriefOutput(BaseModel):
    """Structured output of the `regenerate_run_debrief` MCP tool."""

    decision_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `regenerate_run_debrief` tool on the given MCP server."""

    @mcp.tool(
        name="regenerate_run_debrief",
        description=(
            "Re-invoke the RunDebriefer agent on demand against a specific Run. "
            "Returns the new `decision_id`. Use when an automated Debrief "
            "needs a fresh take (operator rated it `misleading`, the original "
            "landed `DebriefDeferred`, or a new model version landed). "
            "Optional `parent_decision_id` forms a PROV-O wasInformedBy chain "
            "to the prior Decision (must reference the same Run)."
        ),
    )
    async def regenerate_run_debrief_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        run_id: Annotated[
            UUID,
            Field(description="The Run to regenerate the debrief for."),
        ],
        agent_id: Annotated[
            UUID | None,
            Field(
                default=None,
                description=(
                    "Which RunDebriefer performs the debrief. Omit for the "
                    "seeded singleton. Naming another RunDebriefer re-debriefs "
                    "the Run under that Agent's declared model, which is how "
                    "one Run is compared across two approved models."
                ),
            ),
        ] = None,
        parent_decision_id: Annotated[
            UUID | None,
            Field(
                default=None,
                description=(
                    "Optional ref to the prior RunDebrief Decision; sets the "
                    "new Decision's `parent_id` to form an audit chain."
                ),
            ),
        ] = None,
    ) -> RegenerateRunDebriefOutput:
        handler = get_handler()
        decision_id = await handler(
            RegenerateRunDebrief(
                run_id=run_id,
                parent_decision_id=parent_decision_id,
                agent_id=agent_id,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RegenerateRunDebriefOutput(decision_id=decision_id)
