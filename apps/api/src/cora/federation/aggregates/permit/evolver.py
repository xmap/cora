"""Evolver: replay events to reconstruct Permit state.

Status mapping per event type:

  - `PermitDefined`:   DEFINED   (genesis)
  - `PermitActivated`: ACTIVE
  - `PermitSuspended`: SUSPENDED
  - `PermitResumed`:   ACTIVE    (audit twin of Activated)
  - `PermitRevoked`:   REVOKED   (terminal)

Source-state guards live at the decider, NOT here; the evolver
trusts the event log (folded events have already passed their
decider). Transition events applied to empty state raise
`ValueError` via the shared `require_state` helper at
`cora.infrastructure.evolver`.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.federation.aggregates.permit.events import (
    PermitActivated,
    PermitDefined,
    PermitEvent,
    PermitResumed,
    PermitRevoked,
    PermitSuspended,
    PublicationReceiptRecorded,
)
from cora.federation.aggregates.permit.state import Permit, PermitStatus
from cora.infrastructure.evolver import require_state


def evolve(state: Permit | None, event: PermitEvent) -> Permit:
    match event:
        case PermitDefined(
            permit_id=permit_id,
            peer_facility_id=peer_facility_id,
            direction=direction,
            allowed_credential_ids=allowed_credential_ids,
            allowed_payload_types=allowed_payload_types,
            allowed_artifact_kinds=allowed_artifact_kinds,
            abi_tier_floor=abi_tier_floor,
            expires_at=expires_at,
            defined_by_actor_id=defined_by_actor_id,
            terms=terms,
        ):
            _ = state
            return Permit(
                id=permit_id,
                peer_facility_id=peer_facility_id,
                direction=direction,
                allowed_credential_ids=allowed_credential_ids,
                allowed_payload_types=allowed_payload_types,
                allowed_artifact_kinds=allowed_artifact_kinds,
                abi_tier_floor=abi_tier_floor,
                expires_at=expires_at,
                defined_by_actor_id=defined_by_actor_id,
                status=PermitStatus.DEFINED,
                terms=terms,
            )
        case PermitActivated():
            prior = require_state(state, "PermitActivated")
            return _replace_status(prior, PermitStatus.ACTIVE)
        case PermitSuspended():
            prior = require_state(state, "PermitSuspended")
            return _replace_status(prior, PermitStatus.SUSPENDED)
        case PermitResumed():
            prior = require_state(state, "PermitResumed")
            return _replace_status(prior, PermitStatus.ACTIVE)
        case PermitRevoked():
            prior = require_state(state, "PermitRevoked")
            return _replace_status(prior, PermitStatus.REVOKED)
        case PublicationReceiptRecorded():
            prior = require_state(state, "PublicationReceiptRecorded")
            return prior
        case _:  # pragma: no cover
            assert_never(event)


def _replace_status(prior: Permit, new_status: PermitStatus) -> Permit:
    return Permit(
        id=prior.id,
        peer_facility_id=prior.peer_facility_id,
        direction=prior.direction,
        allowed_credential_ids=prior.allowed_credential_ids,
        allowed_payload_types=prior.allowed_payload_types,
        allowed_artifact_kinds=prior.allowed_artifact_kinds,
        abi_tier_floor=prior.abi_tier_floor,
        expires_at=prior.expires_at,
        defined_by_actor_id=prior.defined_by_actor_id,
        status=new_status,
        terms=prior.terms,
    )


def fold(events: Sequence[PermitEvent]) -> Permit | None:
    state: Permit | None = None
    for event in events:
        state = evolve(state, event)
    return state
