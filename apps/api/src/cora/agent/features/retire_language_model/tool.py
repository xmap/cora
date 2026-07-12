"""MCP tool for the `retire_language_model` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.agent.features.retire_language_model.command import RetireLanguageModel
from cora.agent.features.retire_language_model.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH


class RetireLanguageModelOutput(BaseModel):
    """Structured output of the `retire_language_model` MCP tool."""

    language_model_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `retire_language_model` tool on the given MCP server."""

    @mcp.tool(
        name="retire_language_model",
        description=(
            "Retire a LanguageModel (Approved | RetirementAnnounced -> "
            "Retired). Terminal: the model is no longer servable and the "
            "entry cannot be revived. Reachable directly from Approved "
            "because providers remove models without notice. Optional "
            "`reason` (1-500 chars); omit when an unannounced removal "
            "arrived with no vendor statement."
        ),
    )
    async def retire_language_model_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        language_model_id: Annotated[
            UUID, Field(description="Identifier of the LanguageModel to retire.")
        ],
        reason: Annotated[
            str | None,
            Field(
                default=None,
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description="Optional retirement reason.",
            ),
        ] = None,
    ) -> RetireLanguageModelOutput:
        handler = get_handler()
        await handler(
            RetireLanguageModel(language_model_id=language_model_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RetireLanguageModelOutput(language_model_id=language_model_id)
