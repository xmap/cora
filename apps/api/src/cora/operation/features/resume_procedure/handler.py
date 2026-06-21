"""Application handler for the `resume_procedure` slice.

Update-style handler with a custom body (NOT the update-handler
factory): resume reads the parent Run to enforce the off-diagonal guard
(a Held Procedure cannot resume while its parent Run is itself Held).
The factory at `cora.infrastructure.update_handler` loads exactly one
event-store stream; this slice loads a second (the parent Run), so it
stays longhand -- same reason `start_procedure`'s handler is custom.

## Off-diagonal guard

For a Phase-of-Run Procedure (`parent_run_id` set), the handler loads
the parent Run and passes `parent_run_held = (Run.status == Held)` into
the pure decider, which refuses with `ProcedureCannotResumeError` so a
Procedure cannot resume to Running and walk real setpoints while the Run
is paused. This is a one-directional Operation -> Run read
(tach-legal); there is NO cascade from Run-resume into Procedure-resume
(a Layer-3 saga, deferred). Standalone Procedures (no parent_run_id)
skip the load and pass `parent_run_held=False`.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.aggregates.procedure import (
    ProcedureNotFoundError,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.operation.errors import UnauthorizedError
from cora.operation.features.resume_procedure.command import ResumeProcedure
from cora.operation.features.resume_procedure.decider import decide
from cora.run.aggregates.run import RunNotFoundError, RunStatus, load_run

_STREAM_TYPE = "Procedure"
_COMMAND_NAME = "ResumeProcedure"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every resume_procedure handler implements."""

    async def __call__(
        self,
        command: ResumeProcedure,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a resume_procedure handler closed over the shared deps."""

    async def handler(
        command: ResumeProcedure,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "resume_procedure.start",
            command_name=_COMMAND_NAME,
            procedure_id=str(command.procedure_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "resume_procedure.denied",
                command_name=_COMMAND_NAME,
                procedure_id=str(command.procedure_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        stored, version = await deps.event_store.load(_STREAM_TYPE, command.procedure_id)
        state = fold([from_stored(s) for s in stored])
        if state is None:
            raise ProcedureNotFoundError(command.procedure_id)

        # Off-diagonal guard: a Phase-of-Run Procedure cannot resume while
        # its parent Run is Held. One-directional Operation -> Run read; a
        # missing parent Run in the chain is corruption, so raise rather
        # than silently skip the guard (mirrors start_procedure). Standalone
        # Procedures (no parent_run_id) pass parent_run_held=False.
        parent_run_held = False
        if state.parent_run_id is not None:
            parent_run = await load_run(deps.event_store, state.parent_run_id)
            if parent_run is None:
                raise RunNotFoundError(state.parent_run_id)
            parent_run_held = parent_run.status == RunStatus.HELD

        now = deps.clock.now()
        domain_events = decide(
            state=state,
            command=command,
            parent_run_held=parent_run_held,
            now=now,
        )

        new_events = [
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=event.occurred_at,
                event_id=deps.id_generator.new_id(),
                command_name=_COMMAND_NAME,
                correlation_id=correlation_id,
                causation_id=causation_id,
                principal_id=principal_id,
            )
            for event in domain_events
        ]
        await deps.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=command.procedure_id,
            expected_version=version,
            events=new_events,
        )

        _log.info(
            "resume_procedure.success",
            command_name=_COMMAND_NAME,
            procedure_id=str(command.procedure_id),
            parent_run_held=parent_run_held,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )

    return handler
