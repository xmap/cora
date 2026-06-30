"""Vertical slice for the `DiscardDistribution` command.

Module-as-namespace surface:

    from cora.data.features import discard_distribution

    cmd = discard_distribution.DiscardDistribution(
        distribution_id=...,
        reason="bytes reclaimed from cold tier per retention policy",
    )
    handler = discard_distribution.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.data.features.discard_distribution import tool
from cora.data.features.discard_distribution.command import DiscardDistribution
from cora.data.features.discard_distribution.context import DiscardDistributionContext
from cora.data.features.discard_distribution.decider import decide
from cora.data.features.discard_distribution.handler import Handler, bind
from cora.data.features.discard_distribution.route import router

__all__ = [
    "DiscardDistribution",
    "DiscardDistributionContext",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
