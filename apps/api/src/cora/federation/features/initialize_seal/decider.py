"""Pure decider for the `InitializeSeal` command.

Pure function: given the (always None) Seal state, an `InitializeSeal`
command, two `CredentialLookupResult` snapshots, and the self-Facility's
`FacilityLookupResult`, returns the events to append on the Seal
stream. No I/O, no awaits, no side effects.

`now` and `initialized_by` are injected by the application handler from
the Clock port and the request envelope (non-determinism principle:
capture, don't recompute).

`online_credential` and `offline_credential` are likewise handler-
injected: the handler resolves each ref via the `CredentialLookup` port
BEFORE invoking the decider, and the decider partitions on the
`purpose` / `status` of each projection row. Mirrors the
`rotate_seal_online_key` precedent (Pass 2) and the `start_run` pattern
(handler loads upstream projections, threads them into the pure
decider). The decider stays pure: no I/O, no await.

`self_facility` is the third handler-injected projection row: the
Facility row whose `code` equals `command.facility_id`. The decider
checks that BOTH credential ids appear in
`self_facility.trust_anchor_credential_ids`, replacing the deleted
`SealCrossFacilityBindingError` string-equality three-way check (Slice
6 Sub-Slice C structural fold).

The cross-BC `DecisionRegistered` audit event on the Decision stream is
built directly by the handler (not by this decider) and written
atomically alongside the `SealInitialized` event via
`EventStore.append_streams`. Decider stays focused on the Seal BC's
domain invariants.

## Validation

  - State must be None (genesis-only; Seal is a per-facility singleton)
    -> SealAlreadyExistsError
  - facility_id non-empty AND already in canonical form (no leading
    or trailing whitespace); avoids auto-normalization that could mask
    a peer-facility credential drift in the binding check
    -> InvalidSealFacilityIdError
  - online_credential_id != offline_credential_id (key-separation
    invariant; enforced by building the prospective post-state and
    calling `verify_key_separation` per sec-4 AH#15)
    -> SealKeyCollisionError
  - self_facility must not be None
    -> FacilityNotFoundError
  - online_credential must not be None (projection must know the ref)
    -> CredentialNotFoundError (per the start_run -> PlanNotFoundError
    precedent)
  - offline_credential must not be None
    -> CredentialNotFoundError
  - online_credential.purpose must equal "SealOnlineSigning"
    -> SealKeyPurposeMismatchError (HTTP 422)
  - offline_credential.purpose must equal "SealOfflineRoot"
    -> SealKeyPurposeMismatchError (HTTP 422)
  - command.online_credential_id must appear in
    self_facility.trust_anchor_credential_ids
    -> SealCredentialNotTrustAnchorError (HTTP 409; structural cross-
    tenant defense; operator pre-seeds via
    add_facility_trust_anchor_credential)
  - command.offline_credential_id must appear in
    self_facility.trust_anchor_credential_ids
    -> SealCredentialNotTrustAnchorError (HTTP 409)
  - online_credential.status must equal "Active"
    -> SealCannotInitializeWithInactiveCredentialError (HTTP 409;
    Rotating or Revoked secrets cannot back a Seal)
  - offline_credential.status must equal "Active"
    -> SealCannotInitializeWithInactiveCredentialError (HTTP 409)
"""

from datetime import datetime

from cora.federation.aggregates._value_types import FacilityId
from cora.federation.aggregates.credential import (
    CredentialNotFoundError,
    CredentialPurpose,
    CredentialStatus,
)
from cora.federation.aggregates.facility import FacilityNotFoundError
from cora.federation.aggregates.facility._stream_id import facility_stream_id
from cora.federation.aggregates.seal import (
    InvalidSealFacilityIdError,
    Seal,
    SealAlreadyExistsError,
    SealCannotInitializeWithInactiveCredentialError,
    SealCredentialNotTrustAnchorError,
    SealInitialized,
    SealKeyPurposeMismatchError,
    SealStatus,
    verify_key_separation,
)
from cora.federation.features.initialize_seal.command import InitializeSeal
from cora.infrastructure.ports.credential_lookup import CredentialLookupResult
from cora.infrastructure.ports.facility_lookup import FacilityLookupResult
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId

_ONLINE_SLOT = "online_credential_id"
_OFFLINE_SLOT = "offline_credential_id"


