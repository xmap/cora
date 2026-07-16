"""Application handler for the `request_ratification` slice.

Genesis-style longhand handler, mirroring `register_visit.handler` plus the
`supersede_caution` principal-threading convention: the requester is the
envelope `principal_id`, passed into the decider as `requested_by` (the command
surface omits it, so a caller cannot claim a different requester).

Caller-supplied `ratification_id` means the handler does NOT mint the stream id;
it still uses the id generator for the per-event `event_id`. `expected_version=0`
per genesis: the stream must be empty; collision surfaces as
`RatificationAlreadyExistsError` (decider) or `ConcurrencyError` (event store).
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.trust.aggregates.ratification import event_type_name, load_ratification, to_payload
from cora.trust.errors import UnauthorizedError
from cora.trust.features.request_ratification.command import RequestRatification
from cora.trust.features.request_ratification.decider import decide

_STREAM_TYPE = "Ratification"
_COMMAND_NAME = "RequestRatification"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare request_ratification handler -- what `bind()` returns."""

    async def __call__(
        self,
        command: RequestRatification,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


def bind(deps: Kernel) -> Handler:
    """Build a request_ratification handler closed over the shared deps."""

    async def handler(
        command: RequestRatification,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "request_ratification.start",
            command_name=_COMMAND_NAME,
            ratification_id=str(command.ratification_id),
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
                "request_ratification.denied",
                command_name=_COMMAND_NAME,
                ratification_id=str(command.ratification_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()
        state = await load_ratification(deps.event_store, command.ratification_id)

        domain_events = decide(
            state=state,
            command=command,
            requested_by=principal_id,
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
            stream_id=command.ratification_id,
            expected_version=0,
            events=new_events,
        )

        _log.info(
            "request_ratification.success",
            command_name=_COMMAND_NAME,
            ratification_id=str(command.ratification_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )
        return command.ratification_id

    return handler
