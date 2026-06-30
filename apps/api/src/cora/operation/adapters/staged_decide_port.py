"""StagedDecidePort: a two-phase seeder-then-brain composite decider.

Autonomous Bayesian optimization needs an initial design before the GP has
enough data to fit: emit a handful of quasi-random seed points first, then
hand off to the learning brain. `StagedDecidePort` is that handoff as a single
`DecidePort`: it holds a SEEDER child and a BRAIN child and routes each call to
one or the other on the observation count, so the conduct loop sees one port
and stays unaware of the phase change.

This is the composite/delegating-adapter pattern: the same shape Optuna's
`GPSampler` ships in production (a sampler that delegates its first
`n_startup_trials` to an independent random sampler, then switches to the GP).
The composite carries NO optimization logic of its own; it only counts and
routes, delegating the actual deciding to two single-responsibility children.

## Stateless routing (replay-safe handoff)

The phase is a pure function of the evidence handed over: while the number of
SUCCESSFUL observations is below `threshold` the seeder decides, at or above it
the brain decides. The count is re-derived from `evidence.observations` every
call (no internal cursor), so a replay that re-drives an earlier turn routes to
the same child and yields the same advice, provided both children are
themselves replay-stable. (The Sobol seeder is; the GP brain is not, which is
why a GP-steered run is forward-only today, a property of the brain, not of
this router.)

## Why count successful observations

The threshold gates on `obs.succeeded` (the port-level success flag), the
caller-neutral signal that a measurement happened. A failed acquisition is a
real datum for a seeder (a region to skip) but does NOT advance the GP toward
a fittable history, so it must not count toward the handoff. The brain applies
its own, stricter usability filter on top (it also drops non-Good-quality
points); the `threshold >= brain.min_observations` construction invariant
guarantees that by the time the brain is first consulted it has at least its
required floor of successful observations, so the handoff cannot land the brain
in its own reject-when-cold path on the first call.

## Stop semantics

Only the brain phase can advise `Stop`: a seeder covers the space and never
converges, so during the seed phase the composite returns the seeder's
(always-`Measure`) advice. Once handed off, the composite returns the brain's
verdict verbatim, `Stop` included.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cora.operation.ports.decide_port import (
        DecidePort,
        SteeringAdvice,
        SteeringEvidence,
    )

_DEFAULT_THRESHOLD = 5


class StagedDecidePort:
    """A two-phase composite that routes seeder -> brain on successful-obs count.

    Satisfies the `DecidePort` Protocol structurally by delegating to two
    `DecidePort` children. `threshold` is the number of successful
    observations at which the handoff occurs; it must be >= the brain's own
    cold-start floor so the brain is never consulted below it (the caller
    passes the brain's `min_observations` or higher).
    """

    def __init__(
        self,
        *,
        seeder: DecidePort,
        brain: DecidePort,
        threshold: int = _DEFAULT_THRESHOLD,
        brain_min_observations: int = _DEFAULT_THRESHOLD,
    ) -> None:
        if threshold < 1:
            raise ValueError(f"threshold must be >= 1, got {threshold}")
        if threshold < brain_min_observations:
            raise ValueError(
                f"threshold ({threshold}) must be >= the brain's cold-start floor "
                f"({brain_min_observations}); a lower threshold would hand the brain "
                "fewer observations than it needs and trip its reject-when-cold path"
            )
        self._seeder = seeder
        self._brain = brain
        self._threshold = threshold

    async def advise_next(self, evidence: SteeringEvidence) -> SteeringAdvice:
        """Route to the seeder below the threshold, else to the brain.

        The number of successful observations is re-derived from the evidence
        every call, so the routing is stateless and replay-stable. Any
        `Decide*Error` the chosen child raises propagates unchanged (the loop
        folds it into a deferred steering decision).
        """
        successful = sum(1 for obs in evidence.observations if obs.succeeded)
        child = self._seeder if successful < self._threshold else self._brain
        return await child.advise_next(evidence)

    async def aclose(self) -> None:
        """Release both children's resources; idempotent."""
        await self._seeder.aclose()
        await self._brain.aclose()


__all__ = ["StagedDecidePort"]
