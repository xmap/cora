"""Domain events emitted by the Seal aggregate, plus the discriminated union.

Five events shipped at BC genesis:

  - `SealInitialized`: genesis (singleton minted).
  - `SealPointerSigned`: a new head pointer was signed by the
    online key.
  - `SealOnlineKeyRotated`: the online key was swapped (the
    offline root authorizes this; the decider checks purpose binding
    and key separation).
  - `SealRepublishingStarted`: Live to Republishing.
  - `SealRepublishingCompleted`: Republishing to Live, with a
    fresh head hash and bumped sequence number.

The denorm `*_by_actor_id` field on each event mirrors the envelope's
`principal_id`; the brief locks this for Permit / Credential / Seal.
Per Path C
([[project_template_aggregate_timestamps]]) lifecycle bookkeeping
timestamps (`initialized_at`, `last_signed_at`) live on the projection,
not on aggregate state; `signed_at` is carried on the signing event
payload so the projection's `last_signed_at` reflects domain time
(mirrors Calibration revision `established_at`).

Wire shape is flat primitives: UUIDs render as strings, datetimes as
ISO-8601, SealStatus does not travel on payloads (the event
type IS the state-change indicator per the cross-aggregate convention).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identity import ActorId


@dataclass(frozen=True)
class SealInitialized:
    """The Seal singleton was minted for this facility.

    Genesis event. Carries the initial online and offline key
    references; the decider has already verified key separation and
    purpose binding before commit. `initial_sequence_number` is 0;
    `initial_head_hash` is None (no pointer signed yet).
    """

    facility_id: str
    online_credential_id: UUID
    offline_credential_id: UUID
    initialized_by: ActorId
    occurred_at: datetime


@dataclass(frozen=True)
class SealPointerSigned:
    """A new head pointer was signed by the online key.

    `head_hash` is the SHA-256 (lowercase hex) of the canonicalized
    head pointer body. `sequence_number` is strictly greater than the
    prior value (the decider rejects regressions via
    `SealSequenceNumberRegressionError`).

    `signed_at` is the wall-clock the signature was produced; carried
    explicitly so the projection's `last_signed_at` reflects domain
    time rather than event-envelope time (mirrors Calibration revision
    `established_at`).
    """

    facility_id: str
    head_hash: str
    sequence_number: int
    signed_at: datetime
    signed_by: ActorId
    occurred_at: datetime


@dataclass(frozen=True)
class SealOnlineKeyRotated:
    """The online (warm) signing key was rotated to a fresh Credential.

    The decider has verified that the new `online_credential_id` differs
    from the existing `offline_credential_id` (key separation) and that the
    new credential's purpose is `SealOnlineSigning`. The offline root
    is unchanged by this event; rotating the offline root is a
    separate slice and is out of scope here.

    `signed_by_offline_root` records the operator gesture that the
    offline root authorised this rotation (audit-only; verification of
    the offline signature itself is out of scope here).
    """

    facility_id: str
    new_online_credential_id: UUID
    signed_by_offline_root: bool
    rotated_by: ActorId
    occurred_at: datetime


@dataclass(frozen=True)
class SealRepublishingStarted:
    """The offline root began republishing the full registry tree.

    Status moves Live -> Republishing. The online key continues to
    sign pointers during the window; consumers may use the indicator
    to defer trust.
    """

    facility_id: str
    started_by: ActorId
    occurred_at: datetime
    reason: str | None = None


@dataclass(frozen=True)
class SealRepublishingCompleted:
    """The offline root finished republishing the registry tree.

    Status moves Republishing -> Live. `new_head_hash` is the SHA-256
    of the fresh head pointer; `new_sequence_number` is strictly
    greater than the prior value (the decider rejects regressions).
    """

    facility_id: str
    new_head_hash: str
    new_sequence_number: int
    completed_by: ActorId
    occurred_at: datetime


SealEvent = (
    SealInitialized
    | SealPointerSigned
    | SealOnlineKeyRotated
    | SealRepublishingStarted
    | SealRepublishingCompleted
)


def event_type_name(event: SealEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: SealEvent) -> dict[str, Any]:
    """Serialise a Seal event to a JSON-friendly dict for jsonb storage."""
    match event:
        case SealInitialized(
            facility_id=facility_id,
            online_credential_id=online_credential_id,
            offline_credential_id=offline_credential_id,
            initialized_by=initialized_by,
            occurred_at=occurred_at,
        ):
            return {
                "facility_id": facility_id,
                "online_credential_id": str(online_credential_id),
                "offline_credential_id": str(offline_credential_id),
                "initialized_by": str(initialized_by),
                "occurred_at": occurred_at.isoformat(),
            }
        case SealPointerSigned(
            facility_id=facility_id,
            head_hash=head_hash,
            sequence_number=sequence_number,
            signed_at=signed_at,
            signed_by=signed_by,
            occurred_at=occurred_at,
        ):
            return {
                "facility_id": facility_id,
                "head_hash": head_hash,
                "sequence_number": sequence_number,
                "signed_at": signed_at.isoformat(),
                "signed_by": str(signed_by),
                "occurred_at": occurred_at.isoformat(),
            }
        case SealOnlineKeyRotated(
            facility_id=facility_id,
            new_online_credential_id=new_online_credential_id,
            signed_by_offline_root=signed_by_offline_root,
            rotated_by=rotated_by,
            occurred_at=occurred_at,
        ):
            return {
                "facility_id": facility_id,
                "new_online_credential_id": str(new_online_credential_id),
                "signed_by_offline_root": signed_by_offline_root,
                "rotated_by": str(rotated_by),
                "occurred_at": occurred_at.isoformat(),
            }
        case SealRepublishingStarted(
            facility_id=facility_id,
            started_by=started_by,
            occurred_at=occurred_at,
            reason=reason,
        ):
            return {
                "facility_id": facility_id,
                "started_by": str(started_by),
                "occurred_at": occurred_at.isoformat(),
                "reason": reason,
            }
        case SealRepublishingCompleted(
            facility_id=facility_id,
            new_head_hash=new_head_hash,
            new_sequence_number=new_sequence_number,
            completed_by=completed_by,
            occurred_at=occurred_at,
        ):
            return {
                "facility_id": facility_id,
                "new_head_hash": new_head_hash,
                "new_sequence_number": new_sequence_number,
                "completed_by": str(completed_by),
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover
            assert_never(event)


def from_stored(stored: StoredEvent) -> SealEvent:
    """Rebuild a Seal event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.
    """
    payload = stored.payload
    match stored.event_type:
        case "SealInitialized":
            return deserialize_or_raise(
                "SealInitialized",
                lambda: SealInitialized(
                    facility_id=payload["facility_id"],
                    online_credential_id=UUID(payload["online_credential_id"]),
                    offline_credential_id=UUID(payload["offline_credential_id"]),
                    initialized_by=ActorId(UUID(payload["initialized_by"])),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "SealPointerSigned":
            return deserialize_or_raise(
                "SealPointerSigned",
                lambda: SealPointerSigned(
                    facility_id=payload["facility_id"],
                    head_hash=payload["head_hash"],
                    sequence_number=payload["sequence_number"],
                    signed_at=datetime.fromisoformat(payload["signed_at"]),
                    signed_by=ActorId(UUID(payload["signed_by"])),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "SealOnlineKeyRotated":
            return deserialize_or_raise(
                "SealOnlineKeyRotated",
                lambda: SealOnlineKeyRotated(
                    facility_id=payload["facility_id"],
                    new_online_credential_id=UUID(payload["new_online_credential_id"]),
                    signed_by_offline_root=payload["signed_by_offline_root"],
                    rotated_by=ActorId(UUID(payload["rotated_by"])),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "SealRepublishingStarted":
            return deserialize_or_raise(
                "SealRepublishingStarted",
                lambda: SealRepublishingStarted(
                    facility_id=payload["facility_id"],
                    started_by=ActorId(UUID(payload["started_by"])),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    reason=payload.get("reason"),
                ),
            )
        case "SealRepublishingCompleted":
            return deserialize_or_raise(
                "SealRepublishingCompleted",
                lambda: SealRepublishingCompleted(
                    facility_id=payload["facility_id"],
                    new_head_hash=payload["new_head_hash"],
                    new_sequence_number=payload["new_sequence_number"],
                    completed_by=ActorId(UUID(payload["completed_by"])),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case unknown:
            msg = f"Unknown Seal event type: {unknown!r}"
            raise ValueError(msg)


__all__ = [
    "SealEvent",
    "SealInitialized",
    "SealOnlineKeyRotated",
    "SealPointerSigned",
    "SealRepublishingCompleted",
    "SealRepublishingStarted",
    "event_type_name",
    "from_stored",
    "to_payload",
]
