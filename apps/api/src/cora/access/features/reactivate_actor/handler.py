"""Application handler for the `reactivate_actor` slice.

Update-style handler shape (cross-BC pattern for commands targeting an
existing aggregate):

    1. authorize(principal_id, command_name, conduit) -> Allow | Deny
    2. clock.now() -> domain timestamp
    3. event_store.load(stream_type, command.target_id)
       -> (stored_events, current_version)
    4. fold([from_stored(s) for s in stored_events]) -> state
    5. decide(state, command, *, now) -> domain events
    6. wrap each domain event as a NewEvent (via aggregate's to_payload)
    7. event_store.append(stream_type, command.target_id, current_version, ...)

Differs from create-style:
  - Command carries the target aggregate id (caller-supplied).
  - Load + fold + decide instead of skipping the load.
  - expected_version=current_version (vs. 0 for create): race-loser
    on concurrent writes raises ConcurrencyError, mapped to 409 by
    the BC's exception handler.
  - No new_id injected to decider; aggregate already exists.
  - Returns None (no new id).
"""

from typing import Protocol
from uuid import UUID

from cora.access.aggregates.actor import (
    ActorEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.access.errors import UnauthorizedError
from cora.access.features.reactivate_actor.command import ReactivateActor
from cora.access.features.reactivate_actor.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_STREAM_TYPE = "Actor"
_COMMAND_NAME = "ReactivateActor"

# structlog loggers are lazy: get_logger() returns a proxy and config is
# applied at first .info() call. Module-level binding is safe even though
# configure_logging() runs later in build_kernel().
_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every reactivate_actor handler implements.

    See `register_actor.handler.Handler` for the rationale on the
    optional `causation_id` kwarg (the standard correlation/causation
    pattern from event-sourced systems; root entrypoints pass `None`,
    sagas/process managers pass the upstream event's id).
    """

    async def __call__(
        self,
        command: ReactivateActor,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a reactivate_actor handler closed over the shared deps."""

    async def handler(
        command: ReactivateActor,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "reactivate_actor.start",
            command_name=_COMMAND_NAME,
            actor_id=str(command.actor_id),
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
                "reactivate_actor.denied",
                command_name=_COMMAND_NAME,
                actor_id=str(command.actor_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.actor_id,
        )
        history: list[ActorEvent] = [from_stored(s) for s in stored]
        state = fold(history)

        domain_events = decide(state=state, command=command, now=now, principal_id=principal_id)

        # One event_id per emitted event, generated via the IdGenerator
        # port (UUIDv7 in production). See register_actor.handler for
        # the rationale on generating in the handler vs the decider /
        # factory (decider stays pure; factory stays a dict-shuffle).
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
            stream_id=command.actor_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "reactivate_actor.success",
            command_name=_COMMAND_NAME,
            actor_id=str(command.actor_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
