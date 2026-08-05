"""Domain events emitted by the Actor aggregate, plus the discriminated union.

Events live in the aggregate folder (not the slice) because they are
intrinsic facts about the aggregate's history -- the slice just decides
when to emit them. The evolver dispatches on the union; new event types
are appended both as a class definition and to the union alias.

Per the locked "primitives in events" convention, payloads serialize
to plain dicts of primitives. `to_payload` and `from_stored` are the
single home for the (de)serialization logic; per-slice handlers no
longer carry their own serializers.

## V1/V2 dispatch for ActorRegistered (PII vault)

`ActorRegistered` events written before the PII vault landed carry a
`name` field in the payload (V1). Post-vault writes emit the event with
the new `event_type` string `"ActorRegisteredV2"` and no `name` field;
display names live in the `actor_profile` table. Both `event_type`
arms produce the same modern `ActorRegistered` dataclass (no `name`).
The Marten / Axon legacy-rename precedent mirrors
`cora/equipment/aggregates/asset/events.py` (Capability→Family
rename). Backfill migration `20260523120100_backfill_actor_profile.sql`
copies V1 names into `actor_profile` before the new code ships, so
read paths find the right display name even for legacy actors.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.access.aggregates.actor.state import ActorKind
from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent


@dataclass(frozen=True)
class ActorRegistered:
    """A new actor was registered.

    Carries NO PII -- display name and future PII fields live in the
    `actor_profile` table per the PII vault pattern. The cross-BC
    invariant `Agent.id == Actor.id` still holds: `register_actor` and
    `define_agent` both emit this event with the same `actor_id` they
    use to upsert the profile row.

    `kind` discriminates `human` from `agent` from `service_account`.
    REQUIRED at construction: both callsites
    (`register_actor` in Access BC, `define_agent` in Agent BC)
    MUST pass it explicitly so drift between them surfaces as a pyright
    error rather than silently minting an agent-kind Actor through the
    human path. See [[project_agent_bc_design]] P0-4 cleanup pass.

    New writes emit `event_type = "ActorRegisteredV2"`; legacy V1
    writes (carrying `name` in the payload) keep their `event_type =
    "ActorRegistered"` string and replay via the legacy arm in
    `from_stored`, which drops the `name` on rebuild (the backfill
    migration copied legacy names into actor_profile already).
    """

    actor_id: UUID
    occurred_at: datetime
    kind: ActorKind


@dataclass(frozen=True)
class ActorDeactivated:
    """An existing actor was deactivated. The actor remains in the
    system but `Actor.active` flips to False."""

    actor_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class ActorReactivated:
    """A deactivated actor was returned to service: `Actor.active`
    flips back to True.

    The inverse of `ActorDeactivated`, and deliberately so. An Agent
    carries a reversible operator pause (`suspend_agent` /
    `resume_agent`); before this event an Actor's pause was one-way,
    so a mis-issued deactivation had no remedy inside the system. The
    two principal kinds now hold the same availability switch.

    Reactivation restores availability only. It confers no authority
    the actor did not already hold: Policy membership, grants, and
    every other narrowing are untouched, and an actor reactivated
    into a Policy that no longer names them stays unable to act.
    """

    actor_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class ActorProfileForgotten:
    """Audit event for PII erasure (GDPR / PIPL / LGPD / CCPA "right to
    be forgotten").

    Carries NO PII — only `actor_id` + the timestamp when the
    erasure landed. Emitted by the `forget_actor` slice in the same
    Postgres transaction that scrubs + deletes the corresponding
    `actor_profile` row, so the event log carries a permanent audit
    trail of "this actor's PII was erased on this date" without
    re-introducing any identifying data. Aggregate state is
    unchanged by this event; the event exists purely for downstream
    subscribers (the projection swaps the cached `name` for the
    tombstone literal).
    """

    actor_id: UUID
    occurred_at: datetime


# Discriminated union of every event the Actor aggregate emits. Add new
# event classes above and extend this alias when new slices land.
ActorEvent = ActorRegistered | ActorDeactivated | ActorReactivated | ActorProfileForgotten


def event_type_name(event: ActorEvent) -> str:
    """Discriminator string written into StoredEvent.event_type.

    `ActorRegistered` writes use the V2 string; the V1 string lives
    only in `from_stored` for legacy replay. `ActorDeactivated` has
    one shape forever.
    """
    if isinstance(event, ActorRegistered):
        return "ActorRegisteredV2"
    return type(event).__name__


def to_payload(event: ActorEvent) -> dict[str, Any]:
    """Serialize an Actor event to a JSON-friendly dict for jsonb storage.

    Primitives only: UUIDs become strings, datetimes become ISO-8601 strings.
    No PII -- display name lives in actor_profile table.
    """
    match event:
        case ActorRegistered(actor_id=actor_id, occurred_at=occurred_at, kind=kind):
            return {
                "actor_id": str(actor_id),
                "occurred_at": occurred_at.isoformat(),
                "kind": kind.value,
            }
        case ActorDeactivated(actor_id=actor_id, occurred_at=occurred_at):
            return {
                "actor_id": str(actor_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case ActorReactivated(actor_id=actor_id, occurred_at=occurred_at):
            return {
                "actor_id": str(actor_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case ActorProfileForgotten(actor_id=actor_id, occurred_at=occurred_at):
            return {
                "actor_id": str(actor_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> ActorEvent:
    """Rebuild an Actor event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.

    `ActorRegistered` has two `event_type` strings (Marten / Axon
    legacy-rename pattern; mirrors
    `cora/equipment/aggregates/asset/events.py` Capability→Family):

      - `"ActorRegisteredV2"`: post-PII-vault writes; payload has no
        `name` field.
      - `"ActorRegistered"` (legacy V1): pre-vault writes carry a
        `name` field in the payload. The arm drops the name on rebuild
        (the backfill migration copied legacy names into actor_profile
        before the new code went live).

    Both arms produce the same modern `ActorRegistered` dataclass.
    """
    payload = stored.payload
    match stored.event_type:
        case "ActorRegisteredV2":
            return deserialize_or_raise(
                "ActorRegisteredV2",
                lambda: ActorRegistered(
                    actor_id=UUID(payload["actor_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    kind=ActorKind(payload["kind"]),
                ),
                extra=(ValueError,),
            )
        case "ActorRegistered":
            # Legacy V1: payload still carries `name`. Drop it on
            # rebuild; the backfill migration copied the legacy name
            # into actor_profile before this arm started replaying.
            # `kind` may also be absent on the oldest legacy payloads;
            # fall back to HUMAN.
            return deserialize_or_raise(
                "ActorRegistered",
                lambda: ActorRegistered(
                    actor_id=UUID(payload["actor_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    kind=ActorKind(payload.get("kind", ActorKind.HUMAN.value)),
                ),
                extra=(ValueError,),
                message_suffix=" (V1)",
            )
        case "ActorDeactivated":
            return deserialize_or_raise(
                "ActorDeactivated",
                lambda: ActorDeactivated(
                    actor_id=UUID(payload["actor_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
                extra=(ValueError,),
            )
        case "ActorReactivated":
            return deserialize_or_raise(
                "ActorReactivated",
                lambda: ActorReactivated(
                    actor_id=UUID(payload["actor_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
                extra=(ValueError,),
            )
        case "ActorProfileForgotten":
            return deserialize_or_raise(
                "ActorProfileForgotten",
                lambda: ActorProfileForgotten(
                    actor_id=UUID(payload["actor_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
                extra=(ValueError,),
            )
        case _:
            msg = f"Unknown ActorEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "ActorDeactivated",
    "ActorEvent",
    "ActorProfileForgotten",
    "ActorReactivated",
    "ActorRegistered",
    "event_type_name",
    "from_stored",
    "to_payload",
]
