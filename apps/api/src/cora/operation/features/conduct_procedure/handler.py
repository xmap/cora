"""Application handler for the `conduct_procedure` slice.

Thin orchestrator that delegates to `Conductor.conduct()`. The
handler's job is the application-layer concerns the Conductor
itself does not own: command-level authorization (the per-step
`append_activities` calls already authz internally, but the
ConductProcedure entry point gates the entire invocation), envelope
threading, recipe-replay re-expansion when the Procedure was created
via `register_procedure_from_recipe`, and result conversion from
`ConductorResult` to the slice's `ConductProcedureResult` contract.

## Why no `_decider`

Unlike CQRS slices that compute events from state, `conduct_procedure`
records no new events on the Procedure stream directly: the wrapped
`start_procedure` / `append_activities` / `complete_procedure` /
`abort_procedure` handlers are the things that write. The slice is
an orchestration entry point, NOT an aggregate-state-mutating
decider. Therefore no `decider.py`, no `context.py`.

## Recipe-driven re-expansion

When the loaded Procedure has `recipe_id is not None`, the handler
treats it as recipe-driven and runs the five-step replay gate
specified by [[project-run-procedure-replay-design]]:
forbid-non-empty-caller-steps -> find_recipe_expansion_record ->
pins_from_payload -> port-version strict-equals guard ->
load_recipe_at_version -> verify_bindings_hash -> expand ->
verify_steps_hash -> hand fresh steps to Conductor. Legacy
Procedures (`recipe_id is None`) hand `command.steps` to the
Conductor unchanged.

## Authorization scope

`ConductProcedure` is authz-checked as a distinct command. The wrapped
handlers (start / append / complete / abort) each authz internally
with their OWN command names; an operator authorized to call
`ConductProcedure` is NOT automatically authorized for each of those
individually. That's correct: `ConductProcedure` is the
operator-friendly entry; the underlying per-FSM-transition
authorization is what the policy engine actually evaluates at each
call site.
"""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny, EventStore
from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation._recipe_replay import (
    find_recipe_expansion_record,
    pins_from_payload,
    verify_bindings_hash,
    verify_steps_hash,
)
from cora.operation.aggregates.procedure import (
    ProcedureBoundCapabilityDeprecatedError,
    ProcedureNotFoundError,
    ProcedureStepsForbiddenForRecipeDrivenError,
    RecipeExpanderVersionMismatchError,
    RecipeExpansionRecordNotFoundError,
    load_procedure_with_events,
)
from cora.operation.conductor import Conductor, Step
from cora.operation.errors import UnauthorizedError
from cora.operation.features.conduct_procedure.command import (
    ConductProcedure,
    ConductProcedureResult,
)
from cora.operation.ports.recipe_expander import RecipeExpander
from cora.recipe.aggregates.capability import CapabilityStatus, load_capability
from cora.recipe.aggregates.recipe import load_recipe_at_version

_COMMAND_NAME = "ConductProcedure"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every conduct_procedure handler implements."""

    async def __call__(
        self,
        command: ConductProcedure,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ConductProcedureResult: ...


def bind(
    deps: Kernel,
    *,
    conductor: Conductor,
    expansion_port: RecipeExpander,
) -> Handler:
    """Build a conduct_procedure handler closed over deps + Conductor + port.

    `conductor` is BC-internal: wire_operation constructs it from
    the bound FSM handlers + ControlPort + Kernel infra ports.
    `expansion_port` is the same instance wired for
    `register_procedure_from_recipe`; replay reads its `version`
    attribute and calls `expand` against the pinned bindings. The
    `event_store` is read via `deps.event_store` at the
    `load_procedure_with_events` call site (no separate kwarg).
    """

    async def handler(
        command: ConductProcedure,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ConductProcedureResult:
        _log.info(
            "conduct_procedure.start",
            command_name=_COMMAND_NAME,
            procedure_id=str(command.procedure_id),
            step_count=len(command.steps),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )

        authz = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(authz, Deny):
            _log.info(
                "conduct_procedure.denied",
                command_name=_COMMAND_NAME,
                procedure_id=str(command.procedure_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=authz.reason,
            )
            raise UnauthorizedError(authz.reason)

        procedure, stored_events = await load_procedure_with_events(
            deps.event_store, command.procedure_id
        )
        if procedure is None:
            raise ProcedureNotFoundError(command.procedure_id)

        if procedure.recipe_id is not None:
            steps = await _re_expand_steps(
                procedure_id=procedure.id,
                recipe_id=procedure.recipe_id,
                caller_steps=command.steps,
                stored_events=stored_events,
                event_store=deps.event_store,
                expansion_port=expansion_port,
            )
        else:
            steps = tuple(command.steps)

        # Pre-Conductor PseudoAxis expansion: rewrite any virtual-axis
        # SetpointStep into N sequential constituent SetpointSteps so
        # the Conductor's existing dispatch loop walks the constituents
        # in declared order. ActionStep / CheckStep pass through
        # unchanged. PseudoAxis evaluator errors propagate to the
        # routes layer for HTTP status mapping
        # ([[project-pseudoaxis-design]] v3).
        steps = await expansion_port.expand_pseudoaxis(
            steps,
            event_store=deps.event_store,
            correlation_id=correlation_id,
        )

        result = await conductor.conduct(
            procedure_id=command.procedure_id,
            principal_id=principal_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            surface_id=surface_id,
            steps=steps,
        )

        _log.info(
            "conduct_procedure.success",
            command_name=_COMMAND_NAME,
            procedure_id=str(command.procedure_id),
            completed_count=result.completed_count,
            succeeded=result.succeeded,
            failure_class=(result.failure.error_class if result.failure is not None else None),
        )

        return ConductProcedureResult(
            procedure_id=result.procedure_id,
            completed_count=result.completed_count,
            succeeded=result.succeeded,
            failure=result.failure,
        )

    return handler


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
    # Capability before running the expansion port. Symmetric to
    # start_run's RunBoundPlanDeprecatedError. Per the 2026-06-04 domain
    # harmony audit: re-expanding a Recipe against a Deprecated
    # Capability would silently execute against a contract operators
    # have retired.
    capability = await load_capability(event_store, recipe.capability_id)
    if capability is not None and capability.status == CapabilityStatus.DEPRECATED:
        raise ProcedureBoundCapabilityDeprecatedError(procedure_id, recipe.capability_id)

    verify_bindings_hash(procedure_id, pins)
    expanded = expansion_port.expand(recipe.steps, dict(pins.bindings))
    verify_steps_hash(procedure_id, expanded, pins)
    return expanded
