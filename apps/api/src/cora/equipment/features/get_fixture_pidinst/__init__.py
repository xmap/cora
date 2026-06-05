"""Vertical slice for the `get_fixture_pidinst` query.

Read-side slice of project_fixture_pidinst_design: PIDINST v1.0 read
route for the Fixture tier. The view assembler composes a
`FixturePidinstView` one level deep (bound Assets only; sub-Fixtures
NOT recursed into per L24). The route serializes the view to a
`PidinstRecord` via `to_fixture_pidinst_record` and returns the
`PidinstRecordResponse` JSON-LD wire shape on a 200.

Module-as-namespace surface, mirroring `get_asset_pidinst`:

    from cora.equipment.features import get_fixture_pidinst

    handler = get_fixture_pidinst.bind(deps)
    view = await handler(fixture_id, principal_id=..., correlation_id=...)
"""

from cora.equipment.features.get_fixture_pidinst import tool
from cora.equipment.features.get_fixture_pidinst.handler import Handler, bind
from cora.equipment.features.get_fixture_pidinst.route import router

__all__ = [
    "Handler",
    "bind",
    "router",
    "tool",
]
