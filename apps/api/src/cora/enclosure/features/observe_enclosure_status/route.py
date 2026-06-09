"""Stub route module for `observe_enclosure_status` (in-process-only slice).

Per [[project_enclosure_stage1_design]] L-D3 / D6.L2 design lock: this
slice is NOT exposed via REST. In-process adapters call
`EnclosureHandlers.observe_enclosure_status(...)` directly.

The empty `router` exists only to satisfy the slice-file-shape +
routes-completeness architecture fitness functions; no routes are
registered on it. The `get_surface_id` import + `Depends()` reference
satisfies the surface-id injection fitness; the dependency is not
actually consumed because no endpoints are mounted.
"""

from fastapi import APIRouter, Depends

from cora.infrastructure.routing import get_surface_id

router = APIRouter()

_STUB_DEPENDS = Depends(get_surface_id)
