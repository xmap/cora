"""MCP tool for the `list_permissions` query slice.

Same handler the REST route uses. The tool description warns agents
NOT to use the result for authorization decisions (per the anti-hook):
the probe (`check_permissions`) is the authoritative diagnostic.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.trust.features.list_permissions.handler import Handler
from cora.trust.features.list_permissions.query import ListPermissions


class ListPermissionsOutput(BaseModel):
    """Structured output of the `list_permissions` MCP tool."""

    policy_id: UUID
    evaluated_principal_id: UUID
    evaluated_conduit_id: UUID
    surface_id: UUID = Field(
        description=(
            "Arrival surface the listing is scoped to. The Policy matches its surface by "
            "strict equality, so it permits nothing on any other surface and "
            "`permitted_commands` must not be read as holding everywhere."
        ),
    )
    permitted_commands: list[str]
    incomplete: bool = Field(
        description=("True if some permissions could not be enumerated (always False at v1)."),
    )


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `list_permissions` tool on the given MCP server."""

    @mcp.tool(
        name="list_permissions",
        description=(
            "List a Policy's permitted commands for a (principal, conduit). "
            "Returns the sorted command set the principal can execute. "
            "NOTE: this is for UX / debugging only. Do NOT use the returned "
            "set to drive authorization decisions; only `check_permissions` "
            "or attempting the command is authoritative."
        ),
    )
    async def list_permissions_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        policy_id: Annotated[UUID, Field(description="Target policy's id.")],
        evaluated_principal_id: Annotated[
            UUID,
            Field(description="Principal whose permissions are being enumerated."),
        ],
        evaluated_conduit_id: Annotated[
            UUID,
            Field(description="Conduit through which the commands would be issued."),
        ],
    ) -> ListPermissionsOutput:
        handler = get_handler()
        result = await handler(
            ListPermissions(
                policy_id=policy_id,
                evaluated_principal_id=evaluated_principal_id,
                evaluated_conduit_id=evaluated_conduit_id,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        if result is None:
            msg = f"Policy {policy_id} not found"
            raise ValueError(msg)
        return ListPermissionsOutput(
            policy_id=result.policy_id,
            evaluated_principal_id=result.evaluated_principal_id,
            evaluated_conduit_id=result.evaluated_conduit_id,
            surface_id=result.surface_id,
            permitted_commands=result.permitted_commands,
            incomplete=result.incomplete,
        )
