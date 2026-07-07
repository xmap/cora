"""Application handler for the `stop_run` slice.

Bespoke handler (not the `make_run_update_handler` factory) because the
consequence gate (Gate IV) needs a cross-BC PRE-LOAD before the pure decider:
the handler asks the `ConsequenceLookup` port whether a Granted Ratification
covers `(run_id, StopRun)` and threads that fact into `decide(...,
ratification_covered=...)`. Mirrors how `start_run` pre-loads clearance / supply
coverage into its decider context: the port call is I/O in the handler, the
decision stays pure.

The command's `reason` field IS captured on the emitted `RunStopped` event
payload but is intentionally NOT logged at the handler boundary (matches the
Subject discard / Asset condition precedent).
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.run.aggregates.run import event_type_name, fold, from_stored, to_payload
from cora.run.errors import UnauthorizedError
from cora.run.features.stop_run.command import StopRun
from cora.run.features.stop_run.decider import decide

_STREAM_TYPE = "Run"
_COMMAND_NAME = "StopRun"

_log = get_logger("stop_run")


class Handler(Protocol):
    """Callable interface every stop_run handler implements."""

    async def __call__(
        self,
        command: StopRun,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a stop_run handler closed over the shared deps."""

    async def handler(
        command: StopRun,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "stop_run.start",
            command_name=_COMMAND_NAME,
            run_id=str(command.run_id),
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
                "stop_run.denied",
                command_name=_COMMAND_NAME,
                run_id=str(command.run_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        # Consequence-gate pre-load: is (run_id, StopRun) covered by a Granted
        # Ratification? The port call is the handler's I/O; the decider stays pure.
        ratification_covered = await deps.consequence_lookup.granted_coverage_exists(
            run_id=command.run_id,
            command_name=_COMMAND_NAME,
        )

        now = deps.clock.now()
        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.run_id,
        )
        state = fold([from_stored(s) for s in stored])

        domain_events = decide(
            state=state,
            command=command,
            now=now,
            ratification_covered=ratification_covered,
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
            stream_id=command.run_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "stop_run.success",
            command_name=_COMMAND_NAME,
            run_id=str(command.run_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
