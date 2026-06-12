"""Property-based tests for `resume_permit.decide` (Federation BC).

Complements the example-based `test_resume_permit_decider.py` with
universal claims across generated inputs. The decider is a pure
single-source FSM transition

    (state, command, now, resumed_by) -> list[PermitResumed]

Load-bearing properties:

  - state=None always raises `PermitNotFoundError` carrying
    command.permit_id (the existence guard fires before any FSM read).
  - The source-state partition is total over `PermitStatus`: only
    `Suspended` emits exactly one `PermitResumed`; every other status
    raises `PermitCannotResumeError` carrying state.id and the current
    status, so a future status value cannot silently fall through.
  - The emitted event's permit_id is `state.id`, never command.permit_id,
    and resumed_by / occurred_at thread the injected fields verbatim.
  - Pure: same (state, command, now, resumed_by) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
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
    PermitCannotResumeError,
    PermitNotFoundError,
    PermitResumed,
    PermitStatus,
    ReadScope,
    ScopeRef,
)
from cora.federation.features import resume_permit
from cora.federation.features.resume_permit import ResumePermit
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime

_PEER_FACILITY_CODE = FacilityCode("aps-2bm")
_DEFINING_PRINCIPAL_ID = ActorId(UUID("01900000-0000-7000-8000-000000fed003"))

_RESUMABLE_SOURCES = (PermitStatus.SUSPENDED,)
_DISALLOWED_SOURCES = tuple(s for s in PermitStatus if s not in frozenset(_RESUMABLE_SOURCES))


def _terms() -> OutboundTerms:
    return OutboundTerms(
        scopes=frozenset({ScopeRef(kind="dataset", name="ct-2bm")}),
        read_scope=ReadScope.READ_ALL_ARTIFACTS,
        onward_action_scope=OnwardActionScope.READ_ONLY,
    )


def _permit(*, permit_id: UUID, status: PermitStatus, now: datetime) -> Permit:
    return Permit(
        id=permit_id,
        peer_facility_code=_PEER_FACILITY_CODE,
        direction=Direction.OUTBOUND,
        allowed_credential_ids=frozenset(),
        allowed_payload_types=frozenset({"application/cora.dataset+json"}),
        allowed_artifact_kinds=frozenset({"dataset"}),
        abi_tier_floor=AbiTier.STABLE,
        expires_at=now,
        defined_by=_DEFINING_PRINCIPAL_ID,
        defined_at=now,
        status=status,
        terms=_terms(),
    )


@pytest.mark.unit
@given(permit_id=st.uuids(), now=aware_datetimes(), resumed_by=st.uuids())
def test_resume_with_none_state_always_raises_not_found(
    permit_id: UUID,
    now: datetime,
    resumed_by: UUID,
) -> None:
    """Empty stream always raises `PermitNotFoundError` carrying command.permit_id."""
    with pytest.raises(PermitNotFoundError) as exc:
        resume_permit.decide(
            state=None,
            command=ResumePermit(permit_id=permit_id),
            now=now,
            resumed_by=resumed_by,
        )
    assert exc.value.permit_id == permit_id


@pytest.mark.unit
@given(permit_id=st.uuids(), now=aware_datetimes(), resumed_by=st.uuids())
def test_resume_from_suspended_emits_single_event(
    permit_id: UUID,
    now: datetime,
    resumed_by: UUID,
) -> None:
    """Suspended is the only resumable source; emits one PermitResumed."""
    events = resume_permit.decide(
        state=_permit(permit_id=permit_id, status=PermitStatus.SUSPENDED, now=now),
        command=ResumePermit(permit_id=permit_id),
        now=now,
        resumed_by=resumed_by,
    )
    assert events == [PermitResumed(permit_id=permit_id, resumed_by=resumed_by, occurred_at=now)]


@pytest.mark.unit
@given(
    permit_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
    resumed_by=st.uuids(),
)
def test_resume_from_disallowed_source_always_raises_cannot_resume(
    permit_id: UUID,
    source: PermitStatus,
    now: datetime,
    resumed_by: UUID,
) -> None:
    """Any source other than Suspended raises, carrying state.id and status."""
    with pytest.raises(PermitCannotResumeError) as exc:
        resume_permit.decide(
            state=_permit(permit_id=permit_id, status=source, now=now),
            command=ResumePermit(permit_id=permit_id),
            now=now,
            resumed_by=resumed_by,
        )
    assert exc.value.current_status is source
    assert exc.value.permit_id == permit_id


@pytest.mark.unit
@given(
    state_permit_id=st.uuids(),
    command_permit_id=st.uuids(),
    now=aware_datetimes(),
    resumed_by=st.uuids(),
)
def test_resume_uses_state_id_not_command_permit_id(
    state_permit_id: UUID,
    command_permit_id: UUID,
    now: datetime,
    resumed_by: UUID,
) -> None:
    """The emitted event's permit_id is state.id, not command.permit_id."""
    assume(state_permit_id != command_permit_id)
    events = resume_permit.decide(
        state=_permit(permit_id=state_permit_id, status=PermitStatus.SUSPENDED, now=now),
        command=ResumePermit(permit_id=command_permit_id),
        now=now,
        resumed_by=resumed_by,
    )
    assert events[0].permit_id == state_permit_id


@pytest.mark.unit
@given(permit_id=st.uuids(), now=aware_datetimes(), resumed_by=st.uuids())
def test_resume_threads_injected_fields_onto_event(
    permit_id: UUID,
    now: datetime,
    resumed_by: UUID,
) -> None:
    """Handler-injected resumed_by and now ride verbatim onto the event."""
    events = resume_permit.decide(
        state=_permit(permit_id=permit_id, status=PermitStatus.SUSPENDED, now=now),
        command=ResumePermit(permit_id=permit_id),
        now=now,
        resumed_by=resumed_by,
    )
    assert events[0].resumed_by == resumed_by
    assert events[0].occurred_at == now


@pytest.mark.unit
@given(permit_id=st.uuids(), now=aware_datetimes(), resumed_by=st.uuids())
def test_resume_is_pure_same_input_same_output(
    permit_id: UUID,
    now: datetime,
    resumed_by: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _permit(permit_id=permit_id, status=PermitStatus.SUSPENDED, now=now)
    command = ResumePermit(permit_id=permit_id)
    first = resume_permit.decide(state=state, command=command, now=now, resumed_by=resumed_by)
    second = resume_permit.decide(state=state, command=command, now=now, resumed_by=resumed_by)
    assert first == second
