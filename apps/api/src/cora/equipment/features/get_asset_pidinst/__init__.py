"""Vertical slice for the `GetAssetPidinst` query.

Module-as-namespace surface:

    from cora.equipment.features import get_asset_pidinst

    q = get_asset_pidinst.GetAssetPidinst(asset_id=...)
    handler = get_asset_pidinst.bind(deps)
    record = await handler(q, principal_id=..., correlation_id=...)

Slice E.1 of project_asset_persistent_id_design: PIDINST v1.0 read
route that closes the loop slice C left open. Composes
`AssetPidinstView` from the Asset / Model / Family aggregate-loader
output (NOT SQL JOINs across summary projections), then hands the
view to slice C's `to_pidinst_record` serializer.

No MCP `tool.py` in E.1 (L16 + L18 + D6); REST-only. Slice G's
agent-driven scenarios will add it.
"""

from cora.equipment.features.get_asset_pidinst.handler import Handler, bind
from cora.equipment.features.get_asset_pidinst.query import GetAssetPidinst
from cora.equipment.features.get_asset_pidinst.route import (
    PidinstRecordResponse,
    router,
)

__all__ = [
    "GetAssetPidinst",
    "Handler",
    "PidinstRecordResponse",
    "bind",
    "router",
]
