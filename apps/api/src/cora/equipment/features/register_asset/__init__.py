"""Vertical slice for the `RegisterAsset` command.

Module-as-namespace surface, symmetric with the other create-style
command slices:

    from cora.equipment.features import register_asset

    cmd = register_asset.RegisterAsset(name=..., tier=..., parent_id=...)
    handler = register_asset.bind(deps)
    asset_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.equipment.features.register_asset import tool
from cora.equipment.features.register_asset.command import RegisterAsset
from cora.equipment.features.register_asset.decider import decide
from cora.equipment.features.register_asset.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.equipment.features.register_asset.route import router

__all__ = [
    "Handler",
    "IdempotentHandler",
    "RegisterAsset",
    "bind",
    "decide",
    "router",
    "tool",
]
