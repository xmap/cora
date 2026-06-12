"""Application handler for the `register_clearance` slice.

Same shape as `register_supply` / `register_subject` / `register_actor`
/ `register_procedure` / etc.: the locked cross-BC create-style command
pattern. Module-as-namespace: callers use
`from cora.safety.features import register_clearance` then
`register_clearance.bind(deps)` returning a `register_clearance.Handler`.

Idempotency-wrappable per the create-style convention; the
`with_idempotency` wrap is applied at `wire.py`, not here.

`causation_id` is the id of the event/message that triggered this
command (None for HTTP / MCP root calls; sagas / process managers
pass the upstream event's id).
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.safety.aggregates.clearance import event_type_name, to_payload
from cora.safety.errors import UnauthorizedError
from cora.safety.features.register_clearance.command import RegisterClearance
from cora.safety.features.register_clearance.decider import decide
from cora.shared.facility_code import FacilityCode

_STREAM_TYPE = "Clearance"
_COMMAND_NAME = "RegisterClearance"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare register_clearance handler -- what `bind()` returns.

    Has no idempotency_key kwarg. The cross-BC `with_idempotency`
    decorator wraps a bare Handler into an `IdempotentHandler`;
    production wiring in `wire.py` always wraps. Tests can use bare
    Handler directly when they don't need idempotency semantics.
    """

    async def __call__(
        self,
        command: RegisterClearance,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """register_clearance handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: RegisterClearance,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: Kernel) -> Handler:
    """Build a register_clearance handler closed over the shared deps."""

    async def handler(
        command: RegisterClearance,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "register_clearance.start",
            command_name=_COMMAND_NAME,
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
                "register_clearance.denied",
                command_name=_COMMAND_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        facility_lookup_result = await deps.facility_lookup.lookup_by_code(
            FacilityCode(command.facility_code)
        )
        template_lookup_result = await deps.clearance_template_lookup.lookup(command.template_id)

        new_id = deps.id_generator.new_id()
        now = deps.clock.now()

        domain_events = decide(
            state=None,
            command=command,
            now=now,
            new_id=new_id,
            facility_lookup_result=facility_lookup_result,
            template_lookup_result=template_lookup_result,
        )

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
            stream_id=new_id,
            expected_version=0,
            events=new_events,
        )

        _log.info(
            "register_clearance.success",
            command_name=_COMMAND_NAME,
            clearance_id=str(new_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )
        return new_id

    return handler
