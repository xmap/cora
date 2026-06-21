"""Application handler for the `try_conduct_procedure` slice.

Pause-capable conduct. A thin orchestrator that delegates to
`Conductor.try_conduct()` (the pause-to-Held twin of `Conductor.conduct()`):
on a recoverable step failure the Conductor pauses the Procedure to `Held`
rather than aborting it, so the operator can `reconduct` from the pinned
resolved steps. This is the Tier-1 producer that makes a Held + pinned-steps
state reachable so the `reconduct` resume path has something to resume.

Shares the pre-Conductor pipeline (recipe re-expansion + pseudoaxis +
resolved-steps pin) with `conduct_procedure` via the BC-level
`resolve_and_pin_conduct_steps`, and the HTTP/MCP wire shapes via
`_conduct_wire`. It imports NO sibling slice: the cross-slice-independence
fitness forbids that, and the shared seams live outside `features/`.

## Why no `_decider`

Like `conduct_procedure`, records no new events directly: the wrapped
start / append / complete / abort / hold handlers (on the Conductor) write.
An orchestration entry point, not an aggregate-state-mutating decider.

## Authorization scope

`TryConductProcedure` is authz-checked as its own command. The wrapped
transition handlers each authz internally with their OWN command names; an
operator authorized to call `TryConductProcedure` is NOT automatically
authorized for those individually. Same layering as `conduct_procedure`.
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
from cora.operation.features.try_conduct_procedure.command import (
    TryConductProcedure,
    TryConductProcedureResult,
)
from cora.operation.ports.recipe_expander import RecipeExpander

_COMMAND_NAME = "TryConductProcedure"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every try_conduct_procedure handler implements."""

    async def __call__(
        self,
        command: TryConductProcedure,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> TryConductProcedureResult: ...


def bind(
    deps: Kernel,
    *,
    conductor: Conductor,
    expansion_port: RecipeExpander,
) -> Handler:
    """Build a try_conduct_procedure handler closed over deps + Conductor + port.

    `conductor` is the same BC-internal Conductor `conduct_procedure` uses; it
    carries the start / complete / abort / hold handlers (wired at app
    composition) that `Conductor.try_conduct` composes. `expansion_port` is
    the same instance wired for `register_procedure_from_recipe` + conduct.
    """

    async def handler(
        command: TryConductProcedure,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> TryConductProcedureResult:
        _log.info(
            "try_conduct_procedure.start",
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
                "try_conduct_procedure.denied",
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

        result = await conductor.try_conduct(
            procedure_id=command.procedure_id,
            principal_id=principal_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            surface_id=surface_id,
            steps=steps,
        )

        _log.info(
            "try_conduct_procedure.success",
            command_name=_COMMAND_NAME,
            procedure_id=str(command.procedure_id),
            completed_count=result.completed_count,
            succeeded=result.succeeded,
            held=result.held,
            failure_class=(result.failure.error_class if result.failure is not None else None),
        )

        return TryConductProcedureResult(
            procedure_id=result.procedure_id,
            completed_count=result.completed_count,
            succeeded=result.succeeded,
            held=result.held,
            failure=result.failure,
            actuation_kind=(
                result.actuation_kind.value if result.actuation_kind is not None else None
            ),
        )

    return handler
