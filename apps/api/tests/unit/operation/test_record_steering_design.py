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
from cora.infrastructure.ports.llm import ModelRef
from cora.operation._conduct_preparation import (
    SteeringDesign,
    decide_steering_design_recorded,
    verify_steering_design_continuity,
)
from cora.operation.adapters.decide_port_config import DecidePortConfig, LlmDecidePortConfig
from cora.operation.aggregates.procedure import (
    Procedure,
    ProcedureHeld,
    ProcedureRegistered,
    ProcedureStarted,
    ProcedureStatus,
    fold,
    to_payload,
)
from cora.operation.errors import SteeringDesignMismatchError
from cora.operation.ports.decide_port import SteeringBudget
from cora.shared.steering import (
    BoTorchBrain,
    GridWalkBrain,
    InMemoryBrain,
    LlmBrain,
    SobolBrain,
    StagedBrain,
    SteeringAxis,
    SteeringBrain,
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
_DEFINED = ProcedureStatus.DEFINED
_HELD = ProcedureStatus.HELD


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


def _running() -> Procedure | None:
    return fold([_registered(), ProcedureStarted(procedure_id=_PROCEDURE_ID, occurred_at=_EARLIER)])


def _held() -> Procedure | None:
    return fold(
        [
            _registered(),
            ProcedureStarted(procedure_id=_PROCEDURE_ID, occurred_at=_EARLIER),
            ProcedureHeld(
                procedure_id=_PROCEDURE_ID,
                reason="beam dropped",
                occurred_at=_EARLIER,
                actuation_kind="Physical",
            ),
        ]
    )


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
        # Every numeric tunable DISTINCT on purpose. They used to share the
        # dataclass default of 5, which made `points_per_axis`,
        # `min_observations` and `staged_threshold` mutually swappable with
        # no test noticing -- confirmed by mutation during the gate review
        # for this field: reading `staged_threshold` where the flattening
        # means `points_per_axis` passed the entire unit suite.
        "decide": DecidePortConfig(
            substrate="botorch",
            spend_agent_id=_AGENT_ID,
            points_per_axis=3,
            min_observations=4,
            num_restarts=11,
            raw_samples=257,
            seed=7,
            staged_threshold=6,
        ),
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
    events = decide_steering_design_recorded(
        _defined(), [], design, eligible_status=_DEFINED, now=_EARLIER
    )
    return [_stored_pin(to_payload(events[0]), version=version)]


@pytest.mark.unit
def test_decide_records_the_design_for_a_defined_procedure() -> None:
    events = decide_steering_design_recorded(
        _defined(), [], _design(), eligible_status=_DEFINED, now=_NOW
    )

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
    event = decide_steering_design_recorded(
        _defined(), [], _design(), eligible_status=_DEFINED, now=_NOW
    )[0]

    assert event.budget_iterations_remaining == 12
    assert event.budget_wall_clock_seconds_remaining == 600.0
    assert event.points_per_axis == 3
    assert event.min_observations == 4
    assert event.num_restarts == 11
    assert event.raw_samples == 257
    assert event.seed == 7
    assert event.staged_threshold == 6
    # The typed twin of the scalars above: same DecidePortConfig, same
    # `_brain_from_config` call `decide_steering_design_recorded` makes,
    # asserted separately so a divergence between the two shows up as a
    # brain-vs-scalar disagreement rather than being lost in one big
    # equality on the event.
    assert event.brain == BoTorchBrain(min_observations=4, num_restarts=11, raw_samples=257, seed=7)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("substrate", "scalar_field", "brain_field"),
    [
        ("grid_walk", "points_per_axis", "points_per_axis"),
        ("botorch", "min_observations", "min_observations"),
        ("botorch", "num_restarts", "num_restarts"),
        ("botorch", "raw_samples", "raw_samples"),
        ("botorch", "seed", "seed"),
        ("staged", "staged_threshold", "threshold"),
    ],
)
def test_the_typed_brain_agrees_with_its_flat_scalar_twin(
    substrate: str, scalar_field: str, brain_field: str
) -> None:
    """The two recordings of one value must not drift apart.

    `SteeringDesignRecorded` deliberately carries each determining value
    TWICE: once flattened (`points_per_axis` ... `staged_threshold`, kept
    so a reader of the pre-`brain` shape still gets a complete answer) and
    once typed per substrate on `brain`. Two paths to one value is exactly
    the shape that rots: an edit to the flattening that misses
    `_brain_from_config`, or the reverse, leaves a pin that contradicts
    itself and no equality on either half would notice.

    Asserted field by field against the SAME event rather than by
    comparing the two constructions, so both sides come from the one
    `decide_steering_design_recorded` call a caller actually makes.
    """
    config = replace(_design().decide, substrate=substrate)  # type: ignore[arg-type]
    event = decide_steering_design_recorded(
        _defined(), [], _design(decide=config), eligible_status=_DEFINED, now=_NOW
    )[0]

    assert event.brain is not None
    assert getattr(event.brain, brain_field) == getattr(event, scalar_field)


