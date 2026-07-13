"""Vertical slice for the `SealAllocation` command.

Module-as-namespace surface, symmetric with the other transition
command slices, plus the slice-owned TotalSpendReader seam:

    from cora.budget.features import seal_allocation

    cmd = seal_allocation.SealAllocation(allocation_id=UUID("..."))
    handler = seal_allocation.bind(deps, total_spend_reader=reader)
    await handler(cmd, principal_id=..., correlation_id=...)

`make_ledger_total_spend(spend_lookup)` builds the production reader
over `SpendLookup.find_total_spend`; `wire.py` and the CampaignClosed
sealer subscriber both bind it. `zero_total_spend` stays exported for
tests that seal without standing up a ledger.
"""

from cora.budget.features.seal_allocation import tool
from cora.budget.features.seal_allocation.command import SealAllocation
from cora.budget.features.seal_allocation.decider import decide
from cora.budget.features.seal_allocation.handler import (
    Handler,
    TotalSpendReader,
    bind,
    make_ledger_total_spend,
    zero_total_spend,
)
from cora.budget.features.seal_allocation.route import router

__all__ = [
    "Handler",
    "SealAllocation",
    "TotalSpendReader",
    "bind",
    "decide",
    "make_ledger_total_spend",
    "router",
    "tool",
    "zero_total_spend",
]
