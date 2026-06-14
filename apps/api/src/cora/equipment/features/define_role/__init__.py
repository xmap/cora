"""Vertical slice for the `DefineRole` command.

Module-as-namespace surface, symmetric with `define_family`:

    from cora.equipment.features import define_role

    cmd = define_role.DefineRole(
        name="Detector",
        docstring="Acquires 2D image frames on exposure or trigger.",
        required_affordances=frozenset({Affordance.IMAGEABLE}),
        optional_affordances=frozenset({Affordance.BINNABLE}),
        produces=frozenset({"Image"}),
        consumes=frozenset({"TriggerIn"}),
    )
    handler = define_role.bind(deps)
    role_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.equipment.features.define_role import tool
from cora.equipment.features.define_role.command import DefineRole
from cora.equipment.features.define_role.decider import decide
from cora.equipment.features.define_role.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.equipment.features.define_role.route import router

__all__ = [
    "DefineRole",
    "Handler",
    "IdempotentHandler",
    "bind",
    "decide",
    "router",
    "tool",
]
