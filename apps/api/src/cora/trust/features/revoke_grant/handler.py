"""Application handler for the `revoke_grant` slice.

Single-stream terminal-ish set-removal: writes `PolicyGrantRevoked` on
the Policy stream and nothing else. Deliberately NOT cross-BC: unlike
`revoke_credential` (which co-writes a Decision audit via
`append_streams` for SOC incident-timeline reconstruction), revoking one
grant is a routine authorization edit. The mid-run compensation that
HOLDS the revoked principal's in-flight runs is a SEPARATE,
eventually-consistent subscriber reacting to the committed
`PolicyGrantRevoked` event; keeping it out of this handler obeys the
compensation-slice no-cascade lock and keeps `revoke_grant` off the
governed cross-BC co-write registry.

Longhand (not the `make_update_handler` factory): the decider needs
handler-injected `revoked_by` to stamp the audit denorm onto
`PolicyGrantRevoked`, which the factory cannot forward. The body is the
same load-authorize-fold-decide-append sequence as `define_policy`, with
a load+fold of the existing Policy stream (this is an update, not a
genesis) and `append` at the loaded version.

Not idempotency-wrapped at `wire.py`: revoke is set-membership silently
idempotent at the decider (re-revoking an absent principal emits no
event), so HTTP-layer caching adds no value.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.trust.aggregates.policy import (
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.trust.errors import UnauthorizedError
from cora.trust.features.revoke_grant.command import RevokeGrant
from cora.trust.features.revoke_grant.decider import decide

_STREAM_TYPE = "Policy"
_COMMAND_NAME = "RevokeGrant"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every revoke_grant handler implements."""

    async def __call__(
        self,
        command: RevokeGrant,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a revoke_grant handler closed over the shared deps."""

    async def handler(
        command: RevokeGrant,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "revoke_grant.start",
            command_name=_COMMAND_NAME,
            policy_id=str(command.policy_id),
            revoked_principal_id=str(command.principal_id),
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
                "revoke_grant.denied",
                command_name=_COMMAND_NAME,
                policy_id=str(command.policy_id),
                revoked_principal_id=str(command.principal_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.policy_id,
        )
        state = fold([from_stored(s) for s in stored])

        now = deps.clock.now()

        domain_events = decide(
            state=state,
            command=command,
            now=now,
            revoked_by=principal_id,
        )

        if not domain_events:
            _log.info(
                "revoke_grant.noop",
                command_name=_COMMAND_NAME,
                policy_id=str(command.policy_id),
                revoked_principal_id=str(command.principal_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
            )
            return

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
            stream_id=command.policy_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "revoke_grant.success",
            command_name=_COMMAND_NAME,
            policy_id=str(command.policy_id),
            revoked_principal_id=str(command.principal_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
