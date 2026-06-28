"""Application handler for the `conduct_until_advised` slice (steered loop wire).

Thin orchestrator that delegates to `Conductor.conduct_until_advised` (the
DECIDE-axis sibling of `Conductor.conduct_until_converged`): it re-walks one
pass block, handing the accumulated evidence to a brain after each pass, until
the brain advises Stop (or a pass / brain fault aborts). The handler owns the
application-layer concerns the Conductor does not: command-level authorization,
envelope threading, recipe re-expansion of the pinned one-pass block, building
the in-CORA brain from `command.decide`, and result conversion.

Shares the pre-Conductor pipeline (recipe re-expansion + pseudoaxis +
resolved-steps pin) with `conduct_procedure` via `resolve_and_pin_conduct_steps`,
and the wire shapes via `_advise_wire`. It imports NO sibling slice.

## Why no `_decider`

Like `conduct_until_converged`, this records no events directly: the wrapped
start / start_iteration / end_iteration / complete / abort handlers (on the
Conductor) write. An orchestration entry point, not a decider.

## Recipe-driven + identity point-to-captures

The steered axis is a `SteeringRef` setpoint, expressible only in a Recipe, so
the block always comes from the pinned recipe (the handler passes no caller
steps). `point_to_captures` is the built-in identity: each advised coordinate
is seeded under its own axis name, which is the slot the matching `SteeringRef`
setpoint resolves. The brain is built fresh per call from `command.decide` and
closed when the loop ends.
"""

from typing import Any, Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation._conduct_preparation import resolve_and_pin_conduct_steps
from cora.operation.adapters.decide_port_config import build_decide_port
from cora.operation.aggregates.procedure import (
    ProcedureNotFoundError,
    load_procedure_with_events,
)
from cora.operation.conductor import Conductor
from cora.operation.errors import SteeringWireMismatchError, UnauthorizedError
from cora.operation.features.conduct_until_advised.command import (
    ConductUntilAdvised,
    ConductUntilAdvisedResult,
)
from cora.operation.ports.decide_port import SteeringPoint
from cora.operation.ports.recipe_expander import RecipeExpander

_COMMAND_NAME = "ConductUntilAdvised"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every conduct_until_advised handler implements."""

    async def __call__(
        self,
        command: ConductUntilAdvised,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ConductUntilAdvisedResult: ...


def _identity_point_to_captures(point: SteeringPoint) -> dict[str, Any]:
    """Seed each advised coordinate under its own axis name (the wire default).

    The SteeringRef setpoint for an axis resolves `captures[axis_name]`, so the
    point's coordinates seed exactly the axis-named slots. Satisfies the
    Conductor's wire guard (seeded keys == axis names)."""
    return dict(point.coordinates)


def bind(
    deps: Kernel,
    *,
    conductor: Conductor,
    expansion_port: RecipeExpander,
) -> Handler:
    """Build a conduct_until_advised handler closed over deps + Conductor + port.

    `conductor` is the same BC-internal Conductor `conduct_procedure` uses; it
    carries the lifecycle handlers `Conductor.conduct_until_advised` composes.
    `expansion_port` is the same instance wired for
    `register_procedure_from_recipe` + conduct.
    """

    async def handler(
        command: ConductUntilAdvised,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ConductUntilAdvisedResult:
        _log.info(
            "conduct_until_advised.start",
            command_name=_COMMAND_NAME,
            procedure_id=str(command.procedure_id),
            objective_capture_name=command.objective_capture_name,
            substrate=command.decide.substrate,
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
                "conduct_until_advised.denied",
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
            caller_steps=(),
            expansion_port=expansion_port,
            principal_id=principal_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
        )

        decide_port = build_decide_port(command.decide)
        try:
            result = await conductor.conduct_until_advised(
                procedure_id=command.procedure_id,
                principal_id=principal_id,
                correlation_id=correlation_id,
                causation_id=causation_id,
                surface_id=surface_id,
                steps=steps,
                decide_port=decide_port,
                objective=command.objective,
                space=command.space,
                objective_capture_name=command.objective_capture_name,
                point_to_captures=_identity_point_to_captures,
                budget=command.budget,
            )
        except ValueError as exc:
            # conduct_until_advised raises ValueError only from its pre-FSM wire
            # guard (_validate_steering_wire): the request's space / objective do
            # not line up with the pinned recipe's SteeringRef setpoints. No FSM
            # event has fired, so surface a 422 client error, not a 500.
            raise SteeringWireMismatchError(str(exc)) from exc
        finally:
            await decide_port.aclose()

        _log.info(
            "conduct_until_advised.success",
            command_name=_COMMAND_NAME,
            procedure_id=str(command.procedure_id),
            completed_count=result.completed_count,
            succeeded=result.succeeded,
            failure_class=(result.failure.error_class if result.failure is not None else None),
        )

        return ConductUntilAdvisedResult(
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
