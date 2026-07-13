"""Vertical slice for the `SealAllocation` command.

Module-as-namespace surface, symmetric with the other transition
command slices, plus the slice-owned TotalSpendReader seam:

    from cora.budget.features import seal_allocation

    cmd = seal_allocation.SealAllocation(allocation_id=UUID("..."))
    handler = seal_allocation.bind(deps, total_spend_reader=reader)
    await handler(cmd, principal_id=..., correlation_id=...)

`zero_total_spend` is the stage-A reader (`wire.py` binds it); stage
C replaces it with the SpendLookup-backed fold without touching this
slice.
"""

from cora.budget.features.seal_allocation import tool
from cora.budget.features.seal_allocation.command import SealAllocation
from cora.budget.features.seal_allocation.decider import decide
from cora.budget.features.seal_allocation.handler import (
    Handler,
    TotalSpendReader,
    bind,
    zero_total_spend,
)
from cora.budget.features.seal_allocation.route import router

__all__ = [
    "Handler",
    "SealAllocation",
    "TotalSpendReader",
    "bind",
    "decide",
    "router",
    "tool",
    "zero_total_spend",
]
