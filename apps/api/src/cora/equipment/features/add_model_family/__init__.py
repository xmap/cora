"""Vertical slice for the `AddModelFamily` command.

Module-as-namespace surface:

    from cora.equipment.features import add_model_family

    cmd = add_model_family.AddModelFamily(model_id=..., family_id=...)
    handler = add_model_family.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.equipment.features.add_model_family import tool
from cora.equipment.features.add_model_family.command import AddModelFamily
from cora.equipment.features.add_model_family.decider import decide
from cora.equipment.features.add_model_family.handler import Handler, bind
from cora.equipment.features.add_model_family.route import router

__all__ = [
    "AddModelFamily",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
