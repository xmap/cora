"""Application handler for the `supersede_caution` slice.

Cross-aggregate cousin of `register_caution` with two notable
differences (mirrors Safety's `amend_clearance` shape):

  1. Pre-loads the parent Caution + its raw stream version. The
     parent's state goes into `CautionSupersessionContext`; its
     stream version is the optimistic-concurrency token for the
     parent's `CautionSuperseded` append.

  2. Writes the parent's `CautionSuperseded` event AND the child's
     `CautionRegistered` genesis event atomically via
     `EventStore.append_streams`. All-or-nothing: either both streams
     commit or a `ConcurrencyError` rolls back the whole batch.

The supersede slice is create-style at the API layer (POST returns
the new child caution_id; supports Idempotency-Key) so the
`with_idempotency` wrap at wire.py applies just like
`register_caution`.
"""

from typing import Protocol
from uuid import UUID

from cora.caution.aggregates.caution import (
    CautionNotFoundError,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.caution.aggregates.caution.evolver import fold
from cora.caution.errors import UnauthorizedError
from cora.caution.features.supersede_caution.command import SupersedeCaution
from cora.caution.features.supersede_caution.context import CautionSupersessionContext
from cora.caution.features.supersede_caution.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.ports.event_store import StreamAppend
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identity import ActorId

_STREAM_TYPE = "Caution"
_COMMAND_NAME = "SupersedeCaution"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare supersede_caution handler -- what `bind()` returns.

    Returns the new child caution's UUID. Has no idempotency_key
    kwarg; `with_idempotency` at wire.py adds it.
    """

    async def __call__(
        self,
        command: SupersedeCaution,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """supersede_caution handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: SupersedeCaution,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: Kernel) -> Handler:
    """Build a supersede_caution handler closed over the shared deps."""

    async def handler(
        command: SupersedeCaution,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "supersede_caution.start",
            command_name=_COMMAND_NAME,
            parent_id=str(command.parent_id),
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
                "supersede_caution.denied",
                command_name=_COMMAND_NAME,
                parent_id=str(command.parent_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        # Pre-load parent stream + version (cross-aggregate context).
        stored, parent_version = await deps.event_store.load(_STREAM_TYPE, command.parent_id)
        parent = fold([from_stored(s) for s in stored])
        if parent is None:
            raise CautionNotFoundError(command.parent_id)

        context = CautionSupersessionContext(parent=parent, parent_version=parent_version)

        new_id = deps.id_generator.new_id()
        now = deps.clock.now()

        supersession = decide(
            state=None,
            command=command,
            context=context,
            now=now,
            new_id=new_id,
            authored_by=ActorId(principal_id),
        )

        parent_new_events = [
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
            for event in supersession.parent_events
        ]
        child_new_events = [
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
            for event in supersession.child_events
        ]

        await deps.event_store.append_streams(
            [
                StreamAppend(
                    stream_type=_STREAM_TYPE,
                    stream_id=command.parent_id,
                    expected_version=context.parent_version,
                    events=parent_new_events,
                ),
                StreamAppend(
                    stream_type=_STREAM_TYPE,
                    stream_id=new_id,
                    expected_version=0,
                    events=child_new_events,
                ),
            ]
        )

        _log.info(
            "supersede_caution.success",
            command_name=_COMMAND_NAME,
            parent_id=str(command.parent_id),
            child_caution_id=str(new_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            parent_event_count=len(parent_new_events),
            child_event_count=len(child_new_events),
        )
        return new_id

    return handler
