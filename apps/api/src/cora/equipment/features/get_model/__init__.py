"""Vertical slice for the `GetModel` query.

Module-as-namespace surface, symmetric with command slices:

    from cora.equipment.features import get_model

    q = get_model.GetModel(model_id=...)
    handler = get_model.bind(deps)
    model = await handler(q, principal_id=..., correlation_id=...)

Read slices have no decider (queries don't emit events); the handler
is a thin wrapper around `load_model`. The HTTP `router` and MCP
`tool` modules follow the `get_family` precedent.
"""

from cora.equipment.features.get_model import tool
from cora.equipment.features.get_model.handler import Handler, bind
from cora.equipment.features.get_model.query import GetModel
from cora.equipment.features.get_model.route import router

__all__ = [
    "GetModel",
    "Handler",
    "bind",
    "router",
    "tool",
]
