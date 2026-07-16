"""Vertical slice for the `ActivateAllocation` command.

Module-as-namespace surface, symmetric with the other transition
command slices:

    from cora.budget.features import activate_allocation

    cmd = activate_allocation.ActivateAllocation(allocation_id=UUID("..."))
    handler = activate_allocation.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.budget.features.activate_allocation import tool
from cora.budget.features.activate_allocation.command import ActivateAllocation
from cora.budget.features.activate_allocation.decider import decide
from cora.budget.features.activate_allocation.handler import Handler, bind
from cora.budget.features.activate_allocation.route import router

__all__ = [
    "ActivateAllocation",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