@pytest.mark.unit
def test_the_staged_handoff_brain_agrees_with_its_flat_scalar_twins() -> None:
    """The nested arm has the same two-paths risk one level down.

    `StagedBrain.handoff_brain` re-reads the four BoTorch scalars, so it
    can drift from them independently of the top-level `threshold`.
    """
    config = replace(_design().decide, substrate="staged")
    event = decide_steering_design_recorded(
        _defined(), [], _design(decide=config), eligible_status=_DEFINED, now=_NOW
    )[0]

    assert isinstance(event.brain, StagedBrain)
    assert event.brain.handoff_brain.min_observations == event.min_observations
    assert event.brain.handoff_brain.num_restarts == event.num_restarts
    assert event.brain.handoff_brain.raw_samples == event.raw_samples
    assert event.brain.handoff_brain.seed == event.seed


@pytest.mark.unit
@pytest.mark.parametrize(
    ("config", "expected"),
    [
        (DecidePortConfig(substrate="in_memory"), InMemoryBrain()),
        (
            DecidePortConfig(substrate="grid_walk", points_per_axis=9),
            GridWalkBrain(points_per_axis=9),
        ),
        (DecidePortConfig(substrate="sobol"), SobolBrain()),
        (
            DecidePortConfig(
                substrate="botorch", min_observations=4, num_restarts=6, raw_samples=128, seed=2
            ),
            BoTorchBrain(min_observations=4, num_restarts=6, raw_samples=128, seed=2),
        ),
        (
            DecidePortConfig(
                substrate="staged",
                staged_threshold=9,
                min_observations=4,
                num_restarts=6,
                raw_samples=128,
                seed=2,
            ),
            StagedBrain(
                threshold=9,
                handoff_brain=BoTorchBrain(
                    min_observations=4, num_restarts=6, raw_samples=128, seed=2
                ),
            ),
        ),
        (
            DecidePortConfig(
                substrate="llm",
                llm=LlmDecidePortConfig(
                    model_ref=ModelRef(
                        provider="anthropic", model="claude-opus-4-1", snapshot_pin="pinned"
                    )
                ),
            ),
            LlmBrain(provider="anthropic", model="claude-opus-4-1", snapshot_pin="pinned"),
        ),
    ],
)
def test_decide_records_the_brain_matching_every_substrate(
    config: DecidePortConfig, expected: SteeringBrain
) -> None:
    """One `DecidePortConfig` -> `SteeringBrain` mapping per substrate,
    through the REAL `decide_steering_design_recorded` call.

    `test_decide_flattens_the_budget_and_the_brain_config_into_scalars`
    only exercises `botorch`, the design's own default. This is what
    actually proves `_brain_from_config` reads the CORRECT substrate's
    values rather than always returning one fixed variant regardless of
    `config.substrate` -- including `llm`, whose `snapshot_pin` no other
    test in this module's pipeline covers at all.
    """
    event = decide_steering_design_recorded(
        _defined(), [], _design(decide=config), eligible_status=_DEFINED, now=_NOW
    )[0]

    assert event.brain == expected


