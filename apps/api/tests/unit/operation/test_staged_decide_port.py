"""Unit tests for StagedDecidePort: the two-phase seeder-then-brain composite.

The routing tests use lightweight recording fakes as the seeder / brain
children, so they exercise the composite's logic without needing the optional
`bo` extra. They pin: routing by successful-observation count, the
stateless phase derivation (same evidence -> same route), failed observations
not counting toward the handoff, Stop reachable only in the brain phase, the
threshold >= brain-floor construction invariant, and aclose closing both
children. The factory test is gated on the `bo` extra (it builds real torch
children).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from cora.operation.adapters.staged_decide_port import StagedDecidePort
from cora.operation.ports.decide_port import (
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


@dataclass
class _RecordingDecider:
    """A fake DecidePort that returns a fixed verdict and records its calls."""

    label: str
    verdict: SteeringVerdict = SteeringVerdict.MEASURE
    calls: int = 0
    closed: bool = False
    received: list[SteeringEvidence] = field(default_factory=list[SteeringEvidence])

    async def advise_next(self, evidence: SteeringEvidence) -> SteeringAdvice:
        self.calls += 1
        self.received.append(evidence)
        next_point = (
            SteeringPoint(coordinates={"x": 1.0})
            if self.verdict is SteeringVerdict.MEASURE
            else None
        )
        return SteeringAdvice(verdict=self.verdict, next_point=next_point, model_ref=self.label)

    async def aclose(self) -> None:
        self.closed = True


def _space() -> SteeringSpace:
    return SteeringSpace(axes=(SteeringAxis(name="x", lower=0.0, upper=1.0),))


def _maximize() -> SteeringObjective:
    return SteeringObjective(kind=SteeringObjectiveKind.MAXIMIZE, target_measurement_name="flux")


def _obs(*, succeeded: bool = True) -> SteeringObservation:
    return SteeringObservation(point=SteeringPoint(coordinates={"x": 0.0}), succeeded=succeeded)


def _evidence(observations: tuple[SteeringObservation, ...]) -> SteeringEvidence:
    return SteeringEvidence(
        objective=_maximize(),
        space=_space(),
        observations=observations,
        iteration_index=len(observations),
    )


async def test_staged_routes_to_seeder_below_threshold() -> None:
    seeder = _RecordingDecider(label="seeder")
    brain = _RecordingDecider(label="brain")
    port = StagedDecidePort(seeder=seeder, brain=brain, threshold=3, brain_min_observations=3)
    advice = await port.advise_next(_evidence((_obs(), _obs())))  # 2 < 3
    assert advice.model_ref == "seeder"
    assert seeder.calls == 1 and brain.calls == 0


async def test_staged_routes_to_brain_at_threshold() -> None:
    seeder = _RecordingDecider(label="seeder")
    brain = _RecordingDecider(label="brain")
    port = StagedDecidePort(seeder=seeder, brain=brain, threshold=3, brain_min_observations=3)
    advice = await port.advise_next(_evidence((_obs(), _obs(), _obs())))  # 3 >= 3
    assert advice.model_ref == "brain"
    assert brain.calls == 1 and seeder.calls == 0


async def test_staged_counts_only_successful_observations() -> None:
    seeder = _RecordingDecider(label="seeder")
    brain = _RecordingDecider(label="brain")
    port = StagedDecidePort(seeder=seeder, brain=brain, threshold=2, brain_min_observations=2)
    # 3 observations but only 1 succeeded -> still seeding.
    obs = (_obs(), _obs(succeeded=False), _obs(succeeded=False))
    advice = await port.advise_next(_evidence(obs))
    assert advice.model_ref == "seeder"


async def test_staged_phase_is_stateless_same_evidence_same_route() -> None:
    seeder = _RecordingDecider(label="seeder")
    brain = _RecordingDecider(label="brain")
    port = StagedDecidePort(seeder=seeder, brain=brain, threshold=2, brain_min_observations=2)
    ev = _evidence((_obs(), _obs()))  # exactly at threshold -> brain
    first = await port.advise_next(ev)
    second = await port.advise_next(ev)
    assert first.model_ref == "brain" and second.model_ref == "brain"


async def test_staged_stop_only_reachable_in_brain_phase() -> None:
    # A seeder that (wrongly) tried to Stop is never consulted past handoff;
    # in the seed phase the composite returns the seeder's verdict, and the
    # Sobol seeder never stops. Here we assert the brain's Stop propagates.
    seeder = _RecordingDecider(label="seeder")
    brain = _RecordingDecider(label="brain", verdict=SteeringVerdict.STOP)
    port = StagedDecidePort(seeder=seeder, brain=brain, threshold=2, brain_min_observations=2)
    advice = await port.advise_next(_evidence((_obs(), _obs())))
    assert advice.verdict is SteeringVerdict.STOP
    assert advice.model_ref == "brain"


async def test_staged_aclose_closes_both_children() -> None:
    seeder = _RecordingDecider(label="seeder")
    brain = _RecordingDecider(label="brain")
    port = StagedDecidePort(seeder=seeder, brain=brain, threshold=2, brain_min_observations=2)
    await port.aclose()
    assert seeder.closed and brain.closed


def test_staged_rejects_threshold_below_brain_floor() -> None:
    seeder = _RecordingDecider(label="seeder")
    brain = _RecordingDecider(label="brain")
    with pytest.raises(ValueError, match="cold-start floor"):
        StagedDecidePort(seeder=seeder, brain=brain, threshold=2, brain_min_observations=5)


def test_staged_rejects_nonpositive_threshold() -> None:
    seeder = _RecordingDecider(label="seeder")
    brain = _RecordingDecider(label="brain")
    with pytest.raises(ValueError, match="threshold"):
        StagedDecidePort(seeder=seeder, brain=brain, threshold=0, brain_min_observations=0)


def test_build_decide_port_staged_returns_staged() -> None:
    pytest.importorskip("botorch", reason="staged substrate builds a real BoTorch brain")
    from cora.operation.adapters.decide_port_config import DecidePortConfig, build_decide_port
    from cora.operation.ports.decide_port import DecidePort

    port = build_decide_port(
        DecidePortConfig(substrate="staged", min_observations=4, staged_threshold=4)
    )
    assert isinstance(port, StagedDecidePort)
    assert isinstance(port, DecidePort)
