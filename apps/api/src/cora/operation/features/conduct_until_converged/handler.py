"""Application handler for the `conduct_until_converged` slice (slice 6c).

Thin orchestrator that delegates to `Conductor.conduct_until_converged` (the
AUTO sibling of `Conductor.conduct`): it re-walks one pass block until a
loop-evaluated criterion over the captures bus is met OR the patience cap
trips. The handler owns the application-layer concerns the Conductor does not:
command-level authorization, envelope threading, recipe-replay re-expansion of
the one-pass block, reading the registered cap off the loaded Procedure, and
result conversion to `ConductUntilConvergedResult`.

Shares the pre-Conductor pipeline (recipe re-expansion + pseudoaxis +
resolved-steps pin) with `conduct_procedure` via the BC-level
`resolve_and_pin_conduct_steps`, and the HTTP/MCP wire shapes via
`_conduct_wire`. It imports NO sibling slice (the cross-slice-independence
fitness forbids that; the shared seams live outside `features/`).

## Why no `_decider`

Like `conduct_procedure`, this records no new events directly: the wrapped
start / start_iteration / end_iteration / complete / abort handlers (on the
Conductor) write. An orchestration entry point, not an aggregate-state-mutating
decider; therefore no `decider.py`, no `context.py`.

## Convergence predicate + cap

The convergence predicate (`convergence_capture_name` + `criterion`) is a
conduct-time parameter at 6c (pinning it onto the Procedure is a deferred
follow-on). The patience cap is read off the loaded Procedure's
`max_consecutive_unconverged_iterations` (declared at register time): the
command's own field overrides it only when set, so an in-process caller can
supply a cap a Procedure did not declare.
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
from cora.operation.features.conduct_until_converged.command import (
    ConductUntilConverged,
    ConductUntilConvergedResult,
)
from cora.operation.ports.recipe_expander import RecipeExpander

_COMMAND_NAME = "ConductUntilConverged"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every conduct_until_converged handler implements."""

    async def __call__(
        self,
        command: ConductUntilConverged,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ConductUntilConvergedResult: ...


def bind(
    deps: Kernel,
    *,
    conductor: Conductor,
    expansion_port: RecipeExpander,
) -> Handler:
    """Build a conduct_until_converged handler closed over deps + Conductor + port.

    `conductor` is the same BC-internal Conductor `conduct_procedure` uses; it
    carries the start / start_iteration / end_iteration / complete / abort
    handlers (wired at app composition) that `Conductor.conduct_until_converged`
    composes. `expansion_port` is the same instance wired for
    `register_procedure_from_recipe` + conduct.
    """

    async def handler(
        command: ConductUntilConverged,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ConductUntilConvergedResult:
        _log.info(
            "conduct_until_converged.start",
            command_name=_COMMAND_NAME,
            procedure_id=str(command.procedure_id),
            convergence_capture_name=command.convergence_capture_name,
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
                "conduct_until_converged.denied",
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

        # The command's explicit cap overrides the registered one only when
        # supplied; otherwise the loop honors the Procedure's declared
        # max_consecutive_unconverged_iterations.
        cap = (
            command.max_consecutive_unconverged_iterations
            if command.max_consecutive_unconverged_iterations is not None
            else procedure.max_consecutive_unconverged_iterations
        )

        result = await conductor.conduct_until_converged(
            procedure_id=command.procedure_id,
            principal_id=principal_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            surface_id=surface_id,
            steps=steps,
            convergence_capture_name=command.convergence_capture_name,
            criterion=command.criterion,
            max_consecutive_unconverged_iterations=cap,
        )

        _log.info(
            "conduct_until_converged.success",
            command_name=_COMMAND_NAME,
            procedure_id=str(command.procedure_id),
            completed_count=result.completed_count,
            succeeded=result.succeeded,
            failure_class=(result.failure.error_class if result.failure is not None else None),
        )

        return ConductUntilConvergedResult(
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
