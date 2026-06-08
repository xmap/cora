"""Pure decider for the `AddFacilityTrustAnchorCredential` command.

Adds a credential id to a Facility's `trust_anchor_credential_ids`
frozenset. Three disqualifying conditions surface as dedicated error
classes:

  - Facility does not exist (state is None) -> FacilityNotFoundError (404)
  - Facility is Decommissioned OR kind=Area (shared lifecycle/kind
    guard; Area facilities inherit the parent Site's trust posture
    and never carry their own anchors) ->
    FacilityCannotAddTrustAnchorCredentialError (409)
  - credential_id already in trust_anchor_credential_ids
    (strict-not-idempotent; mirrors AssetAlternateIdentifierAlreadyPresentError) ->
    FacilityTrustAnchorCredentialAlreadyPresentError (409)

The lifecycle guard mirrors `add_asset_alternate_identifier` exactly:
a Decommissioned Facility is out of service, and trust-anchor changes
are not permitted. Symmetric with `remove_facility_trust_anchor_credential`
which raises the same shared lifecycle/kind error class.

`added_by` is handler-injected from the request envelope's
`principal_id` (capture-don't-recompute) and stamped onto the
emitted `FacilityTrustAnchorCredentialAdded` event.
"""

from datetime import datetime

from cora.federation.aggregates.facility import (
    Facility,
    FacilityCannotAddTrustAnchorCredentialError,
    FacilityKind,
    FacilityNotFoundError,
    FacilityStatus,
    FacilityTrustAnchorCredentialAdded,
    FacilityTrustAnchorCredentialAlreadyPresentError,
)
from cora.federation.features.add_facility_trust_anchor_credential.command import (
    AddFacilityTrustAnchorCredential,
)
from cora.shared.identity import ActorId


def decide(
    state: Facility | None,
    command: AddFacilityTrustAnchorCredential,
    *,
    now: datetime,
    added_by: ActorId,
) -> list[FacilityTrustAnchorCredentialAdded]:
    """Decide the events produced by adding a trust-anchor credential.

    Invariants:
      - State must not be None -> FacilityNotFoundError
      - Facility must be Active AND kind=Site
        -> FacilityCannotAddTrustAnchorCredentialError
      - credential_id must not already be in state.trust_anchor_credential_ids
        -> FacilityTrustAnchorCredentialAlreadyPresentError
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

    if state.kind is FacilityKind.AREA:
        raise FacilityCannotAddTrustAnchorCredentialError(
            state.id,
            command.credential_id,
            reason=(
                f"facility kind is {FacilityKind.AREA.value} "
                "(Area facilities inherit the parent Site's trust posture; "
                "trust anchors bind to Site-tier facilities only)"
            ),
        )

    if command.credential_id in state.trust_anchor_credential_ids:
        raise FacilityTrustAnchorCredentialAlreadyPresentError(
            state.id,
            command.credential_id,
        )

    return [
        FacilityTrustAnchorCredentialAdded(
            facility_id=state.id,
            credential_id=command.credential_id,
            added_by=added_by,
            occurred_at=now,
        )
    ]


__all__ = ["decide"]
