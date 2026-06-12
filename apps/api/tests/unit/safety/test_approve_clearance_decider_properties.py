"""Property-based tests for `approve_clearance.decide` (Safety BC).

Complements the example-based `test_approve_clearance_decider.py` with
universal claims across generated inputs. The decider is a pure
single-source FSM transition with an optional validity window

    (state, command, now) -> list[ClearanceApproved]

Load-bearing properties:

  - state=None always raises `ClearanceNotFoundError` carrying
    command.clearance_id, regardless of clock.
  - The source-state partition is total over `ClearanceStatus`: only
    `UnderReview` (with an Approved terminal review step) can emit; every
    other status raises `ClearanceCannotApproveError` carrying the current
    status, so a future status value cannot silently fall through. The
    status guard fires before the review-chain and window guards.
  - Happy path emits exactly one `ClearanceApproved` whose clearance_id is
    `state.id` (never `command.clearance_id`), threading the command's
    validity window and occurred_at=now.
  - An inverted window (valid_from >= valid_until) raises
    `InvalidClearanceValidityWindowError` carrying both bounds.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.safety.aggregates.clearance import (
    Clearance,
    ClearanceApproved,
    ClearanceCannotApproveError,
    ClearanceNotFoundError,
    ClearanceStatus,
    ClearanceTitle,
    InvalidClearanceValidityWindowError,
    ReviewStep,
    RunBinding,
)
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateId,
    clearance_template_stream_id,
)
from cora.safety.features import approve_clearance
from cora.safety.features.approve_clearance import ApproveClearance
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes, printable_ascii_text

_FIXED_NOW_DT = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_VALID_FROM = datetime(2026, 5, 16, tzinfo=UTC)
_VALID_UNTIL = datetime(2026, 6, 15, tzinfo=UTC)

_APPROVABLE_SOURCES = (ClearanceStatus.UNDER_REVIEW,)
_DISALLOWED_SOURCES = tuple(s for s in ClearanceStatus if s not in frozenset(_APPROVABLE_SOURCES))


def _approving_step(step_index: int = 0) -> ReviewStep:
    return ReviewStep(
        step_index=step_index,
        role="ESH",
        decided_by=ActorId(uuid4()),
        decision="Approved",
        decided_at=_FIXED_NOW_DT,
    )


def _clearance(
    *,
    clearance_id: UUID,
    status: ClearanceStatus = ClearanceStatus.UNDER_REVIEW,
    title: str = "Pilot",
    review_steps: tuple[ReviewStep, ...] = (),
) -> Clearance:
    return Clearance(
        id=clearance_id,
        template_id=ClearanceTemplateId(clearance_template_stream_id("aps", "ESAF")),
        facility_code=FacilityCode("aps"),
        title=ClearanceTitle(title),
        bindings=frozenset({RunBinding(run_id=uuid4())}),
        review_steps=review_steps,
        status=status,
    )


@pytest.mark.unit
@given(clearance_id=st.uuids(), now=aware_datetimes())
def test_approve_with_none_state_always_raises_not_found(
    clearance_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `ClearanceNotFoundError` carrying command id."""
    with pytest.raises(ClearanceNotFoundError) as exc:
        approve_clearance.decide(
            state=None,
            command=ApproveClearance(clearance_id=clearance_id),
            now=now,
        )
    assert exc.value.clearance_id == clearance_id


@pytest.mark.unit
@given(
    clearance_id=st.uuids(),
    title=printable_ascii_text(max_size=32),
    now=aware_datetimes(),
)
def test_approve_from_under_review_emits_single_event(
    clearance_id: UUID,
    title: str,
    now: datetime,
) -> None:
    """UnderReview with an Approved terminal step emits one ClearanceApproved."""
    events = approve_clearance.decide(
        state=_clearance(
            clearance_id=clearance_id,
            title=title,
            review_steps=(_approving_step(),),
        ),
        command=ApproveClearance(clearance_id=clearance_id),
        now=now,
    )
    assert events == [
        ClearanceApproved(
            clearance_id=clearance_id,
            valid_from=None,
            valid_until=None,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    clearance_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_approve_from_disallowed_source_always_raises_cannot_approve(
    clearance_id: UUID,
    source: ClearanceStatus,
    now: datetime,
) -> None:
    """Any source other than UnderReview raises, carrying the current status.

    The status guard fires before the review-chain guard, so an Approved
    terminal step on a disallowed status still raises.
    """
    with pytest.raises(ClearanceCannotApproveError) as exc:
        approve_clearance.decide(
            state=_clearance(
                clearance_id=clearance_id,
                status=source,
                review_steps=(_approving_step(),),
            ),
            command=ApproveClearance(clearance_id=clearance_id),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(state_id=st.uuids(), command_id=st.uuids(), now=aware_datetimes())
def test_approve_uses_state_id_not_command_clearance_id(
    state_id: UUID,
    command_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's clearance_id is state.id, not command.clearance_id."""
    assume(state_id != command_id)
    events = approve_clearance.decide(
        state=_clearance(clearance_id=state_id, review_steps=(_approving_step(),)),
        command=ApproveClearance(clearance_id=command_id),
        now=now,
    )
    assert events[0].clearance_id == state_id


@pytest.mark.unit
@given(clearance_id=st.uuids(), now=aware_datetimes())
def test_approve_threads_validity_window_and_occurred_at(
    clearance_id: UUID,
    now: datetime,
) -> None:
    """A valid window (valid_from < valid_until) threads onto the event."""
    events = approve_clearance.decide(
        state=_clearance(clearance_id=clearance_id, review_steps=(_approving_step(),)),
        command=ApproveClearance(
            clearance_id=clearance_id,
            valid_from=_VALID_FROM,
            valid_until=_VALID_UNTIL,
        ),
        now=now,
    )
    assert events[0].valid_from == _VALID_FROM
    assert events[0].valid_until == _VALID_UNTIL
    assert events[0].occurred_at == now


@pytest.mark.unit
@given(clearance_id=st.uuids(), now=aware_datetimes())
def test_approve_with_inverted_window_always_raises_invalid_window(
    clearance_id: UUID,
    now: datetime,
) -> None:
    """An inverted window raises, carrying both bounds in order supplied."""
    with pytest.raises(InvalidClearanceValidityWindowError) as exc:
        approve_clearance.decide(
            state=_clearance(clearance_id=clearance_id, review_steps=(_approving_step(),)),
            command=ApproveClearance(
                clearance_id=clearance_id,
                valid_from=_VALID_UNTIL,
                valid_until=_VALID_FROM,
            ),
            now=now,
        )
    assert exc.value.valid_from == _VALID_UNTIL
    assert exc.value.valid_until == _VALID_FROM


@pytest.mark.unit
@given(clearance_id=st.uuids(), now=aware_datetimes())
def test_approve_is_pure_same_input_same_output(
    clearance_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _clearance(clearance_id=clearance_id, review_steps=(_approving_step(),))
    command = ApproveClearance(clearance_id=clearance_id)
    first = approve_clearance.decide(state=state, command=command, now=now)
    second = approve_clearance.decide(state=state, command=command, now=now)
    assert first == second
