"""Pure decider for the `RotateSealOnlineKey` command.

Live -> Live transition that swaps `online_credential_id` to a fresh
Credential. Strict-not-idempotent: re-rotating to the same ref the
slot already holds raises `SealCannotRotateError` so the audit
gesture stays meaningful (the offline-root authorises a real change
each time).

`rotated_by` is handler-injected from the request envelope's
`principal_id` (capture-don't-recompute) and stamped onto the emitted
`SealOnlineKeyRotated` event for the audit denorm.

`new_online_credential` is handler-injected too: the handler resolves
the new ref via the `CredentialLookup` port BEFORE invoking the
decider, and the decider partitions on the `purpose` / `status` of the
projection row. Mirrors the start_run pattern (handler loads upstream
projections, threads them into the pure decider). The decider stays
pure: no I/O, no await.

The key-separation invariant (sec-4 AH#15) is enforced by building the
prospective post-transition `Seal` state with the new online ref and
calling `verify_key_separation` before returning events. The helper
raises `SealKeyCollisionError` when `new_online_credential_id` would equal
`offline_credential_id`; HTTP routes this to 422.

## Validation

  - State must not be None (Seal must exist) -> SealNotFoundError
  - Current status must be Live -> SealCannotRotateError
  - new_online_credential_id must differ from current online_credential_id
    -> SealCannotRotateError (no-op rotation rejected)
  - self_facility must not be None
    -> FacilityNotFoundError
  - new_online_credential must not be None (the projection must know
    the ref) -> CredentialNotFoundError (per the start_run ->
    PlanNotFoundError / MethodNotFoundError precedent)
  - new_online_credential.purpose must equal "SealOnlineSigning"
    -> SealKeyPurposeMismatchError (HTTP 422)
  - command.new_online_credential_id must appear in
    self_facility.trust_anchor_credential_ids
    -> SealCredentialNotTrustAnchorError (HTTP 409; structural cross-
    tenant defense; operator pre-seeds via
    add_facility_trust_anchor_credential)
  - new_online_credential.status must equal "Active"
    -> SealCannotRotateWithInactiveCredentialError (HTTP 409;
    Rotating or Revoked secrets cannot back a Seal)
  - new_online_credential_id must differ from offline_credential_id
    -> SealKeyCollisionError (via verify_key_separation helper)
"""

from dataclasses import replace
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
    Seal,
    SealCannotRotateError,
    SealCannotRotateWithInactiveCredentialError,
    SealCredentialNotTrustAnchorError,
    SealKeyPurposeMismatchError,
    SealNotFoundError,
    SealOnlineKeyRotated,
    SealStatus,
    verify_key_separation,
)
from cora.federation.features.rotate_seal_online_key.command import (
    RotateSealOnlineKey,
)
from cora.infrastructure.ports.credential_lookup import CredentialLookupResult
from cora.infrastructure.ports.facility_lookup import FacilityLookupResult
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId

_ONLINE_SLOT = "online_credential_id"


def decide(
    state: Seal | None,
    command: RotateSealOnlineKey,
    *,
    now: datetime,
    rotated_by: ActorId,
    new_online_credential: CredentialLookupResult | None,
    self_facility: FacilityLookupResult | None,
) -> list[SealOnlineKeyRotated]:
    """Decide the events produced by rotating the Seal online key.

    Invariants:
      - State must not be None -> SealNotFoundError
      - state.status must be Live -> SealCannotRotateError
      - new_online_credential_id must differ from state.online_credential_id
        -> SealCannotRotateError (no-op rotation rejected)
      - self_facility must not be None
        -> FacilityNotFoundError
      - new_online_credential must not be None
        -> CredentialNotFoundError (unknown credential ref)
      - new_online_credential.purpose must be SealOnlineSigning
        -> SealKeyPurposeMismatchError
      - command.new_online_credential_id must be in
        self_facility.trust_anchor_credential_ids
        -> SealCredentialNotTrustAnchorError
      - new_online_credential.status must be Active
        -> SealCannotRotateWithInactiveCredentialError
      - new_online_credential_id must differ from state.offline_credential_id
        -> SealKeyCollisionError (via verify_key_separation)
    """
    if state is None:
        raise SealNotFoundError(command.facility_id)
    if state.status is not SealStatus.LIVE:
        raise SealCannotRotateError(state.facility_id, state.status)
    if command.new_online_credential_id == state.online_credential_id:
        raise SealCannotRotateError(state.facility_id, state.status)

    if self_facility is None:
        raise FacilityNotFoundError(FacilityId(facility_stream_id(FacilityCode(state.facility_id))))

    if new_online_credential is None:
        raise CredentialNotFoundError(command.new_online_credential_id)
    if new_online_credential.purpose != CredentialPurpose.SEAL_ONLINE_SIGNING.value:
        raise SealKeyPurposeMismatchError(
            facility_id=state.facility_id,
            slot=_ONLINE_SLOT,
            credential_id=command.new_online_credential_id,
            expected_purpose=CredentialPurpose.SEAL_ONLINE_SIGNING.value,
            actual_purpose=new_online_credential.purpose,
        )
    # Structural cross-tenant defense (Slice 6 Sub-Slice C): the new
    # online credential id must be in the bound Facility's trust-anchor
    # set. Replaces the deleted SealCrossFacilityBindingError string-
    # equality check.
    if command.new_online_credential_id not in self_facility.trust_anchor_credential_ids:
        raise SealCredentialNotTrustAnchorError(
            facility_id=state.facility_id,
            credential_id=command.new_online_credential_id,
            key_ref_role="online",
        )
    if new_online_credential.status != CredentialStatus.ACTIVE.value:
        raise SealCannotRotateWithInactiveCredentialError(
            facility_id=state.facility_id,
            slot=_ONLINE_SLOT,
            credential_id=command.new_online_credential_id,
            actual_status=new_online_credential.status,
        )

    prospective = replace(state, online_credential_id=command.new_online_credential_id)
    verify_key_separation(prospective)

    return [
        SealOnlineKeyRotated(
            facility_id=state.facility_id,
            new_online_credential_id=command.new_online_credential_id,
            signed_by_offline_root=command.signed_by_offline_root,
            rotated_by=rotated_by,
            occurred_at=now,
        )
    ]


__all__ = ["decide"]
