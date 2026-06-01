"""Vertical slice for the `RemoveModelFamily` command.

Module-as-namespace surface:

    from cora.equipment.features import remove_model_family

    cmd = remove_model_family.RemoveModelFamily(model_id=..., family_id=...)
    handler = remove_model_family.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.equipment.features.remove_model_family import tool
from cora.equipment.features.remove_model_family.command import RemoveModelFamily
from cora.equipment.features.remove_model_family.decider import decide
from cora.equipment.features.remove_model_family.handler import Handler, bind
from cora.equipment.features.remove_model_family.route import router

__all__ = [
    "Handler",
    "RemoveModelFamily",
    "bind",
    "decide",
    "router",
    "tool",
]
