"""MCP tool for the `define_policy` slice.

Same shape as `define_zone` / `define_conduit` MCP tools. Permission
sets arrive as MCP-typed `list[UUID]` / `list[str]` and convert to
`frozenset` before constructing the command.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.trust.aggregates.policy import POLICY_NAME_MAX_LENGTH
from cora.trust.features.define_policy.command import DefinePolicy
from cora.trust.features.define_policy.handler import IdempotentHandler


class DefinePolicyOutput(BaseModel):
    """Structured output of the `define_policy` MCP tool."""

    policy_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `define_policy` tool on the given MCP server."""

    @mcp.tool(
        name="define_policy",
        description="Define a new authorization Policy for a Conduit.",
    )
    async def define_policy_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=POLICY_NAME_MAX_LENGTH,
                description="Display name for the new policy.",
            ),
        ],
        conduit_id: Annotated[
            UUID,
            Field(
                description=(
                    "UUID of the Conduit this policy governs (not validated for existence)."
                ),
            ),
        ],
        permitted_principal_ids: Annotated[
            list[UUID],
            Field(
                description=("Principals (UUIDs) allowed via this conduit. Empty -> deny-all."),
            ),
        ],
        permitted_commands: Annotated[
            list[str],
            Field(
                description=("Command names allowed via this conduit. Empty -> deny-all."),
            ),
        ],
        surface_id: Annotated[
            UUID,
            Field(
                description=(
                    "UUID of the Surface this policy governs. Required: every policy "
                    "binds a concrete Surface seeded by the deployment; the nil "
                    "sentinel is rejected (InvalidPolicySurfaceError)."
                ),
            ),
        ],
    ) -> DefinePolicyOutput:
        handler = get_handler()
        policy_id = await handler(
            DefinePolicy(
                name=name,
                conduit_id=conduit_id,
                permitted_principal_ids=frozenset(permitted_principal_ids),
                permitted_commands=frozenset(permitted_commands),
                surface_id=surface_id,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return DefinePolicyOutput(policy_id=policy_id)
