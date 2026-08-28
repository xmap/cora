"""The `ListEnclosures` query: intent dataclass for this read slice.

Mirrors `ListClearances`: cursor pagination + optional `lifecycle` /
`permit_status` / `facility_code` filters. Each filter is optional;
passing `None` means "don't filter on this dimension".

The three filters match the projection's two indexes exactly:
`proj_enclosure_summary_gate_idx (lifecycle, permit_status)` and
`proj_enclosure_summary_facility_code_idx (facility_code) WHERE
lifecycle = 'Active'`.

`limit` defaults to 50 (capped at 100 in the route layer per the
existing `list_*` convention). `cursor` is opaque base64-encoded
`(registered_at, enclosure_id)`.
"""

from dataclasses import dataclass
from typing import Literal

LifecycleFilter = Literal["Active", "Decommissioned"]
PermitStatusFilter = Literal["Unknown", "Permitted", "NotPermitted"]


@dataclass(frozen=True)
class ListEnclosures:
    """List enclosures with cursor pagination + lifecycle / permit_status / facility_code filters.

    Cursor pagination is keyed on (registered_at, enclosure_id).
    """

    cursor: str | None = None
    limit: int = 50
    lifecycle: LifecycleFilter | None = None
    permit_status: PermitStatusFilter | None = None
    facility_code: str | None = None
