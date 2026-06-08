"""Domain events emitted by the Conduit aggregate, plus the discriminated union.

Mirrors `cora/trust/aggregates/zone/events.py` in shape: event
classes, discriminated union, `event_type_name`, `to_payload`,
`from_stored`. The persistence-envelope construction (`NewEvent`)
lives at `cora.infrastructure.event_envelope.to_new_event`.

Events:
  - `ConduitDefined` — genesis.
  - `ConduitLogbookOpened` — declares a new observation logbook
    attached to the Conduit. Carries the logbook id, kind
    discriminator (for example, `"traversals"`), and the schema declaration
    documenting what columns the entry rows will have. Today the
    only logbook kind is `traversals` (per-decision authz audit
    log), opened automatically at conduit-creation.
  - `ConduitLogbookClosed` — terminates a logbook. Future-additive;
    no current path emits it (the traversals logbook never closes
    until conduit-archive ships, which is itself deferred).

Logbook events DO live on the Conduit's main event stream — they
are part of the Conduit's lifecycle audit (compliance grade: an
auditor can replay the Conduit stream alone and see when each
logbook was opened, with what schema, and when it closed). The
high-cardinality entry rows themselves live in separate
`entries_<kind>` tables and do NOT fold into Conduit state.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.logbook import LogbookSchema


@dataclass(frozen=True)
class ConduitDefined:
    """A new Trust conduit was defined between two zones."""

    conduit_id: UUID
    name: str
    source_zone_id: UUID
    target_zone_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class ConduitLogbookOpened:
    """An observation logbook was attached to this Conduit.

    `logbook_id` is a fresh UUIDv7 from the IdGenerator; uniquely
    identifies this logbook session and tags every entry row written
    to it. `kind` is the discriminator (today: `traversals`).
    `schema` declares the per-entry column shape — carried in
    the event payload so the lifecycle audit captures the schema as
    of this opening (G8 lock; supports per-logbook schema evolution
    by declaring a new `kind` or a new logbook with updated schema).
    """

    conduit_id: UUID
    logbook_id: UUID
    kind: str
    schema: LogbookSchema
    occurred_at: datetime


@dataclass(frozen=True)
class ConduitLogbookClosed:
    """An observation logbook attached to this Conduit was closed.

    Future-additive (no command path emits this today). When
    conduit-archive ships, it will auto-close every open logbook
    before the archive transition (mirrors the Run terminal
    auto-close pattern).
    """

    conduit_id: UUID
    logbook_id: UUID
    occurred_at: datetime


# Discriminated union of every event the Conduit aggregate emits.
ConduitEvent = ConduitDefined | ConduitLogbookOpened | ConduitLogbookClosed


def event_type_name(event: ConduitEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: ConduitEvent) -> dict[str, Any]:
    """Serialize a Conduit event to a JSON-friendly dict for jsonb storage.

    Primitives only: UUIDs become strings, datetimes become ISO-8601 strings.
    `LogbookSchema` serializes via its own `to_dict()`.
    """
    match event:
        case ConduitDefined(
            conduit_id=conduit_id,
            name=name,
            source_zone_id=source_zone_id,
            target_zone_id=target_zone_id,
            occurred_at=occurred_at,
        ):
            return {
                "conduit_id": str(conduit_id),
                "name": name,
                "source_zone_id": str(source_zone_id),
                "target_zone_id": str(target_zone_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case ConduitLogbookOpened(
            conduit_id=conduit_id,
            logbook_id=logbook_id,
            kind=kind,
            schema=schema,
            occurred_at=occurred_at,
        ):
            return {
                "conduit_id": str(conduit_id),
                "logbook_id": str(logbook_id),
                "kind": kind,
                "schema": schema.to_dict(),
                "occurred_at": occurred_at.isoformat(),
            }
        case ConduitLogbookClosed(
            conduit_id=conduit_id,
            logbook_id=logbook_id,
            occurred_at=occurred_at,
        ):
            return {
                "conduit_id": str(conduit_id),
                "logbook_id": str(logbook_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> ConduitEvent:
    """Rebuild a Conduit event from a StoredEvent loaded from the event store."""
    payload = stored.payload
    match stored.event_type:
        case "ConduitDefined":
            return deserialize_or_raise(
                "ConduitDefined",
                lambda: ConduitDefined(
                    conduit_id=UUID(payload["conduit_id"]),
                    name=payload["name"],
                    source_zone_id=UUID(payload["source_zone_id"]),
                    target_zone_id=UUID(payload["target_zone_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "ConduitLogbookOpened":
            return deserialize_or_raise(
                "ConduitLogbookOpened",
                lambda: ConduitLogbookOpened(
                    conduit_id=UUID(payload["conduit_id"]),
                    logbook_id=UUID(payload["logbook_id"]),
                    kind=payload["kind"],
                    schema=LogbookSchema.from_dict(payload["schema"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "ConduitLogbookClosed":
            return deserialize_or_raise(
                "ConduitLogbookClosed",
                lambda: ConduitLogbookClosed(
                    conduit_id=UUID(payload["conduit_id"]),
                    logbook_id=UUID(payload["logbook_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case _:
            msg = f"Unknown ConduitEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "ConduitDefined",
    "ConduitEvent",
    "ConduitLogbookClosed",
    "ConduitLogbookOpened",
    "event_type_name",
    "from_stored",
    "to_payload",
]
