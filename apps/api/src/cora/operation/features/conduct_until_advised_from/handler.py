"""Application handler for the `conduct_until_advised_from` slice (steered RESUME).

The DECIDE-axis twin of `conduct_from_procedure`: where that resumes a flat pinned
step list, this resumes an iterating GP-steered loop. It re-seeds the brain from
the recorded closed passes and consults it only at the open frontier, so the
already-measured passes are neither re-driven nor re-measured (strategy A per
[[project_resumable_conduct_design]]).

Thin orchestrator that delegates the resume + loop + terminalize composition to
`Conductor.conduct_until_advised_from`. The handler owns the application-layer
concerns the Conductor does not: authorization, envelope threading, the pinned
step lookup, the RECONSTRUCTION (read the recorded outcomes + advised points and
pair them into the closed-pass history), building the brain from `command.decide`,
and result conversion.

## Flow

  1. authz `ConductUntilAdvisedFrom`.
  2. load the Procedure + its raw events.
  3. status guard FIRST: a non-Held Procedure is a `ProcedureCannotResumeError`
     (409), raised BEFORE any lookup so a Defined / Completed Procedure is never
     a misleading 500.
  4. locate the PINNED `ResolvedStepsRecorded` (a conducted, Held Procedure
     ALWAYS has one; its absence is corruption -> `ResolvedStepsRecordNotFoundError`,
     500) and parse it back into `Step`s -- resume NEVER re-derives the block.
  5. RECONSTRUCT the closed passes: read the recorded outcomes (the measured y,
     via `ProcedureOutcomeLookup`) + the advised points (the x, from the
     `ProcedureIterationEnded` events on the stream), pair them into a
     `ResumePlan`, and reject a plan with no open frontier
     (`SteeringResumeHasNoFrontierError`, 409): no closed pass, or the last
     closed pass advised Stop (the campaign already ended, nothing to resume).
  6. `Conductor.conduct_until_advised_from(...)`: resume (Held -> Running, with its
     own authz + off-diagonal parent-Run-Held guard) -> continue the decide loop
     at the frontier -> terminalize (complete on brain Stop / abort on a fault).
  7. project the `ConductorResult` onto `ConductUntilAdvisedFromResult`.

## Authorization scope

`ConductUntilAdvisedFrom` is authz-checked as its own command. The wrapped
`resume_procedure` / `complete_procedure` / `abort_procedure` /
`start_iteration` / `end_iteration` handlers (on the Conductor) each authz
internally with their OWN command names. Same layering as `conduct_from_procedure`.
"""

from typing import Any, Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation._recipe_expansion import find_resolved_steps_record
from cora.operation._steering_resume import reconstruct_observations
from cora.operation.adapters.decide_port_config import build_decide_port
from cora.operation.aggregates.procedure import (
    ProcedureCannotResumeError,
    ProcedureNotFoundError,
    ProcedureStatus,
    ResolvedStepsRecordNotFoundError,
    load_procedure_with_events,
)
from cora.operation.conductor import (
    Conductor,
    steps_from_payload,
)
from cora.operation.errors import (
    SteeringWireMismatchError,
    UnauthorizedError,
)
from cora.operation.features.conduct_until_advised_from.command import (
    ConductUntilAdvisedFrom,
    ConductUntilAdvisedFromResult,
)
from cora.operation.ports.decide_port import SteeringLlmCall, SteeringPoint
from cora.operation.ports.procedure_outcome_lookup import ProcedureOutcomeLookup
from cora.operation.ports.recipe_expander import RecipeExpander

