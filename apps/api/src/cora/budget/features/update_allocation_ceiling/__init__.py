"""Vertical slice for the `UpdateAllocationCeiling` command.

Module-as-namespace surface, symmetric with the other transition
command slices:

    from cora.budget.features import update_allocation_ceiling

    cmd = update_allocation_ceiling.UpdateAllocationCeiling(
        allocation_id=UUID("..."), ceiling_usd=18000.0,
    )
    handler = update_allocation_ceiling.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.budget.features.update_allocation_ceiling import tool
from cora.budget.features.update_allocation_ceiling.command import UpdateAllocationCeiling
from cora.budget.features.update_allocation_ceiling.decider import decide
from cora.budget.features.update_allocation_ceiling.handler import Handler, bind
from cora.budget.features.update_allocation_ceiling.route import router

__all__ = [
    "Handler",
    "UpdateAllocationCeiling",
    "bind",
    "decide",
    "router",
    "tool",
]
