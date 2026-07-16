"""Domain events emitted by the Allocation aggregate, plus the discriminated union.

Mirrors the locked event-module shape: event classes, discriminated
union, `event_type_name`, `to_payload`, `from_stored`.

Five genesis-and-lifecycle events:

  - `AllocationGranted`        -- genesis (Granted); the award verb of
                                  the paper and of HPC accounting, an
                                  allowlisted deviation from the
                                  Defined/Registered genesis convention
  - `AllocationActivated`      -- transition (Granted -> Active); opens
                                  the spend window
  - `AllocationCeilingAmended` -- non-transition amendment (Granted |
                                  Active); PUT semantics, the supplied
                                  ceiling IS the post-amend ceiling
  - `AllocationSealed`         -- transition (Active -> Sealed);
                                  terminal, carries the final-spend
                                  snapshot
  - `AllocationVoided`         -- transition (Granted | Active ->
                                  Voided); terminal, REQUIRED reason

Events carry primitives (str / float), not the state VOs, matching how
`LanguageModelDefined` carries plain strings: the evolver wraps
primitives back into VOs at fold time, so payload bytes stay decoupled
from VO validation churn.

`granted_by` / `activated_by` / `sealed_by` carry the acting
principal on the PAYLOAD (not only the envelope) because the folded
state records those fact-acts as `<verb>_at` / `<verb>_by` pairs per
[[project_fold_symmetry_design]]; `AllocationCeilingAmended` and
`AllocationVoided` fold no timestamp, so their actor lives only on
the envelope (`StoredEvent.principal_id`).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identity import ActorId

# ---------------------------------------------------------------------------
# Event classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AllocationGranted:
    """A new allocation envelope was granted (genesis -> Granted).

    Initial status implicitly `Granted` (event type IS the state-change
    indicator; the genesis evolver hardcodes the mapping). A Granted
    envelope is dormant: the spend window opens only at activation, so
    granting never affects a running experiment.

    `campaign_id` is a bare cross-BC reference (eventual-consistency
    stance per the Caution / Calibration precedent); when set, the
    CampaignClosed subscriber seals this envelope beside the
    campaign's own books.
    """

    allocation_id: UUID
    ceiling_usd: float
    campaign_id: UUID | None
    note: str
    granted_by: ActorId
    occurred_at: datetime


@dataclass(frozen=True)
class AllocationActivated:
    """The spend window opened (Granted -> Active).

    From this moment the envelope check arms: `occurred_at` becomes
    the `activated_at` window start every total-spend fold uses.
    """

    allocation_id: UUID
    activated_by: ActorId
    occurred_at: datetime


@dataclass(frozen=True)
class AllocationCeilingAmended:
    """The ceiling was amended (Granted | Active; PUT semantics).

    The supplied ceiling IS the post-amend ceiling, not a delta: the
    cost-overrun tighten lever must land at an exact number the
    operator chose, and a delta would compound across retries.
    No status change; amendment is not a lifecycle step.
    """

    allocation_id: UUID
    ceiling_usd: float
    occurred_at: datetime


@dataclass(frozen=True)
class AllocationSealed:
    """The books closed with a final-spend snapshot (Active -> Sealed). Terminal.

    `spent_usd` is computed by the caller at seal time (folded from
    the inference ledger over [activated_at, sealed_at)); storing the
    snapshot here is the closing-the-books claim: the sealed envelope
    carries its own final figure even as the ledger keeps growing for
    successor envelopes. `reason` is optional: a routine seal needs no
    justification, an early one usually carries context.
    """

    allocation_id: UUID
    spent_usd: float
    reason: str | None
    sealed_by: ActorId
    occurred_at: datetime


@dataclass(frozen=True)
class AllocationVoided:
    """The grant was withdrawn (Granted | Active -> Voided). Terminal.

    `reason` is REQUIRED: withdrawing an award is a governance act the
    audit log must always carry context for, distinct from the seal
    (which closes books with a spend snapshot; the void records that
    the award never stood).
    """

    allocation_id: UUID
    reason: str
    occurred_at: datetime


# Discriminated union of every event the Allocation aggregate emits.
AllocationEvent = (
    AllocationGranted
    | AllocationActivated
    | AllocationCeilingAmended
    | AllocationSealed
    | AllocationVoided
)


def event_type_name(event: AllocationEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: AllocationEvent) -> dict[str, Any]:
    """Serialise an Allocation event to a JSON-friendly dict for jsonb storage.

    Primitives only: UUIDs (including ActorId) become strings,
    datetimes become ISO-8601 strings.
    """
    match event:
        case AllocationGranted(
            allocation_id=allocation_id,
            ceiling_usd=ceiling_usd,
            campaign_id=campaign_id,
            note=note,
            granted_by=granted_by,
            occurred_at=occurred_at,
        ):
            return {
                "allocation_id": str(allocation_id),
                "ceiling_usd": ceiling_usd,
                "campaign_id": str(campaign_id) if campaign_id is not None else None,
                "note": note,
                "granted_by": str(granted_by),
                "occurred_at": occurred_at.isoformat(),
            }
        case AllocationActivated(
            allocation_id=allocation_id,
            activated_by=activated_by,
            occurred_at=occurred_at,
        ):
            return {
                "allocation_id": str(allocation_id),
                "activated_by": str(activated_by),
                "occurred_at": occurred_at.isoformat(),
            }
        case AllocationCeilingAmended(
            allocation_id=allocation_id,
            ceiling_usd=ceiling_usd,
            occurred_at=occurred_at,
        ):
            return {
                "allocation_id": str(allocation_id),
                "ceiling_usd": ceiling_usd,
                "occurred_at": occurred_at.isoformat(),
            }
        case AllocationSealed(
            allocation_id=allocation_id,
            spent_usd=spent_usd,
            reason=reason,
            sealed_by=sealed_by,
            occurred_at=occurred_at,
        ):
            return {
                "allocation_id": str(allocation_id),
                "spent_usd": spent_usd,
                "reason": reason,
                "sealed_by": str(sealed_by),
                "occurred_at": occurred_at.isoformat(),
            }
        case AllocationVoided(
            allocation_id=allocation_id,
            reason=reason,
            occurred_at=occurred_at,
        ):
            return {
                "allocation_id": str(allocation_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> AllocationEvent:
    """Rebuild an Allocation event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.

    Each arm delegates to `deserialize_or_raise`, which catches
    KeyError / TypeError / AttributeError and re-raises as ValueError
    tagged with the event-type name.

    Nullable fields (`campaign_id`, the Sealed arm's `reason`) use
    `payload.get(...)` so future migrations that add new nullable
    fields remain forward-compat at replay time.
    """
    payload = stored.payload
    match stored.event_type:
        case "AllocationGranted":

            def _build_granted() -> AllocationGranted:
                campaign_id_raw = payload.get("campaign_id")
                return AllocationGranted(
                    allocation_id=UUID(payload["allocation_id"]),
                    ceiling_usd=payload["ceiling_usd"],
                    campaign_id=(UUID(campaign_id_raw) if campaign_id_raw is not None else None),
                    note=payload["note"],
                    granted_by=ActorId(UUID(payload["granted_by"])),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )

            return deserialize_or_raise("AllocationGranted", _build_granted)
        case "AllocationActivated":
            return deserialize_or_raise(
                "AllocationActivated",
                lambda: AllocationActivated(
                    allocation_id=UUID(payload["allocation_id"]),
                    activated_by=ActorId(UUID(payload["activated_by"])),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AllocationCeilingAmended":
            return deserialize_or_raise(
                "AllocationCeilingAmended",
                lambda: AllocationCeilingAmended(
                    allocation_id=UUID(payload["allocation_id"]),
                    ceiling_usd=payload["ceiling_usd"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AllocationSealed":
            return deserialize_or_raise(
                "AllocationSealed",
                lambda: AllocationSealed(
                    allocation_id=UUID(payload["allocation_id"]),
                    spent_usd=payload["spent_usd"],
                    reason=payload.get("reason"),
                    sealed_by=ActorId(UUID(payload["sealed_by"])),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AllocationVoided":
            return deserialize_or_raise(
                "AllocationVoided",
                lambda: AllocationVoided(
                    allocation_id=UUID(payload["allocation_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case _:
            msg = f"Unknown AllocationEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "AllocationActivated",
    "AllocationCeilingAmended",
    "AllocationEvent",
    "AllocationGranted",
    "AllocationSealed",
    "AllocationVoided",
    "event_type_name",
    "from_stored",
    "to_payload",
]
