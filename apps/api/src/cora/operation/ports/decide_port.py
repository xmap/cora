"""DecidePort: the domain-shaped seam over which CORA asks an external brain
"given everything measured so far, what should I measure next, or stop?".

`DecidePort` is the DECIDE-axis sibling of `ControlPort` and `ComputePort`.
ControlPort drives hardware value-IO; ComputePort drives a compute job;
DecidePort drives the CHOICE of the next acquisition. It lives in the same
BC home (`cora.operation.ports`) as its siblings, and reuses their value
types (`Measurement`, `ArtifactRef`, `ActuationKind`) field-for-field, so a
conduct result maps onto a steering observation with no translation layer.
It is homed here, not in the Decision BC, because tach forbids
`cora.decision` from importing `cora.operation.ports` (where those value
types live) and the first caller is the Conductor (Operation BC). The
Decision BC keeps owning the `Decision` aggregate; an across-Run steerer
(deferred) records its rationale there via the signed-subscriber path.

## Optimizer- and action-neutral by construction

The brain behind the seam may be a static grid walker, a Bayesian
optimizer, or an LLM agent; CORA cannot tell which, and must not. So:

  - Optimizer internals (kernel, acquisition function, surrogate model, GP
    posterior, exploration weight) NEVER cross the seam: they live inside
    the adapter and its config.
  - Control specifics (PV / motor / trigger / scan / acquire / the
    conductor's captures bus) NEVER cross the seam: a `next_point` is a set
    of coordinates keyed by axis NAME, not a command. Translating a point
    into Conductor steps is the caller's job, not the port's.

`SteeringObjective` names WHAT good means by a Measurement NAME, origin-
agnostic (a control read OR a compute output), which is the single decision
that keeps a compute-steering brain expressible with these same DTOs.

## The six-noun kernel

Every autonomous experiment, on any beamline, with any brain, needs the
same six things; remove one and the loop is undecidable:

  1. `SteeringObjective` - what good means.
  2. `SteeringSpace` / `SteeringAxis` - where we may look.
  3. `SteeringEvidence` - what has happened (the full history, handed to a
     STATELESS brain; CORA never assumes the brain remembers prior calls).
  4. `SteeringObservation` - one datum of that history.
  5. `SteeringAdvice` - what to do next, and whether to quit.
  6. `SteeringBudget` - how much is left.

`SteeringPoint` is the derived coordinate value type the brain proposes and
the caller translates.

## Stateless brain

`advise_next` hands over the full `SteeringEvidence.observations` every
call, so a brain that holds no memory (an LLM, a pure function) and a brain
that caches a surrogate internally (a GP) both satisfy the same surface.
The port promises nothing about cross-call memory, so it never carries a
session handle; a stateful adapter rebuilds from the full history.

## Exceptions

Five exception families mirror CORA's standard shape and the ControlPort /
ComputePort posture: `DecidePort` is not REST-accessible. The caller folds
a raised exception into a recorded steering decision (deferred / rejected)
rather than crashing the loop, exactly as the executor folds ControlPort
exceptions into event-payload metadata per
[[project_non_determinism_principle]].

## Earned, not minted

Ships with one test fake (`InMemoryDecidePort`) plus, in the next slice, a
single in-CORA `GridWalkDecidePort` (no external optimizer). A routing
registry and a real GP adapter (gpCAM) are earned at their own triggers,
exactly as ControlPort earned its registry from a third substrate and
ComputePort deferred its registry to a second.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from cora.operation.ports.compute_port import ArtifactRef
from cora.operation.ports.control_port import ActuationKind
from cora.operation.ports.measurement import Measurement
from cora.shared.decision_signals import REASONING_MAX_LENGTH, DecisionConfidenceSource


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


class SteeringVerdict(StrEnum):
    """The brain's continue-or-quit decision, fused with its suggestion.

    `Measure`: take another acquisition at the advised `next_point`.
    `Stop`: the brain is done (objective met, space exhausted, or it judges
    further measurement not worthwhile). A `Stop` carries no `next_point`.

    The verdict is fused into `SteeringAdvice` (not a separate port call)
    because a brain decides 'continue vs stop' and 'where' in one inference;
    splitting them would let the two answers disagree.
    """

    MEASURE = "Measure"
    STOP = "Stop"


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


@dataclass(frozen=True)
class SteeringObservation:
    """One prior trial: we measured AT `point` and got THIS.

    Reuses `Measurement` / `ArtifactRef` / `ActuationKind` field-for-field
    from the conduct result so the caller maps a `ConductorResult` onto an
    observation with no translation. `succeeded=False` with empty
    `measurements` is legal and first-class: a failed acquisition is a data
    point (a region to avoid), not something the caller silently drops.
    `actuation_kind` threads provenance so a brain may distrust a simulated
    point; the adapter may also ignore it.
    """

    point: SteeringPoint
    measurements: tuple[Measurement, ...] = ()
    artifact_ref: ArtifactRef | None = None
    actuation_kind: ActuationKind | None = None
    succeeded: bool = True


@dataclass(frozen=True)
class SteeringBudget:
    """How much the loop has left, for the brain to weigh and the caller to
    backstop.

    Both fields optional because a campaign may be bounded by count, by
    time, by neither (open-ended), or by the brain's own convergence. The
    stop ceiling lives with the loop (the caller's guard), not inside the
    decider, mirroring how `conduct_until_converged` carries its patience
    cap rather than letting the criterion own it.
    """

    iterations_remaining: int | None = None
    wall_clock_seconds_remaining: float | None = None


@dataclass(frozen=True)
class SteeringEvidence:
    """The full picture handed to a stateless brain on each `advise_next`.

    `objective` + `space` say what good means and where to look; the ordered
    `observations` are the history so the brain reconstructs context every
    call; `budget` + `iteration_index` let it (and the caller's guard) reason
    about exhaustion. The scope ids are OPTIONAL and additive: the
    in-conductor home fills `procedure_id`; an across-Run steerer (deferred)
    fills `campaign_id` + `run_id`. One value type, two homes.

    `iteration_index` follows the first-class iteration naming
    (`iteration_index` / `iteration_count`); it is the 0-based loop turn the
    caller is on.
    """

    objective: SteeringObjective
    space: SteeringSpace
    observations: tuple[SteeringObservation, ...] = ()
    budget: SteeringBudget = field(default_factory=SteeringBudget)
    iteration_index: int = 0
    procedure_id: UUID | None = None
    run_id: UUID | None = None
    campaign_id: UUID | None = None


class DecideNotAvailableError(Exception):
    """The decider could not be reached at all.

    Triggered when an optimizer service / subprocess / model endpoint is
    unreachable or unconfigured. A configuration / environment gap, not a
    per-call rejection. The caller folds this into a deferred steering
    decision rather than crashing the loop.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Decider not available: {reason}")
        self.reason = reason


class DecideTimeoutError(Exception):
    """A hard await ceiling elapsed before the decider returned advice.

    Carries the breached ceiling so logs distinguish "the brain took too
    long" from generic latency. The caller folds it into a deferred
    decision.
    """

    def __init__(self, timeout_s: float) -> None:
        super().__init__(f"Decider advice exceeded {timeout_s}s")
        self.timeout_s = timeout_s


class DecideEvidenceRejectedError(Exception):
    """The decider refused the evidence it was handed.

    Triggered when a brain cannot act on the given evidence (e.g. an empty
    history a particular optimizer requires to be seeded, or an objective it
    does not support). Distinct from `DecideNotAvailableError` (the decider
    is reachable; it is this specific request it declined).
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Decider rejected the evidence: {reason}")
        self.reason = reason


class DecideAdviceMalformedError(Exception):
    """The decider returned advice that violates the port contract.

    Triggered when advice is internally inconsistent (a `Measure` with no
    `next_point`, a `Stop` carrying one), an out-of-range confidence, or an
    over-length rationale. Raised at `SteeringAdvice` construction so a
    malformed brain answer is caught at the seam, and by adapters that
    translate a brain's raw output into advice. The caller folds it into a
    deferred decision.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Decider advice malformed: {reason}")
        self.reason = reason


class DecideAccessDeniedError(Exception):
    """The steering principal may not act through this decider.

    The authorization analogue of ControlPort's `ControlAccessDeniedError`:
    the caller's principal is not permitted to consult the decider for this
    campaign / procedure. Distinct from a malformed answer; the brain never
    ran.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Decider access denied: {reason}")
        self.reason = reason


@dataclass(frozen=True)
class SteeringAdvice:
    """The decider's only output: a next action, or a stop, with provenance.

    `verdict` fuses continue-vs-stop with the suggestion: `Measure` carries
    a `next_point`, `Stop` carries none. `rationale` / `confidence` /
    `confidence_source` / `alternatives` / `model_ref` are the provenance a
    caller records (the in-conductor home onto the iteration ledger; an
    across-Run steerer onto a `Decision`). `confidence_source` reuses the
    shared `DecisionConfidenceSource` so a recorded confidence carries the
    same ISO-42001 derivation label whatever the home.

    Self-validating at construction (raising `DecideAdviceMalformedError`)
    so a malformed brain answer cannot enter the loop: confidence stays in
    [0.0, 1.0] (NaN rejected), the rationale fits `REASONING_MAX_LENGTH`,
    and the verdict / `next_point` pairing is consistent.
    """

    verdict: SteeringVerdict
    next_point: SteeringPoint | None = None
    rationale: str | None = None
    confidence: float | None = None
    confidence_source: DecisionConfidenceSource | None = None
    alternatives: tuple[str, ...] = ()
    model_ref: str | None = None

    def __post_init__(self) -> None:
        if self.verdict is SteeringVerdict.MEASURE and self.next_point is None:
            raise DecideAdviceMalformedError("Measure verdict requires a next_point")
        if self.verdict is SteeringVerdict.STOP and self.next_point is not None:
            raise DecideAdviceMalformedError("Stop verdict must not carry a next_point")
        if self.confidence is not None:
            if self.confidence != self.confidence:  # NaN check (NaN != NaN)
                raise DecideAdviceMalformedError("confidence is NaN")
            if not (0.0 <= self.confidence <= 1.0):
                raise DecideAdviceMalformedError(
                    f"confidence {self.confidence!r} outside [0.0, 1.0]"
                )
        if self.rationale is not None and len(self.rationale) > REASONING_MAX_LENGTH:
            raise DecideAdviceMalformedError(f"rationale exceeds {REASONING_MAX_LENGTH} chars")


@dataclass(frozen=True)
class AdviceAuditFields:
    """The decision-provenance subset of a `SteeringAdvice`, mapped once.

    The sole shape both recording homes consume: the in-conductor iteration
    ledger and an across-Run `Decision`. Produced only by
    `advice_to_audit_fields` so the four validated fields {reasoning,
    confidence, confidence_source, alternatives} stay parity-consistent
    across homes; `model_ref` rides along but is convention-only on the
    Decision side until a typed validator is earned.
    """

    reasoning: str | None
    confidence: float | None
    confidence_source: DecisionConfidenceSource | None
    alternatives: tuple[str, ...]
    model_ref: str | None


def advice_to_audit_fields(advice: SteeringAdvice) -> AdviceAuditFields:
    """Map a `SteeringAdvice` onto its decision-provenance fields.

    The single producer of the audit subset, so the in-conductor and
    across-Run recording homes cannot drift in how advice becomes a decision
    record. Pure: the advice is already validated at construction, so this
    only projects.
    """
    return AdviceAuditFields(
        reasoning=advice.rationale,
        confidence=advice.confidence,
        confidence_source=advice.confidence_source,
        alternatives=advice.alternatives,
        model_ref=advice.model_ref,
    )


@runtime_checkable
class DecidePort(Protocol):
    """Domain-shaped decide seam for autonomous experimentation.

    Optimizer- and action-agnostic. Concrete deciders (`InMemoryDecidePort`,
    a future `GridWalkDecidePort`, a future GP / LLM adapter) implement the
    brain behind the seam. Per [[project_non_determinism_principle]] the
    caller captures the advice onto its event stream at decide time, so a
    replay never re-asks the brain.

    The port is one advisory STEP, never the loop: the caller owns iterate /
    feed-back / stop-guard / conduct. A port that owned the loop could not
    host a stateless brain and would duplicate the Conductor's job.
    """

    async def advise_next(self, evidence: SteeringEvidence) -> SteeringAdvice:
        """Given everything measured so far, advise the next action or stop.

        One async request/response per loop iteration: the caller hands over
        the accumulated `evidence` and gets back a captured-once
        `SteeringAdvice`. Async because the brain is I/O-bound (a model
        call, an optimizer service, a subprocess). Raises
        `DecideNotAvailableError`, `DecideTimeoutError`,
        `DecideEvidenceRejectedError`, `DecideAdviceMalformedError`, or
        `DecideAccessDeniedError`; the caller folds any of these into a
        deferred steering decision rather than crashing the loop.
        """
        ...

    async def aclose(self) -> None:
        """Release any decider resources; idempotent.

        Provided so composition code can `aclose()` any `DecidePort` without
        branching on type (mirrors `ControlPort.aclose` / `ComputePort.aclose`).
        The in-memory fake is a no-op; an adapter holding a model client pool
        or optimizer subprocess releases it here.
        """
        ...


__all__ = [
    "AdviceAuditFields",
    "DecideAccessDeniedError",
    "DecideAdviceMalformedError",
    "DecideEvidenceRejectedError",
    "DecideNotAvailableError",
    "DecidePort",
    "DecideTimeoutError",
    "SteeringAdvice",
    "SteeringAxis",
    "SteeringBudget",
    "SteeringEvidence",
    "SteeringObjective",
    "SteeringObjectiveKind",
    "SteeringObservation",
    "SteeringPoint",
    "SteeringSpace",
    "SteeringVerdict",
    "advice_to_audit_fields",
]
