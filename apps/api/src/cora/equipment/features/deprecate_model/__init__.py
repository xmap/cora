"""Vertical slice for the `DeprecateModel` command.

Module-as-namespace surface:

    from cora.equipment.features import deprecate_model

    cmd = deprecate_model.DeprecateModel(
        model_id=...,
        reason="Vendor end-of-life 2026-Q3; replaced by ANT130-LZS",
    )
    handler = deprecate_model.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.equipment.features.deprecate_model import tool
from cora.equipment.features.deprecate_model.command import DeprecateModel
from cora.equipment.features.deprecate_model.decider import decide
from cora.equipment.features.deprecate_model.handler import Handler, bind
from cora.equipment.features.deprecate_model.route import router

__all__ = [
    "DeprecateModel",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
