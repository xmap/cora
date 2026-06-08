"""Application handler for the `rotate_seal_online_key` slice.

Cross-BC atomic mid-lifecycle transition: writes `SealOnlineKeyRotated`
on the Federation Seal stream AND a `DecisionRegistered` audit on the
Decision BC stream in ONE Postgres transaction via
`EventStore.append_streams`. Mirrors `revoke_credential`: a security-
touching action whose audit emission is atomic with the domain event.

The Seal aggregate is a per-facility singleton; the stream UUID is
derived deterministically from `command.facility_id` via UUID5 over a
fixed federation namespace (see `_stream_id.seal_stream_id`). The
expected version on append is the loaded `current_version`, not zero
(Seal must already have been initialized).

Longhand update handler: the decider needs handler-injected
`rotated_by` to stamp the audit denorm onto
`SealOnlineKeyRotated`, so this slice cannot use the
`make_update_handler` factory (which only forwards `state`, `command`,
`now`). The longhand body wraps the same load-authorize-fold-decide-
append sequence, with the append using `append_streams` instead of
`append` so the audit emission is atomic with the rotation.

Not idempotency-wrapped at wire.py: rotate_seal_online_key is a
strict-not-idempotent transition (re-rotating to the same ref raises
`SealCannotRotateError` -> HTTP 409; rotating against a Republishing
Seal raises `SealCannotRotateError` -> HTTP 409); HTTP-layer caching
adds no value when the decider rejects replays.

Rotating the online key is the operator gesture the offline root
authorises in response to suspected compromise or planned rollover;
the Decision-BC audit emission gives the SOC a single stream to scrub
when reconstructing incident timelines, which is why this slice is
cross-BC (matching `revoke_credential`).

Cross-aggregate purpose binding: the handler resolves
`new_online_credential_id` via the `CredentialLookup` port before invoking
the decider and threads the projection row (or None) into the pure
decider, which raises `CredentialNotFoundError` on miss,
`SealKeyPurposeMismatchError` on wrong purpose, and
`SealCannotRotateWithInactiveCredentialError` on non-Active status.
Mirrors the `start_run` handler-loads-projection-then-passes-to-decider
pattern.
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
from cora.federation.aggregates.facility._stream_id import facility_stream_id
from cora.federation.aggregates.seal import (
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.federation.aggregates.seal._stream_id import seal_stream_id
from cora.federation.errors import UnauthorizedError
from cora.federation.features.rotate_seal_online_key.command import (
    RotateSealOnlineKey,
)
from cora.federation.features.rotate_seal_online_key.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.ports.event_store import StreamAppend
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId

_SEAL_STREAM_TYPE = "Seal"
_DECISION_STREAM_TYPE = "Decision"
_COMMAND_NAME = "RotateSealOnlineKey"
_AUDIT_CONTEXT = "SealOnlineKeyRotated"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every rotate_seal_online_key handler implements."""

    async def __call__(
        self,
        command: RotateSealOnlineKey,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a rotate_seal_online_key handler closed over the shared deps."""

    async def handler(
        command: RotateSealOnlineKey,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        stream_id = seal_stream_id(command.facility_id)

        _log.info(
            "rotate_seal_online_key.start",
            command_name=_COMMAND_NAME,
            facility_id=command.facility_id,
            stream_id=str(stream_id),
            new_online_credential_id=str(command.new_online_credential_id),
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
                "rotate_seal_online_key.denied",
                command_name=_COMMAND_NAME,
                facility_id=command.facility_id,
                stream_id=str(stream_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        stored, current_version = await deps.event_store.load(
            stream_type=_SEAL_STREAM_TYPE,
            stream_id=stream_id,
        )
        state = fold([from_stored(s) for s in stored])

        new_online_credential = await deps.credential_lookup.lookup(
            command.new_online_credential_id
        )
        try:
            self_facility_id = facility_stream_id(FacilityCode(command.facility_id))
        except ValueError:
            self_facility = None
        else:
            self_facility = await deps.facility_lookup.lookup(self_facility_id)

        now = deps.clock.now()

        seal_domain_events = decide(
            state=state,
            command=command,
            now=now,
            rotated_by=ActorId(principal_id),
            new_online_credential=new_online_credential,
            self_facility=self_facility,
        )

        decision_id = deps.id_generator.new_id()
        decision_event = DecisionRegistered(
            decision_id=decision_id,
            decided_by=ActorId(principal_id),
            context=_AUDIT_CONTEXT,
            choice=str(command.facility_id),
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

        seal_new_events = [
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
            for event in seal_domain_events
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
                    stream_type=_SEAL_STREAM_TYPE,
                    stream_id=stream_id,
                    expected_version=current_version,
                    events=seal_new_events,
                ),
            ]
        )

        _log.info(
            "rotate_seal_online_key.success",
            command_name=_COMMAND_NAME,
            facility_id=command.facility_id,
            stream_id=str(stream_id),
            decision_id=str(decision_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            seal_event_count=len(seal_new_events),
            decision_event_count=len(decision_new_events),
            new_seal_version=current_version + len(seal_new_events),
        )

    return handler
