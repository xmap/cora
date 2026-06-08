"""Application handler for the `rate_decision` slice.

Update-style handler. Single-stream append on the Decision stream.
Loads the target Decision, calls the pure decider, appends the
resulting `DecisionRated` event.

NOT idempotency-wrapped: ratings are intentionally NOT idempotent at
the HTTP-key level. Multiple legitimate rating events from the same
actor are valid (the operator changed their mind); the projection
handles latest-per-actor-wins. Idempotency-Key caching would defeat
this on retry-with-same-key+same-body.

`causation_id` propagates from upstream (None for HTTP / MCP root
calls).
"""

from typing import Protocol
from uuid import UUID

from cora.decision.aggregates.decision import (
    DecisionNotFoundError,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.decision.aggregates.decision.evolver import fold
from cora.decision.errors import UnauthorizedError
from cora.decision.features.rate_decision.command import RateDecision
from cora.decision.features.rate_decision.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identity import ActorId

_STREAM_TYPE = "Decision"
_COMMAND_NAME = "RateDecision"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every rate_decision handler implements."""

    async def __call__(
        self,
        command: RateDecision,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a rate_decision handler closed over the shared deps."""

    async def handler(
        command: RateDecision,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "rate_decision.start",
            command_name=_COMMAND_NAME,
            decision_id=str(command.decision_id),
            rating=command.rating.value,
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
                "rate_decision.denied",
                command_name=_COMMAND_NAME,
                decision_id=str(command.decision_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=authz.reason,
            )
            raise UnauthorizedError(authz.reason)

        # Raw load + fold via evolver: we need the stream version
        # for the optimistic append, which `load_decision` does
        # not return; doing both inline avoids a redundant load.
        stored, version = await deps.event_store.load(_STREAM_TYPE, command.decision_id)
        state = fold([from_stored(s) for s in stored])
        if state is None:
            raise DecisionNotFoundError(command.decision_id)

        now = deps.clock.now()
        domain_events = decide(
            state=state,
            command=command,
            now=now,
            rated_by=ActorId(principal_id),
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
            stream_id=command.decision_id,
            expected_version=version,
            events=new_events,
        )

        _log.info(
            "rate_decision.success",
            command_name=_COMMAND_NAME,
            decision_id=str(command.decision_id),
            rating=command.rating.value,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )

    return handler
