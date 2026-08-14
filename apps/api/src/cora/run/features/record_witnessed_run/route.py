"""Stub route module for `record_witnessed_run` (in-process-only slice).

Per the roadmap's anti-scope: no operator path to a witnessed genesis. No
REST route, no MCP tool, typed `MonitorSourceId` and a `trigger` guard,
mirroring the shipped `observe_enclosure_status` lock. This is the wall
that stops the witnessed path being used to launder around a driven
refusal. In-process adapters (the capture-watch runtime) call
`RunHandlers.record_witnessed_run(...)` directly.

The empty `router` exists only to satisfy the slice-file-shape +
routes-completeness architecture fitness functions; no routes are
registered on it.
"""

from fastapi import APIRouter, Depends

from cora.infrastructure.routing import get_surface_id

router = APIRouter()

_STUB_DEPENDS = Depends(get_surface_id)
