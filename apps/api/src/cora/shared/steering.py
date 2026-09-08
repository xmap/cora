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
from typing import Any, Final, assert_never


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
class InMemoryBrain:
    """The deterministic in-memory fake's config: none.

    It replays seeded advice then advises Stop; there is no tunable to
    record.
    """


@dataclass(frozen=True)
class GridWalkBrain:
    """The `grid_walk` substrate's own config: the per-axis lattice resolution."""

    points_per_axis: int


@dataclass(frozen=True)
class SobolBrain:
    """The `sobol` substrate's own config: none.

    The whole rule is the space plus the observation count; there is
    nothing else to record.
    """


@dataclass(frozen=True)
class BoTorchBrain:
    """The `botorch` GP brain's own config: the fit and acquisition dials.

    Field names match the adapter's own constructor keywords
    (`BoTorchDecidePort.__init__`) verbatim, so a reader does not have to
    map a recorded name onto a differently-spelled runtime one.
    """

    min_observations: int
    num_restarts: int
    raw_samples: int
    seed: int


@dataclass(frozen=True)
class StagedBrain:
    """The `staged` composite's own config: its handoff point plus the brain it hands off to.

    `threshold` is the successful-observation count at which the composite
    switches from seeding to steering. The seeder half is not represented
    here: `build_decide_port`'s `staged` arm always constructs a bare
    `SobolDecidePort()` (`SobolBrain` carries no fields regardless), so a
    `seeder` field would record a choice the running code does not
    actually offer. `handoff_brain` is nested rather than flattened,
    because a staged run's own `min_observations` genuinely means two
    different things at once: the composite's threshold floor and the
    child GP's cold-start floor, which `StagedDecidePort.__init__`
    validates against each other under two DIFFERENT names (`threshold`
    vs `brain_min_observations`) for exactly this reason. Flattening them
    back onto one field, the way `DecidePortConfig.min_observations` does
    today, is the ambiguity nesting exists to remove.

    Named `handoff_brain`, not the adapter constructor's own bare `brain`
    keyword: on `StagedDecidePort.__init__` that name is unambiguous
    because the container is a Port, not a Brain. Nested inside
    `StagedBrain`, `.brain.brain` on a chain that starts at
    `SteeringDesignRecorded` would stutter and read as though the second
    `.brain` were a mistake; `.brain.handoff_brain` names what it holds
    instead.
    """

    threshold: int
    handoff_brain: BoTorchBrain


@dataclass(frozen=True)
class LlmBrain:
    """The `llm` substrate's own config: which model was asked to steer.

    `provider` / `model` / `snapshot_pin` deliberately duplicate
    `cora.infrastructure.ports.llm.ModelRef`'s three fields as plain
    primitives rather than importing that class: `cora.shared` depends on
    nothing (`tach.toml`), so it cannot reach `cora.infrastructure`. This
    is the same deliberate duplication `_model_ref.py` documents between
    the Agent aggregate's write-time `ModelRef` and the port's wire-shape
    `ModelRef`; a third copy for the same layering reason is not a new
    pattern.

    This is a design-time fact (what was CONFIGURED for the segment), not
    a per-call one: the model actually reached is a property of one LLM
    response and belongs on the iteration record alongside
    `SteeringLlmCall.response_model`, not here. `snapshot_pin` is
    included because an unpinned alias ("latest") is itself a sampling-rule
    fact worth a Rubin-ignorability reader knowing: a deployment upgrade
    between passes could silently change which model answered.
    """

    provider: str
    model: str
    snapshot_pin: str | None = None


