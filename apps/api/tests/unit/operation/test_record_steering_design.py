"""Tier-0 steering-design recording: decide_steering_design_recorded.

Covers:
  - the helper emits one SteeringDesignRecorded for a Defined Procedure,
    flattening the runtime's SteeringBudget + DecidePortConfig into the
    scalars the event carries.
  - None / already-Running state -> no event, the same status rule as the
    steps pin it rides with, so the design can never be pinned without the
    steps it chose.
  - the duplicate guard: an identical design already pinned is suppressed, a
    CORRECTED one is not, and the comparison reads the LATEST pin rather than
    the first.
"""

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.operation._conduct_preparation import (
    SteeringDesign,
    decide_steering_design_recorded,
)
from cora.operation.adapters.decide_port_config import DecidePortConfig
from cora.operation.aggregates.procedure import (
    Procedure,
    ProcedureRegistered,
    ProcedureStarted,
    fold,
    to_payload,
)
from cora.operation.ports.decide_port import SteeringBudget
from cora.shared.steering import (
    SteeringAxis,
    SteeringDesignSource,
    SteeringObjective,
    SteeringObjectiveKind,
    SteeringSpace,
    SteeringSubstrate,
)

_NOW = datetime(2026, 9, 3, 12, 0, 0, tzinfo=UTC)
_EARLIER = datetime(2026, 9, 3, 11, 0, 0, tzinfo=UTC)
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-0000000000d1")
_AGENT_ID = UUID("01900000-0000-7000-8000-0000000000e1")


def _registered() -> ProcedureRegistered:
    return ProcedureRegistered(
        procedure_id=_PROCEDURE_ID,
        name="steered align",
        kind="rotation_center_characterization",
        target_asset_ids=(),
        parent_run_id=None,
        occurred_at=_EARLIER,
    )


def _defined() -> Procedure | None:
    return fold([_registered()])


def _space(upper: float = 5.0) -> SteeringSpace:
    return SteeringSpace(axes=(SteeringAxis(name="theta", lower=-5.0, upper=upper),))


def _design(**overrides: Any) -> SteeringDesign:
    fields: dict[str, Any] = {
        "objective": SteeringObjective(
            kind=SteeringObjectiveKind.SATISFY,
            target_measurement_name="rotation_center",
            target_value=1024.0,
        ),
        "objective_capture_name": "rotation_center",
        "space": _space(),
        "decide": DecidePortConfig(substrate="botorch", spend_agent_id=_AGENT_ID, seed=7),
        "budget": SteeringBudget(iterations_remaining=12, wall_clock_seconds_remaining=600.0),
    }
    fields.update(overrides)
    return SteeringDesign(**fields)


def _stored_pin(payload: dict[str, Any], *, version: int) -> StoredEvent:
    return StoredEvent(
        position=version,
        event_id=uuid4(),
        stream_type="Procedure",
        stream_id=_PROCEDURE_ID,
        version=version,
        event_type="SteeringDesignRecorded",
        schema_version=1,
        payload=payload,
        occurred_at=_EARLIER,
        recorded_at=_EARLIER,
        correlation_id=uuid4(),
        causation_id=None,
    )


def _pinned(design: SteeringDesign, *, version: int = 1) -> Sequence[StoredEvent]:
    """The stream as it looks after `design` was already pinned once, earlier.

    Round-trips through `to_payload` so the stored side is a payload, which is
    what the guard compares against on a real stream.
    """
    events = decide_steering_design_recorded(_defined(), [], design, now=_EARLIER)
    return [_stored_pin(to_payload(events[0]), version=version)]


@pytest.mark.unit
def test_decide_records_the_design_for_a_defined_procedure() -> None:
    events = decide_steering_design_recorded(_defined(), [], _design(), now=_NOW)

    assert len(events) == 1
    event = events[0]
    assert event.procedure_id == _PROCEDURE_ID
    assert event.objective.kind is SteeringObjectiveKind.SATISFY
    assert event.objective.target_value == 1024.0
    assert event.objective_capture_name == "rotation_center"
    assert event.space == _space()
    assert event.substrate is SteeringSubstrate.BOTORCH
    assert event.spend_agent_id == _AGENT_ID
    assert event.design_source is SteeringDesignSource.REQUEST
    assert event.occurred_at == _NOW


@pytest.mark.unit
def test_decide_flattens_the_budget_and_the_brain_config_into_scalars() -> None:
    """The event cannot hold `SteeringBudget` or `DecidePortConfig` themselves.

    `cora.operation.aggregates` may import only `cora.infrastructure` and
    `cora.shared`, so both runtime value objects are unavailable at the event,
    and every one of their fields has to arrive as a scalar. A field silently
    left behind here is a design input the record does not have, which is the
    whole failure the pin exists to prevent, so the flattening is asserted
    field by field rather than through an equality on the event.
    """
    event = decide_steering_design_recorded(_defined(), [], _design(), now=_NOW)[0]

    assert event.budget_iterations_remaining == 12
    assert event.budget_wall_clock_seconds_remaining == 600.0
    assert event.points_per_axis == 5
    assert event.min_observations == 5
    assert event.num_restarts == 10
    assert event.raw_samples == 256
    assert event.seed == 7
    assert event.staged_threshold == 5


