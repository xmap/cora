"""Unit-tier tests for the `SteeringDesignRecorded` pin, driven through the
REAL `conduct_until_advised` application handler against an in-memory event
store.

`resolve_and_pin_conduct_steps` (`cora.operation._conduct_preparation`) appends
`SteeringDesignRecorded` immediately after `ResolvedStepsRecorded`, in the same
`event_store.append` call, whenever the caller passes a `steering_design=`. The
steered handler `conduct_until_advised` is that caller; its unsteered sibling
`conduct_procedure` passes none. These tests decode the events the handler
actually wrote back off the Procedure stream (via `from_stored`), rather than
inspecting the pure decider functions in isolation, so a wiring mistake between
the handler and the shared pipeline would show up here.

Covers:

  - the design pin lands directly after the steps pin, both before the FSM
    opens (test 1)
  - the pinned `spend_agent_id` and substrate-tunable defaults come from the
    RESOLVED `DecidePortConfig`, not a wire request (test 2)
  - the pinned objective / space / budget mirror the command (test 3)
  - the unsteered `conduct_procedure` sibling pins no `SteeringDesignRecorded`
    at all (regression guard, test 4)
"""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.operation._recipe_expansion import (
    canonical_json_bytes,
    expand,
    steps_to_wire_with_closing,
)
from cora.operation.adapters.decide_port_config import DecidePortConfig
from cora.operation.adapters.in_memory_compute_port import InMemoryComputePort
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.adapters.in_memory_recipe_expander import InMemoryRecipeExpander
from cora.operation.aggregates.procedure import (
    ProcedureRegistered,
    RecipeExpansionRecorded,
    SteeringDesignRecorded,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.operation.conductor import Conductor, ConductorResult
from cora.operation.features import (
    abort_procedure,
    complete_procedure,
    start_iteration,
    start_procedure,
)
from cora.operation.features import (
    end_iteration as end_iteration_feature,
)
from cora.operation.features.conduct_procedure.command import ConductProcedure
from cora.operation.features.conduct_procedure.handler import bind as bind_conduct_procedure
from cora.operation.features.conduct_until_advised.command import ConductUntilAdvised
from cora.operation.features.conduct_until_advised.handler import bind as bind_conduct_until_advised
from cora.operation.ports.decide_port import (
    SteeringAxis,
    SteeringBudget,
    SteeringObjective,
    SteeringObjectiveKind,
    SteeringSpace,
)
from cora.operation.ports.measurement import Measurement
from cora.recipe.aggregates.recipe import (
    RecipeComputeStep,
    RecipeDefined,
    RecipeSetpointStep,
    RecipeStep,
    SteeringRef,
)
from cora.recipe.aggregates.recipe import event_type_name as recipe_event_type_name
from cora.recipe.aggregates.recipe import to_payload as recipe_to_payload
from cora.shared.steering import SteeringDesignSource
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 8, 20, 9, 0, 0, tzinfo=UTC)
_MOTOR_ADDR = "motor"
_OBJECTIVE_NAME = "offset"


def _steering_recipe_steps() -> tuple[RecipeComputeStep, RecipeSetpointStep]:
    """One steered pass: deposit the objective, then move the SteeringRef axis.

    The Recipe-authored twin of `test_steering_ref._steering_block`: a
    `RecipeComputeStep` deposits the objective under `_OBJECTIVE_NAME`, and a
    `RecipeSetpointStep` moves `_MOTOR_ADDR` via a `SteeringRef`, the only
    value-kind the decide loop seeds before each pass.
    """
    return (
        RecipeComputeStep(
            command=("solver", "metric"),
            input_uris=("file:///a.h5",),
            output_uri=None,
            parameters={},
            capture_name=_OBJECTIVE_NAME,
        ),
        RecipeSetpointStep(address=_MOTOR_ADDR, value=SteeringRef(steering_axis_name=_MOTOR_ADDR)),
    )


