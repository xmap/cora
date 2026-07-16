"""Domain events emitted by the Ratification aggregate, plus the union.

Lifecycle events (1 genesis + 2 terminal transitions):

  - `RatificationRequested` -- genesis (Requested status). Carries the target
                               action reference, the gated command name, the
                               triggering consequence class, and the requester.
  - `RatificationGranted`   -- Requested -> Granted (a different, independent
                               principal co-signed).
  - `RatificationDenied`    -- Requested -> Denied (+ reason).

The granting/denying principal is the envelope `principal_id` per CORA
convention, not a payload field, so the events carry no `granted_by` /
`denied_by`. The requester is on the genesis payload because independence is
checked against it at grant/deny time and must survive replay.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent


@dataclass(frozen=True)
class RatificationRequested:
    """A co-signature was requested for a consequential target action."""

    ratification_id: UUID
    target_action_id: UUID
    command_name: str
    consequence_class: str
    requested_by: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class RatificationGranted:
    """A different, independent principal co-signed the pending action."""

    ratification_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class RatificationDenied:
    """A different, independent principal refused the pending action (+ reason)."""

    ratification_id: UUID
    reason: str
    occurred_at: datetime


RatificationEvent = RatificationRequested | RatificationGranted | RatificationDenied


def event_type_name(event: RatificationEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: RatificationEvent) -> dict[str, Any]:
    """Serialize a Ratification event to a JSON-friendly dict for jsonb storage."""
    match event:
        case RatificationRequested(
            ratification_id=ratification_id,
            target_action_id=target_action_id,
            command_name=command_name,
            consequence_class=consequence_class,
            requested_by=requested_by,
            occurred_at=occurred_at,
        ):
            return {
                "ratification_id": str(ratification_id),
                "target_action_id": str(target_action_id),
                "command_name": command_name,
                "consequence_class": consequence_class,
                "requested_by": str(requested_by),
                "occurred_at": occurred_at.isoformat(),
            }
        case RatificationGranted(ratification_id=ratification_id, occurred_at=occurred_at):
            return {
                "ratification_id": str(ratification_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case RatificationDenied(
            ratification_id=ratification_id, reason=reason, occurred_at=occurred_at
        ):
            return {
                "ratification_id": str(ratification_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover - exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> RatificationEvent:
    """Rebuild a Ratification event from a StoredEvent loaded from the store."""
    payload = stored.payload
    match stored.event_type:
        case "RatificationRequested":
            return deserialize_or_raise(
                "RatificationRequested",
                lambda: RatificationRequested(
                    ratification_id=UUID(payload["ratification_id"]),
                    target_action_id=UUID(payload["target_action_id"]),
                    command_name=payload["command_name"],
                    consequence_class=payload["consequence_class"],
                    requested_by=UUID(payload["requested_by"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "RatificationGranted":
            return deserialize_or_raise(
                "RatificationGranted",
                lambda: RatificationGranted(
                    ratification_id=UUID(payload["ratification_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "RatificationDenied":
            return deserialize_or_raise(
                "RatificationDenied",
                lambda: RatificationDenied(
                    ratification_id=UUID(payload["ratification_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case _:
            msg = f"Unknown RatificationEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "RatificationDenied",
    "RatificationEvent",
    "RatificationGranted",
    "RatificationRequested",
    "event_type_name",
    "from_stored",
    "to_payload",
]
