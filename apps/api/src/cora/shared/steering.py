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
reason. `DecidePort` re-exports the intent value types that MOVED out of it, so
existing Operation importers stay stable. Names that originated here, such as
`SteeringSubstrate` and `SteeringDesignSource`, are imported from this module
directly: there is no legacy importer to keep stable, and the substrate one must
not enter the port's public surface, which is deliberately blind to which brain
is behind the seam.

`serialize_objective` / `deserialize_objective` / `serialize_space` /
`deserialize_space` live here for the same reason as the VOs themselves: both
`CampaignSteeringDeclared` and the Operation Procedure's `SteeringDesignRecorded`
carry `SteeringObjective` / `SteeringSpace`, and a shared VO must not carry two
payload shapes across the two streams.

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


class SteeringSubstrate(StrEnum):
    """Which brain materialised a steered run's `DecidePort`.

    Mirrors, value for value, the `DecideSubstrate` Literal in
    `cora.operation.adapters.decide_port_config` (kept in sync by a
    fitness test, since tach forbids this shared module from importing
    that adapter-tier Literal directly). Lives here rather than being
    imported from there because it is recorded on a Procedure event,
    and events are typed with shared vocabulary, not adapter internals.

    `IN_MEMORY` is the deterministic fake; `GRID_WALK` is the in-CORA
    grid/sweep decider; `SOBOL` is the Sobol initial-design seeder;
    `BOTORCH` is the GP Bayesian-optimization brain; `STAGED` is the
    two-phase sobol-then-botorch composite; `LLM` is the LLM steering
    brain.
    """

    IN_MEMORY = "in_memory"
    GRID_WALK = "grid_walk"
    SOBOL = "sobol"
    BOTORCH = "botorch"
    STAGED = "staged"
    LLM = "llm"


class SteeringDesignSource(StrEnum):
    """Where a pinned steering design originated.

    One value today: `REQUEST`, the operator- or agent-supplied wire
    request that started or resumed the conduct segment. Every design
    pin currently traces to that single origin, so a second value
    would have nothing to distinguish itself from and no reader ready
    to branch on it; this stays single-valued until an across-Run
    steerer can itself originate a design, at which point widening
    this enum is purely additive.
    """

    REQUEST = "Request"


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


# ---------------------------------------------------------------------------
# Serialize / deserialize (public; shared across every event stream that
# carries these VOs, so the same value object never carries two payload
# shapes -- Campaign's CampaignSteeringDeclared and Operation's
# SteeringDesignRecorded both call these rather than each hand-rolling
# their own encode/decode).
# ---------------------------------------------------------------------------


def serialize_objective(objective: SteeringObjective) -> dict[str, Any]:
    """Encode a SteeringObjective to a JSON-friendly dict."""
    return {
        "kind": objective.kind.value,
        "target_measurement_name": objective.target_measurement_name,
        "target_value": objective.target_value,
    }


def deserialize_objective(payload: dict[str, Any]) -> SteeringObjective:
    """Decode a JSON-friendly dict to a SteeringObjective."""
    return SteeringObjective(
        kind=SteeringObjectiveKind(payload["kind"]),
        target_measurement_name=payload.get("target_measurement_name"),
        target_value=payload.get("target_value"),
    )


def serialize_space(space: SteeringSpace) -> dict[str, Any]:
    """Encode a SteeringSpace to a JSON-friendly dict (choices tuple -> list)."""
    return {
        "axes": [
            {
                "name": axis.name,
                "lower": axis.lower,
                "upper": axis.upper,
                "choices": list(axis.choices),
            }
            for axis in space.axes
        ]
    }


def deserialize_space(payload: dict[str, Any]) -> SteeringSpace:
    """Decode a JSON-friendly dict to a SteeringSpace (choices list -> tuple)."""
    return SteeringSpace(
        axes=tuple(
            SteeringAxis(
                name=axis["name"],
                lower=axis.get("lower"),
                upper=axis.get("upper"),
                choices=tuple(axis.get("choices", [])),
            )
            for axis in payload["axes"]
        )
    )


__all__ = [
    "SteeringAxis",
    "SteeringDesignSource",
    "SteeringObjective",
    "SteeringObjectiveKind",
    "SteeringPoint",
    "SteeringSpace",
    "SteeringSubstrate",
    "deserialize_objective",
    "deserialize_space",
    "serialize_objective",
    "serialize_space",
]
