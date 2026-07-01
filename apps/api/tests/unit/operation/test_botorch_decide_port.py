"""Unit tests for BoTorchDecidePort: the GP Bayesian-optimization brain.

These pin the objective-kind guard (reject Explore / Satisfy / missing
target), the reject-when-cold floor, the usable-observation filter (drop
failed + non-Good), the candidate-in-bounds contract, objective-sense
(Minimize vs Maximize) handling, the continuous-only axis guard, and the
factory wiring. They require the optional `bo` dependency group (torch +
botorch); the module is skipped wholesale when botorch is absent.
"""

from datetime import UTC, datetime

import pytest

pytest.importorskip("botorch", reason="BoTorchDecidePort needs the optional 'bo' extra")

from cora.operation.adapters.botorch_decide_port import BoTorchDecidePort
from cora.operation.adapters.decide_port_config import (
    DecidePortConfig,
    build_decide_port,
)
from cora.operation.ports.decide_port import (
    DecideColdStartError,
    DecideEvidenceRejectedError,
    DecidePort,
    SteeringAxis,
    SteeringEvidence,
    SteeringObjective,
    SteeringObjectiveKind,
    SteeringObservation,
    SteeringPoint,
    SteeringSpace,
    SteeringVerdict,
)
from cora.operation.ports.measurement import Measurement, Quality

_T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _space() -> SteeringSpace:
    return SteeringSpace(axes=(SteeringAxis(name="x", lower=0.0, upper=10.0),))


def _maximize(target: str = "flux") -> SteeringObjective:
    return SteeringObjective(kind=SteeringObjectiveKind.MAXIMIZE, target_measurement_name=target)


def _obs(
    x: float,
    flux: float | None,
    *,
    succeeded: bool = True,
    quality: Quality = "Good",
    name: str = "flux",
) -> SteeringObservation:
    measurements: tuple[Measurement, ...] = ()
    if flux is not None:
        measurements = (
            Measurement(value=flux, kind="Scalar", quality=quality, produced_at=_T0, name=name),
        )
    return SteeringObservation(
        point=SteeringPoint(coordinates={"x": x}), measurements=measurements, succeeded=succeeded
    )


def _evidence(
    objective: SteeringObjective,
    observations: tuple[SteeringObservation, ...],
    space: SteeringSpace | None = None,
) -> SteeringEvidence:
    return SteeringEvidence(
        objective=objective,
        space=space if space is not None else _space(),
        observations=observations,
        iteration_index=len(observations),
    )


def _seed_obs(n: int = 5) -> tuple[SteeringObservation, ...]:
    # A simple concave-ish set so the GP has signal; values are arbitrary.
    return tuple(_obs(float(i), flux=float(i) * (10 - i)) for i in range(n))


async def test_botorch_proposes_point_within_bounds() -> None:
    port = BoTorchDecidePort(min_observations=3)
    advice = await port.advise_next(_evidence(_maximize(), _seed_obs(5)))
    assert advice.verdict is SteeringVerdict.MEASURE
    assert advice.next_point is not None
    x = advice.next_point.coordinates["x"]
    assert 0.0 <= x <= 10.0
    assert advice.model_ref == "botorch"


async def test_botorch_handles_minimize_objective() -> None:
    port = BoTorchDecidePort(min_observations=3)
    objective = SteeringObjective(
        kind=SteeringObjectiveKind.MINIMIZE, target_measurement_name="flux"
    )
    advice = await port.advise_next(_evidence(objective, _seed_obs(5)))
    assert advice.next_point is not None
    assert 0.0 <= advice.next_point.coordinates["x"] <= 10.0


async def test_botorch_rejects_when_cold() -> None:
    # The cold path raises the TRANSIENT DecideColdStartError subtype (so the
    # staged composite can fall back to its seeder), still catchable as the base
    # DecideEvidenceRejectedError.
    port = BoTorchDecidePort(min_observations=5)
    with pytest.raises(DecideColdStartError, match="usable observations"):
        await port.advise_next(_evidence(_maximize(), _seed_obs(2)))
    with pytest.raises(DecideEvidenceRejectedError):
        await port.advise_next(_evidence(_maximize(), _seed_obs(2)))