async def _seed_recipe_driven_procedure(
    store: InMemoryEventStore,
    procedure_id: UUID,
    recipe_id: UUID,
    *,
    recipe_steps: tuple[RecipeStep, ...],
) -> UUID:
    """Seed the Recipe stream plus the 2-event Procedure genesis block.

    Mirrors `test_conduct_procedure_handler._seed_recipe_driven_procedure`,
    but computes `steps_hash` by running the REAL `expand()` against
    `recipe_steps` instead of hand-casting each step to a `SetpointStep`: that
    cast assumes every recipe step is a setpoint, which the steered block
    (a `RecipeComputeStep` first) is not. Returns the minted `capability_id`.
    """
    capability_id = uuid4()
    bindings: dict[str, object] = {}
    recipe_event = RecipeDefined(
        recipe_id=recipe_id,
        name="R",
        capability_id=capability_id,
        steps=recipe_steps,
        occurred_at=_NOW,
    )
    await store.append(
        stream_type="Recipe",
        stream_id=recipe_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=recipe_event_type_name(recipe_event),
                payload=recipe_to_payload(recipe_event),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="seed",
                correlation_id=uuid4(),
                causation_id=None,
                principal_id=uuid4(),
            ),
        ],
    )
    bindings_hash = hashlib.sha256(canonical_json_bytes(dict(bindings))).hexdigest()
    expanded = expand(recipe_steps, bindings)
    steps_hash = hashlib.sha256(
        canonical_json_bytes(steps_to_wire_with_closing(expanded, ()))
    ).hexdigest()
    registered = ProcedureRegistered(
        procedure_id=procedure_id,
        name="P",
        kind="steered_align",
        target_asset_ids=(),
        parent_run_id=None,
        capability_id=capability_id,
        recipe_id=recipe_id,
        occurred_at=_NOW,
    )
    recorded = RecipeExpansionRecorded(
        procedure_id=procedure_id,
        recipe_id=recipe_id,
        recipe_version=None,
        capability_id=capability_id,
        capability_version=None,
        bindings=bindings,
        expansion_port_version=InMemoryRecipeExpander().version,
        steps_hash=steps_hash,
        bindings_hash=bindings_hash,
        step_count=len(recipe_steps),
        occurred_at=_NOW,
    )
    new_events = [
        to_new_event(
            event_type=event_type_name(event),  # type: ignore[arg-type]
            payload=to_payload(event),  # type: ignore[arg-type]
            occurred_at=_NOW,
            event_id=uuid4(),
            command_name="seed",
            correlation_id=uuid4(),
            causation_id=None,
            principal_id=uuid4(),
        )
        for event in (registered, recorded)
    ]
    await store.append(
        stream_type="Procedure",
        stream_id=procedure_id,
        expected_version=0,
        events=new_events,
    )
    return capability_id


@dataclass
class _FakeConductor:
    """Fake Conductor for the UNSTEERED `conduct_procedure` regression guard.

    The real Conductor is exercised by the steered handler tests; this test
    only needs `resolve_and_pin_conduct_steps` (the shared pipeline) to have
    run before the Conductor is reached, so a canned result is enough.
    """

    result: ConductorResult

    async def conduct(self, **_: object) -> ConductorResult:
        return self.result


def _space() -> SteeringSpace:
    return SteeringSpace(axes=(SteeringAxis(name=_MOTOR_ADDR, lower=0.0, upper=10.0),))


def _objective() -> SteeringObjective:
    return SteeringObjective(
        kind=SteeringObjectiveKind.SATISFY,
        target_measurement_name=_OBJECTIVE_NAME,
        target_value=0.0,
    )


def _measurement(value: float) -> Measurement:
    return Measurement(
        value=value,
        kind="Scalar",
        quality="Good",
        produced_at=_NOW,
        name=_OBJECTIVE_NAME,
        units="pixel",
    )


async def _run_steered_conduct(
    store: InMemoryEventStore,
    procedure_id: UUID,
    *,
    decide: DecidePortConfig | None = None,
    budget: SteeringBudget | None = None,
    objective: SteeringObjective | None = None,
    space: SteeringSpace | None = None,
) -> None:
    """Seed a recipe-driven Procedure and drive it through the REAL
    `conduct_until_advised` handler with a REAL `Conductor`, to one completed
    pass (`in_memory` unseeded advises Stop on the first ask)."""
    recipe_id = uuid4()
    await _seed_recipe_driven_procedure(
        store, procedure_id, recipe_id, recipe_steps=_steering_recipe_steps()
    )
    deps = build_deps(ids=[uuid4() for _ in range(40)], now=_NOW, event_store=store)
    control_port = InMemoryControlPort()
    control_port.simulate_connect(_MOTOR_ADDR)
    compute_port = InMemoryComputePort()
    compute_port.set_measurement_sequence(((_measurement(2.0),),))
    conductor = Conductor(
        control_port=control_port,
        append_step=lambda *_a, **_k: _no_append(),  # type: ignore[arg-type]
        clock=deps.clock,
        id_generator=deps.id_generator,
        compute_port=compute_port,
        start_procedure=start_procedure.bind(deps),
        complete_procedure=complete_procedure.bind(deps),
        abort_procedure=abort_procedure.bind(deps),
        start_iteration=start_iteration.bind(deps),
        end_iteration=end_iteration_feature.bind(deps),
    )
    handler = bind_conduct_until_advised(
        deps,
        conductor=conductor,
        expansion_port=InMemoryRecipeExpander(),
    )
    await handler(
        ConductUntilAdvised(
            procedure_id=procedure_id,
            objective=objective or _objective(),
            space=space or _space(),
            objective_capture_name=_OBJECTIVE_NAME,
            decide=decide or DecidePortConfig(),
            budget=budget,
        ),
        principal_id=uuid4(),
        correlation_id=uuid4(),
    )


