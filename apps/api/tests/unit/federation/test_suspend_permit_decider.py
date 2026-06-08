"""Unit tests for the `suspend_permit` slice's pure decider.

Pin the FSM source-state guard (Active is the only legal source),
the not-found branch, idempotency (same inputs -> same outputs),
handler-injected `new_id`-style `suspended_by` reproducibility,
and the strict-not-idempotent posture (re-suspend a Suspended permit
raises rather than no-ops). Slice-level integration (handler ->
event-store -> projection) is covered by the integration suite.

`reason` flows from the command through the decider onto the emitted
`PermitSuspended` event payload so operator context survives on the
immutable event log; tests pin both the with-reason and the
None-default paths.
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
    PermitCannotSuspendError,
    PermitNotFoundError,
    PermitStatus,
    PermitSuspended,
    ReadScope,
    ScopeRef,
)
from cora.federation.features import suspend_permit
from cora.federation.features.suspend_permit import SuspendPermit
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_EXPIRES_AT = datetime(2027, 5, 30, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = ActorId(UUID("01900000-0000-7000-8000-000000fed001"))
_PERMIT_ID = UUID("01900000-0000-7000-8000-000000fed002")
_OTHER_ACTOR_ID = ActorId(UUID("01900000-0000-7000-8000-000000fed003"))


def _terms() -> OutboundTerms:
    return OutboundTerms(
        scopes=frozenset({ScopeRef(kind="dataset", name="alpha")}),
        read_scope=ReadScope.READ_ALL_ARTIFACTS,
        onward_action_scope=OnwardActionScope.READ_ONLY,
    )


def _permit(status: PermitStatus) -> Permit:
    return Permit(
        id=_PERMIT_ID,
        peer_facility_id="aps-2bm",
        direction=Direction.OUTBOUND,
        allowed_credential_ids=frozenset({UUID("01900000-0000-7000-8000-00000000c001")}),
        allowed_payload_types=frozenset({"application/vnd.cora.dataset+json"}),
        allowed_artifact_kinds=frozenset({"dataset"}),
        abi_tier_floor=AbiTier.STABLE,
        expires_at=_EXPIRES_AT,
        defined_by=_PRINCIPAL_ID,
        defined_at=_NOW,
        status=status,
        terms=_terms(),
    )


def _command(**overrides: object) -> SuspendPermit:
    base: dict[str, object] = {"permit_id": _PERMIT_ID, "reason": "operator pause"}
    base.update(overrides)
    return SuspendPermit(**base)  # type: ignore[arg-type]


@pytest.mark.unit
def test_suspend_permit_emits_event_when_state_is_active() -> None:
    state = _permit(PermitStatus.ACTIVE)
    events = suspend_permit.decide(
        state=state,
        command=_command(),
        now=_NOW,
        suspended_by=_PRINCIPAL_ID,
    )
    assert events == [
        PermitSuspended(
            permit_id=_PERMIT_ID,
            suspended_by=_PRINCIPAL_ID,
            occurred_at=_NOW,
            reason="operator pause",
        )
    ]


@pytest.mark.unit
def test_suspend_permit_rejects_when_state_is_none() -> None:
    """The permit must exist; missing state raises PermitNotFoundError."""
    with pytest.raises(PermitNotFoundError):
        suspend_permit.decide(
            state=None,
            command=_command(),
            now=_NOW,
            suspended_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_suspend_permit_rejects_when_state_is_defined() -> None:
    """Defined permits must be Activated first; suspend rejects."""
    state = _permit(PermitStatus.DEFINED)
    with pytest.raises(PermitCannotSuspendError):
        suspend_permit.decide(
            state=state,
            command=_command(),
            now=_NOW,
            suspended_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_suspend_permit_rejects_when_already_suspended() -> None:
    """Strict-not-idempotent: re-suspending raises rather than no-ops."""
    state = _permit(PermitStatus.SUSPENDED)
    with pytest.raises(PermitCannotSuspendError):
        suspend_permit.decide(
            state=state,
            command=_command(),
            now=_NOW,
            suspended_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_suspend_permit_rejects_when_revoked() -> None:
    """Revoked is terminal; suspend rejects."""
    state = _permit(PermitStatus.REVOKED)
    with pytest.raises(PermitCannotSuspendError):
        suspend_permit.decide(
            state=state,
            command=_command(),
            now=_NOW,
            suspended_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_suspend_permit_flows_reason_onto_event_payload() -> None:
    """`reason` is captured on the command and flows through to the
    emitted `PermitSuspended` event so operator context survives on
    the immutable event log."""
    state = _permit(PermitStatus.ACTIVE)
    events = suspend_permit.decide(
        state=state,
        command=_command(reason="peer paused pending PII review"),
        now=_NOW,
        suspended_by=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, PermitSuspended)
    assert event.reason == "peer paused pending PII review"


@pytest.mark.unit
def test_suspend_permit_defaults_reason_to_none_when_omitted() -> None:
    """`reason` defaults to None on the command and the emitted event
    carries None when the operator did not supply one."""
    state = _permit(PermitStatus.ACTIVE)
    events = suspend_permit.decide(
        state=state,
        command=SuspendPermit(permit_id=_PERMIT_ID),
        now=_NOW,
        suspended_by=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, PermitSuspended)
    assert event.reason is None
    assert event.suspended_by == _PRINCIPAL_ID


@pytest.mark.unit
def test_suspend_permit_is_pure_same_inputs_same_outputs() -> None:
    state = _permit(PermitStatus.ACTIVE)
    first = suspend_permit.decide(
        state=state,
        command=_command(),
        now=_NOW,
        suspended_by=_PRINCIPAL_ID,
    )
    second = suspend_permit.decide(
        state=state,
        command=_command(),
        now=_NOW,
        suspended_by=_PRINCIPAL_ID,
    )
    assert first == second


@pytest.mark.unit
def test_suspend_permit_uses_handler_injected_actor_id_verbatim() -> None:
    """Sanity: handler-injected `suspended_by` is used verbatim;
    decider doesn't synthesize it."""
    state = _permit(PermitStatus.ACTIVE)
    injected = uuid4()
    events = suspend_permit.decide(
        state=state,
        command=_command(),
        now=_NOW,
        suspended_by=injected,
    )
    assert events[0].suspended_by == injected


@pytest.mark.unit
def test_suspend_permit_uses_handler_injected_now_verbatim() -> None:
    """`now` is injected from the handler's clock per the
    non-determinism principle; the decider records it verbatim."""
    state = _permit(PermitStatus.ACTIVE)
    custom_now = datetime(2027, 1, 15, 9, 30, 0, tzinfo=UTC)
    events = suspend_permit.decide(
        state=state,
        command=_command(),
        now=custom_now,
        suspended_by=_PRINCIPAL_ID,
    )
    assert events[0].occurred_at == custom_now


@pytest.mark.unit
def test_suspend_permit_actor_id_independent_of_defined_by() -> None:
    """The suspending actor need NOT be the genesis-defining actor;
    the emitted event records whichever id the handler injects."""
    state = _permit(PermitStatus.ACTIVE)
    events = suspend_permit.decide(
        state=state,
        command=_command(),
        now=_NOW,
        suspended_by=_OTHER_ACTOR_ID,
    )
    assert events[0].suspended_by == _OTHER_ACTOR_ID
    assert state.defined_by == _PRINCIPAL_ID