@pytest.mark.unit
def test_decide_records_null_budget_scalars_for_an_open_ended_segment() -> None:
    event = decide_steering_design_recorded(
        _defined(), [], _design(budget=None), eligible_status=_DEFINED, now=_NOW
    )[0]

    assert event.budget_iterations_remaining is None
    assert event.budget_wall_clock_seconds_remaining is None


@pytest.mark.unit
def test_decide_records_nothing_when_state_is_none() -> None:
    assert (
        decide_steering_design_recorded(None, [], _design(), eligible_status=_DEFINED, now=_NOW)
        == []
    )


@pytest.mark.unit
def test_decide_records_nothing_when_procedure_already_running() -> None:
    assert (
        decide_steering_design_recorded(
            _running(), [], _design(), eligible_status=_DEFINED, now=_NOW
        )
        == []
    )


@pytest.mark.unit
def test_decide_records_the_design_for_a_held_procedure_on_the_resume_arm() -> None:
    events = decide_steering_design_recorded(
        _held(), [], _design(), eligible_status=_HELD, now=_NOW
    )

    assert len(events) == 1
    assert events[0].occurred_at == _NOW


@pytest.mark.unit
def test_decide_records_nothing_for_a_held_procedure_on_the_forward_arm() -> None:
    """The reachable case that rules out accepting both statuses at once.

    A forward conduct against a Held Procedure runs the shared pipeline, whose
    steps decider refuses that status. A design decider that accepted Held as
    well would append a lone design pin with no steps beside it and only then
    fail in the Conductor, leaving the record carrying a design for a segment
    that never ran a step.
    """
    assert (
        decide_steering_design_recorded(_held(), [], _design(), eligible_status=_DEFINED, now=_NOW)
        == []
    )


@pytest.mark.unit
def test_decide_records_nothing_for_a_defined_procedure_on_the_resume_arm() -> None:
    assert (
        decide_steering_design_recorded(_defined(), [], _design(), eligible_status=_HELD, now=_NOW)
        == []
    )


@pytest.mark.unit
def test_decide_suppresses_a_re_pin_of_an_identical_design() -> None:
    design = _design()

    assert (
        decide_steering_design_recorded(
            _defined(), _pinned(design), design, eligible_status=_DEFINED, now=_NOW
        )
        == []
    )


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

    events = decide_steering_design_recorded(
        _defined(), _pinned(first), corrected, eligible_status=_DEFINED, now=_NOW
    )

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
    assert decide_steering_design_recorded(
        _defined(), _pinned(_design()), corrected, eligible_status=_DEFINED, now=_NOW
    )


@pytest.mark.unit
def test_decide_suppresses_a_re_pin_that_differs_only_in_when_it_happened() -> None:
    design = _design()
    pinned = _pinned(design)
    assert pinned[0].payload["occurred_at"] == _EARLIER.isoformat()

    assert (
        decide_steering_design_recorded(
            _defined(), pinned, design, eligible_status=_DEFINED, now=_NOW
        )
        == []
    )


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

    events = decide_steering_design_recorded(
        _defined(), stream, original, eligible_status=_DEFINED, now=_NOW
    )

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

    events = decide_steering_design_recorded(
        _defined(), [steps_pin], design, eligible_status=_DEFINED, now=_NOW
    )

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

    assert decide_steering_design_recorded(
        _defined(), [widened], design, eligible_status=_DEFINED, now=_NOW
    )


