"""Vertical slice for the `MarkDistributionStale` command.

Module-as-namespace surface:

    from cora.data.features import mark_distribution_stale

    cmd = mark_distribution_stale.MarkDistributionStale(
        distribution_id=...,
        reason="storage array declared dead by operations, bytes unreachable",
    )
    handler = mark_distribution_stale.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.data.features.mark_distribution_stale import tool
from cora.data.features.mark_distribution_stale.command import MarkDistributionStale
from cora.data.features.mark_distribution_stale.decider import decide
from cora.data.features.mark_distribution_stale.handler import Handler, bind
from cora.data.features.mark_distribution_stale.route import router

__all__ = [
    "Handler",
    "MarkDistributionStale",
    "bind",
    "decide",
    "router",
    "tool",
]
