"""Application handler for the `register_facility` slice.

Single-stream genesis: writes `FacilityRegistered` on the Federation
Facility stream via `EventStore.append`. No cross-BC Decision audit per
[[project_facility_aggregate_design]] Lock "No cross-BC atomic-writes
in slice 5". Facility creation is structural-scaffolding metadata,
not an authorization decision warranting the Decision-stream audit.

Idempotency-wrappable per the create-style convention; the
`with_idempotency` wrap is applied at `wire.py`, not here.

Stream-id derivation: the handler constructs `FacilityCode(command.code)`
at the port edge (surfacing `InvalidFacilityCodeError` as 422 on bad
input) and derives the Facility stream id deterministically via
`facility_stream_id(code)`. Two effects follow:

  1. Live-path uniqueness: two operators racing `register_facility(code='aps')`
     collide on the same stream id; the second `append(expected_version=0)`
     raises `ConcurrencyError`, which the handler translates to
     `FacilityAlreadyExistsError`.
  2. Bootstrap determinism: the self-Facility seed at lifespan startup
     (Sub-Slice D) does not need to coordinate ids with `id_generator`;
     it derives the stream id from the configured `SELF_FACILITY_CODE`.

`registered_by` is handler-injected from the request envelope's
`principal_id`; not on the command per the "no spoofable author"
discipline.

`causation_id` is the id of the event/message that triggered this
command (None for HTTP / MCP root calls).
"""

from typing import Protocol
from uuid import UUID

from cora.federation.aggregates._value_types import FacilityId
from cora.federation.aggregates.facility import (
    FacilityAlreadyExistsError,
    event_type_name,
    facility_stream_id,
    to_payload,
)
from cora.federation.aggregates.facility.read import load_facility
from cora.federation.errors import UnauthorizedError
from cora.federation.features.register_facility.command import RegisterFacility
from cora.federation.features.register_facility.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.ports.event_store import ConcurrencyError
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId

_FACILITY_STREAM_TYPE = "Facility"
_COMMAND_NAME = "RegisterFacility"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare register_facility handler: what `bind()` returns.

    Returns the new Facility's UUID (the FacilityId derived from
    FacilityCode via facility_stream_id). Has no idempotency_key kwarg;
    `with_idempotency` at wire.py adds it.
    """

    async def __call__(
        self,
        command: RegisterFacility,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """register_facility handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: RegisterFacility,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: Kernel) -> Handler:
    """Build a register_facility handler closed over the shared deps."""

    async def handler(
        command: RegisterFacility,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "register_facility.start",
            command_name=_COMMAND_NAME,
            code=command.code,
            kind=command.kind.value,
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
                "register_facility.denied",
                command_name=_COMMAND_NAME,
                code=command.code,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        # FacilityCode VO construction at the port edge enforces the
        # codepoint pattern (lowercase ASCII alnum + dash, 1-32 chars);
        # any violation surfaces as InvalidFacilityCodeError -> 422.
        code = FacilityCode(command.code)
        facility_id = FacilityId(facility_stream_id(code))
        now = deps.clock.now()

        existing = await load_facility(deps.event_store, facility_id)

        # Cross-stream parent lookup (Sub-Slice A of Slice 6; closes the
        # Slice 5 deferral). When command.parent_id is None this short-
        # circuits to None and the decider's Site/Area structural-
        # invariant arm handles the rest. When non-None, the FacilityLookup
        # port returns a projection row OR None for not-found; the
        # decider translates None to FacilityParentNotFoundError (404)
        # and partitions on result.kind for the Site requirement.
        parent_lookup_result = None
        if command.parent_id is not None:
            parent_lookup_result = await deps.facility_lookup.lookup(command.parent_id)

        facility_domain_events = decide(
            state=existing,
            command=command,
            now=now,
            facility_id=facility_id,
            code=code,
            registered_by=ActorId(principal_id),
            parent_lookup_result=parent_lookup_result,
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

        try:
            await deps.event_store.append(
                stream_type=_FACILITY_STREAM_TYPE,
                stream_id=facility_id,
                expected_version=0,
                events=facility_new_events,
            )
        except ConcurrencyError as exc:
            # The deterministic stream-id derivation means a collision
            # on expected_version=0 is structurally "this code is already
            # registered". Translate to the domain error so the route
            # surfaces it as 409.
            raise FacilityAlreadyExistsError(code) from exc

        _log.info(
            "register_facility.success",
            command_name=_COMMAND_NAME,
            facility_id=str(facility_id),
            code=code.value,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            facility_event_count=len(facility_new_events),
        )
        return facility_id

    return handler
