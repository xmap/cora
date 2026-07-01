"""BoTorchDecidePort: a Gaussian-process Bayesian-optimization brain.

The first LEARNING decider behind `DecidePort`: it fits a Gaussian process to
the observation history and proposes the next point by optimizing an
acquisition function. BoTorch (MIT, on PyTorch + GPyTorch) supplies the GP and
acquisition primitives; this adapter is the ACL that maps CORA's six-noun
steering evidence onto BoTorch tensors and the chosen candidate back onto a
`SteeringPoint`. The optimizer internals (kernel, acquisition, surrogate,
posterior) stay caged here and never cross the port seam.

## Re-fit from history every call (stateless, cold-start, fixed seed)

The adapter holds NO model across calls. Each `advise_next` rebuilds a fresh
`SingleTaskGP` from the full `SteeringEvidence.observations` and re-runs
`fit_gpytorch_mll`. This is BoTorch's own canonical closed-loop pattern and
honors the port's stateless-brain contract: the advice is a function of the
evidence handed over, not of any cached state. The fit is cold-start (no
warm-start from a previous `state_dict`) and uses a fixed seed, which removes
warm-start path-dependence; it does NOT make the result bit-reproducible
across BLAS / threading / hardware / library versions (see below).

## NOT replay-safe: forward runs only (the boundary)

`fit_gpytorch_mll` + `optimize_acqf` are not bit-reproducible across
environments even with a fixed seed (PyTorch makes no such guarantee; the
acquisition optimization is a non-convex random-restart heuristic; MC
sampling and GP fitting carry intrinsic randomness). The conduct loop's
replay-determinism property holds only for a PURE-FUNCTION brain (the grid
walker, the Sobol seeder); this GP brain is the first that breaks it. A
GP-steered run is therefore a FRESH-FORWARD-RUN-only feature today, and the
caller marks such a run non-replayable. Making GP-steered runs replayable
needs the recorded-decision leg (record the advised next_point and re-seed it
on replay instead of re-asking the brain); that is deferred until a GP-steered
run must actually be replayed or resumed.

## Rejects when cold

A GP needs seed points before a fit is meaningful. With fewer than
`min_observations` usable observations the adapter raises the transient
`DecideColdStartError` (a `DecideEvidenceRejectedError` subtype) rather than
fitting a degenerate model: it never self-seeds. The staged decider catches
that subtype and falls back to its seeder for another point, so the brain is
only fitted once warm; a direct caller gets a clear rejection it can act on.

## Objective kinds

Only `Minimize` / `Maximize` reach the GP today (BoTorch maximizes, so a
`Minimize` objective negates the scalar). `Satisfy` and `Explore` are rejected
(`Explore` carries no target measurement and wants coverage, not optimization;
`Satisfy` would need a target-distance reformulation). A missing
`target_measurement_name`, or an observation missing that named measurement,
is also rejected rather than guessed.
"""

# torch / botorch / gpytorch ship no type stubs; mirror the EPICS control-port
# adapters' suppression so their untyped surface does not leak Unknown across
# this ACL. The CORA-owned domain shapes (evidence, advice, measurements)
# stay fully typed; only the optimizer-library calls are exempted.
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cora.operation.adapters._optional_torch import require_botorch, require_torch
from cora.operation.ports.decide_port import (
    DecideAdviceMalformedError,
    DecideColdStartError,
    DecideEvidenceRejectedError,
    SteeringAdvice,
    SteeringEvidence,
    SteeringObjective,
    SteeringObservation,
    SteeringPoint,
    SteeringSpace,
    SteeringVerdict,
)
from cora.shared.steering import SteeringObjectiveKind

if TYPE_CHECKING:
    from cora.shared.steering import SteeringAxis

_MODEL_REF = "botorch"
_DEFAULT_MIN_OBSERVATIONS = 5
_DEFAULT_NUM_RESTARTS = 10
_DEFAULT_RAW_SAMPLES = 256
_DEFAULT_SEED = 0

_SUPPORTED_KINDS = frozenset({SteeringObjectiveKind.MINIMIZE, SteeringObjectiveKind.MAXIMIZE})


