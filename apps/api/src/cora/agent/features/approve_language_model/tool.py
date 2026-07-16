"""MCP tool for the `approve_language_model` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.agent.features.approve_language_model.command import ApproveLanguageModel
from cora.agent.features.approve_language_model.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class ApproveLanguageModelOutput(BaseModel):
    """Structured output of the `approve_language_model` MCP tool."""

    language_model_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `approve_language_model` tool on the given MCP server."""

    @mcp.tool(
        name="approve_language_model",
        description=(
            "Approve a Defined LanguageModel (Defined -> Approved). The "
            "facility's governance act: from this moment the catalog entry "
            "is usable for its declared data tier and the pricing bridge may "
            "feed from it. Source set is {Defined} only; approving from any "
            "other status raises an error."
        ),
    )
    async def approve_language_model_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        language_model_id: Annotated[
            UUID, Field(description="Identifier of the LanguageModel to approve.")
        ],
    ) -> ApproveLanguageModelOutput:
        handler = get_handler()
        await handler(
            ApproveLanguageModel(language_model_id=language_model_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return ApproveLanguageModelOutput(language_model_id=language_model_id)
