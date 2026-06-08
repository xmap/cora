"""Application handler for the `register_credential` slice.

Cross-BC atomic genesis: writes `CredentialRegistered` on the
Federation Credential stream AND a `DecisionRegistered` audit on
the Decision BC stream in ONE Postgres transaction via
`EventStore.append_streams`. Mirrors `define_permit` (which writes
`PermitDefined` on the Federation Permit stream the same way) and
`define_agent` before it.

The decider builds only the Credential BC event
(`CredentialRegistered`); this handler additionally builds the
Decision BC audit event (`DecisionRegistered`) and threads both
into the single `append_streams` call. The audit Decision's id is
generated fresh by the handler and used as the new Decision stream
id.

Idempotency-wrappable per the create-style convention; the
`with_idempotency` wrap is applied at `wire.py`, not here.

`registered_by` is handler-injected from the request
envelope's `principal_id`; not on the command per the
"no spoofable author" discipline that started with
`register_caution`.

Per AH#6 of the locked design the handler accepts `secret_ref` as a
pre-existing opaque str (URI / KMS ARN / vault path) and writes it
verbatim into `CredentialRegistered.secret_ref`; the raw secret
bytes are the CALLER'S responsibility to land in the SecretStore
adapter BEFORE invoking this slice. No SecretStore dep on the
handler.

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
from cora.federation.aggregates.credential import (
    event_type_name,
    to_payload,
)
from cora.federation.errors import UnauthorizedError
from cora.federation.features.register_credential.command import RegisterCredential
from cora.federation.features.register_credential.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.ports.event_store import StreamAppend
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identity import ActorId

_CREDENTIAL_STREAM_TYPE = "Credential"
_DECISION_STREAM_TYPE = "Decision"
_COMMAND_NAME = "RegisterCredential"
_AUDIT_CONTEXT = "CredentialRegistered"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare register_credential handler: what `bind()` returns.

    Returns the new credential's UUID. Has no idempotency_key kwarg;
    `with_idempotency` at wire.py adds it.
    """

    async def __call__(
        self,
        command: RegisterCredential,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """register_credential handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: RegisterCredential,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: Kernel) -> Handler:
    """Build a register_credential handler closed over the shared deps."""

    async def handler(
        command: RegisterCredential,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "register_credential.start",
            command_name=_COMMAND_NAME,
            facility_id=command.facility_id,
            audience=command.audience,
            purpose=command.purpose.value,
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
                "register_credential.denied",
                command_name=_COMMAND_NAME,
                facility_id=command.facility_id,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        new_id = deps.id_generator.new_id()
        now = deps.clock.now()

        credential_domain_events = decide(
            state=None,
            command=command,
            now=now,
            new_id=new_id,
            registered_by=ActorId(principal_id),
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

        credential_new_events = [
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
            for event in credential_domain_events
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
                    stream_type=_CREDENTIAL_STREAM_TYPE,
                    stream_id=new_id,
                    expected_version=0,
                    events=credential_new_events,
                ),
            ]
        )

        _log.info(
            "register_credential.success",
            command_name=_COMMAND_NAME,
            credential_id=str(new_id),
            decision_id=str(decision_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            credential_event_count=len(credential_new_events),
            decision_event_count=len(decision_new_events),
        )
        return new_id

    return handler
