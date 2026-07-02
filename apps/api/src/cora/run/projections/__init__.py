"""Run BC projections.

Two projections today: RunSummaryProjection (the GET /runs read model)
and RunActorInvolvementProjection (the cross-BC actor -> in-flight-runs
index backing the authority-revocation kill-switch). Add a new projection
by creating a new module here + re-exporting its class + adding it to
`register_run_projections`.
"""

from cora.run.projections.actor_involvement import RunActorInvolvementProjection
from cora.run.projections.summary import RunSummaryProjection

__all__ = ["RunActorInvolvementProjection", "RunSummaryProjection"]