_COMMAND_NAME = "ConductUntilAdvisedFrom"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every conduct_until_advised_from handler implements."""

    async def __call__(
        self,
        command: ConductUntilAdvisedFrom,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ConductUntilAdvisedFromResult: ...


def _identity_point_to_captures(point: SteeringPoint) -> dict[str, Any]:
    """Seed each advised coordinate under its own axis name (the wire default).

    Identical to the `conduct_until_advised` handler's built-in: the SteeringRef
    setpoint for an axis resolves `captures[axis_name]`, so the point's
    coordinates seed exactly the axis-named slots."""
    return dict(point.coordinates)


def bind(
    deps: Kernel,
    *,
    conductor: Conductor,
    expansion_port: RecipeExpander,
    outcome_lookup: ProcedureOutcomeLookup,
) -> Handler:
    """Build a conduct_until_advised_from handler closed over deps + conductor + ports.

    `conductor` is the same BC-internal Conductor the conduct family uses; it
    carries the resume + iteration + complete + abort handlers
    `Conductor.conduct_until_advised_from` composes. `expansion_port` re-expands the
    pinned recipe block (the same instance wired for conduct). `outcome_lookup`
    reads the recorded measured values (the y-side of the reconstruction).
    """

    async def handler(
        command: ConductUntilAdvisedFrom,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ConductUntilAdvisedFromResult:
        _log.info(
            "conduct_until_advised_from.start",
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
                "conduct_until_advised_from.denied",
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

        # Status guard FIRST (mirrors conduct_from): a non-Held Procedure is a 409,
        # not a 500, and keeps the missing-record case below as genuine
        # corruption. The off-diagonal parent-Run-Held guard stays inside
        # Conductor.conduct_until_advised_from's resume call.
        if procedure.status is not ProcedureStatus.HELD:
            raise ProcedureCannotResumeError(command.procedure_id, current_status=procedure.status)

        # Re-expand the PINNED recipe block (never re-derive). A Held steered
        # Procedure that was conducted always has exactly one
        # ResolvedStepsRecorded; its absence is corruption (500).
        record = find_resolved_steps_record(stored_events)
        if record is None:
            raise ResolvedStepsRecordNotFoundError(command.procedure_id)
        steps = steps_from_payload(record.payload["resolved_steps"])

        # RECONSTRUCT the brain's history from the self-describing outcome rows
        # (each carries its own point + measurements), so this is a sort-then-map
        # with no join to the iteration events. The FSM iteration counters come
        # from the loaded aggregate: `iteration_count` seeds the loop's
        # start_iteration numbering, and `current_iteration_index` (set only when
        # a mid-crash hold left a pass open) is closed by the conductor before
        # the frontier so the counter does not collide.
        outcomes = await outcome_lookup.read_procedure_outcomes(procedure_id=command.procedure_id)
        closed_observations = reconstruct_observations(outcomes)

        llm_calls: list[SteeringLlmCall] = []
        decide_port = build_decide_port(
            command.decide,
            llm=deps.llm,
            usage_sink=llm_calls.append,
            spend_guard=deps.spend_guard,
            clock=deps.clock,
        )
        try:
            result = await conductor.conduct_until_advised_from(
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
                closed_observations=closed_observations,
                fsm_iteration_count=procedure.iteration_count,
                open_iteration_index=procedure.current_iteration_index,
                budget=command.budget,
            )
        except ValueError as exc:
            # conduct_until_advised_from raises ValueError only from its pre-FSM
            # wire guard (_validate_steering_wire): the request's space /
            # objective do not line up with the pinned recipe's SteeringRef
            # setpoints. No FSM event has fired, so surface a 422, not a 500.
            raise SteeringWireMismatchError(str(exc)) from exc
        finally:
            await decide_port.aclose()

        _log.info(
            "conduct_until_advised_from.success",
            command_name=_COMMAND_NAME,
            procedure_id=str(command.procedure_id),
            re_establishment_boundary=len(closed_observations),
            completed_count=result.completed_count,
            succeeded=result.succeeded,
            failure_class=(result.failure.error_class if result.failure is not None else None),
        )

        return ConductUntilAdvisedFromResult(
            procedure_id=result.procedure_id,
            completed_count=result.completed_count,
            succeeded=result.succeeded,
            re_establishment_boundary=len(closed_observations),
            failure=result.failure,
            actuation_kind=(
                result.actuation_kind.value if result.actuation_kind is not None else None
            ),
            measurements=result.measurements,
            llm_calls=tuple(llm_calls),
        )

    return handler