async def test_botorch_permanent_rejection_is_not_cold_start() -> None:
    # A permanent rejection (unsupported objective) must NOT be the cold-start
    # subtype, so the staged composite lets it propagate instead of seeding.
    port = BoTorchDecidePort(min_observations=1)
    objective = SteeringObjective(kind=SteeringObjectiveKind.EXPLORE)
    with pytest.raises(DecideEvidenceRejectedError) as excinfo:
        await port.advise_next(_evidence(objective, _seed_obs(5)))
    assert not isinstance(excinfo.value, DecideColdStartError)


async def test_botorch_rejects_explore_objective() -> None:
    port = BoTorchDecidePort(min_observations=1)
    objective = SteeringObjective(kind=SteeringObjectiveKind.EXPLORE)
    with pytest.raises(DecideEvidenceRejectedError, match="Minimize / Maximize"):
        await port.advise_next(_evidence(objective, _seed_obs(5)))


async def test_botorch_rejects_satisfy_objective() -> None:
    port = BoTorchDecidePort(min_observations=1)
    objective = SteeringObjective(
        kind=SteeringObjectiveKind.SATISFY, target_measurement_name="flux", target_value=1.0
    )
    with pytest.raises(DecideEvidenceRejectedError, match="Minimize / Maximize"):
        await port.advise_next(_evidence(objective, _seed_obs(5)))


async def test_botorch_rejects_missing_target_measurement_name() -> None:
    port = BoTorchDecidePort(min_observations=1)
    objective = SteeringObjective(kind=SteeringObjectiveKind.MAXIMIZE, target_measurement_name=None)
    with pytest.raises(DecideEvidenceRejectedError, match="target_measurement_name"):
        await port.advise_next(_evidence(objective, _seed_obs(5)))


async def test_botorch_skips_failed_and_non_good_observations() -> None:
    # 5 raw obs but 2 unusable (one failed, one Uncertain) -> 3 usable < floor of 4.
    port = BoTorchDecidePort(min_observations=4)
    obs = (
        _obs(0.0, 1.0),
        _obs(1.0, 2.0),
        _obs(2.0, None, succeeded=False),
        _obs(3.0, 3.0, quality="Uncertain"),
        _obs(4.0, 4.0),
    )
    with pytest.raises(DecideEvidenceRejectedError, match="usable observations"):
        await port.advise_next(_evidence(_maximize(), obs))


async def test_botorch_rejects_discrete_axis() -> None:
    port = BoTorchDecidePort(min_observations=1)
    space = SteeringSpace(axes=(SteeringAxis(name="slot", choices=("A", "B")),))
    with pytest.raises(DecideEvidenceRejectedError, match="continuous"):
        await port.advise_next(_evidence(_maximize(), _seed_obs(5), space=space))


async def test_botorch_rejects_space_with_no_axes() -> None:
    port = BoTorchDecidePort(min_observations=1)
    space = SteeringSpace(axes=())
    with pytest.raises(DecideEvidenceRejectedError):
        await port.advise_next(_evidence(_maximize(), _seed_obs(5), space=space))


async def test_botorch_aclose_is_noop() -> None:
    assert await BoTorchDecidePort(min_observations=1).aclose() is None


def test_botorch_rejects_nonpositive_config() -> None:
    with pytest.raises(ValueError, match="min_observations"):
        BoTorchDecidePort(min_observations=0)
    with pytest.raises(ValueError, match="num_restarts"):
        BoTorchDecidePort(num_restarts=0)
    with pytest.raises(ValueError, match="raw_samples"):
        BoTorchDecidePort(raw_samples=0)


def test_build_decide_port_botorch_returns_botorch() -> None:
    port = build_decide_port(DecidePortConfig(substrate="botorch"))
    assert isinstance(port, BoTorchDecidePort)
    assert isinstance(port, DecidePort)
