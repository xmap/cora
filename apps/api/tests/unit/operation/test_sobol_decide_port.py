"""Unit tests for SobolDecidePort: the deterministic, stateless Sobol
initial-design seeder behind DecidePort.

These pin the deterministic (unscrambled) sequence, the stateless position
derivation from observation count, the bounds scaling, the continuous-only
axis guard, the never-stops contract, and the factory wiring. They require
the optional `bo` dependency group (torch); the module is skipped wholesale
when torch is absent so a base-install test run does not error.
"""

import pytest

pytest.importorskip("torch", reason="SobolDecidePort needs the optional 'bo' extra (torch)")

from cora.operation.adapters.decide_port_config import (
    DecidePortConfig,
    build_decide_port,
)
from cora.operation.adapters.sobol_decide_port import SobolDecidePort
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


def _explore() -> SteeringObjective:
    return SteeringObjective(kind=SteeringObjectiveKind.EXPLORE)


def _obs(coords: dict[str, object], *, succeeded: bool = True) -> SteeringObservation:
    return SteeringObservation(point=SteeringPoint(coordinates=coords), succeeded=succeeded)


def _evidence(
    space: SteeringSpace, observations: tuple[SteeringObservation, ...]
) -> SteeringEvidence:
    return SteeringEvidence(
        objective=_explore(),
        space=space,
        observations=observations,
        iteration_index=len(observations),
    )


async def test_sobol_first_point_is_sequence_start() -> None:
    port = SobolDecidePort()
    space = SteeringSpace(axes=(SteeringAxis(name="energy", lower=0.0, upper=1.0),))
    advice = await port.advise_next(_evidence(space, ()))
    assert advice.verdict is SteeringVerdict.MEASURE
    assert advice.next_point is not None
    # Unscrambled 1-D Sobol starts at 0.0 (then 0.5, 0.75, 0.25, ...).
    assert advice.next_point.coordinates["energy"] == 0.0


async def test_sobol_is_deterministic_same_evidence_same_advice() -> None:
    port = SobolDecidePort()
    space = SteeringSpace(axes=(SteeringAxis(name="x", lower=0.0, upper=1.0),))
    ev = _evidence(space, ())
    first = await port.advise_next(ev)
    second = await port.advise_next(ev)
    assert first == second


async def test_sobol_position_follows_observation_count() -> None:
    port = SobolDecidePort()
    space = SteeringSpace(axes=(SteeringAxis(name="x", lower=0.0, upper=1.0),))
    # 1-D unscrambled Sobol: index 0 -> 0.0, index 1 -> 0.5.
    a0 = await port.advise_next(_evidence(space, ()))
    a1 = await port.advise_next(_evidence(space, (_obs({"x": 0.0}),)))
    assert a0.next_point is not None and a1.next_point is not None
    assert a0.next_point.coordinates["x"] == 0.0
    assert a1.next_point.coordinates["x"] == 0.5


async def test_sobol_scales_to_axis_bounds() -> None:
    port = SobolDecidePort()
    space = SteeringSpace(axes=(SteeringAxis(name="energy", lower=8.0, upper=12.0),))
    # index 1 -> unit 0.5 -> 8.0 + 0.5 * 4.0 = 10.0
    advice = await port.advise_next(_evidence(space, (_obs({"energy": 8.0}),)))
    assert advice.next_point is not None
    assert advice.next_point.coordinates["energy"] == 10.0


async def test_sobol_multi_axis_point_covers_all_names() -> None:
    port = SobolDecidePort()
    space = SteeringSpace(
        axes=(
            SteeringAxis(name="x", lower=0.0, upper=1.0),
            SteeringAxis(name="y", lower=0.0, upper=10.0),
        )
    )
    advice = await port.advise_next(_evidence(space, ()))
    assert advice.next_point is not None
    assert set(advice.next_point.coordinates) == {"x", "y"}
    # First Sobol point is the origin of the (unscrambled) sequence.
    assert advice.next_point.coordinates["x"] == 0.0
    assert advice.next_point.coordinates["y"] == 0.0


async def test_sobol_never_stops() -> None:
    port = SobolDecidePort()
    space = SteeringSpace(axes=(SteeringAxis(name="x", lower=0.0, upper=1.0),))
    # Even with many observations, a seeder keeps emitting points.
    obs = tuple(_obs({"x": 0.0}) for _ in range(50))
    advice = await port.advise_next(_evidence(space, obs))
    assert advice.verdict is SteeringVerdict.MEASURE


async def test_sobol_advances_past_failed_observation() -> None:
    port = SobolDecidePort()
    space = SteeringSpace(axes=(SteeringAxis(name="x", lower=0.0, upper=1.0),))
    # A failed observation still counts toward position (index 1 -> 0.5).
    advice = await port.advise_next(_evidence(space, (_obs({"x": 0.0}, succeeded=False),)))
    assert advice.next_point is not None
    assert advice.next_point.coordinates["x"] == 0.5


async def test_sobol_ignores_objective_kind() -> None:
    port = SobolDecidePort()
    space = SteeringSpace(axes=(SteeringAxis(name="x", lower=0.0, upper=1.0),))
    objective = SteeringObjective(
        kind=SteeringObjectiveKind.SATISFY, target_measurement_name="flux", target_value=1.0
    )
    evidence = SteeringEvidence(objective=objective, space=space)
    advice = await port.advise_next(evidence)
    # A seeder never early-stops on Satisfy: that is the brain's job.
    assert advice.verdict is SteeringVerdict.MEASURE


async def test_sobol_rejects_space_with_no_axes() -> None:
    port = SobolDecidePort()
    evidence = SteeringEvidence(objective=_explore(), space=SteeringSpace(axes=()))
    with pytest.raises(DecideEvidenceRejectedError):
        await port.advise_next(evidence)


async def test_sobol_rejects_discrete_choices_axis() -> None:
    port = SobolDecidePort()
    space = SteeringSpace(axes=(SteeringAxis(name="slot", choices=("A", "B")),))
    with pytest.raises(DecideEvidenceRejectedError):
        await port.advise_next(_evidence(space, ()))


async def test_sobol_rejects_axis_without_bounds() -> None:
    port = SobolDecidePort()
    space = SteeringSpace(axes=(SteeringAxis(name="x"),))
    with pytest.raises(DecideEvidenceRejectedError):
        await port.advise_next(_evidence(space, ()))


async def test_sobol_aclose_is_noop() -> None:
    assert await SobolDecidePort().aclose() is None


def test_build_decide_port_sobol_returns_sobol() -> None:
    port = build_decide_port(DecidePortConfig(substrate="sobol"))
    assert isinstance(port, SobolDecidePort)
    assert isinstance(port, DecidePort)