async def _no_append() -> int:
    return 0


async def _stored_event_types(store: InMemoryEventStore, procedure_id: UUID) -> list[str]:
    stored, _version = await store.load(stream_type="Procedure", stream_id=procedure_id)
    return [event.event_type for event in stored]


@pytest.mark.unit
async def test_conduct_until_advised_pins_the_design_immediately_after_the_steps() -> None:
    """The design pin lands at ResolvedStepsRecorded's index + 1, not merely
    "somewhere before the run starts".

    Asserting only that both events appear before `ProcedureStarted` would
    stay green under a mutation that moves the design pin to right before
    `ProcedureStarted` instead of right after the steps pin: both would still
    precede the FSM opening. That mutation matters because a design recorded
    after the steps it produced were already pinned separately is no longer
    the SAME-append guarantee the module docstring promises, and a design
    pinned any later than immediately-after is no longer a record of what was
    chosen at the moment the steps were fixed. Strict adjacency is the only
    assertion that catches it.
    """
    procedure_id = uuid4()
    store = InMemoryEventStore()
    await _run_steered_conduct(store, procedure_id)

    event_types = await _stored_event_types(store, procedure_id)
    steps_index = event_types.index("ResolvedStepsRecorded")
    design_index = event_types.index("SteeringDesignRecorded")
    started_index = event_types.index("ProcedureStarted")

    assert design_index == steps_index + 1
    assert steps_index < started_index
    assert design_index < started_index


@pytest.mark.unit
async def test_conduct_until_advised_pins_the_resolved_config_not_the_requested_one() -> None:
    procedure_id = uuid4()
    store = InMemoryEventStore()
    spend_agent_id = uuid4()
    await _run_steered_conduct(
        store, procedure_id, decide=DecidePortConfig(spend_agent_id=spend_agent_id)
    )

    stored, _version = await store.load(stream_type="Procedure", stream_id=procedure_id)
    pinned = next(from_stored(e) for e in stored if e.event_type == "SteeringDesignRecorded")
    assert isinstance(pinned, SteeringDesignRecorded)

    assert pinned.spend_agent_id == spend_agent_id
    assert pinned.points_per_axis == 5
    assert pinned.min_observations == 5
    assert pinned.num_restarts == 10
    assert pinned.raw_samples == 256
    assert pinned.seed == 0
    assert pinned.staged_threshold == 5


@pytest.mark.unit
async def test_conduct_until_advised_pins_the_objective_space_and_budget_from_the_command() -> None:
    procedure_id = uuid4()
    store = InMemoryEventStore()
    budget = SteeringBudget(iterations_remaining=7, wall_clock_seconds_remaining=120.0)
    objective = _objective()
    space = _space()
    await _run_steered_conduct(store, procedure_id, budget=budget, objective=objective, space=space)

    stored, _version = await store.load(stream_type="Procedure", stream_id=procedure_id)
    pinned = next(from_stored(e) for e in stored if e.event_type == "SteeringDesignRecorded")
    assert isinstance(pinned, SteeringDesignRecorded)

    assert pinned.objective == objective
    assert pinned.objective_capture_name == _OBJECTIVE_NAME
    assert pinned.space == space
    assert pinned.budget_iterations_remaining == budget.iterations_remaining
    assert pinned.budget_wall_clock_seconds_remaining == budget.wall_clock_seconds_remaining
    assert pinned.design_source is SteeringDesignSource.REQUEST


@pytest.mark.unit
async def test_conduct_procedure_pins_no_steering_design() -> None:
    """The unsteered sibling: `steering_design` defaults to None, and the
    three unsteered callers of `resolve_and_pin_conduct_steps` (of which
    `conduct_procedure` is one) must stay untouched by the design pin."""
    procedure_id = uuid4()
    recipe_id = uuid4()
    store = InMemoryEventStore()
    await _seed_recipe_driven_procedure(
        store,
        procedure_id,
        recipe_id,
        recipe_steps=(RecipeSetpointStep(address="dev:x", value=1.0),),
    )
    deps = build_deps(ids=[uuid4() for _ in range(10)], now=_NOW, event_store=store)
    conductor = _FakeConductor(result=ConductorResult(procedure_id=procedure_id, completed_count=1))
    handler = bind_conduct_procedure(
        deps,
        conductor=conductor,  # type: ignore[arg-type]
        expansion_port=InMemoryRecipeExpander(),
    )
    await handler(
        ConductProcedure(procedure_id=procedure_id, steps=()),
        principal_id=uuid4(),
        correlation_id=uuid4(),
    )

    event_types = await _stored_event_types(store, procedure_id)

    assert "ResolvedStepsRecorded" in event_types
    assert "SteeringDesignRecorded" not in event_types
