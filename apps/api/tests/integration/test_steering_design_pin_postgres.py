"""End-to-end integration: a steered conduct pins its design in real Postgres.

The unit tier drives the same handlers against an in-memory store, which
answers whether the code appends the right events but not whether the payload
survives a round trip through `jsonb`. That gap matters more here than for most
events: `SteeringDesignRecorded` carries two nested value objects (the objective
and the search space, the space itself a list of axes), and the whole reason the
event is typed the way it is was to keep those out of the opaque bucket. A dict
that serializes fine in process and comes back from asyncpg reshaped would
defeat that quietly.

No scenario covered this before. `test_19bm_rotation_characterization.py` calls
the Conductor directly and therefore never reaches the handler where the pin is
written, so a pin that failed only against real storage would have shipped with
the whole suite green.

Covers:
  - the forward conduct writes both pins into one append, adjacent, before the
    FSM opens, and the design survives Postgres byte for byte
  - a resume writes its own pin and the recorded space is the resumed one
  - a resume whose space cannot express an already-recorded coordinate is
    refused, and refused without touching the stream
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import asyncpg
import pytest

from cora.infrastructure.event_envelope import to_new_event
from cora.operation import wire_operation
from cora.operation.adapters.decide_port_config import DecidePortConfig
from cora.operation.aggregates.procedure import (
    ProcedureHeld,
    SteeringDesignRecorded,
    from_stored,
)
from cora.operation.aggregates.procedure import (
    event_type_name as procedure_event_type_name,
)
from cora.operation.aggregates.procedure import (
    to_payload as procedure_to_payload,
)
from cora.operation.errors import SteeringDesignMismatchError
from cora.operation.features.conduct_until_advised import ConductUntilAdvised
from cora.operation.features.conduct_until_advised_from import ConductUntilAdvisedFrom
from cora.operation.features.register_procedure_from_recipe import (
    RegisterProcedureFromRecipe,
)
from cora.operation.ports.decide_port import (
    SteeringAxis,
    SteeringBudget,
    SteeringObjective,
    SteeringObjectiveKind,
    SteeringSpace,
)
from cora.recipe.aggregates.recipe import (
    RecipeComputeStep,
    RecipeDefined,
    RecipeSetpointStep,
    SteeringRef,
    event_type_name,
    to_payload,
)
from tests.integration._helpers import build_postgres_deps, seed_capability_postgres

_NOW = datetime(2026, 9, 3, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_AGENT_ID = UUID("01900000-0000-7000-8000-0000000000e1")
_MOTOR_ADDR = "motor"
_OBJECTIVE_NAME = "offset"


def _objective() -> SteeringObjective:
    return SteeringObjective(
        kind=SteeringObjectiveKind.SATISFY,
        target_measurement_name=_OBJECTIVE_NAME,
        target_value=0.0,
    )


def _space() -> SteeringSpace:
    """Two axes, one continuous and one categorical, so the round trip covers
    both `lower` / `upper` and a populated `choices` list."""
    return SteeringSpace(
        axes=(
            SteeringAxis(name=_MOTOR_ADDR, lower=-5.0, upper=5.0),
            SteeringAxis(name="filter", choices=("A", "B")),
        )
    )


def _steered_recipe_steps() -> tuple[object, ...]:
    """One steered pass: deposit the objective, then move each seeded axis."""
    return (
        RecipeComputeStep(
            command=("solver", "metric"),
            input_uris=("file:///a.h5",),
            output_uri=None,
            parameters={},
            capture_name=_OBJECTIVE_NAME,
        ),
        RecipeSetpointStep(address=_MOTOR_ADDR, value=SteeringRef(steering_axis_name=_MOTOR_ADDR)),
        RecipeSetpointStep(address="filter", value=SteeringRef(steering_axis_name="filter")),
    )


async def _seed_steered_procedure(deps: Any, procedure_id: UUID, recipe_id: UUID) -> None:
    capability_id = UUID(int=procedure_id.int + 1)
    await seed_capability_postgres(deps.event_store, capability_id)
    recipe_event = RecipeDefined(
        recipe_id=recipe_id,
        name="R",
        capability_id=capability_id,
        steps=_steered_recipe_steps(),  # type: ignore[arg-type]
        occurred_at=_NOW,
    )
    await deps.event_store.append(
        stream_type="Recipe",
        stream_id=recipe_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(recipe_event),
                payload=to_payload(recipe_event),
                occurred_at=_NOW,
                event_id=UUID(int=recipe_id.int + 0x10),
                command_name="seed",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )
    handlers = wire_operation(deps)
    await handlers.register_procedure_from_recipe(
        RegisterProcedureFromRecipe(
            name="P",
            kind="rotation_center_characterization",
            target_asset_ids=(),
            parent_run_id=None,
            recipe_id=recipe_id,
            bindings={},
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


def _command(procedure_id: UUID, **overrides: Any) -> ConductUntilAdvised:
    fields: dict[str, Any] = {
        "procedure_id": procedure_id,
        "objective": _objective(),
        "space": _space(),
        "objective_capture_name": _OBJECTIVE_NAME,
        "decide": DecidePortConfig(spend_agent_id=_AGENT_ID),
        "budget": SteeringBudget(iterations_remaining=9, wall_clock_seconds_remaining=300.0),
    }
    fields.update(overrides)
    return ConductUntilAdvised(**fields)


async def _design_pins(deps: Any, procedure_id: UUID) -> list[SteeringDesignRecorded]:
    events, _version = await deps.event_store.load("Procedure", procedure_id)
    pins = [from_stored(e) for e in events if e.event_type == "SteeringDesignRecorded"]
    return [pin for pin in pins if isinstance(pin, SteeringDesignRecorded)]


async def _event_types(deps: Any, procedure_id: UUID) -> list[str]:
    events, _version = await deps.event_store.load("Procedure", procedure_id)
    return [e.event_type for e in events]


@pytest.mark.integration
async def test_steered_conduct_pins_its_design_through_postgres_jsonb(
    db_pool: asyncpg.Pool,
) -> None:
    """Both nested value objects come back off real storage unchanged.

    Asserting the whole rebuilt objective and space, not a field or two: the
    defect this event was retyped to avoid is a nested structure quietly
    flattening, and a spot check on `kind` would survive an axis list that came
    back empty.
    """
    procedure_id = UUID("01900000-0000-7000-8000-000009010001")
    recipe_id = UUID("01900000-0000-7000-8000-000009010004")
    ids = [procedure_id] + [UUID(int=0x01900000_0000_7000_8000_000009010100 + i) for i in range(40)]
    deps = build_postgres_deps(db_pool, now=_NOW, ids=ids)
    await _seed_steered_procedure(deps, procedure_id, recipe_id)

    await wire_operation(deps).conduct_until_advised(
        _command(procedure_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    pins = await _design_pins(deps, procedure_id)
    assert len(pins) == 1
    assert pins[0].objective == _objective()
    assert pins[0].space == _space()
    assert pins[0].budget_iterations_remaining == 9
    assert pins[0].budget_wall_clock_seconds_remaining == 300.0
    assert pins[0].spend_agent_id == _AGENT_ID


@pytest.mark.integration
async def test_steered_conduct_writes_both_pins_adjacent_and_before_the_fsm_opens(
    db_pool: asyncpg.Pool,
) -> None:
    procedure_id = UUID("01900000-0000-7000-8000-000009020001")
    recipe_id = UUID("01900000-0000-7000-8000-000009020004")
    ids = [procedure_id] + [UUID(int=0x01900000_0000_7000_8000_000009020100 + i) for i in range(40)]
    deps = build_postgres_deps(db_pool, now=_NOW, ids=ids)
    await _seed_steered_procedure(deps, procedure_id, recipe_id)

    await wire_operation(deps).conduct_until_advised(
        _command(procedure_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    event_types = await _event_types(deps, procedure_id)
    steps_index = event_types.index("ResolvedStepsRecorded")
    design_index = event_types.index("SteeringDesignRecorded")

    assert design_index == steps_index + 1
    assert design_index < event_types.index("ProcedureStarted")


async def _seed_held_after_a_steered_segment(
    deps: Any, procedure_id: UUID, recipe_id: UUID
) -> None:
    """Drive a real forward conduct, then land the Procedure in Held.

    The forward half is genuine: the handler resolves the recipe, writes both
    pins and runs a pass. The hold is appended directly, because a hold is an
    interruption from outside the loop and a conduct that returns has already
    reached a terminal state, so there is no in-test moment at which
    `hold_procedure` would be accepted.
    """
    await _seed_steered_procedure(deps, procedure_id, recipe_id)
    await wire_operation(deps).conduct_until_advised(
        _command(procedure_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    _events, version = await deps.event_store.load("Procedure", procedure_id)
    held = ProcedureHeld(
        procedure_id=procedure_id,
        reason="beam dropped",
        occurred_at=_NOW,
        actuation_kind="Simulated",
    )
    await deps.event_store.append(
        stream_type="Procedure",
        stream_id=procedure_id,
        expected_version=version,
        events=[
            to_new_event(
                event_type=procedure_event_type_name(held),
                payload=procedure_to_payload(held),
                occurred_at=_NOW,
                event_id=UUID(int=procedure_id.int + 0xBEEF),
                command_name="seed",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )


def _resume_command(procedure_id: UUID, **overrides: Any) -> ConductUntilAdvisedFrom:
    fields: dict[str, Any] = {
        "procedure_id": procedure_id,
        "objective": _objective(),
        "space": _space(),
        "objective_capture_name": _OBJECTIVE_NAME,
        "decide": DecidePortConfig(spend_agent_id=_AGENT_ID),
        "budget": SteeringBudget(iterations_remaining=4, wall_clock_seconds_remaining=120.0),
    }
    fields.update(overrides)
    return ConductUntilAdvisedFrom(**fields)


@pytest.mark.integration
async def test_resumed_steered_conduct_pins_the_design_it_actually_ran_under(
    db_pool: asyncpg.Pool,
) -> None:
    """A resume under narrowed bounds records the narrowing rather than refusing.

    Bounds may move because nothing recorded is stranded by the move, so the
    resumed segment's own pin is the only place the change is visible
    afterwards. Both pins must survive Postgres, not just the first.
    """
    procedure_id = UUID("01900000-0000-7000-8000-000009030001")
    recipe_id = UUID("01900000-0000-7000-8000-000009030004")
    ids = [procedure_id] + [UUID(int=0x01900000_0000_7000_8000_000009030100 + i) for i in range(80)]
    deps = build_postgres_deps(db_pool, now=_NOW, ids=ids)
    await _seed_held_after_a_steered_segment(deps, procedure_id, recipe_id)
    narrowed = SteeringSpace(
        axes=(
            SteeringAxis(name=_MOTOR_ADDR, lower=-1.0, upper=1.0),
            SteeringAxis(name="filter", choices=("A", "B")),
        )
    )

    await wire_operation(deps).conduct_until_advised_from(
        _resume_command(procedure_id, space=narrowed),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    pins = await _design_pins(deps, procedure_id)
    assert len(pins) == 2
    assert pins[0].space == _space()
    assert pins[1].space == narrowed
    assert pins[1].budget_iterations_remaining == 4


@pytest.mark.integration
async def test_resume_refusing_a_space_that_lost_an_axis_leaves_the_stream_untouched(
    db_pool: asyncpg.Pool,
) -> None:
    """The refusal is a read, so it must add nothing of its own.

    A guard that appended before deciding would grow the stream on every
    rejected attempt, and against real storage that is the difference between a
    refusal and a write nobody asked for.
    """
    procedure_id = UUID("01900000-0000-7000-8000-000009040001")
    recipe_id = UUID("01900000-0000-7000-8000-000009040004")
    ids = [procedure_id] + [UUID(int=0x01900000_0000_7000_8000_000009040100 + i) for i in range(80)]
    deps = build_postgres_deps(db_pool, now=_NOW, ids=ids)
    await _seed_held_after_a_steered_segment(deps, procedure_id, recipe_id)
    dropped = SteeringSpace(axes=(SteeringAxis(name=_MOTOR_ADDR, lower=-5.0, upper=5.0),))
    before = await _event_types(deps, procedure_id)

    with pytest.raises(SteeringDesignMismatchError) as excinfo:
        await wire_operation(deps).conduct_until_advised_from(
            _resume_command(procedure_id, space=dropped),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    assert excinfo.value.differing_fields == ("space.axes.filter.missing",)
    assert await _event_types(deps, procedure_id) == before
