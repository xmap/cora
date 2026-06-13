"""MCP tool for the `dismiss_event_in_reaction` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.agent.features.dismiss_event_in_reaction.command import (
    DismissEventInReaction,
)
from cora.agent.features.dismiss_event_in_reaction.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `dismiss_event_in_reaction` tool on the given MCP server."""

    @mcp.tool(
        name="dismiss_event_in_reaction",
        description=(
            "Advance a Reaction's projection_bookmarks row past a single "
            "poison event so the worker can resume. Records the dismissal "
            "as an auditable Decision (context=ReactionDismissal, "
            "choice=EventDismissed) so the operator action is preserved "
            "alongside every other operator judgment call. Use when an "
            "LLM-bound Reaction (run_debriefer, caution_drafter) wedges "
            "on a single event the apply path cannot process; the operator "
            "dashboard surfaces the event_id and last_error_message. "
            "Rejects if the event is already past the bookmark (no "
            "rewinds). Returns the new Decision id."
        ),
    )
    async def dismiss_event_in_reaction_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        subscriber_name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=200,
                description="Name of the subscriber (matches `Reaction.name`).",
            ),
        ],
        event_id: Annotated[
            UUID,
            Field(description="The event_id the operator wants to dismiss."),
        ],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description=(
                    "Free-form reason captured into the Decision's reasoning "
                    "(1-500 chars after trimming)."
                ),
            ),
        ],
    ) -> dict[str, str]:
        handler = get_handler()
        decision_id = await handler(
            DismissEventInReaction(
                subscriber_name=subscriber_name,
                event_id=event_id,
                reason=reason,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return {"decision_id": str(decision_id)}
