"""Application handler for the `update_agent_budget` slice.

Built on the hoisted `make_agent_update_handler`
factory.
"""

from typing import Protocol
from uuid import UUID

from cora.agent._agent_update_handler import make_agent_update_handler
from cora.agent.features.update_agent_budget.command import UpdateAgentBudget
from cora.agent.features.update_agent_budget.decider import decide
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID


class Handler(Protocol):
    """Callable interface every update_agent_budget handler implements."""

    async def __call__(
        self,
        command: UpdateAgentBudget,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a update_agent_budget handler closed over the shared deps."""
    return make_agent_update_handler(
        deps,
        command_name="UpdateAgentBudget",
        log_prefix="update_agent_budget",
        decide_fn=decide,
    )
