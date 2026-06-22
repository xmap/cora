"""Shared pre-conduct pipeline for the conduct verb-family slices.

`conduct_procedure` and `try_conduct_procedure` resolve the SAME step list
the same way before handing it to the Conductor, then pin it identically:

  1. recipe re-expansion when the Procedure was created from a recipe
     (the five-step replay gate per [[project-run-procedure-replay-design]]);
  2. pseudoaxis -> constituent expansion when the Procedure is a Run phase
     (resolve each virtual-axis SetpointStep's constituents from the Run's
     Plan wires);
  3. pin the FINAL resolved list as a `ResolvedStepsRecorded` provenance
     event BEFORE any step executes, so a later resume replays this exact
     list rather than re-deriving it.

A slice cannot import a sibling slice (the cross-slice-independence fitness),
so this BC-level module owns the shared pipeline, mirroring `_conduct_wire`
(shared HTTP/MCP shapes) and `_recipe_expansion/_resolved_steps_replay` (the resume-side read).
The pin is emitted inline rather than via a dedicated command slice:
`ResolvedStepsRecorded` is an internal provenance event with no operator
entry point, exactly like `RecipeExpansionRecorded`.
"""

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import EventStore
from cora.infrastructure.ports.event_store import StoredEvent
from cora.operation._recipe_expansion import (
    find_recipe_expansion_record,
    pins_from_payload,
    verify_bindings_hash,
    verify_steps_hash,
)
from cora.operation.aggregates.procedure import (
    Procedure,
    ProcedureBoundCapabilityDeprecatedError,
    ProcedureStatus,
    ProcedureStepsForbiddenForRecipeDrivenError,
    RecipeExpanderVersionMismatchError,
    RecipeExpansionRecordNotFoundError,
    ResolvedStepsRecorded,
    event_type_name,
    to_payload,
)
from cora.operation.conductor import Step, step_to_payload
from cora.operation.ports.recipe_expander import RecipeExpander
from cora.recipe.aggregates.capability import CapabilityStatus, load_capability
from cora.recipe.aggregates.plan import (
    PlanNotFoundError,
    constituents_from_wires,
    load_plan,
)
from cora.recipe.aggregates.recipe import load_recipe_at_version
from cora.run.aggregates.run import RunNotFoundError, load_run

if TYPE_CHECKING:
    from cora.operation._pseudoaxis import ConstituentResolver


def decide_resolved_steps_recorded(
    state: Procedure | None,
    resolved_steps: Sequence[Mapping[str, Any]],
    *,
    now: datetime,
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
    """
    if state is None or state.status is not ProcedureStatus.DEFINED:
        return []
    steps = tuple(dict(step) for step in resolved_steps)
    return [
        ResolvedStepsRecorded(
            procedure_id=state.id,
            resolved_steps=steps,
            step_count=len(steps),
            occurred_at=now,
        )
    ]


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
) -> tuple[Step, ...]:
    """Resolve the final conduct step list + pin it as `ResolvedStepsRecorded`.

    The shared pre-Conductor work for `conduct` / `try_conduct`: recipe
    re-expansion (recipe-driven Procedures) -> pseudoaxis constituent
    expansion (Run-phase Procedures) -> pin. Returns the resolved steps to
    hand to the Conductor. `command_name` rides the pinned event's metadata.
    """
    if procedure.recipe_id is not None:
        steps = await _re_expand_steps(
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
    # pass through unchanged ([[project-pseudoaxis-design]] v3).
    steps = await expansion_port.expand_pseudoaxis(
        steps,
        event_store=deps.event_store,
        correlation_id=correlation_id,
        constituent_resolver=constituent_resolver,
    )

    # Pin the resolved step list (after recipe + pseudoaxis expansion) BEFORE
    # conducting, so a future resume replays this exact list. The helper emits
    # the event only while the Procedure is still Defined and returns []
    # otherwise, leaving the Conductor's start_procedure to surface a lifecycle
    # failure (keeps the conduct route's failures-in-body contract).
    resolved_steps_events = decide_resolved_steps_recorded(
        procedure,
        tuple(step_to_payload(step) for step in steps),
        now=deps.clock.now(),
    )
    if resolved_steps_events:
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
                for event in resolved_steps_events
            ],
        )

    return steps


async def _re_expand_steps(
    *,
    procedure_id: UUID,
    recipe_id: UUID,
    caller_steps: Sequence[Step],
    stored_events: list[StoredEvent],
    event_store: EventStore,
    expansion_port: RecipeExpander,
) -> tuple[Step, ...]:
    """Run the recipe-replay gate per [[project-run-procedure-replay-design]].

    Six steps: reject non-empty caller steps -> find_recipe_expansion_record
    (raise RecipeExpansionRecordNotFoundError on None) -> pins_from_payload
    -> port-version strict-equals (raise RecipeExpanderVersionMismatchError
    on drift) -> load_recipe_at_version (raise RecipeExpansionRecordNotFoundError
    when None on a recipe-driven Procedure; RecipeVersionNotFoundError
    propagates from helper) -> load_capability + reject Deprecated
    (raise ProcedureBoundCapabilityDeprecatedError, symmetric to
    start_run's RunBoundPlanDeprecatedError) -> verify_bindings_hash ->
    expand -> verify_steps_hash -> return the re-expanded tuple.
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
    expanded = expansion_port.expand(recipe.steps, dict(pins.bindings))
    verify_steps_hash(procedure_id, expanded, pins)
    return expanded
