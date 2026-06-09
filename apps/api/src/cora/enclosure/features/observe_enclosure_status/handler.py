"""Application handler for the `observe_enclosure_status` slice.

Update-style handler: loads the Enclosure stream, folds the history,
calls the pure decider with the per-aggregate `triggered_by` kwarg
(pulled from `command.monitor_source_id`), and appends the emitted
events. Per the L-EV-2 status-change-only contract, the decider
returns `[]` for identical-status observations; when that happens
the handler skips the append entirely (no event emitted, no
idempotency fingerprint written).

Per [[project_enclosure_stage1_design]]: this handler is
intentionally NOT exposed via REST route or MCP tool. In-process
adapters (the future EPICS / P4P / Tango subscriber) drive
observations by pulling `EnclosureHandlers.observe_enclosure_status`
and invoking it directly with a `MonitorSourceId` carried on the
command.

Monitor-triggered slices pull attribution from the command, not
from the request principal. The in-process adapter that produced
the observation owns the `MonitorSourceId`; the request principal
is typically a service account whose identity is incidental.
Mirrors `observe_supply_status` per
[[project_supply_monitor_trigger_design]].

The handler does NOT wrap with `with_idempotency`. Monitor-trigger
observations are inherently retry-safe: identical-status
re-emissions are silently absorbed by the decider's `[]`
short-circuit, and distinct-status transitions are status-change-
only so re-observation of a transition that already landed is
itself a no-op against the folded state. This mirrors the Supply
observe precedent.
"""

from typing import Protocol
from uuid import UUID

from cora.enclosure.aggregates.enclosure import (
    EnclosureEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.enclosure.errors import UnauthorizedError
from cora.enclosure.features.observe_enclosure_status.command import (
    ObserveEnclosureStatus,
)
from cora.enclosure.features.observe_enclosure_status.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_STREAM_TYPE = "Enclosure"
_COMMAND_NAME = "ObserveEnclosureStatus"
_LOG_PREFIX = "observe_enclosure_status"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every observe_enclosure_status handler implements."""

    async def __call__(
        self,
        command: ObserveEnclosureStatus,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an observe_enclosure_status handler closed over the shared deps."""

    async def handler(
        command: ObserveEnclosureStatus,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        target_id: UUID = command.enclosure_id

        _log.info(
            f"{_LOG_PREFIX}.start",
            command_name=_COMMAND_NAME,
            enclosure_id=str(target_id),
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
                enclosure_id=str(target_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=target_id,
        )
        history: list[EnclosureEvent] = [from_stored(s) for s in stored]
        state = fold(history)

        domain_events = decide(
            state=state,
            command=command,
            now=now,
            triggered_by=command.monitor_source_id,
        )

        if not domain_events:
            _log.info(
                f"{_LOG_PREFIX}.noop",
                command_name=_COMMAND_NAME,
                enclosure_id=str(target_id),
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
            stream_id=target_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            f"{_LOG_PREFIX}.success",
            command_name=_COMMAND_NAME,
            enclosure_id=str(target_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
