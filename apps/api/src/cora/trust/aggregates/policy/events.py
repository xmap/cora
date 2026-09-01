"""Domain events emitted by the Policy aggregate, plus the discriminated union.

Mirrors `cora/trust/aggregates/conduit/events.py` in shape: event
classes, discriminated union, `event_type_name`, `to_payload`,
`from_stored`. The persistence-envelope construction (`NewEvent`)
lives at `cora.infrastructure.event_envelope.to_new_event`.

`PolicyDefined.grants` is stored as a list of two-element
`[principal_id, command_name]` arrays (events carry primitives per
CONTRIBUTING.md; lists JSON-serialize cleanly). The evolver converts
them to a `frozenset` of tuples when folding into Policy state, where
set-membership semantics matter for `evaluate`. `to_payload` sorts the
pairs so the same logical permission set serializes deterministically
across runs (important for hash-based idempotency and any future
content-addressed lookup).

## Reading a pre-pairs event

Events written before `grants` existed carry `permitted_principal_ids`
and `permitted_commands` as two independent lists, which `evaluate`
then multiplied. `from_stored` reconstructs those as the full
cross-product of pairs, so such an event folds to exactly the
permissions it has always granted: identical `evaluate` results, by
construction, for every policy stream already on disk.

The cross-product lives HERE, at the deserialization boundary, and
nowhere else. That is the same place, and for the same reason, that a
legacy event's missing `surface_id` gets its default: one function owns
the difference between what is on disk and what the domain works with,
so no downstream code has to know two shapes exist. `to_payload` never
writes the legacy pair of lists, so the shape is read-only history.
"""

from collections.abc import Mapping
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

    `grants`: the (principal, command) pairs this policy permits. Events
    written before pairs existed carry two independent lists instead;
    `from_stored` cross-products them, per this module's docstring.

    `surface_id`: additive. The legacy V1 bootstrap PolicyDefined event
    on disk lacks this field; `from_stored` defaults the missing value to
    `UUID(int=0)` so that immutable seed still folds cleanly. New events
    always carry a real Surface (`define_policy` rejects the nil
    sentinel), so nil arises only from that one legacy seed.
    """

    policy_id: UUID
    name: str
    conduit_id: UUID
    grants: tuple[tuple[UUID, str], ...]
    occurred_at: datetime
    surface_id: UUID = NIL_SENTINEL_ID


@dataclass(frozen=True)
class PolicyGrantRevoked:
    """One principal's grant was revoked from a Policy's allow-list.

    Drops every grant naming `principal_id` from `Policy.grants`, so the
    revocation removes that actor's authority entirely rather than one
    command of it. `revoked_by`
    is the invoking principal (the operator or observer that issued the
    revocation), handler-injected from the request envelope, distinct from
    `principal_id` (the grant being removed). `reason` is operator free text
    (audit denorm on the immutable log; also feeds the downstream mid-run
    compensation Decision). This is the kill-switch trigger event: a separate,
    eventually-consistent subscriber reacts to it to hold the revoked
    principal's in-flight runs (kept out of the emitting handler per the
    compensation-slice no-cascade lock).
    """

    policy_id: UUID
    principal_id: UUID
    revoked_by: UUID
    reason: str
    occurred_at: datetime


# Discriminated union of every event the Policy aggregate emits.
PolicyEvent = PolicyDefined | PolicyGrantRevoked


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
            grants=grants,
            occurred_at=occurred_at,
            surface_id=surface_id,
        ):
            return {
                "policy_id": str(policy_id),
                "name": name,
                "conduit_id": str(conduit_id),
                "surface_id": str(surface_id),
                "grants": sorted(
                    [str(principal_id), command_name] for principal_id, command_name in grants
                ),
                "occurred_at": occurred_at.isoformat(),
            }
        case PolicyGrantRevoked(
            policy_id=policy_id,
            principal_id=principal_id,
            revoked_by=revoked_by,
            reason=reason,
            occurred_at=occurred_at,
        ):
            return {
                "policy_id": str(policy_id),
                "principal_id": str(principal_id),
                "revoked_by": str(revoked_by),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def _grants_from_payload(payload: Mapping[str, Any]) -> tuple[tuple[UUID, str], ...]:
    """Read `grants`, or reconstruct it from a pre-pairs payload.

    The ONLY place the legacy two-list shape is understood. A payload
    carrying `grants` is authoritative and its pairs are returned as
    written. A payload without one predates pairs, and its two
    independent lists are cross-producted, which is precisely what the
    old `evaluate` did with them at decision time: every listed
    principal was permitted every listed command. Moving that
    multiplication from the check to the fold changes where it happens,
    never what it yields.

    Both branches deduplicate and sort, so the same logical permission
    set yields the same tuple whichever shape produced it. Dedup matters
    beyond tidiness: a legacy payload may repeat an entry in either list
    (the old state folded both to frozensets, so nothing upstream had a
    reason to prevent it), and the cross-product would then repeat the
    pair once per repetition. Folding to `Policy` collapses that anyway,
    but anything reading the EVENT before it folds -- an audit trail, a
    grant count -- would otherwise double-count.
    """
    stored_grants = payload.get("grants")
    if stored_grants is not None:
        return tuple(
            sorted(
                {(UUID(principal_id), command_name) for principal_id, command_name in stored_grants}
            )
        )
    return tuple(
        sorted(
            {
                (UUID(principal_id), command_name)
                for principal_id in payload["permitted_principal_ids"]
                for command_name in payload["permitted_commands"]
            }
        )
    )


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
                    grants=_grants_from_payload(payload),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    surface_id=UUID(payload.get("surface_id", str(NIL_SENTINEL_ID))),
                ),
            )
        case "PolicyGrantRevoked":
            return deserialize_or_raise(
                "PolicyGrantRevoked",
                lambda: PolicyGrantRevoked(
                    policy_id=UUID(payload["policy_id"]),
                    principal_id=UUID(payload["principal_id"]),
                    revoked_by=UUID(payload["revoked_by"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case _:
            msg = f"Unknown PolicyEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "PolicyDefined",
    "PolicyEvent",
    "PolicyGrantRevoked",
    "event_type_name",
    "from_stored",
    "to_payload",
]
