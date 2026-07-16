"""Application handler for the `deny_ratification` slice.

Transition longhand handler: loads current Ratification state, threads the
envelope `principal_id` into the decider as `denied_by` (the independence check
compares it against the requester), and appends the resulting event with
optimistic concurrency at the loaded version. Mirrors the `supersede_caution`
principal-threading convention rather than the update-handler factory, because
the factory does not pass the principal into the decider.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.trust.aggregates.ratification import (
    RatificationNotFoundError,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.trust.errors import UnauthorizedError
from cora.trust.features.deny_ratification.command import DenyRatification
from cora.trust.features.deny_ratification.decider import decide

_STREAM_TYPE = "Ratification"
_COMMAND_NAME = "DenyRatification"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare deny_ratification handler -- what `bind()` returns."""

    async def __call__(
        self,
        command: DenyRatification,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a deny_ratification handler closed over the shared deps."""

    async def handler(
        command: DenyRatification,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "deny_ratification.start",
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
                "deny_ratification.denied",
                command_name=_COMMAND_NAME,
                ratification_id=str(command.ratification_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()
        stored, version = await deps.event_store.load(_STREAM_TYPE, command.ratification_id)
        if not stored:
            raise RatificationNotFoundError(command.ratification_id)
        state = fold([from_stored(s) for s in stored])

        domain_events = decide(
            state=state,
            command=command,
            denied_by=principal_id,
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
            expected_version=version,
            events=new_events,
        )

        _log.info(
            "deny_ratification.success",
            command_name=_COMMAND_NAME,
            ratification_id=str(command.ratification_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )

    return handler