@pytest.mark.unit
def test_decide_records_null_budget_scalars_for_an_open_ended_segment() -> None:
    event = decide_steering_design_recorded(_defined(), [], _design(budget=None), now=_NOW)[0]

    assert event.budget_iterations_remaining is None
    assert event.budget_wall_clock_seconds_remaining is None


@pytest.mark.unit
def test_decide_records_nothing_when_state_is_none() -> None:
    assert decide_steering_design_recorded(None, [], _design(), now=_NOW) == []


@pytest.mark.unit
def test_decide_records_nothing_when_procedure_already_running() -> None:
    running = fold(
        [_registered(), ProcedureStarted(procedure_id=_PROCEDURE_ID, occurred_at=_EARLIER)]
    )
    assert decide_steering_design_recorded(running, [], _design(), now=_NOW) == []


@pytest.mark.unit
def test_decide_suppresses_a_re_pin_of_an_identical_design() -> None:
    design = _design()

    assert decide_steering_design_recorded(_defined(), _pinned(design), design, now=_NOW) == []


@pytest.mark.unit
def test_decide_re_pins_a_design_whose_only_difference_is_the_space() -> None:
    """The case the guard must NOT swallow.

    A conduct can fail after the pin and before `start_procedure`, leaving the
    Procedure Defined; the operator then corrects the space and retries. That
    second design is the one that governed the run, so suppressing it would
    leave the record asserting a search over bounds nothing was drawn from.
    """
    first = _design()
    corrected = _design(space=_space(upper=9.0))

    events = decide_steering_design_recorded(_defined(), _pinned(first), corrected, now=_NOW)

    assert len(events) == 1
    assert events[0].space == _space(upper=9.0)


@pytest.mark.unit
@pytest.mark.parametrize(
    "corrected",
    [
        _design(objective_capture_name="other_capture"),
        _design(decide=DecidePortConfig(substrate="grid_walk", spend_agent_id=_AGENT_ID, seed=7)),
        _design(decide=DecidePortConfig(substrate="botorch", spend_agent_id=_AGENT_ID, seed=8)),
        _design(decide=DecidePortConfig(substrate="botorch", spend_agent_id=None, seed=7)),
        _design(budget=SteeringBudget(iterations_remaining=11, wall_clock_seconds_remaining=600.0)),
        _design(budget=None),
    ],
)
def test_decide_re_pins_a_design_differing_in_any_single_input(corrected: SteeringDesign) -> None:
    """Every input the guard compares, varied one at a time.

    Comparing serialized payloads means a key the comparison never reaches is
    indistinguishable from a key that matched, and one design input quietly
    excluded from the guard is one input a correction cannot re-pin.
    """
    assert decide_steering_design_recorded(_defined(), _pinned(_design()), corrected, now=_NOW)


@pytest.mark.unit
def test_decide_suppresses_a_re_pin_that_differs_only_in_when_it_happened() -> None:
    design = _design()
    pinned = _pinned(design)
    assert pinned[0].payload["occurred_at"] == _EARLIER.isoformat()

    assert decide_steering_design_recorded(_defined(), pinned, design, now=_NOW) == []


@pytest.mark.unit
def test_decide_compares_against_the_latest_pin_not_the_first() -> None:
    """Two pins already on the stream, and the design matches the OLDER one.

    A head-scanning reader would compare against the abandoned first attempt,
    find a match and suppress, leaving the stream claiming the corrected design
    was the last word when the operator had reverted to the original. The pin
    that governs is always the most recent.
    """
    original = _design()
    corrected = _design(space=_space(upper=9.0))
    stream = [*_pinned(original, version=1), *_pinned(corrected, version=2)]

    events = decide_steering_design_recorded(_defined(), stream, original, now=_NOW)

    assert len(events) == 1
    assert events[0].space == _space()


@pytest.mark.unit
def test_decide_ignores_pins_of_other_event_types_on_the_stream() -> None:
    """A steps pin sits next to every design pin, and must not be read as one."""
    design = _design()
    steps_pin = replace(
        _pinned(design)[0],
        event_type="ResolvedStepsRecorded",
        payload={"procedure_id": str(_PROCEDURE_ID), "resolved_steps": [], "step_count": 0},
    )

    events = decide_steering_design_recorded(_defined(), [steps_pin], design, now=_NOW)

    assert len(events) == 1


@pytest.mark.unit
def test_decide_re_pins_when_the_stored_pin_carries_a_key_this_code_cannot_read() -> None:
    """A payload from a wider schema is not the same design, it is unreadable.

    Treating it as identical would suppress a pin on the strength of a row this
    build cannot fully compare, and the field it cannot see is exactly the one
    that might differ.
    """
    design = _design()
    pinned = _pinned(design)
    widened = replace(pinned[0], payload={**pinned[0].payload, "acquisition": "qEI"})

    assert decide_steering_design_recorded(_defined(), [widened], design, now=_NOW)
