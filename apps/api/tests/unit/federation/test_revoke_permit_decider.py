"""Pure-decider tests for the `revoke_permit` slice.

Widest-source terminal transition: any non-Revoked status (Defined,
Active, or Suspended) -> Revoked. Strict-not-idempotent: re-revoking
an already-Revoked permit raises `PermitCannotRevokeError` per the
`deregister_supply` precedent.

`revoked_by` is handler-injected from the request
envelope's `principal_id` (capture-don't-recompute) and stamped onto
the emitted `PermitRevoked` event as the audit denorm.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.federation.aggregates.permit import (
    AbiTier,
    Direction,
    OnwardActionScope,
    OutboundTerms,
    Permit,
    PermitCannotRevokeError,
    PermitNotFoundError,
    PermitRevoked,
    PermitStatus,
    ReadScope,
    ScopeRef,
)
from cora.federation.features import revoke_permit
from cora.federation.features.revoke_permit import RevokePermit
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_PERMIT_ID = UUID("01900000-0000-7000-8000-000000fed001")
_DEFINED_BY_ACTOR_ID = ActorId(UUID("01900000-0000-7000-8000-000000fed002"))
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000fed003")
_EXPIRES_AT = datetime(2027, 1, 1, 0, 0, 0, tzinfo=UTC)
_CREDENTIAL_ID = UUID("01900000-0000-7000-8000-000000fed004")


def _outbound_terms() -> OutboundTerms:
    return OutboundTerms(
        scopes=frozenset({ScopeRef(kind="dataset", name="public", qualifier=None)}),
        read_scope=ReadScope.READ_ALL_ARTIFACTS,
        onward_action_scope=OnwardActionScope.READ_ONLY,
    )


def _permit(status: PermitStatus) -> Permit:
    return Permit(
        id=_PERMIT_ID,
        peer_facility_id="aps-2bm",
        direction=Direction.OUTBOUND,
        allowed_credential_ids=frozenset({_CREDENTIAL_ID}),
        allowed_payload_types=frozenset({"application/json"}),
        allowed_artifact_kinds=frozenset({"dataset"}),
        abi_tier_floor=AbiTier.STABLE,
        expires_at=_EXPIRES_AT,
        defined_by=_DEFINED_BY_ACTOR_ID,
        defined_at=_NOW,
        status=status,
        terms=_outbound_terms(),
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "current_status",
    [
        PermitStatus.DEFINED,
        PermitStatus.ACTIVE,
        PermitStatus.SUSPENDED,
    ],
)
def test_revoke_permit_emits_event_from_any_non_revoked_status(
    current_status: PermitStatus,
) -> None:
    events = revoke_permit.decide(
        state=_permit(current_status),
        command=RevokePermit(permit_id=_PERMIT_ID),
        now=_NOW,
        revoked_by=_PRINCIPAL_ID,
    )
    assert events == [
        PermitRevoked(
            permit_id=_PERMIT_ID,
            revoked_by=_PRINCIPAL_ID,
            occurred_at=_NOW,
            reason=None,
        )
    ]


@pytest.mark.unit
def test_revoke_permit_rejects_when_already_revoked() -> None:
    """Strict-not-idempotent: re-revoking a Revoked permit raises."""
    with pytest.raises(PermitCannotRevokeError) as exc_info:
        revoke_permit.decide(
            state=_permit(PermitStatus.REVOKED),
            command=RevokePermit(permit_id=_PERMIT_ID),
            now=_NOW,
            revoked_by=_PRINCIPAL_ID,
        )
    assert exc_info.value.permit_id == _PERMIT_ID
    assert exc_info.value.current_status == PermitStatus.REVOKED


@pytest.mark.unit
def test_revoke_permit_rejects_when_state_is_none() -> None:
    with pytest.raises(PermitNotFoundError) as exc_info:
        revoke_permit.decide(
            state=None,
            command=RevokePermit(permit_id=_PERMIT_ID),
            now=_NOW,
            revoked_by=_PRINCIPAL_ID,
        )
    assert exc_info.value.permit_id == _PERMIT_ID


@pytest.mark.unit
def test_revoke_permit_captures_handler_injected_revoked_by() -> None:
    """`revoked_by` is captured verbatim from the handler, not recomputed."""
    arbitrary_principal = uuid4()
    events = revoke_permit.decide(
        state=_permit(PermitStatus.ACTIVE),
        command=RevokePermit(permit_id=_PERMIT_ID),
        now=_NOW,
        revoked_by=arbitrary_principal,
    )
    assert events[0].revoked_by == arbitrary_principal


@pytest.mark.unit
def test_revoke_permit_uses_supplied_now_for_occurred_at() -> None:
    """Non-determinism injected from handler per project_non_determinism_principle."""
    custom_now = datetime(2099, 1, 1, 0, 0, 0, tzinfo=UTC)
    events = revoke_permit.decide(
        state=_permit(PermitStatus.DEFINED),
        command=RevokePermit(permit_id=_PERMIT_ID),
        now=custom_now,
        revoked_by=_PRINCIPAL_ID,
    )
    assert events[0].occurred_at == custom_now


@pytest.mark.unit
def test_revoke_permit_is_pure_same_inputs_same_outputs() -> None:
    state = _permit(PermitStatus.ACTIVE)
    command = RevokePermit(permit_id=_PERMIT_ID)
    first = revoke_permit.decide(state=state, command=command, now=_NOW, revoked_by=_PRINCIPAL_ID)
    second = revoke_permit.decide(state=state, command=command, now=_NOW, revoked_by=_PRINCIPAL_ID)
    assert first == second


@pytest.mark.unit
def test_revoke_permit_flows_reason_onto_event_payload() -> None:
    """`reason` is captured on the command and flows through to the
    emitted `PermitRevoked` event so operator context survives on
    the immutable event log."""
    events = revoke_permit.decide(
        state=_permit(PermitStatus.DEFINED),
        command=RevokePermit(permit_id=_PERMIT_ID, reason="peer decommissioned"),
        now=_NOW,
        revoked_by=_PRINCIPAL_ID,
    )
    event = events[0]
    assert isinstance(event, PermitRevoked)
    assert event.reason == "peer decommissioned"


@pytest.mark.unit
def test_revoke_permit_defaults_reason_to_none_when_omitted() -> None:
    """`reason` defaults to None on the command and the emitted event
    carries None when the operator did not supply one."""
    events = revoke_permit.decide(
        state=_permit(PermitStatus.DEFINED),
        command=RevokePermit(permit_id=_PERMIT_ID),
        now=_NOW,
        revoked_by=_PRINCIPAL_ID,
    )
    event = events[0]
    assert isinstance(event, PermitRevoked)
    assert event.reason is None
