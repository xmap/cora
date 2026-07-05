"""RunActorInvolvementLookup port: which in-flight Runs does a principal drive?

The kill-switch's resolver. The authority-revocation holder subscriber (K3), on a
committed PolicyGrantRevoked, asks this port for the revoked principal's in-flight
runs and holds each. Shaped around that consumer need: "give me the run ids this
principal drives that are still holdable (Running or Held)".

## Convention

Same shape as ClearanceLookup / Authorize: consumer-shaped contract, one
implementor (Run BC ships PostgresRunActorInvolvementLookup reading
proj_run_actor_involvement), placed in cora.infrastructure.ports for neutral
access. Adapters translate the projection's columns to this shape.

## Involvement scope (v1)

"Drives" is STARTER-ONLY for v1: the runs a principal STARTED (the RunStarted
envelope principal) and that are still in-flight. The projection reserves a
'supervisor' role for a later additive widening to "started or supervises"; when
that lands, this port's contract widens with it and callers need no change (the
method already means "drives", whatever the fold defines that as).
"""

from typing import Protocol
from uuid import UUID


class RunActorInvolvementLookup(Protocol):
    """Cross-BC port: query Run's actor-involvement projection."""

    async def runs_driven_by(self, principal_id: UUID) -> list[UUID]:
        """Return the ids of in-flight Runs the principal drives.

        In-flight means status in (Running, Held): a run that can still be held.
        Terminal runs (Completed / Aborted / Stopped / Truncated) are excluded
        even though the projection retains their rows for audit. Empty list means
        the principal drives no holdable run right now, which is the normal case
        for a post-hoc agent that starts no runs.
        """
        ...


class NoInvolvementLookup:
    """Test-default stub: the principal drives no runs.

    Mirrors AllowAllAuthorize / AlwaysCoveredClearanceLookup as the test-default
    from the deps builder: tests that do not exercise the kill-switch hold get
    this stub, so revoking a grant holds nothing. Tests that exercise the auto-hold
    override with the real PostgresRunActorInvolvementLookup and seed runs via
    start_run. It is also the honest production behavior for today's post-hoc
    agents (they start no runs), so wiring it as the default is not merely a test
    convenience.
    """

    async def runs_driven_by(self, principal_id: UUID) -> list[UUID]:
        _ = principal_id  # no involvement recorded
        return []


__all__ = ["NoInvolvementLookup", "RunActorInvolvementLookup"]
