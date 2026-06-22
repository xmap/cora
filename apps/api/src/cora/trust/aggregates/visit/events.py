"""Domain events emitted by the Visit aggregate, plus the discriminated union.

Lifecycle events (8 transitions + 1 voided terminal):

  - `VisitRegistered`   -- genesis (Planned status)
  - `VisitArrived`      -- Planned -> Arrived
  - `VisitStarted`      -- Arrived -> InProgress
  - `VisitHeld`         -- InProgress -> OnHold (+ reason)
  - `VisitResumed`      -- OnHold -> InProgress
  - `VisitCompleted`    -- InProgress | OnHold -> Completed
  - `VisitCancelled`    -- Planned | Arrived -> Cancelled (+ reason)
  - `VisitAborted`      -- InProgress | OnHold -> Aborted (+ reason)
  - `VisitVoided`       -- any non-terminal -> Voided (+ reason)
                          FHIR `entered-in-error` analog.

Presence events: `VisitCheckedIn` / `VisitCheckedOut`. Surface-control
events: `VisitSurfaceControlTaken` / `VisitSurfaceControlReleased`.

`VisitRegistered.permitted_*` lists become `frozenset` on state in the
evolver -- same list-on-event / frozenset-on-state pattern as PolicyDefined.
`external_refs` is serialized as a sorted list of dicts in to_payload for
deterministic byte-equality across runs.

`parent_id` and `external_refs` ship on the VisitRegistered event
payload alongside the lifecycle fields to avoid a two-pass payload migration
when the partOf cohesion check + external-ref query slices land.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identifier import Identifier


@dataclass(frozen=True)
class VisitRegistered:
    """A new Visit was registered for a Policy + Surface pair."""

    visit_id: UUID
    policy_id: UUID
    surface_id: UUID
    type: str  # VisitType.value -- serialized as string for JSON round-trip
    planned_start_at: datetime
    planned_end_at: datetime
    occurred_at: datetime
    parent_id: UUID | None = None
    external_refs: frozenset[Identifier] = field(default_factory=frozenset[Identifier])


@dataclass(frozen=True)
class VisitArrived:
    """The Visit team has arrived (explicit operator gesture).

    Distinct from any presence event (`VisitCheckedIn`).
    Operator may call `record_visit_arrival` without any individual actor
    check-in (e.g., team here but specific presences not tracked).
    Defends V6 explicit-gesture lock.
    """

    visit_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class VisitStarted:
    """Work on the Visit has begun (explicit operator gesture)."""

    visit_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class VisitHeld:
    """The Visit was paused for an external reason (NOT child commissioning).

    OnHold is reserved for genuine envelope pauses (beam dump, equipment
    fault, safety hold, extended user break). Commissioning-during-user
    does NOT put parent OnHold -- parent stays InProgress; control concern
    lives on `proj_surface_active_visit`.
    """

    visit_id: UUID
    reason: str
    occurred_at: datetime


@dataclass(frozen=True)
class VisitResumed:
    """The Visit returned to InProgress from OnHold."""

    visit_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class VisitCompleted:
    """The Visit reached normal terminal status."""

    visit_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class VisitCancelled:
    """The Visit was cancelled before work began (Planned or Arrived).

    Distinct from `VisitAborted` (work started then stopped) and from
    `VisitVoided` (registration was a mistake). Cancellation is the
    "real allocation, never started" terminator. HL7 v2 A11 precedent.
    """

    visit_id: UUID
    reason: str
    occurred_at: datetime


@dataclass(frozen=True)
class VisitAborted:
    """The Visit was stopped mid-work (InProgress or OnHold).

    Distinct from `VisitCancelled` (pre-work) and `VisitVoided` (mistake).
    HL7 v2 A13 precedent.
    """

    visit_id: UUID
    reason: str
    occurred_at: datetime


@dataclass(frozen=True)
class VisitVoided:
    """The Visit should never have existed (registration was a mistake).

    FHIR R5 `entered-in-error` analog. Distinguished from `VisitCancelled`
    (real allocation, operator pre-work cancel) and `VisitAborted` (real
    work stopped). Reachable from ANY non-terminal status. Use cases:
    BSS double-sent a registration, duplicate Visit, registration error.
    """

    visit_id: UUID
    reason: str
    occurred_at: datetime


@dataclass(frozen=True)
class VisitCheckedIn:
    """An actor checked in to the Visit in physical or remote mode.

    Does NOT change Visit.status -- presence is orthogonal to lifecycle
    (V6 explicit-gesture lock: operator must `record_visit_arrival` separately
    before any check-in is permitted). Adds one open `PresenceEntry`
    to `presence_entries` via set-union in the evolver.
    """

    visit_id: UUID
    actor_id: UUID
    mode: str  # PresenceMode.value -- serialized as string for JSON round-trip
    occurred_at: datetime


@dataclass(frozen=True)
class VisitCheckedOut:
    """An actor checked out of the Visit.

    Does NOT change Visit.status. Evolver finds the open
    `PresenceEntry` for this `actor_id` and REPLACES it with a new entry
    carrying `check_out_at` populated (frozen-replace pattern). The two
    entries are distinct frozenset members because PresenceEntry's hash
    covers all four fields.
    """

    visit_id: UUID
    actor_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class VisitSurfaceControlTaken:
    """The Visit took operational control of the Surface.

    SINGLE-stream Visit write -- Surface aggregate state is NOT mutated
    (Surface remains infrastructure-stable per the design research). The
    `proj_surface_active_visit` projection materializes "who drives
    now": this event triggers a 2-statement transaction that marks the
    prior holder's row released_at + INSERTs a new holder row.

    Does NOT change Visit.status -- control is orthogonal to lifecycle
    (a Visit may hold/release the Surface multiple times within one
    InProgress). Parent-stays-in-progress lock: a child Visit
    (commissioning) taking control of the Surface from its part_of
    parent leaves the parent's status untouched.
    """

    visit_id: UUID
    surface_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class VisitSurfaceControlReleased:
    """The Visit released operational control of the Surface.

    Projection marks the row's released_at = occurred_at. No auto-flip
    to the parent Visit (if any) -- the parent must explicitly call
    take_control_of_surface again to reclaim, per V6 explicit-gesture
    lock.
    """

    visit_id: UUID
    surface_id: UUID
    occurred_at: datetime


# Discriminated union of every event the Visit aggregate emits today.
VisitEvent = (
    VisitRegistered
    | VisitArrived
    | VisitStarted
    | VisitHeld
    | VisitResumed
    | VisitCompleted
    | VisitCancelled
    | VisitAborted
    | VisitVoided
    | VisitCheckedIn
    | VisitCheckedOut
    | VisitSurfaceControlTaken
    | VisitSurfaceControlReleased
)


def event_type_name(event: VisitEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def _external_refs_to_payload(refs: frozenset[Identifier]) -> list[dict[str, str]]:
    """Sort + serialize Identifiers for deterministic payload bytes."""
    return sorted(
        ({"scheme": r.scheme, "value": r.value} for r in refs),
        key=lambda d: (d["scheme"], d["value"]),
    )


def _external_refs_from_payload(payload: list[dict[str, str]]) -> frozenset[Identifier]:
    """Rebuild Identifier set from a payload's serialized list."""
    return frozenset(Identifier(scheme=item["scheme"], value=item["value"]) for item in payload)