SteeringBrain = InMemoryBrain | GridWalkBrain | SobolBrain | BoTorchBrain | StagedBrain | LlmBrain
"""The typed per-substrate steering-brain config space.

One variant per `SteeringSubstrate` member, carrying exactly the values
that determine what that brain does and nothing a run of a DIFFERENT
substrate would have to declare irrelevant. `BRAIN_TYPE_BY_SUBSTRATE`
below is the totality of that pairing; the sibling fitness test asserts
its keys equal the full `SteeringSubstrate` enum, mirroring
`test_steering_substrate_matches_decide_substrate_literal`.

Deliberately a true union of distinct classes (the `ControlAddress`
shape: `EpicsPvAddress | TangoAttributeAddress | InMemoryAddress`), not
one flat class with a kind field and every substrate's fields hoisted
onto it. A run recording `GridWalkBrain(points_per_axis=5)` carries no
`seed` slot to leave unset; the flat `DecidePortConfig` a run's config
comes from does, and a grid-walk run's recorded `seed` is a design fact
that had no effect on it. See [[project-per-kind-field-belongs-in-its-arm]].

`gen_record_dispositions._merge` folds a multi-variant union's field
dispositions into one rule covering every arm's keys, so this exports
correctly under `SteeringDesignRecorded` provided no two variants reuse a
field NAME for a different disposition; `BoTorchBrain.seed: int` and
`StagedBrain.handoff_brain.seed` (nested, not a naming collision) are the
only `seed`-named fields in this union, and both resolve identically.

No emitter reads this yet: the type exists so both recording surfaces
(a Procedure segment's `SteeringDesignRecorded`, a future across-Run
steerer) can share one vocabulary, exactly as `SteeringObjective` /
`SteeringSpace` do.
"""

BRAIN_TYPE_BY_SUBSTRATE: Mapping[SteeringSubstrate, type] = {
    SteeringSubstrate.IN_MEMORY: InMemoryBrain,
    SteeringSubstrate.GRID_WALK: GridWalkBrain,
    SteeringSubstrate.SOBOL: SobolBrain,
    SteeringSubstrate.BOTORCH: BoTorchBrain,
    SteeringSubstrate.STAGED: StagedBrain,
    SteeringSubstrate.LLM: LlmBrain,
}
"""Which `SteeringBrain` variant records a given substrate's config.

The single source `serialize_brain` / `deserialize_brain` dispatch
through, and what the sibling fitness test checks for completeness
against `SteeringSubstrate`. A substrate added here without a matching
enum member, or vice versa, is what that test exists to catch; the two
are hand-maintained independently (one is an enum literal, the other a
class reference), so the comparison is a real check, not a decorative
one that agrees with itself by construction.
"""

LLM_REF_SEPARATOR: Final = ":"
"""What separates provider from model in an `llm` brain's flat `model_ref`.

Shared by the renderer (`DecidingBrainRef.__str__`) and the reader
(`decider_replayability._is_llm_ref`) on purpose. The two must agree for a
recorded ref to survive a round trip, so they are deliberately NOT
independent sides of a check: one constant, one convention.
"""


class InvalidDecidingBrainRefError(ValueError):
    """A `DecidingBrainRef` names a substrate and a payload that cannot co-occur."""


