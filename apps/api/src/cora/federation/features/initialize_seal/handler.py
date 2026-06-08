"""Application handler for the `initialize_seal` slice.

Cross-BC atomic genesis: writes `SealInitialized` on the Federation
Seal stream AND a `DecisionRegistered` audit on the Decision BC
stream in ONE Postgres transaction via
`EventStore.append_streams`. Mirrors `register_credential` and
`define_permit` before it.

The decider builds only the Seal BC event (`SealInitialized`);
this handler additionally builds the Decision BC audit event
(`DecisionRegistered`) and threads both into the single
`append_streams` call. The audit Decision's id is generated fresh
by the handler and used as the new Decision stream id; `choice`
carries the facility_id so the audit row correlates back to the
singleton.

Stream-id derivation: the Seal singleton is keyed on facility_id
(str), but the event store still keys streams by UUID. The handler
derives a deterministic stream UUID via
`seal_stream_id(facility_id)` (UUID5 over a fixed federation
namespace) so the genesis write targets the canonical stream and
later transitions reach the same stream without out-of-band id
coordination.

The handler also resolves BOTH `online_credential_id` and `offline_credential_id`
through `deps.credential_lookup` BEFORE invoking the decider and
threads the resolved `CredentialLookupResult` snapshots into the
decider for cross-aggregate purpose-binding + status-Active checks.
Mirrors the `start_run` pattern (handler loads upstream projections,
threads them into the pure decider) and the `rotate_seal_online_key`
precedent shipped in Pass 2.

Idempotency-wrappable per the create-style convention; the
`with_idempotency` wrap is applied at `wire.py`, not here.

`initialized_by` is handler-injected from the request
envelope's `principal_id` per the "no spoofable author" discipline.

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
from cora.federation.aggregates.facility._stream_id import facility_stream_id
from cora.federation.aggregates.seal import (
    event_type_name,
    to_payload,
)
from cora.federation.aggregates.seal._stream_id import seal_stream_id
from cora.federation.errors import UnauthorizedError
from cora.federation.features.initialize_seal.command import InitializeSeal
from cora.federation.features.initialize_seal.decider import decide
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
_COMMAND_NAME = "InitializeSeal"
_AUDIT_CONTEXT = "SealInitialized"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare initialize_seal handler: what `bind()` returns.

    Returns the deterministic Seal stream UUID. Has no
    idempotency_key kwarg; `with_idempotency` at wire.py adds it.
    """

    async def __call__(
        self,
        command: InitializeSeal,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """initialize_seal handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: InitializeSeal,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: Kernel) -> Handler:
    """Build an initialize_seal handler closed over the shared deps."""

    async def handler(
        command: InitializeSeal,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "initialize_seal.start",
            command_name=_COMMAND_NAME,
            facility_id=command.facility_id,
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
                "initialize_seal.denied",
                command_name=_COMMAND_NAME,
                facility_id=command.facility_id,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        stream_id = seal_stream_id(command.facility_id.strip())

        online_credential = await deps.credential_lookup.lookup(command.online_credential_id)
        offline_credential = await deps.credential_lookup.lookup(command.offline_credential_id)
        # Skip the FacilityLookup when the command facility_id is not a
        # well-formed FacilityCode; the decider's canonical-form arm fires
        # first and surfaces InvalidSealFacilityIdError (400) before the
        # self_facility=None check would surface FacilityNotFoundError.
        try:
            self_facility_id = facility_stream_id(FacilityCode(command.facility_id.strip()))
        except ValueError:
            self_facility = None
        else:
            self_facility = await deps.facility_lookup.lookup(self_facility_id)

        now = deps.clock.now()

        seal_domain_events = decide(
            state=None,
            command=command,
            now=now,
            initialized_by=ActorId(principal_id),
            online_credential=online_credential,
            offline_credential=offline_credential,
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
                    expected_version=0,
                    events=seal_new_events,
                ),
            ]
        )

        _log.info(
            "initialize_seal.success",
            command_name=_COMMAND_NAME,
            facility_id=command.facility_id,
            stream_id=str(stream_id),
            decision_id=str(decision_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            seal_event_count=len(seal_new_events),
            decision_event_count=len(decision_new_events),
        )
        return stream_id

    return handler
