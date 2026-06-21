"""Vertical slice for the `AssignAssetPersistentId` command.

Assigns a `PersistentIdentifier` (PIDINST v1.0 Property 1) to an
existing Asset. Set-once at the aggregate level: a second assign
raises `AssetPersistentIdAlreadyAssignedError`. Decommissioned
assets reject the assign with `AssetPersistentIdAssignmentForbiddenError`.

Server-mint posture per Lock 12: the route forwards
`(asset_id, scheme, suffix)` to the handler, and the handler closure
resolves the `PersistentIdentifier` from the `PersistentIdentifierMinter`
port (`StubPersistentIdentifierMinter` in F.1;
`DataCitePersistentIdentifierMinter` in F.2) before invoking the pure
decider. One minter call site (the handler), not two.

Module-as-namespace surface:

    from cora.equipment.features import assign_asset_persistent_id

    cmd = assign_asset_persistent_id.AssignAssetPersistentId(
        asset_id=...,
        scheme=PersistentIdentifierScheme.DOI,
        suffix="APS-2BM-CAM-001",
    )
    handler = assign_asset_persistent_id.bind(deps)
    persistent_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.equipment.features.assign_asset_persistent_id import tool
from cora.equipment.features.assign_asset_persistent_id.command import AssignAssetPersistentId
from cora.equipment.features.assign_asset_persistent_id.decider import decide
from cora.equipment.features.assign_asset_persistent_id.handler import Handler, bind
from cora.equipment.features.assign_asset_persistent_id.route import router

__all__ = [
    "AssignAssetPersistentId",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
