"""Shared pre-conduct pipeline for the conduct verb-family slices.

`conduct_procedure` and `conduct_or_hold_procedure` resolve the SAME step list
the same way before handing it to the Conductor, then pin it identically:

  1. recipe re-expansion when the Procedure was created from a recipe
     (the five-step replay gate per [[project-run-procedure-replay-design]]);
  2. pseudoaxis -> constituent expansion when the Procedure is a Run phase
     (resolve each virtual-axis SetpointStep's constituents from the Run's
     Plan wires);
  3. pin the FINAL resolved list as a `ResolvedStepsRecorded` provenance
     event BEFORE any step executes, so a later resume replays this exact
     list rather than re-deriving it, and, for a STEERED conduct, pin the
     design inputs as a `SteeringDesignRecorded` in the SAME append.

A slice cannot import a sibling slice (the cross-slice-independence fitness),
so this BC-level module owns the shared pipeline, mirroring `_conduct_wire`
(shared HTTP/MCP shapes) and `_recipe_expansion/_resolved_steps_replay` (the resume-side read).
The pins are emitted inline rather than via a dedicated command slice: both
are internal provenance events with no operator entry point, exactly like
`RecipeExpansionRecorded`. They share ONE `append` call because a second
append would open a window in which the steps are pinned and the design that
chose them is not, manufacturing exactly the absence the design pin exists to
remove.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.event_payload import find_last_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import EventStore
from cora.infrastructure.ports.event_store import StoredEvent
from cora.operation._recipe_expansion import (
    find_recipe_expansion_record,
    pins_from_payload,
    verify_bindings_hash,
    verify_steps_hash,
)
from cora.operation.adapters.decide_port_config import DecidePortConfig
from cora.operation.aggregates.procedure import (
    Procedure,
    ProcedureBoundCapabilityDeprecatedError,
    ProcedureEvent,
    ProcedureStatus,
    ProcedureStepsForbiddenForRecipeDrivenError,
    RecipeExpanderVersionMismatchError,
    RecipeExpansionRecordNotFoundError,
    ResolvedStepsRecorded,
    SteeringDesignRecorded,
    event_type_name,
    to_payload,
)
from cora.operation.conductor import Step, step_to_payload
from cora.operation.errors import SteeringDesignMismatchError
from cora.operation.ports.decide_port import SteeringBudget
from cora.operation.ports.recipe_expander import RecipeExpander
from cora.recipe.aggregates.capability import CapabilityStatus, load_capability
from cora.recipe.aggregates.plan import (
    PlanNotFoundError,
    constituents_from_wires,
    load_plan,
)
from cora.recipe.aggregates.recipe import load_recipe_at_version
from cora.run.aggregates.run import RunNotFoundError, load_run
from cora.shared.steering import (
    SteeringDesignSource,
    SteeringObjective,
    SteeringSpace,
    SteeringSubstrate,
    serialize_objective,
    serialize_space,
)

if TYPE_CHECKING:
    from cora.operation._pseudoaxis import ConstituentResolver


def decide_resolved_steps_recorded(
    state: Procedure | None,
    resolved_steps: Sequence[Mapping[str, Any]],
    *,
    now: datetime,
    resolved_closing_steps: Sequence[Mapping[str, Any]] = (),
) -> list[ResolvedStepsRecorded]:
    """Pin the resolved step list iff the Procedure is pre-conduct (Defined).

    Returns a single `ResolvedStepsRecorded` when `state` is `Defined`
    (the normal conduct path, before `start_procedure` transitions it to
    `Running`). Returns `[]` when `state` is None or not `Defined`: a
    conduct of a missing / already-running / terminal Procedure records no
    resolved steps and lets the Conductor's `start_procedure` produce the
    normal lifecycle failure, preserving the conduct route's failures-in-body
    contract instead of raising a fresh HTTP error here. Kept as a pure
    function so the decision is unit-testable without an event store.

    `resolved_closing_steps` is the SAME resolution applied to the Recipe's
    closing steps, pinned separately (not flattened into `resolved_steps`)
    so a resume boundary can never land inside the closing region.
    """
    if state is None or state.status is not ProcedureStatus.DEFINED:
        return []
    steps = tuple(dict(step) for step in resolved_steps)
    closing_steps = tuple(dict(step) for step in resolved_closing_steps)
    return [
        ResolvedStepsRecorded(
            procedure_id=state.id,
            resolved_steps=steps,
            step_count=len(steps) + len(closing_steps),
            occurred_at=now,
            resolved_closing_steps=closing_steps,
        )
    ]


@dataclass(frozen=True)
class SteeringDesign:
    """The design inputs of ONE steered conduct segment, as the caller holds them.

    A carrier, not a new concept: the steered handlers already have these five
    values on their command, and this bundles them so
    `resolve_and_pin_conduct_steps` gains one parameter rather than five. The
    runtime VOs are carried WHOLE here (`SteeringBudget`, `DecidePortConfig`)
    and flattened to scalars only at the event boundary, where
    `cora.operation.aggregates` may not import either type.

    `budget` is None for an open-ended segment.
    """

    objective: SteeringObjective
    objective_capture_name: str
    space: SteeringSpace
    decide: DecidePortConfig
    budget: SteeringBudget | None = None


def find_latest_steering_design_record(
    stored_events: Sequence[StoredEvent],
) -> StoredEvent | None:
    """The LAST `SteeringDesignRecorded` on a Procedure stream, or None.

    Scans from the TAIL, unlike its two `find_*_record` siblings
    (`find_recipe_expansion_record`, `find_resolved_steps_record`), which scan
    from the head. The direction is the point rather than an inconsistency: a
    stream can carry more than one design pin, because a conduct that fails
    after the pin and before `start_procedure` leaves the Procedure `Defined`
    and the operator's corrected retry pins again. The pin that GOVERNED the
    segment is therefore the most recent one, and a head-scan would return the
    abandoned attempt. Both siblings return the abandoned attempt today; that
    is a recorded read-side defect in `find_resolved_steps_record`, not a
    convention to copy.

    Keeps the siblings' `find_<subject>_record` skeleton and states the delta
    in the name rather than dropping the prefix: the difference here is a
    missing qualifier, not a different kind of operation. The resume path
    needs this same read, at which point it is the third such scanner and
    fires the rule-of-three hoist recorded at `_resolved_steps_replay.py`,
    which is where all three should land together.
    """
    return find_last_event(stored_events, "SteeringDesignRecorded")


def decide_steering_design_recorded(
    state: Procedure | None,
    stored_events: Sequence[StoredEvent],
    design: SteeringDesign,
    *,
    eligible_status: ProcedureStatus,
    now: datetime,
) -> list[SteeringDesignRecorded]:
    """Pin a steered segment's design inputs iff pre-conduct and not already pinned.

    `eligible_status` is required rather than defaulted because the two callers
    genuinely differ and neither is the obvious default: the forward path pins
    while `Defined`, matching `decide_resolved_steps_recorded` so a design is
    never pinned without the steps it chose beside it, and the resume path pins
    while `Held`, where there is no steps pin to accompany because a resume
    replays the pinned list rather than resolving a new one. Accepting both
    statuses unconditionally would be wrong in a reachable way: a forward
    conduct against a Held Procedure would emit a lone design pin, since the
    steps decider refuses that status, and only then fail in the Conductor.

    The design-implies-steps direction does not hold in reverse, deliberately:
    on a retry whose design is unchanged the duplicate guard below suppresses
    this pin while the steps pin fires again, leaving a steps pin with no
    design beside it. That reads correctly, because the design already on the
    stream is still the one in force.

    Also returns `[]` when the latest pin already on the stream carries an
    IDENTICAL design. This guard is load-bearing here in a way it is not for
    the steps pin: two failure paths (`build_decide_port`'s `ValueError` and
    the Conductor's steering wire guard) fire after the pin and leave the
    Procedure `Defined`, so a retry re-pins. For the steps that re-pin is
    byte-identical and harmless; here the operator has usually CORRECTED the
    space in between, so the second pin carries a different design and is the
    one that must survive. Suppressing only the identical case keeps the
    stream free of noise without ever discarding a real correction.

    Comparison is over the SERIALIZED payload minus `occurred_at`, not over
    the dataclass: the stored side is a payload, and rebuilding it through
    `from_stored` would raise on a row written before a field existed, turning
    a duplicate check into a 500. A payload that cannot be compared simply
    differs, and differing means pin again, which is the safe direction.
    """
    if state is None or state.status is not eligible_status:
        return []
    budget = design.budget
    event = SteeringDesignRecorded(
        procedure_id=state.id,
        objective=design.objective,
        objective_capture_name=design.objective_capture_name,
        space=design.space,
        budget_iterations_remaining=(None if budget is None else budget.iterations_remaining),
        budget_wall_clock_seconds_remaining=(
            None if budget is None else budget.wall_clock_seconds_remaining
        ),
        substrate=SteeringSubstrate(design.decide.substrate),
        points_per_axis=design.decide.points_per_axis,
        min_observations=design.decide.min_observations,
        num_restarts=design.decide.num_restarts,
        raw_samples=design.decide.raw_samples,
        seed=design.decide.seed,
        staged_threshold=design.decide.staged_threshold,
        spend_agent_id=design.decide.spend_agent_id,
        design_source=SteeringDesignSource.REQUEST,
        occurred_at=now,
    )
    latest = find_latest_steering_design_record(stored_events)
    if latest is not None and _designs_match(latest.payload, to_payload(event)):
        return []
    return [event]


_SEGMENT_START_TYPES = ("ProcedureStarted", "ProcedureResumed")


def find_governing_steering_design_record(
    stored_events: Sequence[StoredEvent],
) -> StoredEvent | None:
    """The latest design pin a conduct segment actually STARTED under, or None.

    Not the same question as `find_latest_steering_design_record`, and the
    difference is load-bearing rather than cosmetic. A pin is written before
    the Conductor runs, and several things between the two can still refuse:
    the steering wire guard, the brain factory, the resume's own authorization.
    Such a pin sits on the stream having governed nothing.

    For the duplicate guard that does not matter, since it only asks what was
    written last. For the continuity check it decides whether a Procedure can
    be resumed at all: measuring against a pin left by an attempt that never
    started means the only design accepted is the one that was just rejected,
    and on a stream with no earlier pin to fall back to, nothing can be
    resumed again. So this reads the last pin PRECEDING the last segment start,
    and a pin with no start after it is correctly invisible.
    """
    last_start = -1
    for index, event in enumerate(stored_events):
        if event.event_type in _SEGMENT_START_TYPES:
            last_start = index
    if last_start < 0:
        return None
    return find_last_event(stored_events[:last_start], "SteeringDesignRecorded")


_CONTINUITY_KEYS = ("objective", "objective_capture_name", "space")


def verify_steering_design_continuity(
    procedure_id: UUID,
    stored_events: Sequence[StoredEvent],
    design: SteeringDesign,
) -> None:
    """Refuse a resume whose objective, capture name or space left the pin behind.

    Only `space` has a first-principles argument: it is a DRAW-time property,
    fixing the support the recorded x values came from, so resuming a brain
    over that history while it proposes within different bounds asks it to
    extrapolate outside the region it has data for.

    The other two are a CONSERVATIVE DEFAULT and should be read as one rather
    than as the same argument. `objective` is applied at fit time, not draw
    time: `reconstruct_observations` keeps every `Measurement` on a recorded
    row and the brain selects its scalar by name, so changing the objective is
    a re-read of identical data. `objective_capture_name` really does have a
    correctness condition, but it is agreement with the PINNED STEPS (the slot
    the block deposits), and checking it here checks a proxy for that. Both are
    refused because a mid-Procedure change to either is far more likely to be a
    mistake than an intention, not because the data becomes incommensurable.

    Budget and brain config are NOT compared: `iterations_remaining` decrements
    across a hold by construction, and a substrate change between segments is a
    legitimate operator decision. Note the asymmetry this leaves, deliberately:
    the substrate IS part of the sampling rule, and it may change freely while
    the objective may not. What makes that defensible is that the substrate is
    RECORDED by the resume's own pin, so the change stays verifiable, which is
    the property this whole event exists to provide.

    Silent when no pin GOVERNED an earlier segment, which covers both a
    Procedure conducted before this event existed and one whose only pin was
    left by an attempt that never started. Refusing the first would make a
    record-keeping improvement retroactively break resumes that were fine, and
    refusing the second would lock the Procedure out of resuming entirely; see
    `find_governing_steering_design_record`.

    The two sides come from different places, which is what makes this a real
    check: one was serialized at conduct time and has been sitting in Postgres
    since, the other is the request in hand. They meet through the same
    `serialize_*` pair, so a change to those functions between the two writes
    would read as a design difference rather than a crash. That is the safe
    direction, and rare enough to leave stated rather than engineered around.
    """
    governing = find_governing_steering_design_record(stored_events)
    if governing is None:
        return
    candidate = {
        "objective": serialize_objective(design.objective),
        "objective_capture_name": design.objective_capture_name,
        "space": serialize_space(design.space),
    }
    differing = tuple(
        key for key in _CONTINUITY_KEYS if governing.payload.get(key) != candidate[key]
    )
    if differing:
        raise SteeringDesignMismatchError(procedure_id, differing)


async def pin_steering_design(
    deps: Kernel,
    *,
    command_name: str,
    procedure: Procedure,
    stored_events: Sequence[StoredEvent],
    design: SteeringDesign,
    eligible_status: ProcedureStatus,
    principal_id: UUID,
    correlation_id: UUID,
    causation_id: UUID | None,
) -> None:
    """Append the design pin on its own, for a segment with no steps pin to ride.

    The resume half of the pin. `resolve_and_pin_conduct_steps` puts the two
    pins in one append because it emits both; a resume emits only this one,
    since it replays the already-pinned step list rather than resolving a new
    one. So a lone append here is not the split the design forbids, it is the
    only event there is to write.

    Without it, a Procedure held and resumed under a different substrate would
    end its life with a record asserting a design that governed only its first
    half.
    """
    events = decide_steering_design_recorded(
        procedure,
        stored_events,
        design,
        eligible_status=eligible_status,
        now=deps.clock.now(),
    )
    if not events:
        return
    _, current_version = await deps.event_store.load(
        stream_type="Procedure", stream_id=procedure.id
    )
    await deps.event_store.append(
        stream_type="Procedure",
        stream_id=procedure.id,
        expected_version=current_version,
        events=[
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=event.occurred_at,
                event_id=deps.id_generator.new_id(),
                command_name=command_name,
                correlation_id=correlation_id,
                causation_id=causation_id,
                principal_id=principal_id,
            )
            for event in events
        ],
    )


def _designs_match(pinned: Mapping[str, Any], candidate: Mapping[str, Any]) -> bool:
    """Two `SteeringDesignRecorded` payloads describe the same design.

    Every key but `occurred_at` must match, INCLUDING keys the candidate does
    not know about: a pinned payload carrying an extra key was written by a
    different schema than the one that built the candidate, and calling those
    two designs identical would suppress a pin on the strength of a row this
    code cannot fully read.
    """
    return {key: value for key, value in pinned.items() if key != "occurred_at"} == {
        key: value for key, value in candidate.items() if key != "occurred_at"
    }


async def resolve_and_pin_conduct_steps(
    deps: Kernel,
    *,
    command_name: str,
    procedure: Procedure,
    stored_events: list[StoredEvent],
    caller_steps: Sequence[Step],
    expansion_port: RecipeExpander,
    principal_id: UUID,
    correlation_id: UUID,
    causation_id: UUID | None,
    steering_design: SteeringDesign | None = None,
) -> tuple[tuple[Step, ...], tuple[Step, ...]]:
    """Resolve the final conduct step list + pin it as `ResolvedStepsRecorded`.

    The shared pre-Conductor work for `conduct` / `conduct_or_hold`: recipe
    re-expansion (recipe-driven Procedures) -> pseudoaxis constituent
    expansion (Run-phase Procedures) -> pin. Returns `(steps, closing_steps)`
    to hand to the Conductor. `command_name` rides the pinned event's
    metadata.

    A legacy (non-recipe-driven) Procedure has no closing steps: `caller_steps`
    is an inline list with no separate closing half, so `closing_steps` is
    always `()` on that path.

    `steering_design` is supplied only by the STEERED entry points, and adds
    a `SteeringDesignRecorded` to the same append, immediately after the steps
    pin. The unsteered callers pass nothing and their append is unchanged.
    """
    closing_steps: tuple[Step, ...] = ()
    if procedure.recipe_id is not None:
        steps, closing_steps = await _re_expand_steps(
            procedure_id=procedure.id,
            recipe_id=procedure.recipe_id,
            caller_steps=caller_steps,
            stored_events=stored_events,
            event_store=deps.event_store,
            expansion_port=expansion_port,
        )
    else:
        steps = tuple(caller_steps)

    # A Phase-of-Run Procedure resolves a pseudoaxis's constituent motors from
    # its Run's Plan wires: parent_run_id -> Run.plan_id -> Plan.wires (the
    # same load chain start_procedure walks for its Supply gate). A missing
    # Run / Plan in that chain is corruption, so raise rather than silently
    # skip. Standalone / recipe-driven Procedures (no parent_run_id) pass no
    # resolver, so any pseudoaxis SetpointStep hits the wiring-deferred default
    # and is rejected with PartitionRuleNotFoundError.
    constituent_resolver: ConstituentResolver | None = None
    if procedure.parent_run_id is not None:
        parent_run = await load_run(deps.event_store, procedure.parent_run_id)
        if parent_run is None:
            raise RunNotFoundError(procedure.parent_run_id)
        plan = await load_plan(deps.event_store, parent_run.plan_id)
        if plan is None:
            raise PlanNotFoundError(parent_run.plan_id)

        def _resolve_constituents(asset_id: UUID) -> tuple[UUID, ...]:
            return constituents_from_wires(plan, asset_id)

        constituent_resolver = _resolve_constituents

    # Pre-Conductor PseudoAxis expansion: rewrite any virtual-axis SetpointStep
    # into N sequential constituent SetpointSteps so the Conductor's dispatch
    # loop walks the constituents in declared order. ActionStep / CheckStep
    # pass through unchanged ([[project-pseudoaxis-design]] v3). Closing steps
    # get the SAME expansion, or a pseudoaxis closing setpoint would reach the
    # Conductor unresolved.
    steps = await expansion_port.expand_pseudoaxis(
        steps,
        event_store=deps.event_store,
        correlation_id=correlation_id,
        constituent_resolver=constituent_resolver,
    )
    closing_steps = await expansion_port.expand_pseudoaxis(
        closing_steps,
        event_store=deps.event_store,
        correlation_id=correlation_id,
        constituent_resolver=constituent_resolver,
    )

    # Pin the resolved step list (after recipe + pseudoaxis expansion) BEFORE
    # conducting, so a future resume replays this exact list. The helper emits
    # the event only while the Procedure is still Defined and returns []
    # otherwise, leaving the Conductor's start_procedure to surface a lifecycle
    # failure (keeps the conduct route's failures-in-body contract).
    # One clock read for both pins: they describe one decision taken at one
    # moment, and two reads would let them disagree about when that was.
    now = deps.clock.now()
    pinned_events: list[ProcedureEvent] = list(
        decide_resolved_steps_recorded(
            procedure,
            tuple(step_to_payload(step) for step in steps),
            now=now,
            resolved_closing_steps=tuple(step_to_payload(step) for step in closing_steps),
        )
    )
    if steering_design is not None:
        pinned_events.extend(
            decide_steering_design_recorded(
                procedure,
                stored_events,
                steering_design,
                eligible_status=ProcedureStatus.DEFINED,
                now=now,
            )
        )
    if pinned_events:
        _, current_version = await deps.event_store.load(
            stream_type="Procedure", stream_id=procedure.id
        )
        await deps.event_store.append(
            stream_type="Procedure",
            stream_id=procedure.id,
            expected_version=current_version,
            events=[
                to_new_event(
                    event_type=event_type_name(event),
                    payload=to_payload(event),
                    occurred_at=event.occurred_at,
                    event_id=deps.id_generator.new_id(),
                    command_name=command_name,
                    correlation_id=correlation_id,
                    causation_id=causation_id,
                    principal_id=principal_id,
                )
                for event in pinned_events
            ],
        )

    return steps, closing_steps


async def _re_expand_steps(
    *,
    procedure_id: UUID,
    recipe_id: UUID,
    caller_steps: Sequence[Step],
    stored_events: list[StoredEvent],
    event_store: EventStore,
    expansion_port: RecipeExpander,
) -> tuple[tuple[Step, ...], tuple[Step, ...]]:
    """Run the recipe-replay gate per [[project-run-procedure-replay-design]].

    Six steps: reject non-empty caller steps -> find_recipe_expansion_record
    (raise RecipeExpansionRecordNotFoundError on None) -> pins_from_payload
    -> port-version strict-equals (raise RecipeExpanderVersionMismatchError
    on drift) -> load_recipe_at_version (raise RecipeExpansionRecordNotFoundError
    when None on a recipe-driven Procedure; RecipeVersionNotFoundError
    propagates from helper) -> load_capability + reject Deprecated
    (raise ProcedureBoundCapabilityDeprecatedError, symmetric to
    start_run's RunBoundPlanDeprecatedError) -> verify_bindings_hash ->
    expand (both `recipe.steps` and `recipe.closing_steps`) ->
    verify_steps_hash (one combined pin) -> return `(steps, closing_steps)`.
    """
    if list(caller_steps):
        raise ProcedureStepsForbiddenForRecipeDrivenError(procedure_id)

    record = find_recipe_expansion_record(stored_events)
    if record is None:
        raise RecipeExpansionRecordNotFoundError(procedure_id)

    pins = pins_from_payload(procedure_id, record.payload)

    if pins.expansion_port_version != expansion_port.version:
        raise RecipeExpanderVersionMismatchError(
            procedure_id,
            pins.expansion_port_version,
            expansion_port.version,
        )

    recipe = await load_recipe_at_version(
        event_store,
        recipe_id,
        pins.recipe_version,
    )
    if recipe is None:
        raise RecipeExpansionRecordNotFoundError(procedure_id)

    # Capability-deprecation gate: reject conduct against a tombstoned
    # Capability before running the expansion port. Symmetric to start_run's
    # RunBoundPlanDeprecatedError: re-expanding a Recipe against a Deprecated
    # Capability would silently execute against a contract operators retired.
    capability = await load_capability(event_store, recipe.capability_id)
    if capability is not None and capability.status == CapabilityStatus.DEPRECATED:
        raise ProcedureBoundCapabilityDeprecatedError(procedure_id, recipe.capability_id)

    verify_bindings_hash(procedure_id, pins)
    bindings_dict = dict(pins.bindings)
    expanded = expansion_port.expand(recipe.steps, bindings_dict)
    expanded_closing = expansion_port.expand(recipe.closing_steps, bindings_dict)
    verify_steps_hash(procedure_id, expanded, pins, closing_steps=expanded_closing)
    return expanded, expanded_closing