def to_payload(event: VisitEvent) -> dict[str, Any]:
    """Serialize a Visit event to a JSON-friendly dict for jsonb storage."""
    match event:
        case VisitRegistered(
            visit_id=visit_id,
            policy_id=policy_id,
            surface_id=surface_id,
            type=type_,
            planned_start_at=planned_start_at,
            planned_end_at=planned_end_at,
            occurred_at=occurred_at,
            parent_id=parent_id,
            external_refs=external_refs,
        ):
            return {
                "visit_id": str(visit_id),
                "policy_id": str(policy_id),
                "surface_id": str(surface_id),
                "type": type_,
                "planned_start_at": planned_start_at.isoformat(),
                "planned_end_at": planned_end_at.isoformat(),
                "occurred_at": occurred_at.isoformat(),
                "parent_id": (str(parent_id) if parent_id is not None else None),
                "external_refs": _external_refs_to_payload(external_refs),
            }
        case VisitArrived(visit_id=visit_id, occurred_at=occurred_at):
            return {
                "visit_id": str(visit_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case VisitStarted(visit_id=visit_id, occurred_at=occurred_at):
            return {
                "visit_id": str(visit_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case VisitHeld(visit_id=visit_id, reason=reason, occurred_at=occurred_at):
            return {
                "visit_id": str(visit_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case VisitResumed(visit_id=visit_id, occurred_at=occurred_at):
            return {
                "visit_id": str(visit_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case VisitCompleted(visit_id=visit_id, occurred_at=occurred_at):
            return {
                "visit_id": str(visit_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case VisitCancelled(visit_id=visit_id, reason=reason, occurred_at=occurred_at):
            return {
                "visit_id": str(visit_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case VisitAborted(visit_id=visit_id, reason=reason, occurred_at=occurred_at):
            return {
                "visit_id": str(visit_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case VisitVoided(visit_id=visit_id, reason=reason, occurred_at=occurred_at):
            return {
                "visit_id": str(visit_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case VisitCheckedIn(
            visit_id=visit_id, actor_id=actor_id, mode=mode, occurred_at=occurred_at
        ):
            return {
                "visit_id": str(visit_id),
                "actor_id": str(actor_id),
                "mode": mode,
                "occurred_at": occurred_at.isoformat(),
            }
        case VisitCheckedOut(visit_id=visit_id, actor_id=actor_id, occurred_at=occurred_at):
            return {
                "visit_id": str(visit_id),
                "actor_id": str(actor_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case VisitSurfaceControlTaken(
            visit_id=visit_id, surface_id=surface_id, occurred_at=occurred_at
        ):
            return {
                "visit_id": str(visit_id),
                "surface_id": str(surface_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case VisitSurfaceControlReleased(
            visit_id=visit_id, surface_id=surface_id, occurred_at=occurred_at
        ):
            return {
                "visit_id": str(visit_id),
                "surface_id": str(surface_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> VisitEvent:
    """Rebuild a Visit event from a StoredEvent loaded from the event store."""
    payload = stored.payload
    match stored.event_type:
        case "VisitRegistered":

            def _build_visit_registered() -> VisitRegistered:
                parent_raw = payload.get("parent_id")
                return VisitRegistered(
                    visit_id=UUID(payload["visit_id"]),
                    policy_id=UUID(payload["policy_id"]),
                    surface_id=UUID(payload["surface_id"]),
                    type=payload["type"],
                    planned_start_at=datetime.fromisoformat(payload["planned_start_at"]),
                    planned_end_at=datetime.fromisoformat(payload["planned_end_at"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    parent_id=UUID(parent_raw) if parent_raw is not None else None,
                    external_refs=_external_refs_from_payload(payload.get("external_refs", [])),
                )

            return deserialize_or_raise("VisitRegistered", _build_visit_registered)
        case "VisitArrived":
            return deserialize_or_raise(
                "VisitArrived",
                lambda: VisitArrived(
                    visit_id=UUID(payload["visit_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "VisitStarted":
            return deserialize_or_raise(
                "VisitStarted",
                lambda: VisitStarted(
                    visit_id=UUID(payload["visit_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "VisitHeld":
            return deserialize_or_raise(
                "VisitHeld",
                lambda: VisitHeld(
                    visit_id=UUID(payload["visit_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "VisitResumed":
            return deserialize_or_raise(
                "VisitResumed",
                lambda: VisitResumed(
                    visit_id=UUID(payload["visit_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "VisitCompleted":
            return deserialize_or_raise(
                "VisitCompleted",
                lambda: VisitCompleted(
                    visit_id=UUID(payload["visit_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "VisitCancelled":
            return deserialize_or_raise(
                "VisitCancelled",
                lambda: VisitCancelled(
                    visit_id=UUID(payload["visit_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "VisitAborted":
            return deserialize_or_raise(
                "VisitAborted",
                lambda: VisitAborted(
                    visit_id=UUID(payload["visit_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "VisitVoided":
            return deserialize_or_raise(
                "VisitVoided",
                lambda: VisitVoided(
                    visit_id=UUID(payload["visit_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "VisitCheckedIn":
            return deserialize_or_raise(
                "VisitCheckedIn",
                lambda: VisitCheckedIn(
                    visit_id=UUID(payload["visit_id"]),
                    actor_id=UUID(payload["actor_id"]),
                    mode=payload["mode"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "VisitCheckedOut":
            return deserialize_or_raise(
                "VisitCheckedOut",
                lambda: VisitCheckedOut(
                    visit_id=UUID(payload["visit_id"]),
                    actor_id=UUID(payload["actor_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "VisitSurfaceControlTaken":
            return deserialize_or_raise(
                "VisitSurfaceControlTaken",
                lambda: VisitSurfaceControlTaken(
                    visit_id=UUID(payload["visit_id"]),
                    surface_id=UUID(payload["surface_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "VisitSurfaceControlReleased":
            return deserialize_or_raise(
                "VisitSurfaceControlReleased",
                lambda: VisitSurfaceControlReleased(
                    visit_id=UUID(payload["visit_id"]),
                    surface_id=UUID(payload["surface_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case _:
            msg = f"Unknown VisitEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "VisitAborted",
    "VisitArrived",
    "VisitCancelled",
    "VisitCheckedIn",
    "VisitCheckedOut",
    "VisitCompleted",
    "VisitEvent",
    "VisitHeld",
    "VisitRegistered",
    "VisitResumed",
    "VisitStarted",
    "VisitSurfaceControlReleased",
    "VisitSurfaceControlTaken",
    "VisitVoided",
    "event_type_name",
    "from_stored",
    "to_payload",
]
