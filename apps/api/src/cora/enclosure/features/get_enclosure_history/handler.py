"""Application handler for the `get_enclosure_history` query slice.

Reads the Enclosure's OWN event stream directly (not `list_enclosures`'
projection): `proj_enclosure_summary` carries only the LAST permit
change (`last_permit_status_changed_at` advances only on a change, so
a stale value means "no transition since", never "not observed
since" -- see `projections/enclosure.py`). This slice exists to answer
a different question: every exact transition CORA ever recorded for
this enclosure, which a folded current-state view collapses away.

Full event payloads ride this view, mirroring `get_run_history`
exactly -- this is a general-purpose on-network read, not the piece
that talks to the external relay. `EnclosurePermitObserved.reason`
and `.monitor_ref` embed the PSS PV address, and `list_enclosures`'
own HTTP DTO already exposes the equivalent last-observation fields
on-network (`last_permit_status_reason`, `last_source_id`), so there
is no new exposure here. The redaction that matters lives downstream,
in the status-push feature that builds the timeline document actually
sent to the relay: that document carries `from_status` / `to_status`
only, never `reason` / `monitor_ref` / `triggered_by`.

Query handlers do NOT emit `causation_id` log fields.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from cora.enclosure.aggregates.enclosure import fold, from_stored
from cora.enclosure.errors import UnauthorizedError
from cora.enclosure.features.get_enclosure_history.query import GetEnclosureHistory
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_QUERY_NAME = "GetEnclosureHistory"
_STREAM_TYPE = "Enclosure"
_EVENT_LIMIT = 2000

_log = get_logger(__name__)


@dataclass(frozen=True)
class EnclosureHistoryEvent:
    """One event off the Enclosure's own stream, with its own exact timestamps."""

    event_id: UUID
    event_type: str
    version: int
    occurred_at: datetime
    recorded_at: datetime
    payload: dict[str, Any]


@dataclass(frozen=True)
class EnclosureHistoryView:
    """The full read-side composition for `get_enclosure_history`."""

    enclosure_id: UUID
    name: str
    permit_status: str
    lifecycle: str
    events: list[EnclosureHistoryEvent]
    events_truncated: bool


class Handler(Protocol):
    """Callable interface every get_enclosure_history handler implements."""

    async def __call__(
        self,
        query: GetEnclosureHistory,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> EnclosureHistoryView | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_enclosure_history handler closed over the shared deps."""

    async def handler(
        query: GetEnclosureHistory,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> EnclosureHistoryView | None:
        _log.info(
            "get_enclosure_history.start",
            query_name=_QUERY_NAME,
            enclosure_id=str(query.enclosure_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "get_enclosure_history.denied",
                query_name=_QUERY_NAME,
                enclosure_id=str(query.enclosure_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        stored, _version = await deps.event_store.load(_STREAM_TYPE, query.enclosure_id)
        if not stored:
            _log.info(
                "get_enclosure_history.success",
                query_name=_QUERY_NAME,
                enclosure_id=str(query.enclosure_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                found=False,
            )
            return None

        enclosure = fold([from_stored(s) for s in stored])
        assert enclosure is not None  # stored is non-empty, so fold cannot return None

        events_truncated = len(stored) > _EVENT_LIMIT
        events = [
            EnclosureHistoryEvent(
                event_id=s.event_id,
                event_type=s.event_type,
                version=s.version,
                occurred_at=s.occurred_at,
                recorded_at=s.recorded_at,
                payload=s.payload,
            )
            for s in stored[:_EVENT_LIMIT]
        ]

        _log.info(
            "get_enclosure_history.success",
            query_name=_QUERY_NAME,
            enclosure_id=str(query.enclosure_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=True,
            event_count=len(events),
        )
        return EnclosureHistoryView(
            enclosure_id=enclosure.id,
            name=enclosure.name.value,
            permit_status=enclosure.permit_status.value,
            lifecycle=enclosure.lifecycle.value,
            events=events,
            events_truncated=events_truncated,
        )

    return handler


__all__ = [
    "EnclosureHistoryEvent",
    "EnclosureHistoryView",
    "Handler",
    "bind",
]
