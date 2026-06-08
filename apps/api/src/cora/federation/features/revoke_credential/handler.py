"""Application handler for the `revoke_credential` slice.

Cross-BC atomic terminal transition: writes `CredentialRevoked` on
the Federation Credential stream AND a `DecisionRegistered` audit on
the Decision BC stream in ONE Postgres transaction via
`EventStore.append_streams`. Mirrors `define_permit` /
`register_credential` (genesis cross-BC writes) but for a TERMINAL
transition: the Credential stream's expected version is the current
loaded version, not zero; the Decision stream is fresh (expected
version zero).

Longhand update handler (mirrors `revoke_permit`): the decider needs
handler-injected `revoked_by` to stamp the audit denorm onto
`CredentialRevoked`, so this slice cannot use the
`make_update_handler` factory (which only forwards `state`, `command`,
`now`). The longhand body wraps the same load-authorize-fold-decide-
append sequence, with the append using `append_streams` instead of
`append` so the audit emission is atomic with the revocation.

Not idempotency-wrapped at wire.py: revoke is a strict-not-idempotent
transition (re-revoking raises `CredentialCannotRevokeError` -> HTTP
409); HTTP-layer caching adds no value when the decider rejects
replays.

Revoking a credential is a security-touching action (a compromised
secret being retired; an operator pulling a peer's verification
material): the Decision-BC audit emission is what gives the SOC a
single stream to scrub when reconstructing incident timelines, which
is why this slice is cross-BC and the rotation lifecycle slices are
not.
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
    fold,
    from_stored,
    to_payload,
)
from cora.federation.errors import UnauthorizedError
from cora.federation.features.revoke_credential.command import RevokeCredential
from cora.federation.features.revoke_credential.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.ports.event_store import StreamAppend
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identity import ActorId

_CREDENTIAL_STREAM_TYPE = "Credential"
_DECISION_STREAM_TYPE = "Decision"
_COMMAND_NAME = "RevokeCredential"
_AUDIT_CONTEXT = "CredentialRevoked"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every revoke_credential handler implements."""

    async def __call__(
        self,
        command: RevokeCredential,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a revoke_credential handler closed over the shared deps."""

    async def handler(
        command: RevokeCredential,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "revoke_credential.start",
            command_name=_COMMAND_NAME,
            credential_id=str(command.credential_id),
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
                "revoke_credential.denied",
                command_name=_COMMAND_NAME,
                credential_id=str(command.credential_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        stored, current_version = await deps.event_store.load(
            stream_type=_CREDENTIAL_STREAM_TYPE,
            stream_id=command.credential_id,
        )
        state = fold([from_stored(s) for s in stored])

        now = deps.clock.now()

        credential_domain_events = decide(
            state=state,
            command=command,
            now=now,
            revoked_by=principal_id,
        )

        decision_id = deps.id_generator.new_id()
        decision_event = DecisionRegistered(
            decision_id=decision_id,
            decided_by=ActorId(principal_id),
            context=_AUDIT_CONTEXT,
            choice=str(command.credential_id),
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
                    stream_id=command.credential_id,
                    expected_version=current_version,
                    events=credential_new_events,
                ),
            ]
        )

        _log.info(
            "revoke_credential.success",
            command_name=_COMMAND_NAME,
            credential_id=str(command.credential_id),
            decision_id=str(decision_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            credential_event_count=len(credential_new_events),
            decision_event_count=len(decision_new_events),
            new_credential_version=current_version + len(credential_new_events),
        )

    return handler
