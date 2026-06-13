"""MCP tool for the `abort_credential_rotation` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.federation.features.abort_credential_rotation.command import (
    AbortCredentialRotation,
)
from cora.federation.features.abort_credential_rotation.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH


class AbortCredentialRotationOutput(BaseModel):
    """Structured output of the `abort_credential_rotation` MCP tool."""

    credential_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `abort_credential_rotation` tool on the given MCP server."""

    @mcp.tool(
        name="abort_credential_rotation",
        description=(
            "Abort an in-flight credential rotation (Rotating -> Active). "
            "Single-source: requires Credential to be in 'Rotating' status. "
            "Clears pending refs without promoting them; current secret_ref "
            "is unchanged. Use when the rotation cannot complete (peer "
            "refused new material, key generation failed, operator changed "
            "their mind). For terminal removal use 'revoke_credential'."
        ),
    )
    async def abort_credential_rotation_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        credential_id: Annotated[
            UUID,
            Field(description="Target credential's id."),
        ],
        reason: Annotated[
            str | None,
            Field(
                default=None,
                max_length=REASON_MAX_LENGTH,
                description=(
                    "Optional operator-supplied reason for aborting the "
                    "rotation (audit-log breadcrumb)."
                ),
            ),
        ] = None,
    ) -> AbortCredentialRotationOutput:
        handler = get_handler()
        principal_id = get_mcp_principal_id(ctx)
        await handler(
            AbortCredentialRotation(
                credential_id=credential_id,
                aborted_by=principal_id,
                reason=reason,
            ),
            principal_id=principal_id,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return AbortCredentialRotationOutput(credential_id=credential_id)
