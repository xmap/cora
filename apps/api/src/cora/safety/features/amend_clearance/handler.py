"""Application handler for the `amend_clearance` slice.

Cross-aggregate cousin of `register_clearance` with two notable
differences:

  1. Pre-loads the parent Clearance + its raw stream version. The
     parent's state goes into `ClearanceAmendmentContext`; its stream
     version is the optimistic-concurrency token for the parent's
     `ClearanceSuperseded` append.

  2. Writes the parent's `ClearanceSuperseded` event AND the child's
     `ClearanceRegistered` genesis event atomically via
     `EventStore.append_streams`. All-or-nothing: either both streams
     commit or a `ConcurrencyError` rolls back the whole batch.

The amend slice is create-style at the API layer (POST returns the
new child clearance_id; supports Idempotency-Key) so the
`with_idempotency` wrap at wire.py applies just like
`register_clearance`.

CORA's first consumer of `EventStore.append_streams`; the multi-
stream capability lands in the same iteration as this slice (11a-c-2).
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.ports.event_store import StreamAppend
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.safety.aggregates.clearance import (
    ClearanceNotFoundError,
    event_type_name,
    to_payload,
)
from cora.safety.aggregates.clearance.events import from_stored
from cora.safety.aggregates.clearance.evolver import fold
from cora.safety.errors import UnauthorizedError
from cora.safety.features.amend_clearance.command import AmendClearance
from cora.safety.features.amend_clearance.context import ClearanceAmendmentContext
from cora.safety.features.amend_clearance.decider import decide
from cora.shared.facility_code import FacilityCode

_STREAM_TYPE = "Clearance"
_COMMAND_NAME = "AmendClearance"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare amend_clearance handler -- what `bind()` returns.

    Returns the new child clearance's UUID. Has no idempotency_key
    kwarg; `with_idempotency` at wire.py adds it.
    """

    async def __call__(
        self,
        command: AmendClearance,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """amend_clearance handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: AmendClearance,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: Kernel) -> Handler:
    """Build an amend_clearance handler closed over the shared deps."""

    async def handler(
        command: AmendClearance,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "amend_clearance.start",
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
                "amend_clearance.denied",
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
            raise ClearanceNotFoundError(command.parent_id)

        context = ClearanceAmendmentContext(parent=parent, parent_version=parent_version)

        facility_lookup_result = await deps.facility_lookup.lookup_by_code(
            FacilityCode(command.facility_code)
        )
        template_lookup_result = await deps.clearance_template_lookup.lookup(command.template_id)

        new_id = deps.id_generator.new_id()
        now = deps.clock.now()

        amendment = decide(
            state=None,
            command=command,
            context=context,
            now=now,
            new_id=new_id,
            facility_lookup_result=facility_lookup_result,
            template_lookup_result=template_lookup_result,
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
            for event in amendment.parent_events
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
            for event in amendment.child_events
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
            "amend_clearance.success",
            command_name=_COMMAND_NAME,
            parent_id=str(command.parent_id),
            child_clearance_id=str(new_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            parent_event_count=len(parent_new_events),
            child_event_count=len(child_new_events),
        )
        return new_id

    return handler
