"""Property-based tests for `reject_clearance.decide` (Safety BC).

Complements the example-based `test_reject_clearance_decider.py` with
universal claims across generated inputs. The decider is a pure
single-source FSM terminal

    (state, command, now) -> list[ClearanceRejected]

Load-bearing properties:

  - state=None always raises `ClearanceNotFoundError` carrying
    command.clearance_id.
  - The source-state partition is total over `ClearanceStatus`: only
    `UnderReview` emits exactly one `ClearanceRejected`
    (clearance_id=state.id, occurred_at=now); every other status raises
    `ClearanceCannotRejectError` carrying the current status, so a future
    status value cannot silently fall through.
  - The emitted event's clearance_id is `state.id`, never
    `command.clearance_id`.
  - The validated `reason` rides through onto the emitted event.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.safety.aggregates.clearance import (
    Clearance,
    ClearanceCannotRejectError,
    ClearanceNotFoundError,
    ClearanceRejected,
    ClearanceStatus,
    ClearanceTitle,
    RunBinding,
)
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateId,
    clearance_template_stream_id,
)
from cora.safety.features import reject_clearance
from cora.safety.features.reject_clearance import RejectClearance
from cora.shared.facility_code import FacilityCode
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime

_REASON = "ESRB found insufficient PPE specification"

_REJECTABLE_SOURCES = (ClearanceStatus.UNDER_REVIEW,)
_DISALLOWED_SOURCES = tuple(s for s in ClearanceStatus if s not in frozenset(_REJECTABLE_SOURCES))


def _clearance(*, clearance_id: UUID, status: ClearanceStatus) -> Clearance:
    return Clearance(
        id=clearance_id,
        template_id=ClearanceTemplateId(clearance_template_stream_id("aps", "ESAF")),
        facility_code=FacilityCode("aps"),
        title=ClearanceTitle("Pilot"),
        bindings=frozenset({RunBinding(run_id=UUID(int=7))}),
        status=status,
    )


@pytest.mark.unit
@given(clearance_id=st.uuids(), now=aware_datetimes())
def test_reject_with_none_state_always_raises_not_found(
    clearance_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `ClearanceNotFoundError` carrying the command id."""
    with pytest.raises(ClearanceNotFoundError) as exc:
        reject_clearance.decide(
            state=None,
            command=RejectClearance(clearance_id=clearance_id, reason=_REASON),
            now=now,
        )
    assert exc.value.clearance_id == clearance_id


@pytest.mark.unit
@given(clearance_id=st.uuids(), now=aware_datetimes())
def test_reject_from_under_review_emits_single_event(
    clearance_id: UUID,
    now: datetime,
) -> None:
    """UnderReview is the only rejectable source; emits one ClearanceRejected."""
    events = reject_clearance.decide(
        state=_clearance(clearance_id=clearance_id, status=ClearanceStatus.UNDER_REVIEW),
        command=RejectClearance(clearance_id=clearance_id, reason=_REASON),
        now=now,
    )
    assert events == [ClearanceRejected(clearance_id=clearance_id, reason=_REASON, occurred_at=now)]


@pytest.mark.unit
@given(
    clearance_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_reject_from_disallowed_source_always_raises_cannot_reject(
    clearance_id: UUID,
    source: ClearanceStatus,
    now: datetime,
) -> None:
    """Any source other than UnderReview raises, carrying the current status."""
    with pytest.raises(ClearanceCannotRejectError) as exc:
        reject_clearance.decide(
            state=_clearance(clearance_id=clearance_id, status=source),
            command=RejectClearance(clearance_id=clearance_id, reason=_REASON),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(state_id=st.uuids(), command_id=st.uuids(), now=aware_datetimes())
def test_reject_uses_state_id_not_command_clearance_id(
    state_id: UUID,
    command_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's clearance_id is state.id, not command.clearance_id."""
    assume(state_id != command_id)
    events = reject_clearance.decide(
        state=_clearance(clearance_id=state_id, status=ClearanceStatus.UNDER_REVIEW),
        command=RejectClearance(clearance_id=command_id, reason=_REASON),
        now=now,
    )
    assert events[0].clearance_id == state_id


@pytest.mark.unit
@given(clearance_id=st.uuids(), now=aware_datetimes())
def test_reject_threads_reason_onto_event(
    clearance_id: UUID,
    now: datetime,
) -> None:
    """The validated reason rides through onto the emitted event."""
    events = reject_clearance.decide(
        state=_clearance(clearance_id=clearance_id, status=ClearanceStatus.UNDER_REVIEW),
        command=RejectClearance(clearance_id=clearance_id, reason=_REASON),
        now=now,
    )
    assert events[0].reason == _REASON


@pytest.mark.unit
@given(clearance_id=st.uuids(), now=aware_datetimes())
def test_reject_is_pure_same_input_same_output(
    clearance_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _clearance(clearance_id=clearance_id, status=ClearanceStatus.UNDER_REVIEW)
    command = RejectClearance(clearance_id=clearance_id, reason=_REASON)
    first = reject_clearance.decide(state=state, command=command, now=now)
    second = reject_clearance.decide(state=state, command=command, now=now)
    assert first == second
