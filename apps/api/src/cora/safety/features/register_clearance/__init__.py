"""Vertical slice for the `RegisterClearance` command.

Module-as-namespace surface, symmetric with the other create-style
command slices:

    from cora.safety.features import register_clearance

    cmd = register_clearance.RegisterClearance(template_id=..., title="...", bindings=...)
    handler = register_clearance.bind(deps)
    clearance_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.safety.features.register_clearance import tool
from cora.safety.features.register_clearance.command import RegisterClearance
from cora.safety.features.register_clearance.decider import decide
from cora.safety.features.register_clearance.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.safety.features.register_clearance.route import router

__all__ = [
    "Handler",
    "IdempotentHandler",
    "RegisterClearance",
    "bind",
    "decide",
    "router",
    "tool",
]
