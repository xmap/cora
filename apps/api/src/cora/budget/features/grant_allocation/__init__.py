"""Vertical slice for the `GrantAllocation` command.

Module-as-namespace surface, symmetric with the other create-style
command slices:

    from cora.budget.features import grant_allocation

    cmd = grant_allocation.GrantAllocation(
        ceiling_usd=25000.0,
        note="FY26 imaging award",
    )
    handler = grant_allocation.bind(deps)
    allocation_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.budget.features.grant_allocation import tool
from cora.budget.features.grant_allocation.command import GrantAllocation
from cora.budget.features.grant_allocation.decider import decide
from cora.budget.features.grant_allocation.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.budget.features.grant_allocation.route import router

__all__ = [
    "GrantAllocation",
    "Handler",
    "IdempotentHandler",
    "bind",
    "decide",
    "router",
    "tool",
]
