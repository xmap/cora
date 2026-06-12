"""Property-based tests for `suspend_permit.decide` (Federation BC).

Complements the example-based `test_suspend_permit_decider.py` with
universal claims across generated inputs. The decider is a pure
single-source FSM transition

    (state, command, now, suspended_by) -> list[PermitSuspended]

Load-bearing properties:

  - state=None always raises `PermitNotFoundError` carrying
    command.permit_id (existence guard fires before any FSM check).
  - The source-state partition is total over `PermitStatus`: only
    `Active` emits exactly one `PermitSuspended` (permit_id=state.id,
    occurred_at=now); every other status raises
    `PermitCannotSuspendError` carrying the current status, so a future
    status value cannot silently fall through.
  - The emitted event's permit_id is `state.id`, never command.permit_id;
    handler-injected `now` and `suspended_by` thread through verbatim.
  - Pure: same (state, command, now, suspended_by) returns equal events.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

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
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes, printable_ascii_text

_DEFINED_AT = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_EXPIRES_AT = datetime(2027, 5, 30, 12, 0, 0, tzinfo=UTC)
_DEFINED_BY = ActorId(UUID("01900000-0000-7000-8000-000000fed001"))

_SUSPENDABLE_SOURCES = (PermitStatus.ACTIVE,)
_DISALLOWED_SOURCES = tuple(s for s in PermitStatus if s not in frozenset(_SUSPENDABLE_SOURCES))


def _terms() -> OutboundTerms:
    return OutboundTerms(
        scopes=frozenset({ScopeRef(kind="dataset", name="alpha")}),
        read_scope=ReadScope.READ_ALL_ARTIFACTS,
        onward_action_scope=OnwardActionScope.READ_ONLY,
    )


def _permit(*, permit_id: UUID, status: PermitStatus) -> Permit:
    return Permit(
        id=permit_id,
        peer_facility_code=FacilityCode("aps-2bm"),
        direction=Direction.OUTBOUND,
        allowed_credential_ids=frozenset({UUID("01900000-0000-7000-8000-00000000c001")}),
        allowed_payload_types=frozenset({"application/vnd.cora.dataset+json"}),
        allowed_artifact_kinds=frozenset({"dataset"}),
        abi_tier_floor=AbiTier.STABLE,
        expires_at=_EXPIRES_AT,
        defined_by=_DEFINED_BY,
        defined_at=_DEFINED_AT,
        status=status,
        terms=_terms(),
    )


@pytest.mark.unit
@given(
    permit_id=st.uuids(),
    suspended_by=st.uuids(),
    now=aware_datetimes(),
    reason=st.none() | printable_ascii_text(max_size=32),
)
def test_suspend_with_none_state_always_raises_not_found(
    permit_id: UUID,
    suspended_by: UUID,
    now: datetime,
    reason: str | None,
) -> None:
    """Empty stream always raises `PermitNotFoundError` carrying command.permit_id."""
    with pytest.raises(PermitNotFoundError) as exc:
        suspend_permit.decide(
            state=None,
            command=SuspendPermit(permit_id=permit_id, reason=reason),
            now=now,
            suspended_by=ActorId(suspended_by),
        )
    assert exc.value.permit_id == permit_id


@pytest.mark.unit
@given(
    permit_id=st.uuids(),
    suspended_by=st.uuids(),
    now=aware_datetimes(),
    reason=st.none() | printable_ascii_text(max_size=32),
)
def test_suspend_from_active_emits_single_event(
    permit_id: UUID,
    suspended_by: UUID,
    now: datetime,
    reason: str | None,
) -> None:
    """Active is the only suspendable source; emits one PermitSuspended."""
    actor = ActorId(suspended_by)
    events = suspend_permit.decide(
        state=_permit(permit_id=permit_id, status=PermitStatus.ACTIVE),
        command=SuspendPermit(permit_id=permit_id, reason=reason),
        now=now,
        suspended_by=actor,
    )
    assert events == [
        PermitSuspended(
            permit_id=permit_id,
            suspended_by=actor,
            occurred_at=now,
            reason=reason,
        )
    ]


@pytest.mark.unit
@given(
    permit_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    suspended_by=st.uuids(),
    now=aware_datetimes(),
)
def test_suspend_from_disallowed_source_always_raises_cannot_suspend(
    permit_id: UUID,
    source: PermitStatus,
    suspended_by: UUID,
    now: datetime,
) -> None:
    """Any source other than Active raises, carrying the current status."""
    with pytest.raises(PermitCannotSuspendError) as exc:
        suspend_permit.decide(
            state=_permit(permit_id=permit_id, status=source),
            command=SuspendPermit(permit_id=permit_id),
            now=now,
            suspended_by=ActorId(suspended_by),
        )
    assert exc.value.current_status is source
    assert exc.value.permit_id == permit_id


@pytest.mark.unit
@given(
    state_permit_id=st.uuids(),
    command_permit_id=st.uuids(),
    suspended_by=st.uuids(),
    now=aware_datetimes(),
)
def test_suspend_uses_state_id_not_command_permit_id(
    state_permit_id: UUID,
    command_permit_id: UUID,
    suspended_by: UUID,
    now: datetime,
) -> None:
    """The emitted event's permit_id is state.id, not command.permit_id."""
    assume(state_permit_id != command_permit_id)
    events = suspend_permit.decide(
        state=_permit(permit_id=state_permit_id, status=PermitStatus.ACTIVE),
        command=SuspendPermit(permit_id=command_permit_id),
        now=now,
        suspended_by=ActorId(suspended_by),
    )
    assert events[0].permit_id == state_permit_id


@pytest.mark.unit
@given(
    permit_id=st.uuids(),
    suspended_by=st.uuids(),
    now=aware_datetimes(),
)
def test_suspend_threads_injected_now_and_actor_onto_event(
    permit_id: UUID,
    suspended_by: UUID,
    now: datetime,
) -> None:
    """Handler-injected `now` and `suspended_by` thread through verbatim."""
    actor = ActorId(suspended_by)
    events = suspend_permit.decide(
        state=_permit(permit_id=permit_id, status=PermitStatus.ACTIVE),
        command=SuspendPermit(permit_id=permit_id),
        now=now,
        suspended_by=actor,
    )
    assert events[0].occurred_at == now
    assert events[0].suspended_by == actor


@pytest.mark.unit
@given(
    permit_id=st.uuids(),
    suspended_by=st.uuids(),
    now=aware_datetimes(),
    reason=st.none() | printable_ascii_text(max_size=32),
)
def test_suspend_is_pure_same_input_same_output(
    permit_id: UUID,
    suspended_by: UUID,
    now: datetime,
    reason: str | None,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _permit(permit_id=permit_id, status=PermitStatus.ACTIVE)
    command = SuspendPermit(permit_id=permit_id, reason=reason)
    actor = ActorId(suspended_by)
    first = suspend_permit.decide(state=state, command=command, now=now, suspended_by=actor)
    second = suspend_permit.decide(state=state, command=command, now=now, suspended_by=actor)
    assert first == second
