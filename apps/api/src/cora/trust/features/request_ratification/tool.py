"""MCP tool for the `request_ratification` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.trust.aggregates.ratification import CONSEQUENCE_CLASS_MAX_LENGTH
from cora.trust.features.request_ratification.command import RequestRatification
from cora.trust.features.request_ratification.handler import Handler


class RequestRatificationOutput(BaseModel):
    """Structured output of the `request_ratification` MCP tool."""

    ratification_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `request_ratification` tool on the given MCP server."""

    @mcp.tool(
        name="request_ratification",
        description=(
            "Request a second, independent principal's co-signature for a "
            "consequential action. Caller supplies ratification_id. Status "
            "starts at 'Requested'. The requester is the calling principal; an "
            "independent principal must later grant or deny."
        ),
    )
    async def request_ratification_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        ratification_id: Annotated[UUID, Field(description="Caller-supplied UUID.")],
        target_action_id: Annotated[
            UUID,
            Field(description="Opaque id of the action being gated (e.g. the held run id)."),
        ],
        command_name: Annotated[
            str,
            Field(description="Canonical name of the gated command."),
        ],
        consequence_class: Annotated[
            str,
            Field(
                min_length=1,
                max_length=CONSEQUENCE_CLASS_MAX_LENGTH,
                description="Declared class that triggered the requirement (bare-str label).",
            ),
        ],
    ) -> RequestRatificationOutput:
        handler = get_handler()
        await handler(
            RequestRatification(
                ratification_id=ratification_id,
                target_action_id=target_action_id,
                command_name=command_name,
                consequence_class=consequence_class,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RequestRatificationOutput(ratification_id=ratification_id)
