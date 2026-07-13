"""Vertical slice for the `AmendAllocationCeiling` command.

Module-as-namespace surface, symmetric with the other transition
command slices:

    from cora.budget.features import amend_allocation_ceiling

    cmd = amend_allocation_ceiling.AmendAllocationCeiling(
        allocation_id=UUID("..."), ceiling_usd=18000.0,
    )
    handler = amend_allocation_ceiling.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.budget.features.amend_allocation_ceiling import tool
from cora.budget.features.amend_allocation_ceiling.command import AmendAllocationCeiling
from cora.budget.features.amend_allocation_ceiling.decider import decide
from cora.budget.features.amend_allocation_ceiling.handler import Handler, bind
from cora.budget.features.amend_allocation_ceiling.route import router

__all__ = [
    "AmendAllocationCeiling",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
