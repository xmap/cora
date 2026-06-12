"""Domain events emitted by the Permit aggregate.

Five events span the 4-state FSM (shared across directions):

  - `PermitDefined`:   genesis (status = Defined); carries terms tagged-union
  - `PermitActivated`: Defined -> Active
  - `PermitSuspended`: Active -> Suspended
  - `PermitResumed`:   Suspended -> Active (audit twin of Activated)
  - `PermitRevoked`:   Defined | Active | Suspended -> Revoked (terminal)

Status is NOT carried in event payloads; the event type IS the
state-change indicator (matches `PermitActivated -> ACTIVE`,
`ClearanceSubmitted -> SUBMITTED`).

`terms` is serialized as a tagged dict with a `kind` discriminator
(`"Outbound" | "Inbound"`) so the polymorphic shape survives jsonb
round-trips. The decoder rebuilds the typed dataclass from the
discriminator; unknown discriminators raise tagged `ValueError`.

`scopes` on OutboundTerms is serialized as a sorted list of
`[kind, name, qualifier]` triples for jsonb stability;
`allowed_credential_ids`, `allowed_payload_types`,
`allowed_artifact_kinds`, and the inbound-side
`inbound_allowed_artifact_kinds` frozenset fields ride through as
sorted string lists.

Each transition event carries an `<verb>_by_actor_id: UUID` denorm
of the envelope `principal_id` (matches CalibrationDefined /
ClearanceSubmitted precedent).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.federation.aggregates.permit.state import (
    AbiTier,
    Direction,
    InboundTerms,
    OnwardActionScope,
    OutboundTerms,
    ReadScope,
    ReceiptKind,
    ScopeRef,
)
from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId


def _serialize_scopes(scopes: frozenset[ScopeRef]) -> list[list[str | None]]:
    return sorted(
        ([s.kind, s.name, s.qualifier] for s in scopes),
        key=lambda triple: (triple[0] or "", triple[1] or "", triple[2] or ""),
    )


def _deserialize_scopes(raw: list[Any]) -> frozenset[ScopeRef]:
    return frozenset(
        ScopeRef(kind=triple[0], name=triple[1], qualifier=triple[2]) for triple in raw
    )


def serialize_terms(terms: OutboundTerms | InboundTerms) -> dict[str, Any]:
    match terms:
        case OutboundTerms(
            scopes=scopes,
            read_scope=read_scope,
            onward_action_scope=onward_action_scope,
        ):
            return {
                "kind": "Outbound",
                "scopes": _serialize_scopes(scopes),
                "read_scope": read_scope.value,
                "onward_action_scope": onward_action_scope.value,
            }
        case InboundTerms(
            inbound_allowed_artifact_kinds=inbound_allowed_artifact_kinds,
            accepted_canonicalization_versions=accepted_canonicalization_versions,
            required_receipt_kinds=required_receipt_kinds,
            publisher_grant_correlation_handle=publisher_grant_correlation_handle,
        ):
            return {
                "kind": "Inbound",
                "inbound_allowed_artifact_kinds": sorted(inbound_allowed_artifact_kinds),
                "accepted_canonicalization_versions": sorted(accepted_canonicalization_versions),
                "required_receipt_kinds": sorted(r.value for r in required_receipt_kinds),
                "publisher_grant_correlation_handle": publisher_grant_correlation_handle,
            }
        case _:  # pragma: no cover
            assert_never(terms)


def deserialize_terms(raw: dict[str, Any]) -> OutboundTerms | InboundTerms:
    kind = raw.get("kind")
    match kind:
        case "Outbound":
            return OutboundTerms(
                scopes=_deserialize_scopes(raw["scopes"]),
                read_scope=ReadScope(raw["read_scope"]),
                onward_action_scope=OnwardActionScope(raw["onward_action_scope"]),
            )
        case "Inbound":
            return InboundTerms(
                inbound_allowed_artifact_kinds=frozenset(raw["inbound_allowed_artifact_kinds"]),
                accepted_canonicalization_versions=frozenset(
                    raw["accepted_canonicalization_versions"]
                ),
                required_receipt_kinds=frozenset(
                    ReceiptKind(r) for r in raw["required_receipt_kinds"]
                ),
                publisher_grant_correlation_handle=raw.get("publisher_grant_correlation_handle"),
            )
        case unknown:
            msg = f"Unknown Permit terms kind discriminator: {unknown!r}"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class PermitDefined:
    permit_id: UUID
    peer_facility_code: FacilityCode
    direction: Direction
    allowed_credential_ids: frozenset[UUID]
    allowed_payload_types: frozenset[str]
    allowed_artifact_kinds: frozenset[str]
    abi_tier_floor: AbiTier
    expires_at: datetime
    defined_by: ActorId
    terms: OutboundTerms | InboundTerms
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class PermitActivated:
    permit_id: UUID
    activated_by: UUID
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class PermitSuspended:
    permit_id: UUID
    suspended_by: UUID
    occurred_at: datetime
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class PermitResumed:
    permit_id: UUID
    resumed_by: UUID
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class PermitRevoked:
    permit_id: UUID
    revoked_by: UUID
    occurred_at: datetime
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class PublicationReceiptRecorded:
    """A per-BC publish slice recorded a receipt against this outbound permit.

    Cross-BC iter-b federation event. The matching home-aggregate
    event (`<Artifact>Published` on the home BC stream) lands
    atomically via the handler's `EventStore.append_streams` call
    per cross-BC append-streams discipline.

    `content_hash` is the artifact's port-tier content hash
    (recomputed via the matching Canonicalizer adapter on
    the verify side); `home_stream_type` + `home_stream_id` +
    `home_artifact_id` denorm the cross-stream join so audit
    queries do not require a separate index lookup. `receipt_id`
    is the UUID minted by the PublishPort adapter and matches the
    receipt_id on the home-BC published event.

    No status transition: the Permit FSM is `Defined / Active /
    Suspended / Revoked`; recording a receipt is orthogonal to
    those positions. The decider enforces the Active-only
    invariant before emitting this event (publishing under a
    Suspended or Revoked permit is rejected).
    """

    permit_id: UUID
    content_hash: str
    home_stream_type: str
    home_stream_id: UUID
    home_artifact_id: UUID
    receipt_id: UUID
    recorded_at: datetime
    occurred_at: datetime


PermitEvent = (
    PermitDefined
    | PermitActivated
    | PermitSuspended
    | PermitResumed
    | PermitRevoked
    | PublicationReceiptRecorded
)


def event_type_name(event: PermitEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: PermitEvent) -> dict[str, Any]:
    match event:
        case PermitDefined(
            permit_id=permit_id,
            peer_facility_code=peer_facility_code,
            direction=direction,
            allowed_credential_ids=allowed_credential_ids,
            allowed_payload_types=allowed_payload_types,
            allowed_artifact_kinds=allowed_artifact_kinds,
            abi_tier_floor=abi_tier_floor,
            expires_at=expires_at,
            defined_by=defined_by,
            terms=terms,
            occurred_at=occurred_at,
        ):
            return {
                "permit_id": str(permit_id),
                "peer_facility_id": peer_facility_code.value,
                "direction": direction.value,
                "allowed_credential_ids": sorted(str(c) for c in allowed_credential_ids),
                "allowed_payload_types": sorted(allowed_payload_types),
                "allowed_artifact_kinds": sorted(allowed_artifact_kinds),
                "abi_tier_floor": abi_tier_floor.value,
                "expires_at": expires_at.isoformat(),
                "defined_by": str(defined_by),
                "terms": serialize_terms(terms),
                "occurred_at": occurred_at.isoformat(),
            }
        case PermitActivated(
            permit_id=permit_id,
            activated_by=activated_by,
            occurred_at=occurred_at,
        ):
            return {
                "permit_id": str(permit_id),
                "activated_by": str(activated_by),
                "occurred_at": occurred_at.isoformat(),
            }
        case PermitSuspended(
            permit_id=permit_id,
            suspended_by=suspended_by,
            occurred_at=occurred_at,
            reason=reason,
        ):
            return {
                "permit_id": str(permit_id),
                "suspended_by": str(suspended_by),
                "occurred_at": occurred_at.isoformat(),
                "reason": reason,
            }
        case PermitResumed(
            permit_id=permit_id,
            resumed_by=resumed_by,
            occurred_at=occurred_at,
        ):
            return {
                "permit_id": str(permit_id),
                "resumed_by": str(resumed_by),
                "occurred_at": occurred_at.isoformat(),
            }
        case PermitRevoked(
            permit_id=permit_id,
            revoked_by=revoked_by,
            occurred_at=occurred_at,
            reason=reason,
        ):
            return {
                "permit_id": str(permit_id),
                "revoked_by": str(revoked_by),
                "occurred_at": occurred_at.isoformat(),
                "reason": reason,
            }
        case PublicationReceiptRecorded(
            permit_id=permit_id,
            content_hash=content_hash,
            home_stream_type=home_stream_type,
            home_stream_id=home_stream_id,
            home_artifact_id=home_artifact_id,
            receipt_id=receipt_id,
            recorded_at=recorded_at,
            occurred_at=occurred_at,
        ):
            return {
                "permit_id": str(permit_id),
                "content_hash": content_hash,
                "home_stream_type": home_stream_type,
                "home_stream_id": str(home_stream_id),
                "home_artifact_id": str(home_artifact_id),
                "receipt_id": str(receipt_id),
                "recorded_at": recorded_at.isoformat(),
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover
            assert_never(event)


def from_stored(stored: StoredEvent) -> PermitEvent:
    """Rebuild a Permit event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises tagged `ValueError` on
    unknown discriminators or malformed payloads so a contaminated
    stream fails loud rather than silently dropping events.
    """
    payload = stored.payload
    match stored.event_type:
        case "PermitDefined":
            return deserialize_or_raise(
                "PermitDefined",
                lambda: PermitDefined(
                    permit_id=UUID(payload["permit_id"]),
                    peer_facility_code=FacilityCode(payload["peer_facility_id"]),
                    direction=Direction(payload["direction"]),
                    allowed_credential_ids=frozenset(
                        UUID(c) for c in payload["allowed_credential_ids"]
                    ),
                    allowed_payload_types=frozenset(payload["allowed_payload_types"]),
                    allowed_artifact_kinds=frozenset(payload["allowed_artifact_kinds"]),
                    abi_tier_floor=AbiTier(payload["abi_tier_floor"]),
                    expires_at=datetime.fromisoformat(payload["expires_at"]),
                    defined_by=ActorId(UUID(payload["defined_by"])),
                    terms=deserialize_terms(payload["terms"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
                extra=(ValueError,),
            )
        case "PermitActivated":
            return deserialize_or_raise(
                "PermitActivated",
                lambda: PermitActivated(
                    permit_id=UUID(payload["permit_id"]),
                    activated_by=UUID(payload["activated_by"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "PermitSuspended":
            return deserialize_or_raise(
                "PermitSuspended",
                lambda: PermitSuspended(
                    permit_id=UUID(payload["permit_id"]),
                    suspended_by=UUID(payload["suspended_by"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    reason=payload.get("reason"),
                ),
            )
        case "PermitResumed":
            return deserialize_or_raise(
                "PermitResumed",
                lambda: PermitResumed(
                    permit_id=UUID(payload["permit_id"]),
                    resumed_by=UUID(payload["resumed_by"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "PermitRevoked":
            return deserialize_or_raise(
                "PermitRevoked",
                lambda: PermitRevoked(
                    permit_id=UUID(payload["permit_id"]),
                    revoked_by=UUID(payload["revoked_by"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    reason=payload.get("reason"),
                ),
            )
        case "PublicationReceiptRecorded":
            return deserialize_or_raise(
                "PublicationReceiptRecorded",
                lambda: PublicationReceiptRecorded(
                    permit_id=UUID(payload["permit_id"]),
                    content_hash=payload["content_hash"],
                    home_stream_type=payload["home_stream_type"],
                    home_stream_id=UUID(payload["home_stream_id"]),
                    home_artifact_id=UUID(payload["home_artifact_id"]),
                    receipt_id=UUID(payload["receipt_id"]),
                    recorded_at=datetime.fromisoformat(payload["recorded_at"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case unknown:
            msg = f"Unknown Permit event type: {unknown!r}"
            raise ValueError(msg)


__all__ = [
    "PermitActivated",
    "PermitDefined",
    "PermitEvent",
    "PermitResumed",
    "PermitRevoked",
    "PermitSuspended",
    "PublicationReceiptRecorded",
    "deserialize_terms",
    "event_type_name",
    "from_stored",
    "serialize_terms",
    "to_payload",
]
