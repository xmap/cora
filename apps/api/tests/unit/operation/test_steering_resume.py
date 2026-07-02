"""Unit tests for steered-loop observation reconstruction (RESUME).

The highest-value RESUME test: recorded self-describing outcome rows -> the exact
observation history the live loop built. Because each row carries its own point
(x) + measurements (y), reconstruction is a sort-by-index then map with no join
to the iteration events, so it pins: the row-to-observation mapping, the sort
(order independent of input order), gap tolerance (an abandoned mid-crash pass
leaves an index gap that must NOT break reconstruction), and the measurement
round-trip (symmetric with conductor._outcome_measurement_to_dict).
"""

from datetime import UTC, datetime
from typing import Any

import pytest

from cora.operation._steering_resume import reconstruct_observations
from cora.operation.conductor import (
    _outcome_measurement_to_dict,  # pyright: ignore[reportPrivateUsage]
)
from cora.operation.ports.control_port import ActuationKind
from cora.operation.ports.decide_port import SteeringObservation, SteeringPoint
from cora.operation.ports.measurement import Measurement
from cora.operation.ports.procedure_outcome_lookup import RecordedOutcome

_NOW = datetime(2026, 7, 2, 12, 0, 0, tzinfo=UTC)


def _measurement(value: float) -> Measurement:
    return Measurement(value=value, kind="Scalar", quality="Good", produced_at=_NOW, name="flux")


def _outcome(
    *,
    index: int,
    point: dict[str, Any],
    value: float,
    succeeded: bool = True,
    actuation_kind: str | None = "Physical",
) -> RecordedOutcome:
    return RecordedOutcome(
        iteration_index=index,
        point=point,
        measurements=[_outcome_measurement_to_dict(_measurement(value))],
        succeeded=succeeded,
        actuation_kind=actuation_kind,
    )


@pytest.mark.unit
def test_reconstructs_one_observation_that_matches_its_row() -> None:
    """A single self-describing row maps to one observation at its own point."""
    obs = reconstruct_observations([_outcome(index=0, point={"energy": 8.0}, value=1.0)])
    assert len(obs) == 1
    assert obs[0].point.coordinates == {"energy": 8.0}
    assert obs[0].measurements[0].value == 1.0


@pytest.mark.unit
def test_reconstructs_each_pass_at_its_own_recorded_point() -> None:
    """Each observation measures at the point recorded ON its row (no join)."""
    outcomes = [
        _outcome(index=0, point={"energy": 8.0}, value=1.0),
        _outcome(index=1, point={"energy": 10.0}, value=2.0),
        _outcome(index=2, point={"energy": 11.5}, value=3.0),
    ]
    obs = reconstruct_observations(outcomes)
    assert [o.point.coordinates["energy"] for o in obs] == [8.0, 10.0, 11.5]
    assert [o.measurements[0].value for o in obs] == [1.0, 2.0, 3.0]


@pytest.mark.unit
def test_reconstruction_sorts_by_index_regardless_of_input_order() -> None:
    """Rows arriving out of order are sorted ascending by iteration_index."""
    outcomes = [
        _outcome(index=2, point={"energy": 11.5}, value=3.0),
        _outcome(index=0, point={"energy": 8.0}, value=1.0),
        _outcome(index=1, point={"energy": 10.0}, value=2.0),
    ]
    obs = reconstruct_observations(outcomes)
    assert [o.point.coordinates["energy"] for o in obs] == [8.0, 10.0, 11.5]


@pytest.mark.unit
def test_reconstruction_tolerates_an_index_gap_from_an_abandoned_pass() -> None:
    """A gap in iteration_index (abandoned mid-crash pass) does NOT break reconstruction.

    A crash can abandon pass k (its FSM iteration was started + counted, but no
    outcome row survived at a dense index), leaving the recorded rows with a gap
    (e.g. 0, 1, 3). Reconstruction sorts + maps regardless of gaps; the brain's
    cursor is the observation count, not the index, so the history stays correct.
    """
    outcomes = [
        _outcome(index=0, point={"energy": 8.0}, value=1.0),
        _outcome(index=1, point={"energy": 10.0}, value=2.0),
        _outcome(index=3, point={"energy": 12.0}, value=4.0),  # index 2 abandoned
    ]
    obs = reconstruct_observations(outcomes)
    assert len(obs) == 3
    assert [o.point.coordinates["energy"] for o in obs] == [8.0, 10.0, 12.0]
    assert [o.measurements[0].value for o in obs] == [1.0, 2.0, 4.0]


@pytest.mark.unit
def test_reconstruction_returns_empty_tuple_when_no_outcomes() -> None:
    """No recorded outcome -> empty history (the frontier re-ask decides next)."""
    assert reconstruct_observations([]) == ()


@pytest.mark.unit
def test_reconstruction_round_trips_measurement_fields() -> None:
    obs = reconstruct_observations([_outcome(index=0, point={"energy": 8.0}, value=7.25)])
    m = obs[0].measurements[0]
    assert m.name == "flux"
    assert m.value == 7.25
    assert m.kind == "Scalar"
    assert m.quality == "Good"


@pytest.mark.unit
def test_reconstruction_preserves_failed_pass_and_actuation_kind() -> None:
    outcomes = [
        _outcome(index=0, point={"energy": 9.0}, value=1.0),
        RecordedOutcome(
            iteration_index=1,
            point={"energy": 10.0},
            measurements=[],
            succeeded=False,
            actuation_kind="Simulated",
        ),
    ]
    obs = reconstruct_observations(outcomes)
    assert obs[1].succeeded is False
    assert obs[1].measurements == ()
    assert obs[1].actuation_kind is ActuationKind.SIMULATED


@pytest.mark.unit
def test_reconstruction_matches_a_hand_built_observation() -> None:
    """Full equality against the SteeringObservation the live loop would build."""
    obs = reconstruct_observations(
        [
            _outcome(index=0, point={"energy": 8.0}, value=1.0),
            _outcome(index=1, point={"energy": 10.0}, value=2.0),
        ]
    )
    expected_pass_1 = SteeringObservation(
        point=SteeringPoint(coordinates={"energy": 10.0}),
        measurements=(_measurement(2.0),),
        artifact_ref=None,
        actuation_kind=ActuationKind.PHYSICAL,
        succeeded=True,
    )
    assert obs[1] == expected_pass_1
