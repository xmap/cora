"""G2: `conduct_until_advised` wire-time guards fail BEFORE any FSM event.

The steered loop's entry runs `_validate_steering_wire` before
`start_procedure`. A mis-wired static block / space / point_to_captures is a
programmer error, so it raises `ValueError` immediately, with NO Procedure
transition recorded (the transcript stays empty). These tests pin that
fail-fast contract for all four structural mis-wires:

  - COVERAGE: a steering axis the brain may propose is not consumed by any
    SetpointStep CaptureRef in the block (a seeded coordinate would never
    reach actuation).
  - DISJOINTNESS (objective): point_to_captures seeds the objective slot (the
    objective is measured, not seeded).
  - DISJOINTNESS (deposit): point_to_captures seeds a slot the block itself
    deposits (a seed would overwrite a measured value).
  - EXACT COVER: point_to_captures does not seed exactly the axis names (an
    under-seed leaves a CaptureRef unresolved; an over-seed fills a stray slot).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.clock import FakeClock
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.adapters.in_memory_compute_port import InMemoryComputePort
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.adapters.in_memory_decide_port import InMemoryDecidePort
from cora.operation.conductor import ComputeStep, Conductor, SetpointStep
from cora.operation.features.append_activities.command import AppendProcedureActivities
from cora.operation.ports.decide_port import (
    SteeringAxis,
    SteeringObjective,
    SteeringObjectiveKind,
    SteeringPoint,
    SteeringSpace,
)
from cora.recipe.aggregates.recipe.body import CaptureRef

_FIXED_NOW = datetime(2026, 6, 25, 9, 0, 0, tzinfo=UTC)
_OBJECTIVE_NAME = "offset"


class _FakeAppendStep:
    async def __call__(
        self,
        command: AppendProcedureActivities,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> int:
        return len(command.entries)


class _FakeIdGen:
    def new_id(self) -> UUID:
        return uuid4()


class _ExplodingHandler:
    """Any FSM handler call is a contract violation here; it must never run."""

    def __init__(self) -> None:
        self.called = False

    async def __call__(self, command: object, **_: object) -> None:
        self.called = True
        raise AssertionError("FSM handler ran despite a wire-time guard violation")


def _conductor() -> tuple[Conductor, list[_ExplodingHandler]]:
    exploders = [_ExplodingHandler() for _ in range(5)]
    conductor = Conductor(
        control_port=InMemoryControlPort(),
        append_step=_FakeAppendStep(),
        clock=FakeClock(_FIXED_NOW),
        id_generator=_FakeIdGen(),
        compute_port=InMemoryComputePort(),
        start_procedure=exploders[0],  # type: ignore[arg-type]
        complete_procedure=exploders[1],  # type: ignore[arg-type]
        abort_procedure=exploders[2],  # type: ignore[arg-type]
        start_iteration=exploders[3],  # type: ignore[arg-type]
        end_iteration=exploders[4],  # type: ignore[arg-type]
    )
    return conductor, exploders


def _objective() -> SteeringObjective:
    return SteeringObjective(
        kind=SteeringObjectiveKind.SATISFY,
        target_measurement_name=_OBJECTIVE_NAME,
        target_value=0.0,
    )


@pytest.mark.architecture
@pytest.mark.unit
async def test_conduct_until_advised_uncovered_axis_fails_at_wire_time() -> None:
    """A steering axis no SetpointStep CaptureRef consumes raises before any FSM event."""
    conductor, exploders = _conductor()
    # The block deposits the objective but has NO SetpointStep consuming `motor`,
    # so the `motor` axis is uncovered.
    block = (
        ComputeStep(
            command=("solver", "metric"),
            input_uris=("file:///a.h5",),
            output_uri=None,
            parameters={},
            capture_name=_OBJECTIVE_NAME,
        ),
    )

    with pytest.raises(ValueError, match="is not consumed by any SetpointStep"):
        await conductor.conduct_until_advised(
            procedure_id=uuid4(),
            principal_id=uuid4(),
            correlation_id=uuid4(),
            steps=block,  # type: ignore[arg-type]
            decide_port=InMemoryDecidePort(),
            objective=_objective(),
            space=SteeringSpace(axes=(SteeringAxis(name="motor", lower=0.0, upper=10.0),)),
            objective_capture_name=_OBJECTIVE_NAME,
            point_to_captures=lambda point: {"motor": point.coordinates["motor"]},
        )

    assert not any(e.called for e in exploders)


@pytest.mark.architecture
@pytest.mark.unit
async def test_conduct_until_advised_seeded_key_overlapping_objective_fails_at_wire_time() -> None:
    """point_to_captures that seeds the objective slot raises before any FSM event."""
    conductor, exploders = _conductor()
    block = (
        ComputeStep(
            command=("solver", "metric"),
            input_uris=("file:///a.h5",),
            output_uri=None,
            parameters={},
            capture_name=_OBJECTIVE_NAME,
        ),
        SetpointStep(
            address="motor",
            value=CaptureRef(capture_name="motor"),
        ),
    )

    def _seeds_objective(point: SteeringPoint) -> dict[str, object]:
        return {"motor": point.coordinates["motor"], _OBJECTIVE_NAME: 0.0}

    with pytest.raises(ValueError, match="seeds the objective slot"):
        await conductor.conduct_until_advised(
            procedure_id=uuid4(),
            principal_id=uuid4(),
            correlation_id=uuid4(),
            steps=block,  # type: ignore[arg-type]
            decide_port=InMemoryDecidePort(),
            objective=_objective(),
            space=SteeringSpace(axes=(SteeringAxis(name="motor", lower=0.0, upper=10.0),)),
            objective_capture_name=_OBJECTIVE_NAME,
            point_to_captures=_seeds_objective,
        )

    assert not any(e.called for e in exploders)


@pytest.mark.architecture
@pytest.mark.unit
async def test_conduct_until_advised_seeded_key_overlapping_deposit_fails_at_wire_time() -> None:
    """point_to_captures that seeds a slot the block also deposits raises before any FSM event."""
    conductor, exploders = _conductor()
    block = (
        ComputeStep(
            command=("solver", "metric"),
            input_uris=("file:///a.h5",),
            output_uri=None,
            parameters={},
            capture_name=_OBJECTIVE_NAME,
        ),
        ComputeStep(
            command=("solver", "aux"),
            input_uris=("file:///b.h5",),
            output_uri=None,
            parameters={},
            capture_name="aux",
        ),
        SetpointStep(
            address="motor",
            value=CaptureRef(capture_name="motor"),
        ),
    )

    def _seeds_deposit(point: SteeringPoint) -> dict[str, object]:
        return {"motor": point.coordinates["motor"], "aux": 1.0}

    with pytest.raises(ValueError, match="also deposits"):
        await conductor.conduct_until_advised(
            procedure_id=uuid4(),
            principal_id=uuid4(),
            correlation_id=uuid4(),
            steps=block,  # type: ignore[arg-type]
            decide_port=InMemoryDecidePort(),
            objective=_objective(),
            space=SteeringSpace(axes=(SteeringAxis(name="motor", lower=0.0, upper=10.0),)),
            objective_capture_name=_OBJECTIVE_NAME,
            point_to_captures=_seeds_deposit,
        )

    assert not any(e.called for e in exploders)


@pytest.mark.architecture
@pytest.mark.unit
async def test_conduct_until_advised_underseeded_point_fails_at_wire_time() -> None:
    """point_to_captures that does not cover exactly the axis names raises before any FSM event."""
    conductor, exploders = _conductor()
    block = (
        ComputeStep(
            command=("solver", "metric"),
            input_uris=("file:///a.h5",),
            output_uri=None,
            parameters={},
            capture_name=_OBJECTIVE_NAME,
        ),
        SetpointStep(
            address="motor",
            value=CaptureRef(capture_name="motor"),
        ),
    )

    with pytest.raises(ValueError, match="cover exactly"):
        await conductor.conduct_until_advised(
            procedure_id=uuid4(),
            principal_id=uuid4(),
            correlation_id=uuid4(),
            steps=block,  # type: ignore[arg-type]
            decide_port=InMemoryDecidePort(),
            objective=_objective(),
            space=SteeringSpace(axes=(SteeringAxis(name="motor", lower=0.0, upper=10.0),)),
            objective_capture_name=_OBJECTIVE_NAME,
            point_to_captures=lambda _point: {},
        )

    assert not any(e.called for e in exploders)
