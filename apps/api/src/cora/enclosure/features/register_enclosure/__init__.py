"""Vertical slice for the `RegisterEnclosure` command.

Module-as-namespace surface, symmetric with the other create-style
command slices:

    from cora.enclosure.features import register_enclosure

    cmd = register_enclosure.RegisterEnclosure(
        name="...",
        facility_code="...",
    )
    handler = register_enclosure.bind(deps)
    enclosure_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.enclosure.features.register_enclosure import tool
from cora.enclosure.features.register_enclosure.command import RegisterEnclosure
from cora.enclosure.features.register_enclosure.decider import decide
from cora.enclosure.features.register_enclosure.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.enclosure.features.register_enclosure.route import router

__all__ = [
    "Handler",
    "IdempotentHandler",
    "RegisterEnclosure",
    "bind",
    "decide",
    "router",
    "tool",
]
