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
    DecideColdStartError,
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
from cora.shared.steering import DecidingBrainRef, SteeringSubstrate

_SOBOL = DecidingBrainRef(substrate=SteeringSubstrate.SOBOL)
_BOTORCH = DecidingBrainRef(substrate=SteeringSubstrate.BOTORCH)


@dataclass
class _RecordingDecider:
    """A fake DecidePort that returns a fixed verdict and records its calls.

    `deciding_brain` is the child's typed identity, and the composite
    forwarding it unchanged is what makes an iteration record the DECIDING
    LEAF. The two children are named for the substrates the real composite
    pairs, so a routing assertion reads as the brain that answered rather
    than as a test string.
    """

    deciding_brain: DecidingBrainRef
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
        return SteeringAdvice(
            verdict=self.verdict, next_point=next_point, deciding_brain=self.deciding_brain
        )

    async def aclose(self) -> None:
        self.closed = True


@dataclass
class _RaisingDecider:
    """A fake DecidePort brain that always raises a given exception."""

    deciding_brain: DecidingBrainRef
    exc: Exception
    calls: int = 0

    async def advise_next(self, evidence: SteeringEvidence) -> SteeringAdvice:
        self.calls += 1
        raise self.exc

    async def aclose(self) -> None:
        return None


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
    seeder = _RecordingDecider(deciding_brain=_SOBOL)
    brain = _RecordingDecider(deciding_brain=_BOTORCH)
    port = StagedDecidePort(seeder=seeder, brain=brain, threshold=3, brain_min_observations=3)
    advice = await port.advise_next(_evidence((_obs(), _obs())))  # 2 < 3
    assert advice.deciding_brain == _SOBOL
    assert seeder.calls == 1 and brain.calls == 0


async def test_staged_routes_to_brain_at_threshold() -> None:
    seeder = _RecordingDecider(deciding_brain=_SOBOL)
    brain = _RecordingDecider(deciding_brain=_BOTORCH)
    port = StagedDecidePort(seeder=seeder, brain=brain, threshold=3, brain_min_observations=3)
    advice = await port.advise_next(_evidence((_obs(), _obs(), _obs())))  # 3 >= 3
    assert advice.deciding_brain == _BOTORCH
    assert brain.calls == 1 and seeder.calls == 0


async def test_staged_counts_only_successful_observations() -> None:
    seeder = _RecordingDecider(deciding_brain=_SOBOL)
    brain = _RecordingDecider(deciding_brain=_BOTORCH)
    port = StagedDecidePort(seeder=seeder, brain=brain, threshold=2, brain_min_observations=2)
    # 3 observations but only 1 succeeded -> still seeding.
    obs = (_obs(), _obs(succeeded=False), _obs(succeeded=False))
    advice = await port.advise_next(_evidence(obs))
    assert advice.deciding_brain == _SOBOL


async def test_staged_falls_back_to_seeder_when_brain_cold() -> None:
    # Above the count threshold the brain is tried, but it is still cold (fewer
    # USABLE observations than it needs, e.g. non-Good-quality points counted
    # toward the threshold). The composite must fall back to the seeder so the
    # loop keeps seeding, not propagate the reject and abort the run.
    seeder = _RecordingDecider(deciding_brain=_SOBOL)
    brain = _RaisingDecider(
        deciding_brain=_BOTORCH, exc=DecideColdStartError("needs more usable points")
    )
    port = StagedDecidePort(seeder=seeder, brain=brain, threshold=2, brain_min_observations=2)
    advice = await port.advise_next(_evidence((_obs(), _obs(), _obs())))  # 3 >= 2
    assert brain.calls == 1  # the brain was tried
    assert seeder.calls == 1  # and the seeder produced the fallback point
    assert advice.deciding_brain == _SOBOL
    assert advice.verdict is SteeringVerdict.MEASURE


async def test_staged_propagates_permanent_brain_rejection() -> None:
    # A permanent DecideEvidenceRejectedError (not the cold-start subtype) is
    # NOT fixable by more seeding, so it must propagate and let the loop abort
    # rather than seed forever.
    seeder = _RecordingDecider(deciding_brain=_SOBOL)
    brain = _RaisingDecider(
        deciding_brain=_BOTORCH, exc=DecideEvidenceRejectedError("unsupported objective kind")
    )
    port = StagedDecidePort(seeder=seeder, brain=brain, threshold=2, brain_min_observations=2)
    with pytest.raises(DecideEvidenceRejectedError, match="unsupported objective"):
        await port.advise_next(_evidence((_obs(), _obs())))
    assert brain.calls == 1
    assert seeder.calls == 0  # no fallback for a permanent rejection


async def test_staged_phase_is_stateless_same_evidence_same_route() -> None:
    seeder = _RecordingDecider(deciding_brain=_SOBOL)
    brain = _RecordingDecider(deciding_brain=_BOTORCH)
    port = StagedDecidePort(seeder=seeder, brain=brain, threshold=2, brain_min_observations=2)
    ev = _evidence((_obs(), _obs()))  # exactly at threshold -> brain
    first = await port.advise_next(ev)
    second = await port.advise_next(ev)
    assert first.deciding_brain == _BOTORCH and second.deciding_brain == _BOTORCH


async def test_staged_stop_only_reachable_in_brain_phase() -> None:
    # A seeder that (wrongly) tried to Stop is never consulted past handoff;
    # in the seed phase the composite returns the seeder's verdict, and the
    # Sobol seeder never stops. Here we assert the brain's Stop propagates.
    seeder = _RecordingDecider(deciding_brain=_SOBOL)
    brain = _RecordingDecider(deciding_brain=_BOTORCH, verdict=SteeringVerdict.STOP)
    port = StagedDecidePort(seeder=seeder, brain=brain, threshold=2, brain_min_observations=2)
    advice = await port.advise_next(_evidence((_obs(), _obs())))
    assert advice.verdict is SteeringVerdict.STOP
    assert advice.deciding_brain == _BOTORCH


async def test_staged_aclose_closes_both_children() -> None:
    seeder = _RecordingDecider(deciding_brain=_SOBOL)
    brain = _RecordingDecider(deciding_brain=_BOTORCH)
    port = StagedDecidePort(seeder=seeder, brain=brain, threshold=2, brain_min_observations=2)
    await port.aclose()
    assert seeder.closed and brain.closed


def test_staged_rejects_threshold_below_brain_floor() -> None:
    seeder = _RecordingDecider(deciding_brain=_SOBOL)
    brain = _RecordingDecider(deciding_brain=_BOTORCH)
    with pytest.raises(ValueError, match="cold-start floor"):
        StagedDecidePort(seeder=seeder, brain=brain, threshold=2, brain_min_observations=5)


def test_staged_rejects_nonpositive_threshold() -> None:
    seeder = _RecordingDecider(deciding_brain=_SOBOL)
    brain = _RecordingDecider(deciding_brain=_BOTORCH)
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
