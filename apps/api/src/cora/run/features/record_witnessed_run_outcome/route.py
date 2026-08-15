"""Stub route module for `record_witnessed_run_outcome` (in-process-only slice).

Per the roadmap's anti-scope: no operator path to a witnessed terminal,
mirroring `record_witnessed_run`'s own lock. No REST route, no MCP tool.
In-process adapters (the RunWitness runtime) call
`RunHandlers.record_witnessed_run_outcome(...)` directly.

The empty `router` exists only to satisfy the slice-file-shape +
routes-completeness architecture fitness functions; no routes are
registered on it.
"""

from fastapi import APIRouter, Depends

from cora.infrastructure.routing import get_surface_id

router = APIRouter()

_STUB_DEPENDS = Depends(get_surface_id)
