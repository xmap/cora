"""Enclosure bounded context.

Owns observed-permit state for physical enclosures in CORA:

  - `Enclosure` aggregate: a physical enclosure (hutch, cabinet,
    interlocked room) whose permit-to-occupy or permit-to-operate
    is observed via external monitor. Multiple instances at runtime,
    one per enclosed volume that gates downstream work. The enclosure
    is anchored to the containing geography it sits within (the
    Federation `Facility` Site / Area, referenced via `facility_code`);
    the permit observation axis is `Enclosure`.

Observation-axis-only BC. CORA does NOT issue, grant, revoke, or
arbitrate permits; an external interlock system is the source of
truth. CORA reflects the observed status (`Permitted`,
`NotPermitted`, `Unknown`) into the spine so other BCs can gate
work on it. See [[project_enclosure_stage1_design]] for the
anti-locks (D6.L2 observation-axis-only, D9-L1 zero severity
scalars, D10-L1 no Bypassed state).

Layout:
    aggregates/<aggregate>/   -- aggregate state, events union, evolver
    features/<verb>/          -- one vertical slice per command
    projections/              -- read-side summary writers
    routes.py                 -- register_enclosure_routes(app)
    tools.py                  -- register_enclosure_tools(mcp, get_handlers=...)
    wire.py                   -- wire_enclosure(deps) -> EnclosureHandlers
    _projections.py           -- register_enclosure_projections(registry, deps)
"""

from cora.enclosure._projections import register_enclosure_projections
from cora.enclosure.errors import UnauthorizedError
from cora.enclosure.routes import register_enclosure_routes
from cora.enclosure.tools import register_enclosure_tools
from cora.enclosure.wire import EnclosureHandlers, wire_enclosure

__all__ = [
    "EnclosureHandlers",
    "UnauthorizedError",
    "register_enclosure_projections",
    "register_enclosure_routes",
    "register_enclosure_tools",
    "wire_enclosure",
]
