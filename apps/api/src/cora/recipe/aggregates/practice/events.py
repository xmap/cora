"""Domain events emitted by the Practice aggregate, plus the discriminated union.

Mirrors the locked event-module shape: event classes, discriminated
union, `event_type_name`, `to_payload`, `from_stored`. The
persistence-envelope construction (`NewEvent`) lives at
`cora.infrastructure.event_envelope.to_new_event`.

`PracticeDefined` is the genesis; `PracticeVersioned` and
`PracticeDeprecated` cover the `Defined → Versioned → Deprecated`
lifecycle. PracticeVersioned carries an operator-supplied
`version_tag`. PracticeDeprecated carries no extra fields. Mirrors
Method's transition shape and Family's.

## Payload conventions

`method_id` and `site_id` carry as primitive UUIDs in the payload.
Eventual-consistency stance: existence is NOT verified at decide
time (mismatch surfaces at Plan binding).

Status is NOT carried in event payloads — the event type itself
encodes the state change. The evolver hardcodes the mapping per
match arm. Same precedent as MethodDefined / FamilyDefined /
SubjectMounted / ActorDeactivated.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent


@dataclass(frozen=True)
class PracticeDefined:
    """A new facility-adapted Method (Practice) was defined.

    Status is implicit (`Defined`) — the evolver sets it.
    `method_id` is the Method this Practice adapts; `site_id` is the
    Site-level Asset this Practice belongs to. Both eventual-
    consistency refs.
    """

    practice_id: UUID
    name: str
    method_id: UUID
    site_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class PracticeVersioned:
    """A practice's facility adaptation was revised; a new version label was issued.

    Multi-source transition: `Defined | Versioned -> Versioned`. The
    evolver sets status=VERSIONED and updates state.version to the
    new tag. The decider's source-state guard enforces that
    Deprecated practices can't be re-versioned.

    `version_tag` is operator-supplied free text (1-50 chars,
    validated at API boundary AND in the decider). Same precedent
    as MethodVersioned / FamilyVersioned.
    """

    practice_id: UUID
    version_tag: str
    occurred_at: datetime


@dataclass(frozen=True)
class PracticeDeprecated:
    """A practice was marked as no longer recommended for new Plans.

    Multi-source transition: `Defined | Versioned -> Deprecated`. The
    evolver sets status=DEPRECATED; `version` is preserved (the
    historical label of when the practice was last revised before
    deprecation remains visible).

    Existing Plans that reference this Practice are NOT automatically
    invalidated. Deprecation is advisory; future Plan-side enrichment
    may surface a warning at bind-time when referencing a deprecated
    Practice.
    """

    practice_id: UUID
    reason: str
    occurred_at: datetime


# Discriminated union of every event the Practice aggregate emits.
PracticeEvent = PracticeDefined | PracticeVersioned | PracticeDeprecated


def event_type_name(event: PracticeEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: PracticeEvent) -> dict[str, Any]:
    """Serialize a Practice event to a JSON-friendly dict for jsonb storage.

    Primitives only: UUIDs become strings, datetimes become ISO-8601 strings.
    """
    match event:
        case PracticeDefined(
            practice_id=practice_id,
            name=name,
            method_id=method_id,
            site_id=site_id,
            occurred_at=occurred_at,
        ):
            return {
                "practice_id": str(practice_id),
                "name": name,
                "method_id": str(method_id),
                "site_id": str(site_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case PracticeVersioned(
            practice_id=practice_id,
            version_tag=version_tag,
            occurred_at=occurred_at,
        ):
            return {
                "practice_id": str(practice_id),
                "version_tag": version_tag,
                "occurred_at": occurred_at.isoformat(),
            }
        case PracticeDeprecated(
            practice_id=practice_id,
            reason=reason,
            occurred_at=occurred_at,
        ):
            return {
                "practice_id": str(practice_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> PracticeEvent:
    """Rebuild a Practice event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.
    """
    payload = stored.payload
    match stored.event_type:
        case "PracticeDefined":
            return deserialize_or_raise(
                "PracticeDefined",
                lambda: PracticeDefined(
                    practice_id=UUID(payload["practice_id"]),
                    name=payload["name"],
                    method_id=UUID(payload["method_id"]),
                    site_id=UUID(payload["site_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "PracticeVersioned":
            return deserialize_or_raise(
                "PracticeVersioned",
                lambda: PracticeVersioned(
                    practice_id=UUID(payload["practice_id"]),
                    version_tag=payload["version_tag"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "PracticeDeprecated":
            return deserialize_or_raise(
                "PracticeDeprecated",
                lambda: PracticeDeprecated(
                    practice_id=UUID(payload["practice_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case _:
            msg = f"Unknown PracticeEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "PracticeDefined",
    "PracticeDeprecated",
    "PracticeEvent",
    "PracticeVersioned",
    "event_type_name",
    "from_stored",
    "to_payload",
]
