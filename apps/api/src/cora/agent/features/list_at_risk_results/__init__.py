"""Vertical slice for the `ListAtRiskResults` query.

Module-as-namespace surface, symmetric with command slices:

    from cora.agent.features import list_at_risk_results

    q = list_at_risk_results.ListAtRiskResults(language_model_id=...)
    handler = list_at_risk_results.bind(deps)
    view = await handler(q, principal_id=..., correlation_id=...)
"""

from cora.agent.features.list_at_risk_results import tool
from cora.agent.features.list_at_risk_results.handler import (
    AtRiskResultsView,
    Handler,
    bind,
)
from cora.agent.features.list_at_risk_results.query import ListAtRiskResults
from cora.agent.features.list_at_risk_results.route import router

__all__ = [
    "AtRiskResultsView",
    "Handler",
    "ListAtRiskResults",
    "bind",
    "router",
    "tool",
]