@dataclass(frozen=True)
class DecidingBrainRef:
    """WHICH brain decided one steered iteration, typed rather than spelled.

    The `Ref` suffix carries the axis that separates this from `SteeringBrain`
    above, matching `BrainRef` in the Agent BC, which is the same shape for
    the same question. `SteeringBrain` is design-time CONFIG: the dials a
    segment's brain was built with, pinned once on `SteeringDesignRecorded`.
    This is run-time IDENTITY: which brain answered one pass, recorded on every
    `ProcedureIterationEnded` a steered conduct writes. A `staged` segment is
    the case that makes them different facts rather than two spellings of
    one. Its design pins the composite; each iteration is decided by
    whichever child the composite had handed off to by then, which the design
    cannot say and only the iteration knows.

    Carries exactly what the free-text `model_ref` it stands beside encodes,
    and nothing more: four substrates spell their own name, `llm` spells
    `provider:model`. `str()` renders that spelling back, so the two
    recorded forms are one fact rendered twice rather than two fields that
    can drift. `snapshot_pin` is deliberately absent even though `LlmBrain`
    carries it: a pin is a dial on the model, so it belongs to the design,
    and repeating it once per pass would re-record configuration as though it
    were an observation.

    `STAGED` is rejected rather than representable. The composite returns its
    child's advice unchanged, so what reaches an iteration is `sobol` or
    `botorch`; a `DecidingBrainRef` naming the composite would mean the
    composite had grown an identity of its own, which `decider_replayability`
    already refuses to classify. Rejecting it at construction makes that
    state unwritable instead of merely unreadable.
    """

    substrate: SteeringSubstrate
    provider: str | None = None
    model: str | None = None

    def __post_init__(self) -> None:
        match self.substrate:
            case SteeringSubstrate.LLM:
                if not self.provider or not self.model:
                    raise InvalidDecidingBrainRefError(
                        "an llm brain is named by a non-empty provider and model"
                    )
            case (
                SteeringSubstrate.IN_MEMORY
                | SteeringSubstrate.GRID_WALK
                | SteeringSubstrate.SOBOL
                | SteeringSubstrate.BOTORCH
            ):
                if self.provider is not None or self.model is not None:
                    raise InvalidDecidingBrainRefError(
                        f"the {self.substrate.value!r} brain is named by its substrate "
                        "alone and carries no provider or model"
                    )
            case SteeringSubstrate.STAGED:
                raise InvalidDecidingBrainRefError(
                    "the staged composite decides no iteration itself; name the child "
                    "brain it had handed off to"
                )
            case _:  # pragma: no cover - exhaustive over a closed enum
                assert_never(self.substrate)

    def __str__(self) -> str:
        """Render the flat `model_ref` spelling the record still carries.

        The single producer of that string, so the typed field and the legacy
        one on the same event are one fact rendered twice. Total over every
        constructible brain, and readable by `decider_replayability`, which
        still classifies the string form because a stream written before this
        type existed carries only that.

        `__str__` rather than a named converter, following `ControlAddress`
        (the union shape this module's `SteeringBrain` already copies) and
        `FacilityCode`: both render a discriminated value object to the flat
        form the wire carries this way. A `to_model_ref` would read as
        returning `cora.infrastructure.ports.llm.ModelRef`, since every `to_X`
        in the tree returns the type it names, and this returns a string.
        No matching `parse` is offered: the fold deliberately does not
        reconstruct a brain from a legacy ref, and `decider_replayability`
        already reads that form.
        """
        if self.substrate is SteeringSubstrate.LLM:
            return f"{self.provider}{LLM_REF_SEPARATOR}{self.model}"
        return self.substrate.value


def serialize_deciding_brain_ref(brain: DecidingBrainRef) -> dict[str, Any]:
    """Encode a `DecidingBrainRef` to a JSON-friendly dict.

    Writes `substrate` into the payload, unlike `serialize_brain`, whose
    substrate the sibling `SteeringDesignRecorded.substrate` field already
    carries. An iteration event has no such sibling, so the tag rides here.
    """
    return {
        "substrate": brain.substrate.value,
        "provider": brain.provider,
        "model": brain.model,
    }


def deserialize_deciding_brain_ref(payload: Mapping[str, Any]) -> DecidingBrainRef:
    """Decode a JSON-friendly dict to a `DecidingBrainRef`.

    Re-runs `__post_init__`, so a payload whose substrate and model half
    disagree raises on the fold rather than folding to a brain no adapter
    could have produced.
    """
    return DecidingBrainRef(
        substrate=SteeringSubstrate(payload["substrate"]),
        provider=payload.get("provider"),
        model=payload.get("model"),
    )


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


