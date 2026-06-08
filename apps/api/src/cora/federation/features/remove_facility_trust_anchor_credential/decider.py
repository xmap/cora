"""Pure decider for the `RemoveFacilityTrustAnchorCredential` command.

Removes a credential id from a Facility's `trust_anchor_credential_ids`
frozenset. Three disqualifying conditions surface as dedicated error
classes:

  - Facility does not exist (state is None) -> FacilityNotFoundError (404)
  - Facility is Decommissioned (shared lifecycle guard with the add
    decider; kind=Area is structurally impossible to have non-empty
    trust anchors so no separate kind guard fires here) ->
    FacilityCannotAddTrustAnchorCredentialError (409)
  - credential_id NOT in trust_anchor_credential_ids
    (strict-not-idempotent; mirrors AssetAlternateIdentifierNotPresentError) ->
    FacilityTrustAnchorCredentialNotPresentError (409)

Mirror of `remove_asset_alternate_identifier`. Symmetric with
`add_facility_trust_anchor_credential` (same shared lifecycle error
class).

`removed_by` is handler-injected from the request envelope's
`principal_id`; `reason` flows from the command payload.
"""

from datetime import datetime

from cora.federation.aggregates.facility import (
    Facility,
    FacilityCannotAddTrustAnchorCredentialError,
    FacilityNotFoundError,
    FacilityStatus,
    FacilityTrustAnchorCredentialNotPresentError,
    FacilityTrustAnchorCredentialRemoved,
)
from cora.federation.features.remove_facility_trust_anchor_credential.command import (
    RemoveFacilityTrustAnchorCredential,
)
from cora.shared.identity import ActorId


def decide(
    state: Facility | None,
    command: RemoveFacilityTrustAnchorCredential,
    *,
    now: datetime,
    removed_by: ActorId,
) -> list[FacilityTrustAnchorCredentialRemoved]:
    """Decide the events produced by removing a trust-anchor credential.

    Invariants:
      - State must not be None -> FacilityNotFoundError
      - Facility must not be Decommissioned
        -> FacilityCannotAddTrustAnchorCredentialError
      - credential_id must already be in state.trust_anchor_credential_ids
        -> FacilityTrustAnchorCredentialNotPresentError
    """
    if state is None:
        raise FacilityNotFoundError(command.facility_id)

    if state.status is FacilityStatus.DECOMMISSIONED:
        raise FacilityCannotAddTrustAnchorCredentialError(
            state.id,
            command.credential_id,
            reason=(
                f"facility is currently {FacilityStatus.DECOMMISSIONED.value} "
                "(decommissioned; trust-anchor changes are not allowed)"
            ),
        )

    if command.credential_id not in state.trust_anchor_credential_ids:
        raise FacilityTrustAnchorCredentialNotPresentError(
            state.id,
            command.credential_id,
        )

    return [
        FacilityTrustAnchorCredentialRemoved(
            facility_id=state.id,
            credential_id=command.credential_id,
            removed_by=removed_by,
            occurred_at=now,
            reason=command.reason,
        )
    ]


__all__ = ["decide"]
