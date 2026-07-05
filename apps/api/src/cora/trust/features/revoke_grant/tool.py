"""MCP tool for the `revoke_grant` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.trust.features.revoke_grant.command import RevokePolicyGrant
from cora.trust.features.revoke_grant.handler import Handler


class RevokeGrantOutput(BaseModel):
    """Structured output of the `revoke_grant` MCP tool."""

    policy_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `revoke_grant` tool on the given MCP server."""

    @mcp.tool(
        name="revoke_grant",
        description=(
            "Revoke one principal's grant from a Policy's allow-list. Silently "
            "idempotent: revoking an already-absent principal is a no-op. This "
            "is the kill-switch trigger: a separate subscriber reacts to hold "
            "the revoked principal's in-flight runs. Reason REQUIRED. Reason "
            "MUST NOT contain PII."
        ),
    )
    async def revoke_grant_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        policy_id: Annotated[UUID, Field(description="Target Policy's id.")],
        permitted_principal_id: Annotated[
            UUID, Field(description="Principal whose grant is revoked from the policy.")
        ],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description="Operator-supplied reason for the revocation (no PII).",
            ),
        ],
    ) -> RevokeGrantOutput:
        handler = get_handler()
        await handler(
            RevokePolicyGrant(
                policy_id=policy_id,
                permitted_principal_id=permitted_principal_id,
                reason=reason,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RevokeGrantOutput(policy_id=policy_id)
