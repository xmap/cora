"""Application handler for the `decommission_facility` slice.

Single-stream terminal transition: writes `FacilityDecommissioned` on
the Facility stream via `EventStore.append`. No cross-BC Decision audit
per [[project_facility_aggregate_design]] Lock "No cross-BC atomic-writes
in slice 5"; the Facility lifecycle is structural-scaffolding metadata
and not authorization-decision-bearing.

Longhand load-decide-append (mirrors the revoke_credential shape without
the cross-BC append_streams): loads the target Facility, computes the
terminal-transition event via the pure decider, appends with
`expected_version=current_version` so optimistic concurrency catches
concurrent writes.

Not idempotency-wrapped at wire.py: decommission is strict-not-idempotent
(re-decommissioning raises `FacilityCannotDecommissionError` -> HTTP 409);
HTTP-layer caching adds no value when the decider rejects replays.

`decommissioned_by` is handler-injected from the request envelope's
`principal_id`; not on the command per the "no spoofable author"
discipline.

`causation_id` is the id of the event/message that triggered this
command (None for HTTP / MCP root calls).
"""

from typing import Protocol
from uuid import UUID

from cora.federation.aggregates._value_types import FacilityId
from cora.federation.aggregates.facility import (
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.federation.errors import UnauthorizedError
from cora.federation.features.decommission_facility.command import DecommissionFacility
from cora.federation.features.decommission_facility.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identity import ActorId

_FACILITY_STREAM_TYPE = "Facility"
_COMMAND_NAME = "DecommissionFacility"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every decommission_facility handler implements."""

    async def __call__(
        self,
        command: DecommissionFacility,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a decommission_facility handler closed over the shared deps."""

    async def handler(
        command: DecommissionFacility,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "decommission_facility.start",
            command_name=_COMMAND_NAME,
            facility_id=str(command.facility_id),
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
                "decommission_facility.denied",
                command_name=_COMMAND_NAME,
                facility_id=str(command.facility_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        stored, current_version = await deps.event_store.load(
            stream_type=_FACILITY_STREAM_TYPE,
            stream_id=command.facility_id,
        )
        state = fold([from_stored(s) for s in stored])

        now = deps.clock.now()

        facility_domain_events = decide(
            state=state,
            command=command,
            now=now,
            decommissioned_by=ActorId(principal_id),
        )

        facility_new_events = [
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
            for event in facility_domain_events
        ]

        await deps.event_store.append(
            stream_type=_FACILITY_STREAM_TYPE,
            stream_id=FacilityId(command.facility_id),
            expected_version=current_version,
            events=facility_new_events,
        )

        _log.info(
            "decommission_facility.success",
            command_name=_COMMAND_NAME,
            facility_id=str(command.facility_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            facility_event_count=len(facility_new_events),
            new_facility_version=current_version + len(facility_new_events),
        )

    return handler
