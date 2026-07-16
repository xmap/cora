"""Vertical slice for the `VoidAllocation` command.

Module-as-namespace surface, symmetric with the other transition
command slices:

    from cora.budget.features import void_allocation

    cmd = void_allocation.VoidAllocation(
        allocation_id=UUID("..."), reason="Granted against the wrong cycle",
    )
    handler = void_allocation.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.budget.features.void_allocation import tool
from cora.budget.features.void_allocation.command import VoidAllocation
from cora.budget.features.void_allocation.decider import decide
from cora.budget.features.void_allocation.handler import Handler, bind
from cora.budget.features.void_allocation.route import router

__all__ = [
    "Handler",
    "VoidAllocation",
    "bind",
    "decide",
    "router",
    "tool",
]
