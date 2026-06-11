"""The `ListClearances` query -- intent dataclass for this read slice.

Mirrors `ListProcedures`: cursor pagination + optional template_id /
template_code / status / risk_band / facility_code / binds_to_*_id
filters. Each filter is
optional; passing None means "don't filter on this dimension".

`limit` defaults to 50 (capped at 100 in the route layer per the
8e-1c convention). `cursor` is opaque base64-encoded
`(registered_at, clearance_id)`.

The 4 binds_to_* filters use UUID[] GIN indexes on the projection;
each is matched against its corresponding binding-id array column
(SubjectBinding -> subject_binding_ids, AssetBinding -> asset_binding_ids,
RunBinding -> run_binding_ids, ProcedureBinding -> procedure_binding_ids).
ExternalRefBinding refs are not filterable today; defer until consumer
demands.
"""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

ClearanceStatusFilter = Literal[
    "Defined",
    "Submitted",
    "UnderReview",
    "Approved",
    "Active",
    "Expired",
    "Rejected",
    "Superseded",
]
RiskBandFilter = Literal["Green", "Yellow", "Red"]


@dataclass(frozen=True)
class ListClearances:
    """List clearances with cursor pagination + multi-filter support."""

    cursor: str | None = None
    limit: int = 50
    template_id: UUID | None = None
    template_code: str | None = None
    status: ClearanceStatusFilter | None = None
    risk_band: RiskBandFilter | None = None
    facility_code: str | None = None
    binds_to_subject_id: UUID | None = None
    binds_to_asset_id: UUID | None = None
    binds_to_run_id: UUID | None = None
    binds_to_procedure_id: UUID | None = None
