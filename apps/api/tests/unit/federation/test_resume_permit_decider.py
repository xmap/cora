"""Unit tests for the `resume_permit` slice's pure decider.

Pin the not-found guard, the single-source FSM precondition
(`Suspended` only), the strict-not-idempotent posture (rejects every
non-Suspended status), envelope passthrough (resumed_by +
occurred_at), idempotency under repeated inputs, and reproducibility
of the handler-injected payload. Slice-level integration (handler ->
event-store -> projection) is covered by the integration suite.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.federation.aggregates.permit import (
    AbiTier,
    Direction,
    OnwardActionScope,
    OutboundTerms,
    Permit,
    PermitCannotResumeError,
    PermitNotFoundError,
    PermitResumed,
    PermitStatus,
    ReadScope,
    ScopeRef,
)
from cora.federation.features import resume_permit
from cora.federation.features.resume_permit import ResumePermit
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000fed001")
_PERMIT_ID = UUID("01900000-0000-7000-8000-000000fed002")
_DEFINING_PRINCIPAL_ID = ActorId(UUID("01900000-0000-7000-8000-000000fed003"))
_EXPIRES_AT = datetime(2026, 12, 31, 23, 59, 59, tzinfo=UTC)


def _terms() -> OutboundTerms:
    return OutboundTerms(
        scopes=frozenset({ScopeRef(kind="dataset", name="ct-2bm")}),
        read_scope=ReadScope.READ_ALL_ARTIFACTS,
        onward_action_scope=OnwardActionScope.READ_ONLY,
    )


def _existing_permit(*, status: PermitStatus) -> Permit:
    return Permit(
        id=_PERMIT_ID,
        peer_facility_id="aps-2bm",
        direction=Direction.OUTBOUND,
        allowed_credential_ids=frozenset(),
        allowed_payload_types=frozenset({"application/cora.dataset+json"}),
        allowed_artifact_kinds=frozenset({"dataset"}),
        abi_tier_floor=AbiTier.STABLE,
        expires_at=_EXPIRES_AT,
        defined_by=_DEFINING_PRINCIPAL_ID,
        defined_at=_NOW,
        status=status,
        terms=_terms(),
    )


def _command() -> ResumePermit:
    return ResumePermit(permit_id=_PERMIT_ID)


@pytest.mark.unit
def test_resume_permit_emits_event_for_suspended_permit() -> None:
    events = resume_permit.decide(
        state=_existing_permit(status=PermitStatus.SUSPENDED),
        command=_command(),
        now=_NOW,
        resumed_by=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, PermitResumed)
    assert event.permit_id == _PERMIT_ID
    assert event.resumed_by == _PRINCIPAL_ID
    assert event.occurred_at == _NOW


@pytest.mark.unit
def test_resume_permit_captures_resumed_by_from_principal() -> None:
    """Handler-injected resumed_by rides verbatim onto the event."""
    other_principal = UUID("01900000-0000-7000-8000-000000fedaaa")
    events = resume_permit.decide(
        state=_existing_permit(status=PermitStatus.SUSPENDED),
        command=_command(),
        now=_NOW,
        resumed_by=other_principal,
    )
    assert events[0].resumed_by == other_principal
    assert events[0].resumed_by != _DEFINING_PRINCIPAL_ID


@pytest.mark.unit
def test_resume_permit_rejects_when_state_is_none() -> None:
    with pytest.raises(PermitNotFoundError):
        resume_permit.decide(
            state=None,
            command=_command(),
            now=_NOW,
            resumed_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_resume_permit_rejects_when_status_is_defined() -> None:
    """`Defined` permits need `activate_permit`, not `resume_permit`."""
    with pytest.raises(PermitCannotResumeError):
        resume_permit.decide(
            state=_existing_permit(status=PermitStatus.DEFINED),
            command=_command(),
            now=_NOW,
            resumed_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_resume_permit_rejects_when_status_is_active_strict_not_idempotent() -> None:
    """Already-Active permits MUST raise: strict-not-idempotent posture."""
    with pytest.raises(PermitCannotResumeError):
        resume_permit.decide(
            state=_existing_permit(status=PermitStatus.ACTIVE),
            command=_command(),
            now=_NOW,
            resumed_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_resume_permit_rejects_when_status_is_revoked() -> None:
    """`Revoked` is terminal: resume after revoke MUST raise."""
    with pytest.raises(PermitCannotResumeError):
        resume_permit.decide(
            state=_existing_permit(status=PermitStatus.REVOKED),
            command=_command(),
            now=_NOW,
            resumed_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_resume_permit_is_pure_same_inputs_same_outputs() -> None:
    first = resume_permit.decide(
        state=_existing_permit(status=PermitStatus.SUSPENDED),
        command=_command(),
        now=_NOW,
        resumed_by=_PRINCIPAL_ID,
    )
    second = resume_permit.decide(
        state=_existing_permit(status=PermitStatus.SUSPENDED),
        command=_command(),
        now=_NOW,
        resumed_by=_PRINCIPAL_ID,
    )
    assert first == second
