"""Enclosure bounded context.

Owns observed-permit state for physical enclosures in CORA:

  - `Enclosure` aggregate: a physical enclosure (hutch, cabinet,
    interlocked room) whose permit-to-occupy or permit-to-operate
    is observed via external monitor. Multiple instances at runtime,
    one per enclosed volume that gates downstream work. The
    enclosure as physical structure stays as an `Asset` (referenced
    via `containing_asset_id`); the permit observation axis is
    `Enclosure`.

Observation-axis-only BC. CORA does NOT issue, grant, revoke, or
arbitrate permits; an external interlock system is the source of
truth. CORA reflects the observed status (`Permitted`,
`NotPermitted`, `Unknown`) into the spine so other BCs can gate
work on it. See [[project_enclosure_stage1_design]] for the
anti-locks (D6.L2 observation-axis-only, D9-L1 zero severity
scalars, D10-L1 no Bypassed state).

Layout:
    aggregates/<aggregate>/   -- aggregate state, events union, evolver
    routes.py                 -- register_enclosure_routes(app)
    tools.py                  -- register_enclosure_tools(mcp, get_handlers=...)
"""

from cora.enclosure.routes import register_enclosure_routes
from cora.enclosure.tools import register_enclosure_tools

__all__ = [
    "register_enclosure_routes",
    "register_enclosure_tools",
]