class BoTorchDecidePort:
    """A Gaussian-process Bayesian-optimization decider over a SteeringSpace.

    Satisfies the `DecidePort` Protocol structurally. Fits a `SingleTaskGP`
    to the (successful, Good-quality) observation history and optimizes a
    log-noisy expected-improvement acquisition over the space's continuous
    axes. Probes torch + botorch at construction so a missing `bo` extra
    fails as a `ValueError` at handler time, not deep in the loop.

    `min_observations` is the seed-point floor below which the adapter
    rejects-when-cold. `num_restarts` / `raw_samples` tune the acquisition
    optimizer; `seed` fixes the (forward-run) RNG.
    """

    def __init__(
        self,
        *,
        min_observations: int = _DEFAULT_MIN_OBSERVATIONS,
        num_restarts: int = _DEFAULT_NUM_RESTARTS,
        raw_samples: int = _DEFAULT_RAW_SAMPLES,
        seed: int = _DEFAULT_SEED,
    ) -> None:
        if min_observations < 1:
            raise ValueError(f"min_observations must be >= 1, got {min_observations}")
        if num_restarts < 1:
            raise ValueError(f"num_restarts must be >= 1, got {num_restarts}")
        if raw_samples < 1:
            raise ValueError(f"raw_samples must be >= 1, got {raw_samples}")
        require_torch(_MODEL_REF)
        require_botorch(_MODEL_REF)
        self._min_observations = min_observations
        self._num_restarts = num_restarts
        self._raw_samples = raw_samples
        self._seed = seed

    async def advise_next(self, evidence: SteeringEvidence) -> SteeringAdvice:
        """Fit a GP to the history and advise the acquisition-optimal next point.

        Raises `DecideEvidenceRejectedError` for an unsupported objective
        kind, a missing target measurement, or a non-continuous space; the
        transient `DecideColdStartError` subtype for too few usable seed
        observations (which more evidence fixes, so the staged composite
        falls back to its seeder on it); `DecideAdviceMalformedError` if the
        optimizer returns no candidate.
        """
        _require_supported_objective(evidence.objective)
        names = _continuous_axis_names(evidence.space)
        target = evidence.objective.target_measurement_name
        assert target is not None  # guarded by _require_supported_objective

        usable = [obs for obs in evidence.observations if _is_usable(obs, target)]
        if len(usable) < self._min_observations:
            raise DecideColdStartError(
                f"the {_MODEL_REF!r} decider needs >= {self._min_observations} usable "
                f"observations to fit a GP, got {len(usable)}; seed the space first"
            )

        next_point, acq_value = self._propose(
            evidence.objective, evidence.space, names, usable, target
        )
        return SteeringAdvice(
            verdict=SteeringVerdict.MEASURE,
            next_point=SteeringPoint(coordinates=dict(zip(names, next_point, strict=True))),
            rationale=(f"GP-BO over {len(usable)} observations; acquisition value {acq_value:.4g}"),
            model_ref=_MODEL_REF,
        )

    async def aclose(self) -> None:
        """No-op: the adapter holds no model or client across calls."""
        return None

    def _propose(
        self,
        objective: SteeringObjective,
        space: SteeringSpace,
        names: list[str],
        usable: list[SteeringObservation],
        target: str,
    ) -> tuple[list[float], float]:
        """Fit the GP and optimize the acquisition; return (point, acq_value).

        All torch / botorch use is local to this method so the heavy imports
        stay off the module load path.
        """
        import torch
        from botorch.fit import fit_gpytorch_mll
        from botorch.models import SingleTaskGP
        from botorch.models.transforms import Normalize, Standardize
        from botorch.optim import optimize_acqf
        from gpytorch.mlls import ExactMarginalLogLikelihood

        torch.manual_seed(self._seed)

        train_x = torch.tensor(
            [[float(obs.point.coordinates[name]) for name in names] for obs in usable],
            dtype=torch.double,
        )
        # BoTorch maximizes; negate for Minimize so EI drives the scalar down.
        sign = -1.0 if objective.kind is SteeringObjectiveKind.MINIMIZE else 1.0
        train_y = torch.tensor(
            [[sign * _scalar_for(obs, target)] for obs in usable],
            dtype=torch.double,
        )
        bounds = torch.tensor(
            [[_lower(axis) for axis in space.axes], [_upper(axis) for axis in space.axes]],
            dtype=torch.double,
        )

        dimension = len(names)
        model = SingleTaskGP(
            train_X=train_x,
            train_Y=train_y,
            input_transform=Normalize(d=dimension),
            outcome_transform=Standardize(m=1),
        )
        mll = ExactMarginalLogLikelihood(model.likelihood, model)
        fit_gpytorch_mll(mll)

        acqf = _acquisition_for(model, train_x)
        result: Any = optimize_acqf(
            acq_function=acqf,
            bounds=bounds,
            q=1,
            num_restarts=self._num_restarts,
            raw_samples=self._raw_samples,
        )
        candidate, acq_value = result
        if candidate.numel() == 0:  # pragma: no cover  # optimizer always returns q>=1 rows
            raise DecideAdviceMalformedError("acquisition optimizer returned no candidate")
        point = [float(v) for v in candidate.view(-1)]
        return point, float(acq_value)


