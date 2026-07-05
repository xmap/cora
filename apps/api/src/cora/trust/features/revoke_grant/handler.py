"""Application handler for the `revoke_grant` slice.

Single-stream set-removal: loads the Policy, threads the envelope `principal_id`
into the decider as `revoked_by` (the invoker; distinct from the command's
`principal_id`, which is the grant being removed), and appends the resulting
`PolicyGrantRevoked` at the loaded version. Same load-authorize-fold-decide-append
sequence as `define_policy`, but a transition (append at the loaded version, not
genesis 0).

NOT idempotency-wrapped at wire.py: revoke is set-membership silently idempotent
(a re-issued revoke of an already-absent principal produces no event), so
HTTP-layer caching adds no value.

The mid-run compensation that HOLDS the revoked principal's in-flight runs is a
SEPARATE eventually-consistent subscriber reacting to the committed
`PolicyGrantRevoked` event; it is deliberately kept OUT of this handler to obey
the compensation-slice no-cascade lock and keep `revoke_grant` a routine
authorization edit.
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
from cora.trust.features.revoke_grant.command import RevokePolicyGrant
from cora.trust.features.revoke_grant.decider import decide

_STREAM_TYPE = "Policy"
_COMMAND_NAME = "RevokePolicyGrant"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare revoke_grant handler -- what `bind()` returns."""

    async def __call__(
        self,
        command: RevokePolicyGrant,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a revoke_grant handler closed over the shared deps."""

    async def handler(
        command: RevokePolicyGrant,
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
            revoked_principal_id=str(command.permitted_principal_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )

        # Authorization is command-level (may this principal issue RevokePolicyGrant
        # at all), not per-Policy: there is no per-instance grant check. This is the
        # deliberate posture for the kill-switch, matching define_policy; a
        # per-resource authz check would land on the Authorize port if ever needed.
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
                revoked_principal_id=str(command.permitted_principal_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()
        stored, version = await deps.event_store.load(_STREAM_TYPE, command.policy_id)
        state = fold([from_stored(s) for s in stored])

        domain_events = decide(
            state=state,
            command=command,
            revoked_by=principal_id,
            now=now,
        )

        if not domain_events:
            _log.info(
                "revoke_grant.noop",
                command_name=_COMMAND_NAME,
                policy_id=str(command.policy_id),
                revoked_principal_id=str(command.permitted_principal_id),
                correlation_id=str(correlation_id),
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
            expected_version=version,
            events=new_events,
        )

        _log.info(
            "revoke_grant.success",
            command_name=_COMMAND_NAME,
            policy_id=str(command.policy_id),
            revoked_principal_id=str(command.permitted_principal_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )

    return handler
