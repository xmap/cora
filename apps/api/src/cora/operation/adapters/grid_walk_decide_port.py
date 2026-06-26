"""GridWalkDecidePort: a deterministic, stateless grid/sweep decider.

The first REAL brain behind `DecidePort`, with no external optimizer. It
walks a fixed lattice over the `SteeringSpace` axes in order and advises the
next unvisited point, advising `Stop` when the lattice is exhausted or a
`Satisfy` objective has been met. It is the DecidePort analogue of a plain
raster scan: dumb, predictable, and the honest first decider to prove the
loop seam before a learning brain (a GP / LLM) is earned.

## Stateless by construction

The decider holds no cursor: the lattice position is `len(evidence.
observations)` (how many points the caller has already measured, failures
included), re-derived from the evidence every call. So a replay that
re-drives an earlier turn yields identical advice, honoring the port's
stateless-brain contract. The lattice itself is a pure function of the
`SteeringSpace` and the per-axis resolution, so two calls with the same
evidence always advise the same point.

The position derivation assumes the CALLER appends exactly one observation
per advised point. A failed acquisition still counts (the walk advances past
it rather than retrying, treating a failed point as a region to skip), so a
caller must record a failed point as an observation too. The in-conductor
loop honors this by construction.

## Lattice

Each axis contributes its sample values: a discrete / categorical axis uses
its `choices` verbatim; a continuous axis (`lower` + `upper`) uses
`points_per_axis` evenly-spaced values inclusive of both ends. The lattice
is the Cartesian product in axis order (the first axis varies slowest). An
axis with neither `choices` nor a `[lower, upper]` bound cannot be
enumerated, so the decider rejects the evidence rather than guess.

## Objective use

A grid walker does not optimize: it covers the space and lets the caller
evaluate results. It therefore ignores `objective.kind` for point SELECTION.
The one objective-aware behavior is an early `Stop` for a `Satisfy`
objective whose `target_value` is met exactly by the latest observation's
named measurement; a tolerance band is deferred to a smarter brain.
"""

from collections.abc import Sequence
from itertools import product
from typing import Any

from cora.operation.ports.decide_port import (
    DecideEvidenceRejectedError,
    SteeringAdvice,
    SteeringAxis,
    SteeringEvidence,
    SteeringObjective,
    SteeringObjectiveKind,
    SteeringObservation,
    SteeringPoint,
    SteeringSpace,
    SteeringVerdict,
)

_MODEL_REF = "grid_walk"


class GridWalkDecidePort:
    """A deterministic, stateless grid/sweep decider over a SteeringSpace.

    Satisfies the `DecidePort` Protocol structurally. `points_per_axis` is
    the resolution for continuous axes (discrete axes use their `choices`);
    it is ignored for axes that carry explicit `choices`.
    """

    def __init__(self, *, points_per_axis: int = 5) -> None:
        if points_per_axis < 1:
            raise ValueError(f"points_per_axis must be >= 1, got {points_per_axis}")
        self._points_per_axis = points_per_axis

    async def advise_next(self, evidence: SteeringEvidence) -> SteeringAdvice:
        """Advise the next unvisited lattice point, or Stop.

        Stops when a `Satisfy` objective is already met, or when the lattice
        is exhausted. Raises `DecideEvidenceRejectedError` if the space has
        no axes or an axis cannot be enumerated.
        """
        if evidence.observations and _is_satisfied(evidence.objective, evidence.observations[-1]):
            return SteeringAdvice(
                verdict=SteeringVerdict.STOP,
                rationale="satisfy objective met by the latest observation",
                model_ref=_MODEL_REF,
            )
        lattice = _lattice(evidence.space, self._points_per_axis)
        position = len(evidence.observations)
        if position >= len(lattice):
            return SteeringAdvice(
                verdict=SteeringVerdict.STOP,
                rationale=f"grid exhausted after {len(lattice)} points",
                model_ref=_MODEL_REF,
            )
        return SteeringAdvice(
            verdict=SteeringVerdict.MEASURE,
            next_point=lattice[position],
            rationale=f"grid walk point {position + 1} of {len(lattice)}",
            model_ref=_MODEL_REF,
        )

    async def aclose(self) -> None:
        """No-op: the decider holds no resources."""
        return None


def _is_satisfied(objective: SteeringObjective, observation: SteeringObservation) -> bool:
    """True when a Satisfy objective's target_value is met exactly by the
    observation's named measurement."""
    if objective.kind is not SteeringObjectiveKind.SATISFY:
        return False
    if objective.target_value is None or objective.target_measurement_name is None:
        return False
    return any(
        m.name == objective.target_measurement_name and m.value == objective.target_value
        for m in observation.measurements
    )


def _axis_values(axis: SteeringAxis, points_per_axis: int) -> list[Any]:
    """The sample values for one axis: its choices, or an evenly-spaced sweep.

    An axis that carries `choices` uses them verbatim and ignores any bounds:
    choices win when an axis over-specifies both.
    """
    if axis.choices:
        return list(axis.choices)
    if axis.lower is not None and axis.upper is not None:
        if points_per_axis == 1:
            return [axis.lower]
        step = (axis.upper - axis.lower) / (points_per_axis - 1)
        # Pin the final sample to `upper` so both endpoints are exactly
        # included; only the interior points carry float-spacing drift.
        interior = [axis.lower + i * step for i in range(points_per_axis - 1)]
        return [*interior, axis.upper]
    raise DecideEvidenceRejectedError(
        f"axis {axis.name!r} has neither choices nor a [lower, upper] bound; "
        "a grid walker cannot enumerate it"
    )


def _lattice(space: SteeringSpace, points_per_axis: int) -> Sequence[SteeringPoint]:
    """The Cartesian-product lattice over the space, in axis order."""
    if not space.axes:
        raise DecideEvidenceRejectedError("steering space declares no axes to walk")
    names = [axis.name for axis in space.axes]
    per_axis = [_axis_values(axis, points_per_axis) for axis in space.axes]
    return [
        SteeringPoint(coordinates=dict(zip(names, combo, strict=True)))
        for combo in product(*per_axis)
    ]


__all__ = ["GridWalkDecidePort"]
