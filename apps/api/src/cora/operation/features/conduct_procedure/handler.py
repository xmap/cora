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

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation._conduct_preparation import resolve_and_pin_conduct_steps
from cora.operation.aggregates.procedure import (
    ProcedureNotFoundError,
    load_procedure_with_events,
)
from cora.operation.conductor import Conductor
from cora.operation.errors import UnauthorizedError
from cora.operation.features.conduct_procedure.command import (
    ConductProcedure,
    ConductProcedureResult,
)
from cora.operation.ports.recipe_expander import RecipeExpander

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

        steps = await resolve_and_pin_conduct_steps(
            deps,
            command_name=_COMMAND_NAME,
            procedure=procedure,
            stored_events=stored_events,
            caller_steps=command.steps,
            expansion_port=expansion_port,
            principal_id=principal_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
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
            actuation_kind=(
                result.actuation_kind.value if result.actuation_kind is not None else None
            ),
            measurements=result.measurements,
        )

    return handler
