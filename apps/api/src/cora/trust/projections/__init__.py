"""Trust BC projections.

Multi-aggregate BC: each of Zone / Conduit / Policy / Visit gets its
own projection module under this package, mirroring Equipment's layout
(asset.py + capability.py) and Recipe's (method.py + practice.py +
plan.py). Add a new projection by creating a new module here +
re-exporting its class + adding it to `register_trust_projections`.
"""

from cora.trust.projections.conduit import ConduitSummaryProjection
from cora.trust.projections.policy import PolicySummaryProjection
from cora.trust.projections.ratification_coverage import RatificationCoverageProjection
from cora.trust.projections.surface_active_visit import (
    SurfaceActiveVisit,
    SurfaceActiveVisitProjection,
    load_surface_active_visit,
)
from cora.trust.projections.visit import VisitSummaryProjection
from cora.trust.projections.visit_presence import VisitPresenceProjection
from cora.trust.projections.zone import ZoneSummaryProjection

__all__ = [
    "ConduitSummaryProjection",
    "PolicySummaryProjection",
    "RatificationCoverageProjection",
    "SurfaceActiveVisit",
    "SurfaceActiveVisitProjection",
    "VisitPresenceProjection",
    "VisitSummaryProjection",
    "ZoneSummaryProjection",
    "load_surface_active_visit",
]