def _acquisition_for(model: Any, train_x: Any) -> Any:
    """Build the acquisition function for the fitted model.

    The SINGLE place the acquisition strategy is chosen, isolated so a later
    widening (multi-objective hypervolume improvement, constrained EI, a
    different exploration knob) is a change here, not across the adapter.
    Single-objective today: log noisy expected improvement, the numerically
    stable BoTorch default that needs only the model + the conditioning
    inputs (no externally supplied incumbent).
    """
    from botorch.acquisition.logei import qLogNoisyExpectedImprovement

    return qLogNoisyExpectedImprovement(model=model, X_baseline=train_x)


def _require_supported_objective(objective: SteeringObjective) -> None:
    """Reject an objective kind the GP brain does not handle, or a missing target."""
    if objective.kind not in _SUPPORTED_KINDS:
        raise DecideEvidenceRejectedError(
            f"the {_MODEL_REF!r} decider supports only Minimize / Maximize objectives, "
            f"got {objective.kind.value}"
        )
    if objective.target_measurement_name is None:
        raise DecideEvidenceRejectedError(
            f"a {objective.kind.value} objective needs a target_measurement_name for the "
            f"{_MODEL_REF!r} decider"
        )


def _continuous_axis_names(space: SteeringSpace) -> list[str]:
    """The axis names, rejecting any non-continuous or unbounded axis."""
    if not space.axes:
        raise DecideEvidenceRejectedError("steering space declares no axes to optimize")
    for axis in space.axes:
        if axis.choices:
            raise DecideEvidenceRejectedError(
                f"axis {axis.name!r} carries choices; the {_MODEL_REF!r} decider "
                "optimizes only bounded continuous axes"
            )
        if axis.lower is None or axis.upper is None:
            raise DecideEvidenceRejectedError(
                f"axis {axis.name!r} has no [lower, upper] bound; the {_MODEL_REF!r} "
                "decider cannot optimize it"
            )
    return [axis.name for axis in space.axes]


def _is_usable(obs: SteeringObservation, target: str) -> bool:
    """True if the observation succeeded and carries a Good-quality target scalar."""
    if not obs.succeeded:
        return False
    return any(
        m.name == target and m.quality == "Good" and isinstance(m.value, (int, float))
        for m in obs.measurements
    )


def _scalar_for(obs: SteeringObservation, target: str) -> float:
    """The target measurement's scalar value (the observation is pre-filtered usable)."""
    for m in obs.measurements:
        if m.name == target and m.quality == "Good" and isinstance(m.value, (int, float)):
            return float(m.value)
    raise DecideEvidenceRejectedError(  # pragma: no cover  # _is_usable pre-filters
        f"observation missing usable target measurement {target!r}"
    )


def _lower(axis: SteeringAxis) -> float:
    assert axis.lower is not None  # guarded by _continuous_axis_names
    return axis.lower


def _upper(axis: SteeringAxis) -> float:
    assert axis.upper is not None  # guarded by _continuous_axis_names
    return axis.upper


__all__ = ["BoTorchDecidePort"]
