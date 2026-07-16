"""MCP tool for the `announce_language_model_retirement` slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.agent.features.announce_language_model_retirement.command import (
    AnnounceLanguageModelRetirement,
)
from cora.agent.features.announce_language_model_retirement.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH


class AnnounceLanguageModelRetirementOutput(BaseModel):
    """Structured output of the `announce_language_model_retirement` MCP tool."""

    language_model_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `announce_language_model_retirement` tool on the given MCP server."""

    @mcp.tool(
        name="announce_language_model_retirement",
        description=(
            "Announce a LanguageModel's retirement (Approved -> "
            "RetirementAnnounced). Records the VENDOR's lifecycle fact: the "
            "provider announced this model will cease to exist. The entry "
            "stays servable until retired; the at-risk-results projection is "
            "live from this moment. `reason` is REQUIRED (1-500 chars); "
            "`effective_at` is the vendor's announced cutoff, omitted when "
            "the vendor gave no date."
        ),
    )
    async def announce_language_model_retirement_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        language_model_id: Annotated[
            UUID,
            Field(description="Identifier of the LanguageModel whose retirement is announced."),
        ],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description="Vendor-sourced retirement reason.",
            ),
        ],
        effective_at: Annotated[
            datetime | None,
            Field(
                default=None,
                description="The vendor's announced cutoff; omit when no date was given.",
            ),
        ] = None,
    ) -> AnnounceLanguageModelRetirementOutput:
        handler = get_handler()
        await handler(
            AnnounceLanguageModelRetirement(
                language_model_id=language_model_id,
                reason=reason,
                effective_at=effective_at,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return AnnounceLanguageModelRetirementOutput(language_model_id=language_model_id)
