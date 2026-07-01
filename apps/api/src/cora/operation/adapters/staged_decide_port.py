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
a fittable history, so it must not count toward the handoff.

## Cold-start fallback (the count is a hint, not a guarantee)

The composite counts what it can see (`obs.succeeded`), but the brain's real
usability bar is stricter and INVISIBLE from here: the GP brain also drops
non-Good-quality points and observations missing the target measurement. So
`successful >= threshold` does NOT prove the brain has enough USABLE points;
a run can cross the count threshold while several successful observations are
Uncertain / Bad / off-target, leaving the brain below its own floor.

Rather than duplicate the brain's private usability predicate here (which
would couple the composite to one brain's filter and drift as the brain
evolves), the composite treats the count as a HINT and defers to the brain's
own verdict: when routing to the brain raises the transient
`DecideColdStartError`, the composite falls back to the seeder for that call
and emits another seed point. The loop then feeds one more observation and
re-consults; the brain is retried as the usable history grows. This keeps the
autonomous loop progressing instead of aborting the whole procedure the first
time the brain finds itself cold (the conduct loop folds any `Decide*Error`
into a run-ending abort), and it keeps the router brain-agnostic: only a
PERMANENT rejection (unsupported objective kind, missing target, non-continuous
axis, all base `DecideEvidenceRejectedError` and not the cold-start subtype)
propagates and ends the run, because more seeding never fixes those.

## Stop semantics

Only the brain phase can advise `Stop`: a seeder covers the space and never
converges, so during the seed phase the composite returns the seeder's
(always-`Measure`) advice. Once handed off, the composite returns the brain's
verdict verbatim, `Stop` included.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cora.operation.ports.decide_port import DecideColdStartError

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
    `DecidePort` children. `threshold` is the successful-observation count at
    which the composite first TRIES the brain. It is a hint, not a hard
    guarantee: because the brain's own usability bar is stricter and invisible
    here, the composite falls back to the seeder whenever the brain signals it
    is still cold (`DecideColdStartError`), so the loop keeps seeding until the
    brain can actually fit. `threshold >= brain_min_observations` is a
    fail-fast sanity check on obviously-misconfigured input, not the safety net
    (the runtime fallback is).
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
                f"({brain_min_observations}); a lower threshold would try the brain "
                "before it can possibly have enough observations to fit"
            )
        self._seeder = seeder
        self._brain = brain
        self._threshold = threshold

    async def advise_next(self, evidence: SteeringEvidence) -> SteeringAdvice:
        """Route to the seeder below the threshold, else try the brain.

        The number of successful observations is re-derived from the evidence
        every call, so the routing is stateless and replay-stable. Below the
        threshold the seeder decides. At or above it the brain is tried; if the
        brain is still cold (raises the transient `DecideColdStartError`, e.g.
        too few Good-quality target observations to fit) the composite falls
        back to the seeder for another point so the loop keeps accreting usable
        observations rather than aborting the run. Any other `Decide*Error`
        (including a permanent `DecideEvidenceRejectedError`) propagates
        unchanged, and the conduct loop folds it into a run-ending abort.
        """
        successful = sum(1 for obs in evidence.observations if obs.succeeded)
        if successful < self._threshold:
            return await self._seeder.advise_next(evidence)
        try:
            return await self._brain.advise_next(evidence)
        except DecideColdStartError:
            return await self._seeder.advise_next(evidence)

    async def aclose(self) -> None:
        """Release both children's resources; idempotent."""
        await self._seeder.aclose()
        await self._brain.aclose()


__all__ = ["StagedDecidePort"]
