"""Application handler for the `define_permit` slice.

Cross-BC atomic genesis: writes `PermitDefined` on the Federation
Permit stream AND a `DecisionRegistered` audit on the Decision BC
stream in ONE Postgres transaction via
`EventStore.append_streams`. Mirrors `define_agent` (which writes
`ActorRegistered` on the Access BC stream the same way).

The decider builds only the Permit BC event (`PermitDefined`);
this handler additionally builds the Decision BC audit event
(`DecisionRegistered`) and threads both into the single
`append_streams` call. The audit Decision's id is generated fresh
by the handler and used as the new Decision stream id.

Idempotency-wrappable per the create-style convention; the
`with_idempotency` wrap is applied at `wire.py`, not here.

`defined_by` is handler-injected from the request
envelope's `principal_id`; not on the command per the
"no spoofable author" discipline that started with
`register_caution`.

`causation_id` is the id of the event/message that triggered this
command (None for HTTP / MCP root calls).
"""

from typing import Protocol
from uuid import UUID

from cora.decision.aggregates.decision import (
    DecisionRegistered,
)
from cora.decision.aggregates.decision import (
    event_type_name as decision_event_type_name,
)
from cora.decision.aggregates.decision import (
    to_payload as decision_to_payload,
)
from cora.federation.aggregates.permit import (
    event_type_name,
    to_payload,
)
from cora.federation.errors import UnauthorizedError
from cora.federation.features.define_permit.command import DefinePermit
from cora.federation.features.define_permit.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.ports.event_store import StreamAppend
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identity import ActorId

_PERMIT_STREAM_TYPE = "Permit"
_DECISION_STREAM_TYPE = "Decision"
_COMMAND_NAME = "DefinePermit"
_AUDIT_CONTEXT = "PermitDefined"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare define_permit handler: what `bind()` returns.

    Returns the new permit's UUID. Has no idempotency_key kwarg;
    `with_idempotency` at wire.py adds it.
    """

    async def __call__(
        self,
        command: DefinePermit,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """define_permit handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: DefinePermit,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: Kernel) -> Handler:
    """Build a define_permit handler closed over the shared deps."""

    async def handler(
        command: DefinePermit,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "define_permit.start",
            command_name=_COMMAND_NAME,
            peer_facility_id=command.peer_facility_id,
            direction=command.direction.value,
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
                "define_permit.denied",
                command_name=_COMMAND_NAME,
                peer_facility_id=command.peer_facility_id,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        new_id = deps.id_generator.new_id()
        now = deps.clock.now()

        permit_domain_events = decide(
            state=None,
            command=command,
            now=now,
            new_id=new_id,
            defined_by=ActorId(principal_id),
        )

        decision_id = deps.id_generator.new_id()
        decision_event = DecisionRegistered(
            decision_id=decision_id,
            decided_by=ActorId(principal_id),
            context=_AUDIT_CONTEXT,
            choice=str(new_id),
            parent_id=None,
            override_kind=None,
            rule=None,
            reasoning=None,
            confidence=None,
            confidence_source=None,
            alternatives=(),
            inputs=None,
            reasoning_signature=None,
            occurred_at=now,
        )

        permit_new_events = [
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
            for event in permit_domain_events
        ]
        decision_new_events = [
            to_new_event(
                event_type=decision_event_type_name(decision_event),
                payload=decision_to_payload(decision_event),
                occurred_at=decision_event.occurred_at,
                event_id=deps.id_generator.new_id(),
                command_name=_COMMAND_NAME,
                correlation_id=correlation_id,
                causation_id=causation_id,
                principal_id=principal_id,
            )
        ]

        await deps.event_store.append_streams(
            [
                StreamAppend(
                    stream_type=_DECISION_STREAM_TYPE,
                    stream_id=decision_id,
                    expected_version=0,
                    events=decision_new_events,
                ),
                StreamAppend(
                    stream_type=_PERMIT_STREAM_TYPE,
                    stream_id=new_id,
                    expected_version=0,
                    events=permit_new_events,
                ),
            ]
        )

        _log.info(
            "define_permit.success",
            command_name=_COMMAND_NAME,
            permit_id=str(new_id),
            decision_id=str(decision_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            permit_event_count=len(permit_new_events),
            decision_event_count=len(decision_new_events),
        )
        return new_id

    return handler
