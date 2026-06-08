"""Pure decider for the `DefinePermit` command.

Pure function: given the (always None) Permit state and a
`DefinePermit` command, returns the events to append on the
Permit stream. No I/O, no awaits, no side effects.

`now`, `new_id`, and `defined_by` are injected by the
application handler from the Clock / IdGenerator ports and the
request envelope (the non-determinism principle: capture, don't
recompute).

The cross-BC `DecisionRegistered` audit event on the Decision
stream is built directly by the handler (not by this decider) and
written atomically alongside the `PermitDefined` event via
`EventStore.append_streams`. Decider stays focused on the Permit
BC's domain invariants.

Invariants:
  - State must be None (genesis-only)
    -> PermitAlreadyExistsError
  - peer_facility_id non-empty after trim
    -> InvalidPermitScopeError
  - expires_at must lie strictly after now
    -> InvalidPermitScopeError
  - allowed_credential_ids non-empty
    -> InvalidPermitScopeError
  - allowed_payload_types non-empty + every member non-empty after trim
    -> InvalidPermitScopeError
  - allowed_artifact_kinds non-empty + every member non-empty after trim
    -> InvalidPermitScopeError
  - direction must mirror type(command.terms): OUTBOUND with
    OutboundTerms, INBOUND with InboundTerms
    -> InvalidPermitScopeError
  - When terms is OutboundTerms: scopes non-empty; read_scope
    and onward_action_scope not None
    -> PermitScopeCollapseError for the read / onward collapse
    matrix; InvalidPermitScopeError for empty scope set.

Initial status is implicit `Defined` (event type IS the state-change
indicator; the genesis evolver hardcodes the mapping).
"""

from datetime import datetime
from uuid import UUID

from cora.federation.aggregates.permit import (
    Direction,
    InboundTerms,
    InvalidPermitScopeError,
    OnwardActionScope,
    OutboundTerms,
    Permit,
    PermitAlreadyExistsError,
    PermitDefined,
    PermitScopeCollapseError,
    ReadScope,
)
from cora.federation.features.define_permit.command import DefinePermit
from cora.shared.identity import ActorId


def decide(
    state: Permit | None,
    command: DefinePermit,
    *,
    now: datetime,
    new_id: UUID,
    defined_by: ActorId,
) -> list[PermitDefined]:
    """Decide the events produced by defining a new Permit.

    Invariants:
      - State must be None (genesis-only) -> PermitAlreadyExistsError
      - peer_facility_id must be non-empty after trim
        -> InvalidPermitScopeError
      - expires_at must lie strictly after now
        -> InvalidPermitScopeError
      - allowed_credential_ids must be non-empty
        -> InvalidPermitScopeError
      - allowed_payload_types must be non-empty and every member
        non-empty after trim -> InvalidPermitScopeError
      - allowed_artifact_kinds must be non-empty and every member
        non-empty after trim -> InvalidPermitScopeError
      - direction must mirror type(terms) (OUTBOUND with OutboundTerms,
        INBOUND with InboundTerms) -> InvalidPermitScopeError
      - OutboundTerms.scopes must be non-empty
        -> InvalidPermitScopeError
      - OutboundTerms read_scope=ListMetadataOnly with
        onward_action_scope=MayExportOffPlatform collapses the matrix
        -> PermitScopeCollapseError
    """
    if state is not None:
        raise PermitAlreadyExistsError(state.id)

    peer_facility_id = command.peer_facility_id.strip()
    if not peer_facility_id:
        raise InvalidPermitScopeError("peer_facility_id must be non-empty")

    if command.expires_at <= now:
        raise InvalidPermitScopeError(
            f"expires_at must lie strictly after now ({now.isoformat()}); "
            f"got {command.expires_at.isoformat()}"
        )

    if not command.allowed_credential_ids:
        raise InvalidPermitScopeError("allowed_credential_ids must be non-empty")

    if not command.allowed_payload_types:
        raise InvalidPermitScopeError("allowed_payload_types must be non-empty")
    for payload_type in command.allowed_payload_types:
        if not payload_type.strip():
            raise InvalidPermitScopeError(
                "allowed_payload_types entries must be non-empty after trim"
            )

    if not command.allowed_artifact_kinds:
        raise InvalidPermitScopeError("allowed_artifact_kinds must be non-empty")
    for kind in command.allowed_artifact_kinds:
        if not kind.strip():
            raise InvalidPermitScopeError(
                "allowed_artifact_kinds entries must be non-empty after trim"
            )

    _ensure_direction_matches_terms(command.direction, command.terms)

    if isinstance(command.terms, OutboundTerms):
        _validate_outbound_terms(command.terms)

    return [
        PermitDefined(
            permit_id=new_id,
            peer_facility_id=peer_facility_id,
            direction=command.direction,
            allowed_credential_ids=command.allowed_credential_ids,
            allowed_payload_types=command.allowed_payload_types,
            allowed_artifact_kinds=command.allowed_artifact_kinds,
            abi_tier_floor=command.abi_tier_floor,
            expires_at=command.expires_at,
            defined_by=defined_by,
            terms=command.terms,
            occurred_at=now,
        )
    ]


def _ensure_direction_matches_terms(
    direction: Direction,
    terms: OutboundTerms | InboundTerms,
) -> None:
    if direction is Direction.OUTBOUND and not isinstance(terms, OutboundTerms):
        raise InvalidPermitScopeError("direction=Outbound requires OutboundTerms; got InboundTerms")
    if direction is Direction.INBOUND and not isinstance(terms, InboundTerms):
        raise InvalidPermitScopeError("direction=Inbound requires InboundTerms; got OutboundTerms")


def _validate_outbound_terms(terms: OutboundTerms) -> None:
    if not terms.scopes:
        raise InvalidPermitScopeError("OutboundTerms.scopes must be non-empty")
    if (
        terms.read_scope is ReadScope.LIST_METADATA_ONLY
        and terms.onward_action_scope is OnwardActionScope.MAY_EXPORT_OFF_PLATFORM
    ):
        raise PermitScopeCollapseError(
            "OutboundTerms collapse the matrix: read_scope=ListMetadataOnly "
            "has no artifact carrier for onward_action_scope=MayExportOffPlatform"
        )


__all__ = ["decide"]