def serialize_brain(brain: SteeringBrain) -> dict[str, Any]:
    """Encode a SteeringBrain variant to a JSON-friendly dict.

    No embedded type tag: the caller's own `substrate` field (already on
    every event this carries) is the discriminant `deserialize_brain`
    needs back, so one is not duplicated inside the payload.
    """
    match brain:
        case InMemoryBrain():
            return {}
        case GridWalkBrain(points_per_axis=points_per_axis):
            return {"points_per_axis": points_per_axis}
        case SobolBrain():
            return {}
        case BoTorchBrain(
            min_observations=min_observations,
            num_restarts=num_restarts,
            raw_samples=raw_samples,
            seed=seed,
        ):
            return {
                "min_observations": min_observations,
                "num_restarts": num_restarts,
                "raw_samples": raw_samples,
                "seed": seed,
            }
        case StagedBrain(threshold=threshold, handoff_brain=child):
            return {"threshold": threshold, "handoff_brain": serialize_brain(child)}
        case LlmBrain(provider=provider, model=model, snapshot_pin=snapshot_pin):
            return {"provider": provider, "model": model, "snapshot_pin": snapshot_pin}
        case _:  # pragma: no cover - exhaustive over SteeringBrain's closed union
            assert_never(brain)


def _deserialize_botorch_brain(payload: Mapping[str, Any]) -> BoTorchBrain:
    """Decode a JSON-friendly dict to a BoTorchBrain.

    Split out of `deserialize_brain` so the `STAGED` case can build its
    nested `BoTorchBrain` without a recursive `deserialize_brain` call: that
    call is typed to return the whole `SteeringBrain` union, and pyright
    cannot narrow a call's return type from the value of one of its
    arguments, only from its declared signature. A helper returning
    `BoTorchBrain` outright removes the ambiguity instead of asserting past it.
    """
    return BoTorchBrain(
        min_observations=payload["min_observations"],
        num_restarts=payload["num_restarts"],
        raw_samples=payload["raw_samples"],
        seed=payload["seed"],
    )


def deserialize_brain(substrate: SteeringSubstrate, payload: Mapping[str, Any]) -> SteeringBrain:
    """Decode a JSON-friendly dict to the SteeringBrain variant for `substrate`.

    Takes `substrate` as an explicit parameter rather than reading a tag out
    of `payload`, mirroring `parse_control_address(raw, substrate)`: the
    caller already knows the substrate from the same event's own
    `substrate` field, so a second embedded tag would be a duplicate a
    reader could read out of step with the first.
    """
    match substrate:
        case SteeringSubstrate.IN_MEMORY:
            return InMemoryBrain()
        case SteeringSubstrate.GRID_WALK:
            return GridWalkBrain(points_per_axis=payload["points_per_axis"])
        case SteeringSubstrate.SOBOL:
            return SobolBrain()
        case SteeringSubstrate.BOTORCH:
            return _deserialize_botorch_brain(payload)
        case SteeringSubstrate.STAGED:
            return StagedBrain(
                threshold=payload["threshold"],
                handoff_brain=_deserialize_botorch_brain(payload["handoff_brain"]),
            )
        case SteeringSubstrate.LLM:
            return LlmBrain(
                provider=payload["provider"],
                model=payload["model"],
                snapshot_pin=payload.get("snapshot_pin"),
            )
        case _:  # pragma: no cover - exhaustive over a closed enum
            assert_never(substrate)


__all__ = [
    "BRAIN_TYPE_BY_SUBSTRATE",
    "LLM_REF_SEPARATOR",
    "BoTorchBrain",
    "DecidingBrainRef",
    "GridWalkBrain",
    "InMemoryBrain",
    "InvalidDecidingBrainRefError",
    "LlmBrain",
    "SobolBrain",
    "StagedBrain",
    "SteeringAxis",
    "SteeringBrain",
    "SteeringDesignSource",
    "SteeringObjective",
    "SteeringObjectiveKind",
    "SteeringPoint",
    "SteeringSpace",
    "SteeringSubstrate",
    "deserialize_brain",
    "deserialize_deciding_brain_ref",
    "deserialize_objective",
    "deserialize_space",
    "serialize_brain",
    "serialize_deciding_brain_ref",
    "serialize_objective",
    "serialize_space",
]