def decide(
    state: Seal | None,
    command: InitializeSeal,
    *,
    now: datetime,
    initialized_by: ActorId,
    online_credential: CredentialLookupResult | None,
    offline_credential: CredentialLookupResult | None,
    self_facility: FacilityLookupResult | None,
) -> list[SealInitialized]:
    """Decide the events produced by initializing a Seal singleton.

    Invariants:
      - State must be None (genesis-only singleton)
        -> SealAlreadyExistsError
      - facility_id non-empty AND canonical (no surrounding whitespace)
        -> InvalidSealFacilityIdError
      - online_credential_id must differ from offline_credential_id
        -> SealKeyCollisionError (via verify_key_separation)
      - self_facility must not be None
        -> FacilityNotFoundError
      - online_credential must not be None
        -> CredentialNotFoundError (unknown credential ref)
      - offline_credential must not be None
        -> CredentialNotFoundError (unknown credential ref)
      - online_credential.purpose must be SealOnlineSigning
        -> SealKeyPurposeMismatchError
      - offline_credential.purpose must be SealOfflineRoot
        -> SealKeyPurposeMismatchError
      - command.online_credential_id must be in
        self_facility.trust_anchor_credential_ids
        -> SealCredentialNotTrustAnchorError
      - command.offline_credential_id must be in
        self_facility.trust_anchor_credential_ids
        -> SealCredentialNotTrustAnchorError
      - online_credential.status must be Active
        -> SealCannotInitializeWithInactiveCredentialError
      - offline_credential.status must be Active
        -> SealCannotInitializeWithInactiveCredentialError
    """
    if state is not None:
        raise SealAlreadyExistsError(state.facility_id)

    facility_id = command.facility_id.strip()
    if not facility_id or facility_id != command.facility_id:
        raise InvalidSealFacilityIdError(command.facility_id)

    prospective = Seal(
        facility_id=facility_id,
        online_credential_id=command.online_credential_id,
        offline_credential_id=command.offline_credential_id,
        current_head_hash=None,
        current_sequence_number=0,
        initialized_by=initialized_by,
        initialized_at=now,
        status=SealStatus.LIVE,
    )
    verify_key_separation(prospective)

    if self_facility is None:
        raise FacilityNotFoundError(FacilityId(facility_stream_id(FacilityCode(facility_id))))

    if online_credential is None:
        raise CredentialNotFoundError(command.online_credential_id)
    if offline_credential is None:
        raise CredentialNotFoundError(command.offline_credential_id)

    if online_credential.purpose != CredentialPurpose.SEAL_ONLINE_SIGNING.value:
        raise SealKeyPurposeMismatchError(
            facility_id=facility_id,
            slot=_ONLINE_SLOT,
            credential_id=command.online_credential_id,
            expected_purpose=CredentialPurpose.SEAL_ONLINE_SIGNING.value,
            actual_purpose=online_credential.purpose,
        )
    if offline_credential.purpose != CredentialPurpose.SEAL_OFFLINE_ROOT.value:
        raise SealKeyPurposeMismatchError(
            facility_id=facility_id,
            slot=_OFFLINE_SLOT,
            credential_id=command.offline_credential_id,
            expected_purpose=CredentialPurpose.SEAL_OFFLINE_ROOT.value,
            actual_purpose=offline_credential.purpose,
        )

    # Structural cross-tenant defense (Slice 6 Sub-Slice C): both
    # credential ids must be in the self-Facility's trust-anchor set.
    # Replaces the deleted SealCrossFacilityBindingError 3-arm string-
    # equality check. The "online_vs_offline" third defense-in-depth
    # check collapses entirely: set-membership against the same Facility
    # makes the cross-check redundant.
    if command.online_credential_id not in self_facility.trust_anchor_credential_ids:
        raise SealCredentialNotTrustAnchorError(
            facility_id=facility_id,
            credential_id=command.online_credential_id,
            key_ref_role="online",
        )
    if command.offline_credential_id not in self_facility.trust_anchor_credential_ids:
        raise SealCredentialNotTrustAnchorError(
            facility_id=facility_id,
            credential_id=command.offline_credential_id,
            key_ref_role="offline",
        )

    if online_credential.status != CredentialStatus.ACTIVE.value:
        raise SealCannotInitializeWithInactiveCredentialError(
            facility_id=facility_id,
            slot=_ONLINE_SLOT,
            credential_id=command.online_credential_id,
            actual_status=online_credential.status,
        )
    if offline_credential.status != CredentialStatus.ACTIVE.value:
        raise SealCannotInitializeWithInactiveCredentialError(
            facility_id=facility_id,
            slot=_OFFLINE_SLOT,
            credential_id=command.offline_credential_id,
            actual_status=offline_credential.status,
        )

    return [
        SealInitialized(
            facility_id=facility_id,
            online_credential_id=command.online_credential_id,
            offline_credential_id=command.offline_credential_id,
            initialized_by=initialized_by,
            occurred_at=now,
        )
    ]


__all__ = ["decide"]
