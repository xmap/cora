"""MCP tool for the `deprecate_language_model` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.agent.features.deprecate_language_model.command import DeprecateLanguageModel
from cora.agent.features.deprecate_language_model.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH


class DeprecateLanguageModelOutput(BaseModel):
    """Structured output of the `deprecate_language_model` MCP tool."""

    language_model_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `deprecate_language_model` tool on the given MCP server."""

    @mcp.tool(
        name="deprecate_language_model",
        description=(
            "Deprecate a LanguageModel (Defined | Approved | "
            "RetirementAnnounced -> Deprecated). Terminal: the FACILITY "
            "withdrew its approval (policy, security, cost), independent of "
            "the vendor's lifecycle; deprecated entries cannot be revived. "
            "`reason` is REQUIRED (1-500 chars): withdrawing approval is a "
            "policy act the audit log must always carry context for."
        ),
    )
    async def deprecate_language_model_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        language_model_id: Annotated[
            UUID, Field(description="Identifier of the LanguageModel to deprecate.")
        ],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description="Deprecation reason (policy act; always required).",
            ),
        ],
    ) -> DeprecateLanguageModelOutput:
        handler = get_handler()
        await handler(
            DeprecateLanguageModel(language_model_id=language_model_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return DeprecateLanguageModelOutput(language_model_id=language_model_id)
