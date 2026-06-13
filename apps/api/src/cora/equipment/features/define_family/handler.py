"""Application handler for the `define_family` slice.

Same shape as `register_actor` / `register_subject` / `define_zone`
/ `define_conduit` / `define_policy` — the locked cross-BC
create-style command pattern. Module-as-namespace: callers use
`from cora.equipment.features import define_family` then
`define_family.bind(deps)` returning a
`define_family.Handler`.

Sixth instance of the create-style template body (after the 5
prior ones). The cross-BC extraction question parked from the
post-Phase-4 review reopens at this 6-instance count, but stays
deferred until we hit either real divergence or a 7th instance —
threading 6 BCs through one factory is a bigger refactor than
threading the next instance through a per-BC helper.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.family import (
    FamilyName,
    event_type_name,
    family_stream_id,
    to_payload,
)
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.define_family.command import DefineFamily
from cora.equipment.features.define_family.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_STREAM_TYPE = "Family"
_COMMAND_NAME = "DefineFamily"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare define_family handler — what `bind()` returns.

    Has no idempotency_key kwarg. The cross-BC `with_idempotency`
    decorator wraps a bare Handler into an `IdempotentHandler`;
    production wiring in `wire.py` always wraps. Tests can use bare
    Handler directly when they don't need idempotency semantics.

    `causation_id` is the id of the event/message that triggered
    this command (None for HTTP / MCP root calls; sagas / process
    managers pass the upstream event's id).
    """

    async def __call__(
        self,
        command: DefineFamily,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """define_family handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: DefineFamily,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: Kernel) -> Handler:
    """Build a define_family handler closed over the shared deps."""

    async def handler(
        command: DefineFamily,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "define_family.start",
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
                "define_family.denied",
                command_name=_COMMAND_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        new_id = family_stream_id(FamilyName(command.name))
        now = deps.clock.now()

        domain_events = decide(
            state=None,
            command=command,
            now=now,
            new_id=new_id,
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
            "define_family.success",
            command_name=_COMMAND_NAME,
            family_id=str(new_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )
        return new_id

    return handler
