"""Domain events emitted by the Policy aggregate, plus the discriminated union.

Mirrors `cora/trust/aggregates/conduit/events.py` in shape: event
classes, discriminated union, `event_type_name`, `to_payload`,
`from_stored`. The persistence-envelope construction (`NewEvent`)
lives at `cora.infrastructure.event_envelope.to_new_event`.

`PolicyDefined.permitted_principal_ids` / `.permitted_commands` are
stored as `list[UUID]` / `list[str]` here (events carry primitives
per CONTRIBUTING.md; lists JSON-serialize cleanly). The evolver
converts them to `frozenset` when folding into Policy state, where
set-membership semantics matter for `evaluate`. `to_payload` sorts
both lists by string form so the same logical permission set
serializes deterministically across runs (important for hash-based
idempotency and any future content-addressed lookup).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.routing import NIL_SENTINEL_ID


@dataclass(frozen=True)
class PolicyDefined:
    """A new authorization Policy was defined for a Conduit + Surface pair.

    `surface_id`: additive. The legacy V1 bootstrap PolicyDefined event
    on disk lacks this field; `from_stored` defaults the missing value to
    `UUID(int=0)` so that immutable seed still folds cleanly. New events
    always carry a real Surface (`define_policy` rejects the nil
    sentinel), so nil arises only from that one legacy seed.
    """

    policy_id: UUID
    name: str
    conduit_id: UUID
    permitted_principal_ids: tuple[UUID, ...]
    permitted_commands: tuple[str, ...]
    occurred_at: datetime
    surface_id: UUID = NIL_SENTINEL_ID


# Discriminated union of every event the Policy aggregate emits.
PolicyEvent = PolicyDefined


def event_type_name(event: PolicyEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: PolicyEvent) -> dict[str, Any]:
    """Serialize a Policy event to a JSON-friendly dict for jsonb storage.

    Permission lists are sorted (UUIDs by string form, command names
    alphabetically) so the persisted payload is deterministic — same
    logical permission set, same payload bytes, same idempotency
    hash.
    """
    match event:
        case PolicyDefined(
            policy_id=policy_id,
            name=name,
            conduit_id=conduit_id,
            permitted_principal_ids=permitted_principal_ids,
            permitted_commands=permitted_commands,
            occurred_at=occurred_at,
            surface_id=surface_id,
        ):
            return {
                "policy_id": str(policy_id),
                "name": name,
                "conduit_id": str(conduit_id),
                "surface_id": str(surface_id),
                "permitted_principal_ids": sorted(str(p) for p in permitted_principal_ids),
                "permitted_commands": sorted(permitted_commands),
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> PolicyEvent:
    """Rebuild a Policy event from a StoredEvent loaded from the event store."""
    payload = stored.payload
    match stored.event_type:
        case "PolicyDefined":
            return deserialize_or_raise(
                "PolicyDefined",
                lambda: PolicyDefined(
                    policy_id=UUID(payload["policy_id"]),
                    name=payload["name"],
                    conduit_id=UUID(payload["conduit_id"]),
                    permitted_principal_ids=tuple(
                        UUID(p) for p in payload["permitted_principal_ids"]
                    ),
                    permitted_commands=tuple(payload["permitted_commands"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    surface_id=UUID(payload.get("surface_id", str(NIL_SENTINEL_ID))),
                ),
            )
        case _:
            msg = f"Unknown PolicyEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "PolicyDefined",
    "PolicyEvent",
    "event_type_name",
    "from_stored",
    "to_payload",
]
