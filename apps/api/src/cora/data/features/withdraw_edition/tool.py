"""MCP tool for the `withdraw_edition` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.data.features.withdraw_edition.command import WithdrawEdition
from cora.data.features.withdraw_edition.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH


class WithdrawEditionOutput(BaseModel):
    """Structured output of the `withdraw_edition` MCP tool."""

    edition_id: UUID = Field(description="Identifier of the withdrawn Edition.")


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `withdraw_edition` tool on the given MCP server."""

    @mcp.tool(
        name="withdraw_edition",
        description=(
            "Withdraw a Published Edition: tombstone its DOI via the "
            "PersistentIdentifierMinter port (the DOI stays Findable as a tombstone; it is "
            "not deleted) and transition to Withdrawn. The withdrawal "
            "reason is mandatory and recorded forever."
        ),
    )
    async def withdraw_edition_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        edition_id: Annotated[UUID, Field(description="The Edition to withdraw.")],
        withdrawal_reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description="Why the Edition is being withdrawn. Recorded forever.",
            ),
        ],
    ) -> WithdrawEditionOutput:
        handler = get_handler()
        await handler(
            WithdrawEdition(
                edition_id=edition_id,
                withdrawal_reason=withdrawal_reason,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return WithdrawEditionOutput(edition_id=edition_id)
