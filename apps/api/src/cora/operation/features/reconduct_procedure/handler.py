"""Application handler for the `reconduct_procedure` slice.

Resume-and-replay orchestration. Mirrors `conduct_procedure`: a thin
slice handler that authz-checks + loads + locates the pinned resolved steps,
then delegates the resume + replay + terminalize composition to
`Conductor.reconduct` (the resume twin of `Conductor.conduct`). No
`decider.py`: like `conduct_procedure` this is an orchestration entry
point, not an aggregate-state-mutating decider.

This handler imports NO sibling slice: the resume / complete / abort
handlers it composes live on the injected `Conductor` (a non-slice
module), exactly as `conduct_procedure` delegates start / complete /
abort to `Conductor.conduct`. That keeps the slice independent (the
cross-slice fitness) and the composition in the one place that already
owns lifecycle-handler orchestration.

## Flow

  1. authz `ReconductProcedure`.
  2. load the Procedure + its raw events.
  3. status guard FIRST: a non-Held Procedure is a `ProcedureCannotResumeError`
     (409), raised BEFORE the step-list lookup so a Defined / Completed
     Procedure is never a misleading 500 and no resume-then-fail partial
     state can occur.
  4. locate the PINNED `ResolvedStepsRecorded` (a conducted, Held Procedure
     ALWAYS has exactly one; its absence is corruption ->
     `ResolvedStepsRecordNotFoundError`, 500) and parse it back into `Step`s
     via `steps_from_payload` -- resume NEVER re-derives the step list.
  5. `Conductor.reconduct(steps, boundary)`: resume (Held -> Running, with
     its own authz + off-diagonal parent-Run-Held guard) -> `execute_from`
     (re-drive setpoints, re-run checks, halt-for-operator on an acquisition)
     -> terminalize (complete on a clean tail / leave Running on an
     acquisition halt / best-effort abort on a genuine step failure).
  6. project the `ConductorResult` onto `ReconductProcedureResult`
     (`acquisition_halt` is the named branch on the resume halt).

The `re_establishment_boundary` is single-sourced: the operator supplies
it once; `Conductor.reconduct` rides it into both
`ProcedureResumed.re_establishment_boundary` (audit) and
`execute_from(boundary=...)` (replay).

## Authorization scope

`ReconductProcedure` is authz-checked as its own command. The wrapped
`resume_procedure` / `complete_procedure` / `abort_procedure` handlers
(on the Conductor) each authz internally with their OWN command names; an
operator authorized to call `ReconductProcedure` is NOT automatically
authorized for those individually. Same layering as `conduct_procedure`.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation._recipe_expansion import find_resolved_steps_record
from cora.operation.aggregates.procedure import (
    InvalidProcedureReEstablishmentBoundaryError,
    ProcedureCannotResumeError,
    ProcedureNotFoundError,
    ProcedureStatus,
    ResolvedStepsRecordNotFoundError,
    load_procedure_with_events,
)
from cora.operation.conductor import Conductor, is_acquisition_halt, steps_from_payload
from cora.operation.errors import UnauthorizedError
from cora.operation.features.reconduct_procedure.command import (
    ReconductProcedure,
    ReconductProcedureResult,
)

_COMMAND_NAME = "ReconductProcedure"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every reconduct_procedure handler implements."""

    async def __call__(
        self,
        command: ReconductProcedure,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ReconductProcedureResult: ...


def bind(deps: Kernel, *, conductor: Conductor) -> Handler:
    """Build a reconduct_procedure handler closed over deps + the Conductor.

    `conductor` is the same BC-internal Conductor `conduct_procedure` uses;
    it carries the resume / complete / abort handlers (wired at app
    composition) that `Conductor.reconduct` composes, so the internal
    transitions land with the same observability shape as direct REST / MCP
    calls.
    """

    async def handler(
        command: ReconductProcedure,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ReconductProcedureResult:
        _log.info(
            "reconduct_procedure.start",
            command_name=_COMMAND_NAME,
            procedure_id=str(command.procedure_id),
            re_establishment_boundary=command.re_establishment_boundary,
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
                "reconduct_procedure.denied",
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

        # Status guard FIRST (mirrors resume's `{Held}` source set): a
        # non-Held Procedure is a 409, not a 500. This keeps the
        # missing-record case below as genuine corruption (a conducted,
        # Held Procedure ALWAYS has its pinned resolved steps) and avoids resuming
        # then failing to find them. The off-diagonal parent-Run-Held
        # guard stays inside Conductor.reconduct's resume call.
        if procedure.status is not ProcedureStatus.HELD:
            raise ProcedureCannotResumeError(command.procedure_id, current_status=procedure.status)

        # Replay the PINNED resolved steps, never re-derive. A Held Procedure that
        # was conducted always has exactly one ResolvedStepsRecorded; its
        # absence here is corruption (500), not an operational outcome.
        record = find_resolved_steps_record(stored_events)
        if record is None:
            raise ResolvedStepsRecordNotFoundError(command.procedure_id)
        steps = steps_from_payload(record.payload["resolved_steps"])

        # Upper-bound guard: a boundary PAST the pinned step count would replay
        # an empty tail and silently auto-complete with nothing re-driven. The
        # resume decider only floors at 0 (it has no manifest to size against);
        # the bound lives here, where the manifest is known. `boundary ==
        # len(steps)` is allowed (a deliberate "everything already done,
        # complete" resume); only strictly-past is rejected.
        if command.re_establishment_boundary > len(steps):
            raise InvalidProcedureReEstablishmentBoundaryError(command.re_establishment_boundary)

        result = await conductor.reconduct(
            procedure_id=command.procedure_id,
            principal_id=principal_id,
            correlation_id=correlation_id,
            steps=steps,
            boundary=command.re_establishment_boundary,
            # The pre-hold conduct's observed kind (folded onto the Held
            # Procedure) so the terminal event reflects the FULL provenance,
            # not just the replay tail -- guards the promote_dataset gate
            # against a boundary>0 resume past a simulated prefix.
            prior_actuation_kind=procedure.actuation_kind,
            causation_id=causation_id,
            surface_id=surface_id,
        )

        actuation_kind = result.actuation_kind.value if result.actuation_kind is not None else None
        acquisition_halt = is_acquisition_halt(result.failure)

        _log.info(
            "reconduct_procedure.success",
            command_name=_COMMAND_NAME,
            procedure_id=str(command.procedure_id),
            completed_count=result.completed_count,
            succeeded=result.succeeded,
            acquisition_halt=acquisition_halt,
            failure_class=(result.failure.error_class if result.failure is not None else None),
        )

        return ReconductProcedureResult(
            procedure_id=command.procedure_id,
            completed_count=result.completed_count,
            succeeded=result.succeeded,
            re_establishment_boundary=command.re_establishment_boundary,
            acquisition_halt=acquisition_halt,
            failure=result.failure,
            actuation_kind=actuation_kind,
        )

    return handler
