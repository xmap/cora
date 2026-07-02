"""MCP tool for the `revoke_grant` slice.

Surfaces the same handler the REST route uses, exposed as a Model Context
Protocol tool. Mirrors `revoke_credential`'s tool surface. `reason` is
required and bounded; the `principal_id` argument is the grant to remove
(a bare UUID that works identically for a human or an agent principal).
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.trust.features.revoke_grant.command import RevokeGrant
from cora.trust.features.revoke_grant.handler import Handler


class RevokeGrantOutput(BaseModel):
    """Structured output of the `revoke_grant` MCP tool."""

    policy_id: UUID
    principal_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `revoke_grant` tool on the given MCP server."""

    @mcp.tool(
        name="revoke_grant",
        description=(
            "Revoke one principal's grant from a Policy: remove the principal "
            "from the policy's permitted set so it can no longer issue the "
            "policy's commands. Works identically for a human or an agent "
            "principal (the id is opaque). Silently idempotent: revoking a "
            "principal that is not in the set is a no-op. Raises if the policy "
            "does not exist. Any in-flight runs the revoked principal has "
            "authority over are held by a separate compensation reaction."
        ),
    )
    async def revoke_grant_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        policy_id: Annotated[
            UUID,
            Field(description="Target policy's id."),
        ],
        principal_id: Annotated[
            UUID,
            Field(description="The principal whose grant is removed from the policy."),
        ],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description=(
                    "Operator-supplied reason for revoking the grant "
                    "(audit-log breadcrumb). Flows onto the PolicyGrantRevoked "
                    "event and the downstream compensation Decision."
                ),
            ),
        ],
    ) -> RevokeGrantOutput:
        handler = get_handler()
        await handler(
            RevokeGrant(policy_id=policy_id, principal_id=principal_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RevokeGrantOutput(policy_id=policy_id, principal_id=principal_id)
