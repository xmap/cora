"""Vertical slice for the `GetEnclosureHistory` query.

Module-as-namespace surface, symmetric with `get_run_history`:

    from cora.enclosure.features import get_enclosure_history

    q = get_enclosure_history.GetEnclosureHistory(enclosure_id=...)
    handler = get_enclosure_history.bind(deps)
    view = await handler(q, principal_id=..., correlation_id=...)
"""

from cora.enclosure.features.get_enclosure_history import tool
from cora.enclosure.features.get_enclosure_history.handler import Handler, bind
from cora.enclosure.features.get_enclosure_history.query import GetEnclosureHistory
from cora.enclosure.features.get_enclosure_history.route import router

__all__ = [
    "GetEnclosureHistory",
    "Handler",
    "bind",
    "router",
    "tool",
]