@pytest.mark.unit
def test_decide_re_pins_once_against_a_legacy_pin_that_predates_the_brain_field() -> None:
    """The mirror of the widened-schema case: the CANDIDATE is the wider one.

    A pin written before `brain` existed has no such key, every pin written
    since carries one, so `_designs_match` cannot call them identical even
    when the design is unchanged. That is the same fail-toward-recording
    direction the widened case takes, reached from the other side, and it
    means the first conduct of an existing steered Procedure appends one
    extra pin. Harmless (the FSM events delimit segments, and a reader
    attributes a pass to the most recent pin at or before it) but real, and
    worth pinning so nobody "fixes" the guard into suppressing it, which
    would suppress a genuine correction on any pre-`brain` stream too.
    """
    design = _design()
    pinned = _pinned(design)
    legacy = replace(
        pinned[0],
        payload={k: v for k, v in pinned[0].payload.items() if k != "brain"},
    )

    assert "brain" not in legacy.payload

    assert decide_steering_design_recorded(
        _defined(), [legacy], design, eligible_status=_DEFINED, now=_NOW
    )


@pytest.mark.unit
def test_decide_suppresses_a_re_pin_once_the_legacy_stream_has_been_re_pinned() -> None:
    """The extra pin above happens ONCE, not on every subsequent conduct.

    Without this, "re-pins against a legacy row" would be indistinguishable
    from "re-pins forever", and the guard would be adding a row per conduct
    on any Procedure old enough to predate the field.
    """
    design = _design()
    pinned = _pinned(design)
    legacy = replace(
        pinned[0],
        payload={k: v for k, v in pinned[0].payload.items() if k != "brain"},
    )
    re_pinned = _pinned(design, version=2)

    assert (
        decide_steering_design_recorded(
            _defined(), [legacy, *re_pinned], design, eligible_status=_DEFINED, now=_NOW
        )
        == []
    )


# --- verify_steering_design_continuity (the resume's refusal) ---


def _fsm(event_type: str, *, version: int) -> StoredEvent:
    return replace(_stored_pin({}, version=version), event_type=event_type)


def _governed(design: SteeringDesign, *, version: int = 1) -> list[StoredEvent]:
    """A pin that a segment actually started under, which is the only kind the
    check measures against."""
    return [*_pinned(design, version=version), _fsm("ProcedureStarted", version=version + 1)]


@pytest.mark.unit
def test_continuity_accepts_a_resume_under_the_governing_design() -> None:
    verify_steering_design_continuity(_PROCEDURE_ID, _governed(_design()), _design())


@pytest.mark.unit
@pytest.mark.parametrize(
    ("changed", "expected"),
    [
        (
            _design(space=SteeringSpace(axes=())),
            ("space.axes.theta.missing",),
        ),
        (
            _design(
                space=SteeringSpace(
                    axes=(
                        SteeringAxis(name="theta", lower=-5.0, upper=5.0),
                        SteeringAxis(name="energy", lower=8000.0, upper=12000.0),
                    )
                )
            ),
            ("space.axes.energy.unrecorded",),
        ),
        (
            _design(space=SteeringSpace(axes=(SteeringAxis(name="tehta", lower=-5.0, upper=5.0),))),
            ("space.axes.theta.missing", "space.axes.tehta.unrecorded"),
        ),
    ],
)
def test_continuity_refuses_a_space_that_cannot_hold_a_recorded_point(
    changed: SteeringDesign, expected: tuple[str, ...]
) -> None:
    """The three ways a coordinate ends up with nowhere to live.

    A dropped axis leaves the recorded point carrying a value the space cannot
    hold; an added one leaves it with no value at all; a renamed one is both at
    once, which is what a typo actually looks like and why the message has to
    name the axis rather than say "space".
    """
    with pytest.raises(SteeringDesignMismatchError) as excinfo:
        verify_steering_design_continuity(_PROCEDURE_ID, _governed(_design()), changed)

    assert excinfo.value.differing_fields == expected


@pytest.mark.unit
def test_continuity_refuses_a_categorical_axis_that_dropped_an_already_drawn_choice() -> None:
    """Optuna calls this one out by name, and for the same reason.

    A narrowed choice list can strand a value some earlier pass was actually
    run at, which no amount of recording makes usable: the brain would be
    handed an observation at a setting it is no longer allowed to express.
    """
    pinned = _design(space=SteeringSpace(axes=(SteeringAxis(name="filter", choices=("A", "B")),)))
    narrowed = _design(space=SteeringSpace(axes=(SteeringAxis(name="filter", choices=("A",)),)))

    with pytest.raises(SteeringDesignMismatchError) as excinfo:
        verify_steering_design_continuity(_PROCEDURE_ID, _governed(pinned), narrowed)

    assert excinfo.value.differing_fields == ("space.axes.filter.choices",)


