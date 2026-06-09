"""Application handler for the `decommission_enclosure` slice.

Single-stream terminal transition: writes `EnclosureDecommissioned` on
the Enclosure stream via `EventStore.append`. No cross-BC Decision
audit; the Enclosure lifecycle is structural-scaffolding metadata and
not authorization-decision-bearing.

Longhand load-decide-append (mirrors `decommission_facility` shape;
diverges by requiring `reason` non-optionally for audit trail):
loads the target Enclosure, computes the terminal-transition event via
the pure decider, appends with `expected_version=current_version` so
optimistic concurrency catches concurrent writes.

Not idempotency-wrapped at wire.py: decommission is strict-not-idempotent
(re-decommissioning raises `EnclosureCannotDecommissionError` -> HTTP
409); HTTP-layer caching adds no value when the decider rejects replays.

`triggered_by` is handler-injected from the request envelope's
`principal_id` and wrapped as `ActorId`; not on the command per the
"no spoofable author" discipline. This contrasts with the
`observe_enclosure_status` slice, where attribution is pulled from a
`MonitorSourceId` carried on the command.

`causation_id` is the id of the event/message that triggered this
command (None for HTTP / MCP root calls).
"""

from typing import Protocol
from uuid import UUID

from cora.enclosure.aggregates._value_types import EnclosureId
from cora.enclosure.aggregates.enclosure import (
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.enclosure.errors import UnauthorizedError
from cora.enclosure.features.decommission_enclosure.command import (
    DecommissionEnclosure,
)
from cora.enclosure.features.decommission_enclosure.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identity import ActorId

_STREAM_TYPE = "Enclosure"
_COMMAND_NAME = "DecommissionEnclosure"
_LOG_PREFIX = "decommission_enclosure"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every decommission_enclosure handler implements."""

    async def __call__(
        self,
        command: DecommissionEnclosure,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a decommission_enclosure handler closed over the shared deps."""

    async def handler(
        command: DecommissionEnclosure,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            f"{_LOG_PREFIX}.start",
            command_name=_COMMAND_NAME,
            enclosure_id=str(command.enclosure_id),
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
                f"{_LOG_PREFIX}.denied",
                command_name=_COMMAND_NAME,
                enclosure_id=str(command.enclosure_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.enclosure_id,
        )
        state = fold([from_stored(s) for s in stored])

        now = deps.clock.now()

        enclosure_domain_events = decide(
            state=state,
            command=command,
            now=now,
            triggered_by=ActorId(principal_id),
        )

        enclosure_new_events = [
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
            for event in enclosure_domain_events
        ]

        await deps.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=EnclosureId(command.enclosure_id),
            expected_version=current_version,
            events=enclosure_new_events,
        )

        _log.info(
            f"{_LOG_PREFIX}.success",
            command_name=_COMMAND_NAME,
            enclosure_id=str(command.enclosure_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            enclosure_event_count=len(enclosure_new_events),
            new_enclosure_version=current_version + len(enclosure_new_events),
        )

    return handler
