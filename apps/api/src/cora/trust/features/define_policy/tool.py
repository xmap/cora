"""MCP tool for the `define_policy` slice.

Same shape as `define_zone` / `define_conduit` MCP tools. Grants arrive
either as an exact mapping or as the two cross-producted lists, and
`_to_command` converts whichever was given into the single command
shape the domain accepts.
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


def _to_command(
    *,
    name: str,
    conduit_id: UUID,
    surface_id: UUID,
    grants: dict[UUID, list[str]] | None,
    permitted_principal_ids: list[UUID] | None,
    permitted_commands: list[str] | None,
) -> DefinePolicy:
    """Translate either accepted argument shape into the one command shape.

    Mirrors the REST route's `_to_command` and rejects the same two
    mistakes, because a tool that quietly picked a winner between the
    shapes would let an agent grant a cross-product while believing it
    had granted a mapping. That is the exact over-grant pairs exist to
    stop, and an agent-facing surface is where it would be least
    visible.
    """
    pair_given = permitted_principal_ids is not None or permitted_commands is not None
    if grants is not None and pair_given:
        msg = (
            "Give either 'grants' or the permitted_principal_ids/permitted_commands pair, not both."
        )
        raise ValueError(msg)
    if grants is not None:
        return DefinePolicy(
            name=name,
            conduit_id=conduit_id,
            grants=frozenset(
                (principal_id, command_name)
                for principal_id, command_names in grants.items()
                for command_name in command_names
            ),
            surface_id=surface_id,
        )
    if permitted_principal_ids is None or permitted_commands is None:
        msg = "Provide 'grants', or both 'permitted_principal_ids' and 'permitted_commands'."
        raise ValueError(msg)
    return DefinePolicy.from_cross_product(
        name=name,
        conduit_id=conduit_id,
        permitted_principal_ids=permitted_principal_ids,
        permitted_commands=permitted_commands,
        surface_id=surface_id,
    )


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
        grants: Annotated[
            dict[UUID, list[str]] | None,
            Field(
                default=None,
                description=(
                    "Preferred. Exact grants: which command names each "
                    "principal may issue. Give this OR the "
                    "permitted_principal_ids/permitted_commands pair, not "
                    "both. Empty mapping -> deny-all."
                ),
            ),
        ] = None,
        permitted_principal_ids: Annotated[
            list[UUID] | None,
            Field(
                default=None,
                description=(
                    "Grants EVERY listed principal EVERY name in "
                    "permitted_commands. Prefer 'grants' unless they really "
                    "do share one command list. Must be given with "
                    "permitted_commands. Empty -> deny-all."
                ),
            ),
        ] = None,
        permitted_commands: Annotated[
            list[str] | None,
            Field(
                default=None,
                description=(
                    "Command names allowed via this conduit, to every "
                    "principal in permitted_principal_ids. Must be given "
                    "with it. Empty -> deny-all."
                ),
            ),
        ] = None,
    ) -> DefinePolicyOutput:
        handler = get_handler()
        policy_id = await handler(
            _to_command(
                name=name,
                conduit_id=conduit_id,
                surface_id=surface_id,
                grants=grants,
                permitted_principal_ids=permitted_principal_ids,
                permitted_commands=permitted_commands,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return DefinePolicyOutput(policy_id=policy_id)
