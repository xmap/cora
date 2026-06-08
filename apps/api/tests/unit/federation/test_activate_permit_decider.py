"""Unit tests for the `activate_permit` slice's pure decider.

Pins the FSM single-source transition (`Defined -> Active`) plus the
strict-not-idempotent guard (re-activating any non-Defined permit raises
PermitCannotActivateError) and the `activated_by` capture from
handler-injected `principal_id`. Slice-level integration (handler ->
event-store) is covered by the handler tests.
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
    PermitActivated,
    PermitCannotActivateError,
    PermitNotFoundError,
    PermitStatus,
    ReadScope,
    ScopeRef,
)
from cora.federation.features import activate_permit
from cora.federation.features.activate_permit import ActivatePermit
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_EXPIRES_AT = datetime(2027, 5, 30, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000fed001")
_PERMIT_ID = UUID("01900000-0000-7000-8000-000000fed002")
_DEFINED_BY_ACTOR_ID = ActorId(UUID("01900000-0000-7000-8000-000000fed003"))


def _terms() -> OutboundTerms:
    return OutboundTerms(
        scopes=frozenset({ScopeRef(kind="dataset", name="alpha")}),
        read_scope=ReadScope.READ_ALL_ARTIFACTS,
        onward_action_scope=OnwardActionScope.READ_ONLY,
    )


def _existing_state(*, status: PermitStatus = PermitStatus.DEFINED) -> Permit:
    return Permit(
        id=_PERMIT_ID,
        peer_facility_id="aps-2bm",
        direction=Direction.OUTBOUND,
        allowed_credential_ids=frozenset({UUID("01900000-0000-7000-8000-00000000c001")}),
        allowed_payload_types=frozenset({"application/vnd.cora.dataset+json"}),
        allowed_artifact_kinds=frozenset({"dataset"}),
        abi_tier_floor=AbiTier.STABLE,
        expires_at=_EXPIRES_AT,
        defined_by=_DEFINED_BY_ACTOR_ID,
        defined_at=_NOW,
        status=status,
        terms=_terms(),
    )


def _command() -> ActivatePermit:
    return ActivatePermit(permit_id=_PERMIT_ID)


@pytest.mark.unit
def test_activate_permit_emits_event_for_defined_permit() -> None:
    events = activate_permit.decide(
        state=_existing_state(status=PermitStatus.DEFINED),
        command=_command(),
        now=_NOW,
        activated_by=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, PermitActivated)
    assert event.permit_id == _PERMIT_ID
    assert event.activated_by == _PRINCIPAL_ID
    assert event.occurred_at == _NOW


@pytest.mark.unit
def test_activate_permit_rejects_when_state_is_none() -> None:
    """No prior PermitDefined event -> handler folds to None -> NotFound."""
    with pytest.raises(PermitNotFoundError):
        activate_permit.decide(
            state=None,
            command=_command(),
            now=_NOW,
            activated_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_activate_permit_rejects_when_already_active() -> None:
    """Strict-not-idempotent: re-activating an Active permit raises."""
    with pytest.raises(PermitCannotActivateError) as excinfo:
        activate_permit.decide(
            state=_existing_state(status=PermitStatus.ACTIVE),
            command=_command(),
            now=_NOW,
            activated_by=_PRINCIPAL_ID,
        )
    assert excinfo.value.current_status is PermitStatus.ACTIVE


@pytest.mark.unit
def test_activate_permit_rejects_when_suspended() -> None:
    """Resume, not activate, is the path back from Suspended."""
    with pytest.raises(PermitCannotActivateError) as excinfo:
        activate_permit.decide(
            state=_existing_state(status=PermitStatus.SUSPENDED),
            command=_command(),
            now=_NOW,
            activated_by=_PRINCIPAL_ID,
        )
    assert excinfo.value.current_status is PermitStatus.SUSPENDED


@pytest.mark.unit
def test_activate_permit_rejects_when_revoked() -> None:
    """Revoked is terminal; no transition back to Active."""
    with pytest.raises(PermitCannotActivateError) as excinfo:
        activate_permit.decide(
            state=_existing_state(status=PermitStatus.REVOKED),
            command=_command(),
            now=_NOW,
            activated_by=_PRINCIPAL_ID,
        )
    assert excinfo.value.current_status is PermitStatus.REVOKED


@pytest.mark.unit
def test_activate_permit_captures_activated_by_from_handler_arg() -> None:
    """Handler injects `principal_id` as `activated_by`; the
    decider denorms it verbatim (non-determinism: capture, don't
    recompute)."""
    other_principal = UUID("01900000-0000-7000-8000-00000000c099")
    events = activate_permit.decide(
        state=_existing_state(status=PermitStatus.DEFINED),
        command=_command(),
        now=_NOW,
        activated_by=other_principal,
    )
    assert events[0].activated_by == other_principal


@pytest.mark.unit
def test_activate_permit_is_pure_same_inputs_same_outputs() -> None:
    first = activate_permit.decide(
        state=_existing_state(status=PermitStatus.DEFINED),
        command=_command(),
        now=_NOW,
        activated_by=_PRINCIPAL_ID,
    )
    second = activate_permit.decide(
        state=_existing_state(status=PermitStatus.DEFINED),
        command=_command(),
        now=_NOW,
        activated_by=_PRINCIPAL_ID,
    )
    assert first == second


@pytest.mark.unit
def test_activate_permit_does_not_mint_its_own_uuid() -> None:
    """Sanity: PermitActivated reuses state.id; decider never calls uuid4()."""
    rogue = uuid4()
    state = _existing_state(status=PermitStatus.DEFINED)
    events = activate_permit.decide(
        state=state,
        command=ActivatePermit(permit_id=rogue),
        now=_NOW,
        activated_by=_PRINCIPAL_ID,
    )
    assert events[0].permit_id == state.id
