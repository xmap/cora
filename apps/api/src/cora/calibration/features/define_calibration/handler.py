"""Application handler for the `define_calibration` slice.

Genesis-style command handler matching `register_caution` /
`define_family` precedent. Module-as-namespace; the BC wires use:

    from cora.calibration.features import define_calibration
    handler = define_calibration.bind(deps)
    calibration_id = await handler(cmd, principal_id=..., correlation_id=...)

Idempotency-wrappable per the create-style convention; the
`with_idempotency` wrap is applied at `wire.py`, not here.

`defined_by` is handler-injected from the request envelope's
`principal_id`; not on the command per the "no spoofable author"
discipline that started with `register_caution`.

`causation_id` is the id of the event/message that triggered this
command (None for HTTP / MCP root calls; sagas / process managers
pass the upstream event's id).
"""

from typing import Protocol
from uuid import UUID

from cora.calibration.aggregates.calibration import event_type_name, to_payload
from cora.calibration.errors import UnauthorizedError
from cora.calibration.features.define_calibration.command import DefineCalibration
from cora.calibration.features.define_calibration.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identity import ActorId

_STREAM_TYPE = "Calibration"
_COMMAND_NAME = "DefineCalibration"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare define_calibration handler — what `bind()` returns.

    Has no idempotency_key kwarg. The cross-BC `with_idempotency`
    decorator wraps a bare Handler into an `IdempotentHandler`;
    production wiring in `wire.py` always wraps. Tests can use bare
    Handler directly when they don't need idempotency semantics.
    """

    async def __call__(
        self,
        command: DefineCalibration,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """define_calibration handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: DefineCalibration,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: Kernel) -> Handler:
    """Build a define_calibration handler closed over the shared deps."""

    async def handler(
        command: DefineCalibration,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "define_calibration.start",
            command_name=_COMMAND_NAME,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            target_id=str(command.target_id),
            quantity=command.quantity.value,
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "define_calibration.denied",
                command_name=_COMMAND_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        new_id = deps.id_generator.new_id()
        now = deps.clock.now()

        domain_events = decide(
            state=None,
            command=command,
            now=now,
            new_id=new_id,
            defined_by=ActorId(principal_id),
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
            "define_calibration.success",
            command_name=_COMMAND_NAME,
            calibration_id=str(new_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )
        return new_id

    return handler
