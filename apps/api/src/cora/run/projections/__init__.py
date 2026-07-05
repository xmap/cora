"""Run BC projections.

Add a new projection by creating a new module here + re-exporting its class +
adding it to `register_run_projections`. RunActorInvolvementProjection backs the
kill-switch's actor-involvement resolver (which in-flight runs a principal drives).
"""

from cora.run.projections.actor_involvement import RunActorInvolvementProjection
from cora.run.projections.summary import RunSummaryProjection

__all__ = ["RunActorInvolvementProjection", "RunSummaryProjection"]
