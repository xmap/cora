"""Domain events emitted by the Distribution aggregate plus the discriminated union.

Mirrors the locked event-module shape: event classes, discriminated union,
``event_type_name``, ``to_payload``, ``from_stored``. The persistence-envelope
construction (``NewEvent``) lives at ``cora.infrastructure.event_envelope.to_new_event``.

## This module ships two events today

  - ``DistributionRegistered`` (genesis): identity + same-BC ref + cross-BC ref +
    integrity + size + encoding + transport + attribution. The status is implicit
    (``Registered``); the evolver sets it.
  - ``DistributionDiscarded`` (transition, terminal): the metadata-only
    reclaim-decision record. Bytes are reclaimed out-of-band (same shape as
    ``DatasetDiscarded``); this event keeps the reclaim reason + attribution
    for audit. The status is implicit (``Discarded``); the evolver sets it.

## Future events NAMED but not locked here

Per [[project-data-distribution-design]] L18:

  - ``DistributionVerified`` (Registered/Verified -> Verified)
  - ``DistributionMarkedStale`` ({Registered, Verified} -> Stale, per L23/L4 +
    operationally relaxed source-state set after gate review)

These will land additively in follow-on slices. The discriminated union and
``from_stored`` switch land their cases at that time. The Verified/Stale flip
stays projection-only today (per state.py "Verified/Stale flip is a projection")
and is NOT retro-converted to stream events by this slice.

## Payload conventions

- UUIDs serialize as strings; set-semantic fields (none today on Distribution)
  would sort deterministically per the existing convention.
- ``checksum`` serializes as a nested object: ``{"algorithm": str, "value": str}``
  matching ``DatasetRegistered.checksum``.
- ``encoding`` serializes as a nested object:
  ``{"media_type": str, "conforms_to": list[str]}`` with ``conforms_to`` sorted.
- ``access_protocol`` serializes as the ``AccessProtocol.value`` bare string per
  [[project-facility-aggregate-design]] cryptographic-chain immutability
  discipline (no typed-VO wrapping on disk).
- Status is NOT carried in the payload; the event type encodes it
  (``DistributionRegistered -> REGISTERED``), same precedent as Dataset.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identity import ActorId


@dataclass(frozen=True)
class DistributionRegistered:
    """A new Distribution was registered as a materialized byte-copy of a Dataset.

    Status is implicit (``Registered``); the evolver sets it. The
    cross-aggregate references (``dataset_id``, ``supply_id``) are
    eventual-consistency primitives; the handler pre-loads each on the
    write path, the evolver does NOT re-verify on fold.

    Per CONTRIBUTING.md "Primitives in event payloads": every field here
    is a primitive (str, int, UUID, datetime). VOs (``DistributionUri``,
    ``DatasetChecksum``, ``DatasetEncoding``, ``AccessProtocol``) are
    reconstructed by the evolver on fold; the decider unwraps VOs before
    constructing the event.

    Fold-symmetry attribution per [[project-fold-symmetry-design]]:
    ``registered_by: ActorId`` carries the envelope ``principal_id`` of
    the register-slice caller. Carried on the event payload so a future
    slice that opts into folding attribution onto Distribution state
    already has the data.
    """

    distribution_id: UUID
    dataset_id: UUID
    supply_id: UUID
    uri: str
    checksum_algorithm: str
    checksum_value: str
    byte_size: int
    media_type: str
    conforms_to: frozenset[str]
    access_protocol: str
    occurred_at: datetime
    registered_by: ActorId


@dataclass(frozen=True)
class DistributionDiscarded:
    """A Distribution copy was discarded (any prior status -> Discarded terminal).

    Metadata-only, same posture as ``DatasetDiscarded``: the bytes for
    this storage-tier copy are reclaimed out-of-band (an operator
    workflow against S3 / Globus / POSIX); this event records the
    reclaim decision + reason for audit. ``reason`` is a free-form
    string (1-500 chars after trimming), captured verbatim.

    The guard is enforced upstream in the decider: a copy may be
    discarded only when a sibling copy of the same Dataset is Verified
    on a different storage tier, and the parent Dataset is not itself
    Discarded. The event itself carries no sibling reference; the
    redundancy invariant lives at decide-time.

    Fold-symmetry attribution per [[project-fold-symmetry-design]]:
    ``discarded_by: ActorId`` carries the envelope ``principal_id`` of
    the discard-slice caller.
    """

    distribution_id: UUID
    reason: str
    occurred_at: datetime
    discarded_by: ActorId


#: Discriminated union over Distribution events. ``DistributionRegistered``
#: is the genesis arm; ``DistributionDiscarded`` is the terminal transition.
#: Future slices extend additively (Verified / MarkedStale).
DistributionEvent = DistributionRegistered | DistributionDiscarded


def event_type_name(event: DistributionEvent) -> str:
    """Discriminator string written into ``StoredEvent.event_type``."""
    return type(event).__name__


def to_payload(event: DistributionEvent) -> dict[str, Any]:
    """Serialize a Distribution event to a JSON-friendly dict for jsonb storage.

    Set-semantic fields (``encoding.conforms_to``) sort deterministically
    so two registrations of the same logical Distribution produce
    byte-identical jsonb.
    """
    match event:
        case DistributionRegistered(
            distribution_id=distribution_id,
            dataset_id=dataset_id,
            supply_id=supply_id,
            uri=uri,
            checksum_algorithm=checksum_algorithm,
            checksum_value=checksum_value,
            byte_size=byte_size,
            media_type=media_type,
            conforms_to=conforms_to,
            access_protocol=access_protocol,
            occurred_at=occurred_at,
            registered_by=registered_by,
        ):
            return {
                "distribution_id": str(distribution_id),
                "dataset_id": str(dataset_id),
                "supply_id": str(supply_id),
                "uri": uri,
                "checksum": {
                    "algorithm": checksum_algorithm,
                    "value": checksum_value,
                },
                "byte_size": byte_size,
                "encoding": {
                    "media_type": media_type,
                    "conforms_to": sorted(conforms_to),
                },
                "access_protocol": access_protocol,
                "occurred_at": occurred_at.isoformat(),
                "registered_by": str(registered_by),
            }
        case DistributionDiscarded(
            distribution_id=distribution_id,
            reason=reason,
            occurred_at=occurred_at,
            discarded_by=discarded_by,
        ):
            return {
                "distribution_id": str(distribution_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
                "discarded_by": str(discarded_by),
            }
        case _:  # pragma: no cover  # exhaustiveness guard for future arms
            assert_never(event)


def from_stored(stored: StoredEvent) -> DistributionEvent:
    """Rebuild a Distribution event from a ``StoredEvent`` loaded from the event store.

    Dispatches on ``stored.event_type``; raises ``ValueError`` on unknown
    discriminators so a stream contaminated with foreign event types fails
    loud rather than silently being dropped by the evolver. Each per-event
    builder is wrapped in ``deserialize_or_raise`` to surface malformed
    payloads as ``MalformedDistributionRegistered`` /
    ``MalformedDistributionDiscarded`` per
    [[project-from-stored-wrap-convention]].
    """
    payload = stored.payload
    match stored.event_type:
        case "DistributionRegistered":

            def _build_registered() -> DistributionRegistered:
                raw_checksum = payload["checksum"]
                raw_encoding = payload["encoding"]
                return DistributionRegistered(
                    distribution_id=UUID(payload["distribution_id"]),
                    dataset_id=UUID(payload["dataset_id"]),
                    supply_id=UUID(payload["supply_id"]),
                    uri=payload["uri"],
                    checksum_algorithm=raw_checksum["algorithm"],
                    checksum_value=raw_checksum["value"],
                    byte_size=int(payload["byte_size"]),
                    media_type=raw_encoding["media_type"],
                    conforms_to=frozenset(raw_encoding["conforms_to"]),
                    access_protocol=payload["access_protocol"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    registered_by=ActorId(UUID(payload["registered_by"])),
                )

            return deserialize_or_raise("DistributionRegistered", _build_registered)
        case "DistributionDiscarded":
            return deserialize_or_raise(
                "DistributionDiscarded",
                lambda: DistributionDiscarded(
                    distribution_id=UUID(payload["distribution_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    discarded_by=ActorId(UUID(payload["discarded_by"])),
                ),
            )
        case _:
            msg = f"Unknown DistributionEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "DistributionDiscarded",
    "DistributionEvent",
    "DistributionRegistered",
    "event_type_name",
    "from_stored",
    "to_payload",
]