@pytest.mark.unit
@pytest.mark.parametrize(
    "changed",
    [
        _design(space=_space(upper=9.0)),
        _design(space=SteeringSpace(axes=(SteeringAxis(name="theta", lower=-1.0, upper=1.0),))),
        _design(objective_capture_name="other_capture"),
        _design(
            objective=SteeringObjective(
                kind=SteeringObjectiveKind.MAXIMIZE, target_measurement_name="rotation_center"
            )
        ),
        _design(
            objective=SteeringObjective(
                kind=SteeringObjectiveKind.SATISFY,
                target_measurement_name="rotation_center",
                target_value=2048.0,
            )
        ),
    ],
)
def test_continuity_allows_a_change_that_leaves_every_recorded_point_expressible(
    changed: SteeringDesign,
) -> None:
    """Widened bounds, narrowed bounds, a new capture slot, a new objective.

    None of these strand a recorded coordinate. Narrowing bounds in particular
    reads like the dangerous case and is the safe one: the brain stays fitted
    on a wider set than it now proposes within, which is interpolation.
    Widening leaves the new region without data, where the model reports high
    variance and goes to look, which is the whole point of exploration.

    Every one of these IS written to the resumed segment's own pin, so a reader
    can see the change. Recording is what buys the permission.
    """
    verify_steering_design_continuity(_PROCEDURE_ID, _governed(_design()), changed)


@pytest.mark.unit
def test_continuity_is_silent_when_no_pin_exists_at_all() -> None:
    verify_steering_design_continuity(
        _PROCEDURE_ID, [_fsm("ProcedureStarted", version=1)], _design()
    )


@pytest.mark.unit
def test_continuity_measures_against_the_latest_governing_pin_not_the_first() -> None:
    """Two designs have governed segments; the one in force is the later.

    A head-scan here would hold every future resume to the design a Procedure
    was first conducted under, so a legitimate re-pin could never be resumed
    from. The two-pin streams elsewhere in this suite are built AFTER the check
    has run, so none of them would catch the direction being wrong.
    """
    first = _design()
    second = _design(space=SteeringSpace(axes=(SteeringAxis(name="chi", lower=-5.0, upper=5.0),)))
    stream = [
        *_pinned(first, version=1),
        _fsm("ProcedureStarted", version=2),
        _fsm("ProcedureHeld", version=3),
        *_pinned(second, version=4),
        _fsm("ProcedureResumed", version=5),
    ]

    verify_steering_design_continuity(_PROCEDURE_ID, stream, second)

    with pytest.raises(SteeringDesignMismatchError):
        verify_steering_design_continuity(_PROCEDURE_ID, stream, first)


@pytest.mark.unit
def test_continuity_ignores_a_pin_no_segment_ever_started_under() -> None:
    """The pin a refused attempt left behind governed nothing.

    Everything between the pin and the Conductor can still refuse: the steering
    wire guard, the brain factory, the resume's own authorization. Measuring
    against what those left behind would accept only the design that was just
    rejected, and on a stream with no earlier governing pin that locks the
    Procedure out of resuming for good.
    """
    abandoned = _design(
        space=SteeringSpace(axes=(SteeringAxis(name="chi", lower=-5.0, upper=5.0),))
    )
    stream = [
        *_pinned(_design(), version=1),
        _fsm("ProcedureStarted", version=2),
        _fsm("ProcedureHeld", version=3),
        *_pinned(abandoned, version=4),
    ]

    verify_steering_design_continuity(_PROCEDURE_ID, stream, _design())

    with pytest.raises(SteeringDesignMismatchError):
        verify_steering_design_continuity(_PROCEDURE_ID, stream, abandoned)
