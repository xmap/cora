"""Domain events emitted by the Facility aggregate, plus the discriminated union.

Two events shipped at BC genesis:

  - `FacilityRegistered`: genesis (status starts at Active).
  - `FacilityDecommissioned`: terminal (status moves to Decommissioned).

Both events fold their envelope `occurred_at` onto state per
[[project_fold_symmetry_design]]: `FacilityRegistered.occurred_at` lands
as `Facility.registered_at` alongside `registered_by` (typed `ActorId`);
`FacilityDecommissioned.occurred_at` lands as `decommissioned_at`
alongside `decommissioned_by` (typed `ActorId`).

`FacilityRegistered` carries the day-one `alternate_identifiers`
optional seed per [[project_facility_aggregate_design]] L5. The genesis
event does NOT carry `persistent_id` (state-only in slice 5; assign slice
deferred) or `trust_anchor_credential_ids` (state-only in slice 5;
add/remove slices deferred to slice 6).

Per [[project_identifier_vo_design]] L137 wire convention: nested
`{"kind", "value"}` for cardinality>1 collections (alternate_identifiers
list-of-dicts), flat-prefix for singular fields (registered_by, etc.).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.federation.aggregates._value_types import CredentialId, FacilityId
from cora.federation.aggregates.facility.state import FacilityKind
from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.facility_code import FacilityCode
from cora.shared.identifier import AlternateIdentifier, AlternateIdentifierKind
from cora.shared.identity import ActorId


@dataclass(frozen=True)
class FacilityRegistered:
    """A new Facility was registered (genesis; status starts at Active).

    `code` is the cross-deployment convergent slug; it derives the
    stream id (via `facility_stream_id`) and is immutable post-genesis.
    `alternate_identifiers` is the optional day-one seed (defaults to
    empty); add / remove slices are deferred per Asset precedent.
    `persistent_id` and `trust_anchor_credential_ids` are state-only
    in slice 5 and therefore absent from the genesis payload.
    """

    facility_id: FacilityId
    code: FacilityCode
    display_name: str
    kind: FacilityKind
    parent_id: FacilityId | None
    registered_by: ActorId
    occurred_at: datetime
    # Parametrized default_factory for the empty frozenset trick: the
    # empty frozenset has no element type for pyright to infer under
    # strict, so the parametrized callable is supplied as the factory.
    alternate_identifiers: frozenset[AlternateIdentifier] = field(
        default_factory=frozenset[AlternateIdentifier]
    )


@dataclass(frozen=True)
class FacilityDecommissioned:
    """A Facility was decommissioned (terminal).

    Valid from `Active` only (per the two-state FSM); the decider
    raises `FacilityCannotDecommissionError` for any other source
    status. Strict-not-idempotent: a re-decommission attempt raises
    rather than no-ops, mirroring the `revoke_credential` precedent.
    """

    facility_id: FacilityId
    decommissioned_by: ActorId
    occurred_at: datetime
    reason: str | None = None


@dataclass(frozen=True)
class FacilityTrustAnchorCredentialAdded:
    """A Credential id was added to a Facility's trust-anchor set.

    Mutates `Facility.trust_anchor_credential_ids: frozenset[CredentialId]`
    by union with the new id. Valid only when the Facility is Active and
    kind=Site (Area Facilities inherit the parent Site's trust posture;
    the decider raises `FacilityCannotAddTrustAnchorCredentialError` for
    either guard violation). Strict-not-idempotent: re-adding an already-
    present credential raises `FacilityTrustAnchorCredentialAlreadyPresentError`.

    Slice 6 Sub-Slice B genesis event. Consumed by the projection writer
    to maintain the JSONB array column. Slice 6 Sub-Slice C will gate
    Seal initialize / rotate on set-membership against this column.
    """

    facility_id: FacilityId
    credential_id: CredentialId
    added_by: ActorId
    occurred_at: datetime


@dataclass(frozen=True)
class FacilityTrustAnchorCredentialRemoved:
    """A Credential id was removed from a Facility's trust-anchor set.

    Mutates `Facility.trust_anchor_credential_ids: frozenset[CredentialId]`
    by difference. Valid only when the Facility is Active (Decommissioned
    facilities reject mutation per the shared lifecycle/kind guard).
    Strict-not-idempotent: removing an already-absent credential raises
    `FacilityTrustAnchorCredentialNotPresentError`.

    `reason` flows through to the projection / event log for operator
    audit-trail breadcrumb (e.g. "key compromise", "rotation cleanup",
    "decommissioned credential garbage-collect").
    """

    facility_id: FacilityId
    credential_id: CredentialId
    removed_by: ActorId
    occurred_at: datetime
    reason: str | None = None


FacilityEvent = (
    FacilityRegistered
    | FacilityDecommissioned
    | FacilityTrustAnchorCredentialAdded
    | FacilityTrustAnchorCredentialRemoved
)


def event_type_name(event: FacilityEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def _alternate_identifier_to_payload(
    alt: AlternateIdentifier,
) -> dict[str, str]:
    return {"kind": alt.kind.value, "value": alt.value}


def to_payload(event: FacilityEvent) -> dict[str, Any]:
    """Serialise a Facility event to a JSON-friendly dict for jsonb storage."""
    match event:
        case FacilityRegistered(
            facility_id=facility_id,
            code=code,
            display_name=display_name,
            kind=kind,
            parent_id=parent_id,
            alternate_identifiers=alternate_identifiers,
            registered_by=registered_by,
            occurred_at=occurred_at,
        ):
            return {
                "facility_id": str(facility_id),
                "code": code.value,
                "display_name": display_name,
                "kind": kind.value,
                "parent_id": (str(parent_id) if parent_id is not None else None),
                "alternate_identifiers": sorted(
                    (_alternate_identifier_to_payload(alt) for alt in alternate_identifiers),
                    key=lambda d: (d["kind"], d["value"]),
                ),
                "registered_by": str(registered_by),
                "occurred_at": occurred_at.isoformat(),
            }
        case FacilityDecommissioned(
            facility_id=facility_id,
            decommissioned_by=decommissioned_by,
            occurred_at=occurred_at,
            reason=reason,
        ):
            return {
                "facility_id": str(facility_id),
                "decommissioned_by": str(decommissioned_by),
                "occurred_at": occurred_at.isoformat(),
                "reason": reason,
            }
        case FacilityTrustAnchorCredentialAdded(
            facility_id=facility_id,
            credential_id=credential_id,
            added_by=added_by,
            occurred_at=occurred_at,
        ):
            return {
                "facility_id": str(facility_id),
                "credential_id": str(credential_id),
                "added_by": str(added_by),
                "occurred_at": occurred_at.isoformat(),
            }
        case FacilityTrustAnchorCredentialRemoved(
            facility_id=facility_id,
            credential_id=credential_id,
            removed_by=removed_by,
            occurred_at=occurred_at,
            reason=reason,
        ):
            return {
                "facility_id": str(facility_id),
                "credential_id": str(credential_id),
                "removed_by": str(removed_by),
                "occurred_at": occurred_at.isoformat(),
                "reason": reason,
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> FacilityEvent:
    """Rebuild a Facility event from a StoredEvent loaded from the event store."""
    payload = stored.payload
    match stored.event_type:
        case "FacilityRegistered":

            def _build_facility_registered() -> FacilityRegistered:
                raw_parent = payload.get("parent_id")
                raw_alts = payload.get("alternate_identifiers", [])
                return FacilityRegistered(
                    facility_id=FacilityId(UUID(payload["facility_id"])),
                    code=FacilityCode(payload["code"]),
                    display_name=payload["display_name"],
                    kind=FacilityKind(payload["kind"]),
                    parent_id=(FacilityId(UUID(raw_parent)) if raw_parent is not None else None),
                    alternate_identifiers=frozenset(
                        AlternateIdentifier(
                            kind=AlternateIdentifierKind(entry["kind"]),
                            value=entry["value"],
                        )
                        for entry in raw_alts
                    ),
                    registered_by=ActorId(UUID(payload["registered_by"])),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )

            return deserialize_or_raise(
                "FacilityRegistered",
                _build_facility_registered,
                extra=(ValueError,),
            )
        case "FacilityDecommissioned":
            return deserialize_or_raise(
                "FacilityDecommissioned",
                lambda: FacilityDecommissioned(
                    facility_id=FacilityId(UUID(payload["facility_id"])),
                    decommissioned_by=ActorId(UUID(payload["decommissioned_by"])),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    reason=payload.get("reason"),
                ),
                extra=(ValueError,),
            )
        case "FacilityTrustAnchorCredentialAdded":
            return deserialize_or_raise(
                "FacilityTrustAnchorCredentialAdded",
                lambda: FacilityTrustAnchorCredentialAdded(
                    facility_id=FacilityId(UUID(payload["facility_id"])),
                    credential_id=CredentialId(UUID(payload["credential_id"])),
                    added_by=ActorId(UUID(payload["added_by"])),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
                extra=(ValueError,),
            )
        case "FacilityTrustAnchorCredentialRemoved":
            return deserialize_or_raise(
                "FacilityTrustAnchorCredentialRemoved",
                lambda: FacilityTrustAnchorCredentialRemoved(
                    facility_id=FacilityId(UUID(payload["facility_id"])),
                    credential_id=CredentialId(UUID(payload["credential_id"])),
                    removed_by=ActorId(UUID(payload["removed_by"])),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    reason=payload.get("reason"),
                ),
                extra=(ValueError,),
            )
        case unknown:
            msg = f"Unknown Facility event type: {unknown!r}"
            raise ValueError(msg)


__all__ = [
    "FacilityDecommissioned",
    "FacilityEvent",
    "FacilityRegistered",
    "FacilityTrustAnchorCredentialAdded",
    "FacilityTrustAnchorCredentialRemoved",
    "event_type_name",
    "from_stored",
    "to_payload",
]
