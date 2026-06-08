"""Domain events emitted by the Campaign aggregate, plus the discriminated union.

Mirrors the locked event-module shape: event classes, discriminated
union, `event_type_name`, `to_payload`, `from_stored`, plus the
`serialize_external_ref` / `deserialize_external_ref` helpers
(round-trip a typed `Identifier` VO through the wire payload).

Six events shipped at BC genesis:

  - `CampaignRegistered` -- genesis (Planned)
  - `CampaignStarted`    -- transition (Planned -> Active)
  - `CampaignHeld`       -- transition (Active -> Held); reason str
  - `CampaignResumed`    -- transition (Held -> Active)
  - `CampaignClosed`     -- transition (Active | Held -> Closed)
  - `CampaignAbandoned`  -- transition (Planned | Active | Held ->
                            Abandoned); reason str

Two events added later for cross-aggregate membership:

  - `CampaignRunAdded`   -- run_id unioned into state.run_ids; written
                            atomically with `RunAddedToCampaign` (or
                            `RunStarted` on the at-start path) via
                            `EventStore.append_streams`
  - `CampaignRunRemoved` -- run_id removed from state.run_ids; written
                            atomically with `RunRemovedFromCampaign`;
                            `reason: str` REQUIRED on the payload as
                            per-membership audit breadcrumb (NOT
                            populated onto `last_status_reason`)

`tags` travels in the genesis payload as a sorted `list[str]` (sorted
for deterministic payload bytes), reconstructed into
`frozenset[CampaignTag]` by the evolver.

`external_refs` travels as a sorted-by-(scheme, value)
`list[{scheme, value}]` for the same deterministic-bytes reason.
The wire-payload key is `value` (not `id`) per the pre-pilot
`id -> value` rename in `[[project_identifier_vo_design]]`.

`subject_id`, `description`, `external_id` are nullable; encoded as
None when absent. `from_stored` uses `.get(...)` for nullable keys
so future migrations that add additional nullable fields stay
forward-compat at replay time.

`lead_actor_id` lives on the genesis payload (operator-asserted
campaign lead; NOT the registering actor). The registering actor's
id lives on the envelope's `principal_id`. Reason fields on Held /
Abandoned events carry the operator's audit breadcrumb on the payload;
the transitioning actor's id lives ONLY on the envelope per 11a-c-1
cross-BC precedent.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.event_payload import deserialize_or_raise, deserialize_vo_or_raise
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identifier import Identifier

# ---------------------------------------------------------------------------
# Identifier serialize / deserialize (public cross-slice helpers)
# ---------------------------------------------------------------------------


def serialize_external_ref(ref: Identifier) -> dict[str, str]:
    """Encode an Identifier (external-ref carrier) to a JSON-friendly dict."""
    return {"scheme": ref.scheme, "value": ref.value}


def deserialize_external_ref(payload: dict[str, Any]) -> Identifier:
    """Decode a JSON-friendly dict to an Identifier.

    Wraps KeyError / TypeError as ValueError so callers don't see
    leaked low-level exceptions when an event payload is malformed.
    """
    return deserialize_vo_or_raise(
        "Identifier",
        lambda: Identifier(scheme=payload["scheme"], value=payload["value"]),
    )


def _serialize_external_refs(refs: frozenset[Identifier]) -> list[dict[str, str]]:
    """Sort + encode a frozenset of Identifier for deterministic bytes."""
    return [serialize_external_ref(r) for r in sorted(refs, key=lambda r: (r.scheme, r.value))]


# ---------------------------------------------------------------------------
# Event classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CampaignRegistered:
    """A new Campaign was registered.

    Initial status implicitly `Planned` (event type IS the state-change
    indicator; the genesis evolver hardcodes the mapping). `tags` is
    `frozenset[str]` here (already-validated tag strings; payload-
    friendly). The evolver reconstructs `frozenset[CampaignTag]` via
    the VO constructor (which re-trims and re-length-checks, but
    that's harmless on already-validated input).

    `lead_actor_id` is the campaign PI / lead operator (operator-
    asserted, may differ from envelope `principal_id`). `subject_id`
    / `description` / `external_id` are optional. `external_refs` is
    `frozenset[Identifier]`.
    """

    campaign_id: UUID
    name: str
    intent: str
    lead_actor_id: UUID
    subject_id: UUID | None
    description: str | None
    tags: frozenset[str]
    external_refs: frozenset[Identifier]
    external_id: str | None
    occurred_at: datetime


@dataclass(frozen=True)
class CampaignStarted:
    """A Planned Campaign was started (Planned -> Active).

    Slim payload; no reason field. The starting actor's id lives ONLY
    on the envelope per 11a-c-1 cross-BC precedent.
    """

    campaign_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class CampaignHeld:
    """An Active Campaign was held (Active -> Held).

    `reason: str` (1-500 chars) carries the operator's audit
    breadcrumb. The transitioning actor's id lives ONLY on the
    envelope.
    """

    campaign_id: UUID
    reason: str
    occurred_at: datetime


@dataclass(frozen=True)
class CampaignResumed:
    """A Held Campaign was resumed (Held -> Active).

    Slim payload. `last_status_reason` (set when the Campaign was
    Held) is intentionally preserved across resume (audit
    breadcrumb: "why was it held before the resume?" stays
    readable). The transitioning actor's id lives ONLY on the
    envelope.
    """

    campaign_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class CampaignClosed:
    """A Campaign was closed (Active | Held -> Closed).

    Normal-terminal; no reason field (mirrors Run `Completed`
    semantic). The transitioning actor's id lives ONLY on the
    envelope.
    """

    campaign_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class CampaignAbandoned:
    """A Campaign was abandoned (Planned | Active | Held -> Abandoned).

    Early-terminal with reason (REQUIRED, mirrors `RunAbortReason`).
    The transitioning actor's id lives ONLY on the envelope.
    """

    campaign_id: UUID
    reason: str
    occurred_at: datetime


@dataclass(frozen=True)
class CampaignRunAdded:
    """A Run was added to this Campaign.

    Written to the Campaign's stream by the cross-aggregate
    `add_run_to_campaign` slice, atomically alongside
    `RunAddedToCampaign` on the Run's stream (via
    `EventStore.append_streams`). Also written by `start_run` when
    `StartRun.campaign_id` is provided (atomic with `RunStarted` on
    the Run stream).

    The transitioning actor's id lives ONLY on the envelope per the
    11a-c-1 cross-BC precedent. Membership idempotency is enforced at
    the decider; the evolver simply unions the run_id into
    `state.run_ids`.
    """

    campaign_id: UUID
    run_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class CampaignRunRemoved:
    """A Run was removed from this Campaign.

    Written to the Campaign's stream by the cross-aggregate
    `remove_run_from_campaign` slice, atomically alongside
    `RunRemovedFromCampaign` on the Run's stream.

    `reason: str` (1-500 chars after trim) is REQUIRED per design memo:
    an operator must say WHY they remove a Run from a Campaign
    (ungrouping is meaningful). The reason is a per-membership audit
    breadcrumb, NOT an aggregate-state mutation: the design memo
    explicitly notes `last_status_reason` is for status-transitions
    only and is NOT updated by remove. The evolver removes the run_id
    from `state.run_ids` and leaves `last_status_reason` alone.
    """

    campaign_id: UUID
    run_id: UUID
    reason: str
    occurred_at: datetime


# Discriminated union of every event the Campaign aggregate emits.
CampaignEvent = (
    CampaignRegistered
    | CampaignStarted
    | CampaignHeld
    | CampaignResumed
    | CampaignClosed
    | CampaignAbandoned
    | CampaignRunAdded
    | CampaignRunRemoved
)


def event_type_name(event: CampaignEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: CampaignEvent) -> dict[str, Any]:
    """Serialise a Campaign event to a JSON-friendly dict for jsonb storage.

    Primitives only: UUIDs become strings, datetimes become ISO-8601
    strings, `tags` becomes a sorted list, `external_refs` becomes a
    sorted list of `{scheme, value}` dicts (deterministic bytes for
    byte-for-byte idempotency replay).
    """
    match event:
        case CampaignRegistered(
            campaign_id=campaign_id,
            name=name,
            intent=intent,
            lead_actor_id=lead_actor_id,
            subject_id=subject_id,
            description=description,
            tags=tags,
            external_refs=external_refs,
            external_id=external_id,
            occurred_at=occurred_at,
        ):
            return {
                "campaign_id": str(campaign_id),
                "name": name,
                "intent": intent,
                "lead_actor_id": str(lead_actor_id),
                "subject_id": str(subject_id) if subject_id is not None else None,
                "description": description,
                "tags": sorted(tags),
                "external_refs": _serialize_external_refs(external_refs),
                "external_id": external_id,
                "occurred_at": occurred_at.isoformat(),
            }
        case CampaignStarted(campaign_id=campaign_id, occurred_at=occurred_at):
            return {
                "campaign_id": str(campaign_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case CampaignHeld(
            campaign_id=campaign_id,
            reason=reason,
            occurred_at=occurred_at,
        ):
            return {
                "campaign_id": str(campaign_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case CampaignResumed(campaign_id=campaign_id, occurred_at=occurred_at):
            return {
                "campaign_id": str(campaign_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case CampaignClosed(campaign_id=campaign_id, occurred_at=occurred_at):
            return {
                "campaign_id": str(campaign_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case CampaignAbandoned(
            campaign_id=campaign_id,
            reason=reason,
            occurred_at=occurred_at,
        ):
            return {
                "campaign_id": str(campaign_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case CampaignRunAdded(
            campaign_id=campaign_id,
            run_id=run_id,
            occurred_at=occurred_at,
        ):
            return {
                "campaign_id": str(campaign_id),
                "run_id": str(run_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case CampaignRunRemoved(
            campaign_id=campaign_id,
            run_id=run_id,
            reason=reason,
            occurred_at=occurred_at,
        ):
            return {
                "campaign_id": str(campaign_id),
                "run_id": str(run_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> CampaignEvent:
    """Rebuild a Campaign event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than being silently dropped by the evolver.

    Each arm delegates to `deserialize_or_raise` which re-raises
    malformed payloads as ValueError carrying the canonical
    `"Malformed {event_type} payload"` text. Nullable fields use
    `payload.get(...)` so future migrations that add new nullable
    fields stay forward-compat at replay time.
    """
    payload = stored.payload
    match stored.event_type:
        case "CampaignRegistered":

            def _build_campaign_registered() -> CampaignRegistered:
                subject_id_raw = payload.get("subject_id")
                external_id_raw = payload.get("external_id")
                external_refs_raw = payload.get("external_refs", [])
                return CampaignRegistered(
                    campaign_id=UUID(payload["campaign_id"]),
                    name=payload["name"],
                    intent=payload["intent"],
                    lead_actor_id=UUID(payload["lead_actor_id"]),
                    subject_id=UUID(subject_id_raw) if subject_id_raw is not None else None,
                    description=payload.get("description"),
                    tags=frozenset(payload.get("tags", [])),
                    external_refs=frozenset(deserialize_external_ref(r) for r in external_refs_raw),
                    external_id=external_id_raw,
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )

            return deserialize_or_raise("CampaignRegistered", _build_campaign_registered)
        case "CampaignStarted":
            return deserialize_or_raise(
                "CampaignStarted",
                lambda: CampaignStarted(
                    campaign_id=UUID(payload["campaign_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "CampaignHeld":
            return deserialize_or_raise(
                "CampaignHeld",
                lambda: CampaignHeld(
                    campaign_id=UUID(payload["campaign_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "CampaignResumed":
            return deserialize_or_raise(
                "CampaignResumed",
                lambda: CampaignResumed(
                    campaign_id=UUID(payload["campaign_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "CampaignClosed":
            return deserialize_or_raise(
                "CampaignClosed",
                lambda: CampaignClosed(
                    campaign_id=UUID(payload["campaign_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "CampaignAbandoned":
            return deserialize_or_raise(
                "CampaignAbandoned",
                lambda: CampaignAbandoned(
                    campaign_id=UUID(payload["campaign_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "CampaignRunAdded":
            return deserialize_or_raise(
                "CampaignRunAdded",
                lambda: CampaignRunAdded(
                    campaign_id=UUID(payload["campaign_id"]),
                    run_id=UUID(payload["run_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "CampaignRunRemoved":
            return deserialize_or_raise(
                "CampaignRunRemoved",
                lambda: CampaignRunRemoved(
                    campaign_id=UUID(payload["campaign_id"]),
                    run_id=UUID(payload["run_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case _:
            msg = f"Unknown CampaignEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "CampaignAbandoned",
    "CampaignClosed",
    "CampaignEvent",
    "CampaignHeld",
    "CampaignRegistered",
    "CampaignResumed",
    "CampaignRunAdded",
    "CampaignRunRemoved",
    "CampaignStarted",
    "deserialize_external_ref",
    "event_type_name",
    "from_stored",
    "serialize_external_ref",
    "to_payload",
]
