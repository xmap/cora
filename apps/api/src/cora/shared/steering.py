"""BC-agnostic steering vocabulary: what good means + where to look.

These value objects describe the INTENT of an autonomous-experiment search,
independent of any brain or beamline: the objective (what good means), the
feasible space (where the brain may look), and a proposed point within it. They
live here, not in the Operation BC's `DecidePort`, because more than one BC needs
them: the Operation `DecidePort` reuses them for the within-procedure steered
loop, and the Campaign aggregate declares a campaign's steering INTENT
(`steering_objective` / `steering_space`) so an across-Run steerer can derive the
next Run. tach forbids `cora.campaign` from importing `cora.operation.ports`, so
the shared value types move here (an allowed campaign dependency), exactly as
`DecisionConfidenceSource` moved to `cora.shared.decision_signals` for the same
reason. `DecidePort` re-exports every name below so existing Operation importers
stay stable.

Deliberately narrow: only the value types two BCs genuinely share live here. The
ADVICE side of the seam (`SteeringAdvice`, `SteeringVerdict`, `SteeringEvidence`,
`SteeringObservation`, `SteeringBudget`, the `Decide*Error` families, the
`DecidePort` Protocol, and the `objective_is_satisfied` predicate that reads a
`Measurement`) stays in `cora.operation.ports.decide_port`: those depend on the
Operation BC's own value types (`Measurement`, `ArtifactRef`, `ActuationKind`)
and only the Operation BC consumes them.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class SteeringObjectiveKind(StrEnum):
    """The optimization SENSE of an objective, without a search strategy.

    The seam tells the brain what 'better' means; the brain owns how to get
    there. `Minimize` / `Maximize` drive a metric down / up; `Satisfy` hits
    a target value; `Explore` has no scalar target (the brain just covers
    the space, e.g. a grid). Anything richer (acquisition function, kernel,
    exploration weight) is the adapter's concern, deliberately not here.
    """

    MINIMIZE = "Minimize"
    MAXIMIZE = "Maximize"
    SATISFY = "Satisfy"
    EXPLORE = "Explore"


@dataclass(frozen=True)
class SteeringPoint:
    """A coordinate in the search space: axis name -> value.

    The brain proposes it; the caller translates it into Conductor steps
    (the port never sees a Step, a PV, or the captures bus). Values are
    `Any` so a continuous axis carries a float, a discrete axis an int, and
    a categorical axis a label, all keyed by the `SteeringAxis.name` that
    is the bridge to the caller's actuation.
    """

    coordinates: Mapping[str, Any]


@dataclass(frozen=True)
class SteeringAxis:
    """One dimension of the feasible set: a name plus its legal range.

    `name` is the substrate-neutral axis label the caller binds to an
    actuation slot; the brain only ever reasons about the name and its
    range. `lower` / `upper` bound a continuous axis; `choices` enumerates a
    discrete or categorical axis (empty for a pure continuous axis). The
    axis declarations are supplied by the caller, never invented by the
    brain, because the caller must translate a `next_point` back into steps.
    """

    name: str
    lower: float | None = None
    upper: float | None = None
    choices: tuple[Any, ...] = ()


@dataclass(frozen=True)
class SteeringSpace:
    """The feasible set the brain may propose points within.

    Required whenever the brain may return `Measure`: it is load-bearing for
    the caller's point-to-step translation (the caller cannot turn a
    `next_point` into actuation without the axis names and ranges),
    independent of which brain is behind the seam.
    """

    axes: tuple[SteeringAxis, ...]


@dataclass(frozen=True)
class SteeringObjective:
    """What 'good' means, by a Measurement NAME, without a search strategy.

    `target_measurement_name` names which `Measurement` in the observations
    is the objective scalar, so the brain ignores the rest. It is a NAME,
    origin-agnostic: the scalar may be a detector read (control) or a
    compute output (a derived quality metric), which is what keeps a
    compute-steering brain expressible with these same DTOs. `target_value`
    is the setpoint a `Satisfy` objective aims at; it is None for
    `Minimize` / `Maximize` / `Explore`.
    """

    kind: SteeringObjectiveKind
    target_measurement_name: str | None = None
    target_value: float | None = None


__all__ = [
    "SteeringAxis",
    "SteeringObjective",
    "SteeringObjectiveKind",
    "SteeringPoint",
    "SteeringSpace",
]
