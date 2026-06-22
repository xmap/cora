"""Application handler for the `version_agent` slice.

Built on the hoisted `make_agent_update_handler` factory along
with the 4 other Agent transition slices (suspend / resume /
grant_tool / revoke_tool / update_budget). Pre-hoist this slice
had a longhand body; the migration is zero behavior change.
"""

from typing import Protocol
from uuid import UUID

from cora.agent._agent_update_handler import make_agent_update_handler
from cora.agent.features.version_agent.command import VersionAgent
from cora.agent.features.version_agent.decider import decide
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID


class Handler(Protocol):
    """Callable interface every version_agent handler implements."""

    async def __call__(
        self,
        command: VersionAgent,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a version_agent handler closed over the shared deps."""
    return make_agent_update_handler(
        deps,
        command_name="VersionAgent",
        log_prefix="version_agent",
        decide_fn=decide,
    )
