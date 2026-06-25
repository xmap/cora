"""Unit tests for GridWalkDecidePort: the deterministic, stateless grid/sweep
decider that is the first real brain behind DecidePort (no gpCAM).

These pin the walk order (continuous sweep, discrete choices, Cartesian
product), the stateless position derivation, the Satisfy early-stop, the
exhaustion Stop, and the evidence-rejection guards.
"""

from datetime import UTC, datetime

import pytest

from cora.operation.adapters.decide_port_config import DecidePortConfig, build_decide_port
from cora.operation.adapters.grid_walk_decide_port import GridWalkDecidePort
from cora.operation.ports.decide_port import (
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
from cora.operation.ports.measurement import Measurement

_T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _explore() -> SteeringObjective:
    return SteeringObjective(kind=SteeringObjectiveKind.EXPLORE)


def _obs(
    coords: dict[str, object], *, flux: float | None = None, succeeded: bool = True
) -> SteeringObservation:
    measurements: tuple[Measurement, ...] = ()
    if flux is not None:
        measurements = (
            Measurement(value=flux, kind="Scalar", quality="Good", produced_at=_T0, name="flux"),
        )
    return SteeringObservation(
        point=SteeringPoint(coordinates=coords), measurements=measurements, succeeded=succeeded
    )


async def _walk(port: GridWalkDecidePort, space: SteeringSpace, objective: SteeringObjective):
    """Drive the decider to exhaustion, returning the ordered coordinate dicts."""
    observations: list[SteeringObservation] = []
    coords: list[dict[str, object]] = []
    for i in range(64):  # generous ceiling; the decider Stops well before
        evidence = SteeringEvidence(
            objective=objective, space=space, observations=tuple(observations), iteration_index=i
        )
        advice = await port.advise_next(evidence)
        if advice.verdict is SteeringVerdict.STOP:
            return coords
        assert advice.next_point is not None
        coords.append(dict(advice.next_point.coordinates))
        observations.append(_obs(dict(advice.next_point.coordinates)))
    raise AssertionError("grid walk did not terminate")


async def test_grid_walk_sweeps_single_continuous_axis_inclusive_then_stops() -> None:
    port = GridWalkDecidePort(points_per_axis=3)
    space = SteeringSpace(axes=(SteeringAxis(name="energy", lower=8.0, upper=12.0),))
    coords = await _walk(port, space, _explore())
    assert [c["energy"] for c in coords] == [8.0, 10.0, 12.0]


async def test_grid_walk_walks_discrete_choices_verbatim() -> None:
    port = GridWalkDecidePort()
    space = SteeringSpace(axes=(SteeringAxis(name="slot", choices=("A", "B", "C")),))
    coords = await _walk(port, space, _explore())
    assert [c["slot"] for c in coords] == ["A", "B", "C"]


async def test_grid_walk_cartesian_product_first_axis_slowest() -> None:
    port = GridWalkDecidePort(points_per_axis=2)
    space = SteeringSpace(
        axes=(
            SteeringAxis(name="x", lower=0.0, upper=1.0),
            SteeringAxis(name="y", lower=0.0, upper=1.0),
        )
    )
    coords = await _walk(port, space, _explore())
    assert coords == [
        {"x": 0.0, "y": 0.0},
        {"x": 0.0, "y": 1.0},
        {"x": 1.0, "y": 0.0},
        {"x": 1.0, "y": 1.0},
    ]


async def test_grid_walk_is_stateless_same_evidence_same_advice() -> None:
    port = GridWalkDecidePort(points_per_axis=3)
    space = SteeringSpace(axes=(SteeringAxis(name="energy", lower=8.0, upper=12.0),))
    evidence = SteeringEvidence(
        objective=_explore(), space=space, observations=(), iteration_index=0
    )
    first = await port.advise_next(evidence)
    second = await port.advise_next(evidence)
    assert first == second
    assert first.next_point is not None
    assert first.next_point.coordinates["energy"] == 8.0


async def test_grid_walk_position_follows_observation_count() -> None:
    port = GridWalkDecidePort(points_per_axis=5)
    space = SteeringSpace(axes=(SteeringAxis(name="energy", lower=0.0, upper=4.0),))
    evidence = SteeringEvidence(
        objective=_explore(),
        space=space,
        observations=(_obs({"energy": 0.0}), _obs({"energy": 1.0})),
        iteration_index=2,
    )
    advice = await port.advise_next(evidence)
    assert advice.next_point is not None
    assert advice.next_point.coordinates["energy"] == 2.0


async def test_grid_walk_stops_when_satisfy_target_met_exactly() -> None:
    port = GridWalkDecidePort(points_per_axis=5)
    space = SteeringSpace(axes=(SteeringAxis(name="energy", lower=8.0, upper=12.0),))
    objective = SteeringObjective(
        kind=SteeringObjectiveKind.SATISFY, target_measurement_name="flux", target_value=1.0
    )
    evidence = SteeringEvidence(
        objective=objective,
        space=space,
        observations=(_obs({"energy": 9.0}, flux=1.0),),
        iteration_index=1,
    )
    advice = await port.advise_next(evidence)
    assert advice.verdict is SteeringVerdict.STOP


async def test_grid_walk_continues_when_satisfy_target_unmet() -> None:
    port = GridWalkDecidePort(points_per_axis=5)
    space = SteeringSpace(axes=(SteeringAxis(name="energy", lower=8.0, upper=12.0),))
    objective = SteeringObjective(
        kind=SteeringObjectiveKind.SATISFY, target_measurement_name="flux", target_value=1.0
    )
    evidence = SteeringEvidence(
        objective=objective,
        space=space,
        observations=(_obs({"energy": 9.0}, flux=0.5),),
        iteration_index=1,
    )
    advice = await port.advise_next(evidence)
    assert advice.verdict is SteeringVerdict.MEASURE


async def test_grid_walk_advances_past_a_failed_observation() -> None:
    port = GridWalkDecidePort(points_per_axis=5)
    space = SteeringSpace(axes=(SteeringAxis(name="energy", lower=0.0, upper=4.0),))
    evidence = SteeringEvidence(
        objective=_explore(),
        space=space,
        observations=(_obs({"energy": 0.0}), _obs({"energy": 1.0}, succeeded=False)),
        iteration_index=2,
    )
    advice = await port.advise_next(evidence)
    assert advice.next_point is not None
    # The failed point at index 1 is not retried; the walk advances to index 2.
    assert advice.next_point.coordinates["energy"] == 2.0


async def test_grid_walk_continues_when_satisfy_named_measurement_absent() -> None:
    port = GridWalkDecidePort(points_per_axis=5)
    space = SteeringSpace(axes=(SteeringAxis(name="energy", lower=8.0, upper=12.0),))
    objective = SteeringObjective(
        kind=SteeringObjectiveKind.SATISFY, target_measurement_name="flux", target_value=1.0
    )
    evidence = SteeringEvidence(
        objective=objective,
        space=space,
        observations=(_obs({"energy": 9.0}),),  # no flux measurement on the observation
        iteration_index=1,
    )
    advice = await port.advise_next(evidence)
    assert advice.verdict is SteeringVerdict.MEASURE


async def test_grid_walk_single_point_per_axis_uses_lower_bound() -> None:
    port = GridWalkDecidePort(points_per_axis=1)
    space = SteeringSpace(axes=(SteeringAxis(name="energy", lower=8.0, upper=12.0),))
    evidence = SteeringEvidence(objective=_explore(), space=space)
    advice = await port.advise_next(evidence)
    assert advice.next_point is not None
    assert advice.next_point.coordinates["energy"] == 8.0


async def test_grid_walk_rejects_space_with_no_axes() -> None:
    port = GridWalkDecidePort()
    evidence = SteeringEvidence(objective=_explore(), space=SteeringSpace(axes=()))
    with pytest.raises(DecideEvidenceRejectedError):
        await port.advise_next(evidence)


async def test_grid_walk_rejects_axis_without_choices_or_bounds() -> None:
    port = GridWalkDecidePort()
    space = SteeringSpace(axes=(SteeringAxis(name="energy"),))
    evidence = SteeringEvidence(objective=_explore(), space=space)
    with pytest.raises(DecideEvidenceRejectedError):
        await port.advise_next(evidence)


async def test_grid_walk_aclose_is_noop() -> None:
    assert await GridWalkDecidePort().aclose() is None


def test_grid_walk_rejects_nonpositive_resolution() -> None:
    with pytest.raises(ValueError, match="points_per_axis"):
        GridWalkDecidePort(points_per_axis=0)


def test_build_decide_port_grid_walk_returns_grid_walk() -> None:
    port = build_decide_port(DecidePortConfig(substrate="grid_walk", points_per_axis=7))
    assert isinstance(port, GridWalkDecidePort)
    assert isinstance(port, DecidePort)
