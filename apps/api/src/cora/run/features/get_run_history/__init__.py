"""Vertical slice for the `GetRunHistory` query.

Module-as-namespace surface, symmetric with `get_run`:

    from cora.run.features import get_run_history

    q = get_run_history.GetRunHistory(run_id=...)
    handler = get_run_history.bind(deps, observation_trail=...)
    view = await handler(q, principal_id=..., correlation_id=...)
"""

from cora.run.features.get_run_history import tool
from cora.run.features.get_run_history.handler import Handler, bind
from cora.run.features.get_run_history.query import GetRunHistory
from cora.run.features.get_run_history.route import router

__all__ = [
    "GetRunHistory",
    "Handler",
    "bind",
    "router",
    "tool",
]
