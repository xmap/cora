"""SobolDecidePort: a deterministic, stateless Sobol initial-design seeder.

A quasi-random seeder behind `DecidePort`, the low-discrepancy sibling of
`GridWalkDecidePort`. It advises the next point of a Sobol sequence over the
`SteeringSpace`, advancing one point per observation already recorded. Its
job is the INITIAL DESIGN: cover the space well enough that a downstream GP
brain has a meaningful first fit. A Sobol low-discrepancy sequence spreads
points more evenly than uniform random and is the conventional Bayesian-
optimization initialization.

## Stateless and replay-deterministic by construction

Like `GridWalkDecidePort`, the seeder holds no cursor: the sequence position
is `len(evidence.observations)`, re-derived every call, so a replay that
re-drives an earlier turn yields identical advice. The Sobol points are an
UNSCRAMBLED (`scramble=False`) sequence, which is a pure function of the
dimension and the draw index, with no random state: the same index always
maps to the same point on every platform and torch version. So the seeder is
a pure-function brain in the sense the conduct loop's replay property
requires, exactly like the grid walker, and unlike the GP brain it seeds.

The seeder SKIPS the sequence's raw 0th point (the all-zeros corner, which
scales to every axis's lower bound: a degenerate, on-the-boundary seed): its
own position `k` maps to raw draw `k + 1`, so the first seed is interior. This
is still a pure function of position, so replay-stability is unchanged.

## Continuous axes only

Sobol generates points in the unit hypercube, scaled to each axis's
`[lower, upper]`. A discrete / categorical axis (one carrying `choices`) has
no continuous range to sample, so the seeder rejects a space that contains
one rather than guessing an encoding; discrete-axis seeding is deferred to a
smarter brain. An axis with neither bounds nor choices is likewise
un-samplable and rejected.

## No objective use, never stops

A seeder covers the space; it does not optimize and it does not converge, so
it ignores `objective.kind` entirely and never advises `Stop`. Deciding when
enough seed points exist is the caller's job (the staged decider hands off to
the GP brain on an observation-count threshold); a seeder consulted forever
keeps emitting Sobol points.
"""

# torch ships no type stubs; mirror the EPICS control-port adapters'
# suppression so torch's untyped surface does not leak Unknown across this
# seeder. CORA-owned domain shapes stay fully typed.
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false

from __future__ import annotations

from typing import TYPE_CHECKING

from cora.operation.adapters._optional_torch import require_torch
from cora.operation.ports.decide_port import (
    DecideEvidenceRejectedError,
    SteeringAdvice,
    SteeringEvidence,
    SteeringPoint,
    SteeringSpace,
    SteeringVerdict,
)

if TYPE_CHECKING:
    from cora.shared.steering import SteeringAxis

_MODEL_REF = "sobol"


class SobolDecidePort:
    """A deterministic, stateless Sobol initial-design seeder over a SteeringSpace.

    Satisfies the `DecidePort` Protocol structurally. Advises the
    `len(observations)`-th point of an unscrambled Sobol sequence scaled to
    the space's continuous axes; never advises `Stop`. Probes `torch` at
    construction so a missing `bo` extra fails as a `ValueError` at handler
    time, not deep in the loop.
    """

    def __init__(self) -> None:
        require_torch(_MODEL_REF)

    async def advise_next(self, evidence: SteeringEvidence) -> SteeringAdvice:
        """Advise the next Sobol point for the current sequence position.

        The position is `len(evidence.observations)` (failed acquisitions
        included: the walk advances past a failed point rather than retrying).
        Raises `DecideEvidenceRejectedError` if the space has no axes or
        carries an axis that is not a bounded continuous axis.
        """
        names = _continuous_axis_names(evidence.space)
        position = len(evidence.observations)
        point = _sobol_point(evidence.space, position)
        return SteeringAdvice(
            verdict=SteeringVerdict.MEASURE,
            next_point=SteeringPoint(coordinates=dict(zip(names, point, strict=True))),
            rationale=f"sobol initial-design point {position + 1}",
            model_ref=_MODEL_REF,
        )

    async def aclose(self) -> None:
        """No-op: the seeder holds no resources."""
        return None


def _continuous_axis_names(space: SteeringSpace) -> list[str]:
    """The axis names, rejecting any non-continuous or unbounded axis."""
    if not space.axes:
        raise DecideEvidenceRejectedError("steering space declares no axes to seed")
    for axis in space.axes:
        _require_continuous(axis)
    return [axis.name for axis in space.axes]


def _require_continuous(axis: SteeringAxis) -> None:
    """Reject a discrete/categorical or unbounded axis a Sobol seeder cannot sample."""
    if axis.choices:
        raise DecideEvidenceRejectedError(
            f"axis {axis.name!r} carries choices; a Sobol seeder samples only "
            "bounded continuous axes"
        )
    if axis.lower is None or axis.upper is None:
        raise DecideEvidenceRejectedError(
            f"axis {axis.name!r} has no [lower, upper] bound; a Sobol seeder cannot sample it"
        )


def _sobol_point(space: SteeringSpace, index: int) -> list[float]:
    """The `index`-th seed point (skipping the origin), scaled to each axis's bounds.

    The 0th point of an UNSCRAMBLED Sobol sequence is the all-zeros corner of
    the unit hypercube, which scales to every axis's lower bound: a degenerate,
    on-the-boundary seed that wastes the first (often expensive) acquisition and
    gives the GP a corner point rather than interior coverage. So the seeder
    skips raw index 0 and maps its own position `index` to raw draw `index + 1`
    (position 0 -> 0.5, 1 -> 0.75, 2 -> 0.25, ... in 1-D). It draws `index + 2`
    points from a fresh unscrambled engine and takes the last; an unscrambled
    Sobol sequence is a pure function of (dimension, draw index), so this stays
    deterministic and replay-stable without any RNG seed.
    """
    import torch

    dimension = len(space.axes)
    engine = torch.quasirandom.SobolEngine(dimension=dimension, scramble=False)
    drawn = engine.draw(index + 2, dtype=torch.double)
    unit = drawn[index + 1]
    point: list[float] = []
    for axis_index, axis in enumerate(space.axes):
        assert axis.lower is not None  # guarded by _require_continuous
        assert axis.upper is not None
        span = axis.upper - axis.lower
        point.append(axis.lower + float(unit[axis_index]) * span)
    return point


__all__ = ["SobolDecidePort"]
