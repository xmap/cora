"""Property-based tests for `start_clearance_review.decide` (Safety BC).

Complements the example-based `test_start_clearance_review_decider.py`
with universal claims across generated inputs. The decider is a pure
single-source FSM transition

    (state, command, now) -> list[ClearanceReviewStarted]

Load-bearing properties:

  - state=None always raises `ClearanceNotFoundError` carrying
    command.clearance_id.
  - The source-state partition is total over `ClearanceStatus`: only
    `Submitted` emits exactly one `ClearanceReviewStarted`
    (clearance_id=state.id, occurred_at=now); every other status raises
    `ClearanceCannotStartReviewError` carrying the current status, so a
    future status value cannot silently fall through.
  - The emitted event's clearance_id is `state.id`, never
    `command.clearance_id`.
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
    ClearanceCannotStartReviewError,
    ClearanceNotFoundError,
    ClearanceReviewStarted,
    ClearanceStatus,
    ClearanceTitle,
    RunBinding,
)
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateId,
    clearance_template_stream_id,
)
from cora.safety.features import start_clearance_review
from cora.safety.features.start_clearance_review import StartClearanceReview
from cora.shared.facility_code import FacilityCode
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_REVIEWER_ROLE = "BeamlineScientist"
_REVIEWER_ROLE_MAX_LENGTH = 50

_REVIEW_STARTABLE_SOURCES = (ClearanceStatus.SUBMITTED,)
_DISALLOWED_SOURCES = tuple(
    s for s in ClearanceStatus if s not in frozenset(_REVIEW_STARTABLE_SOURCES)
)


def _clearance(*, clearance_id: UUID, status: ClearanceStatus) -> Clearance:
    return Clearance(
        id=clearance_id,
        template_id=ClearanceTemplateId(clearance_template_stream_id("aps", "ESAF")),
        facility_code=FacilityCode("aps"),
        title=ClearanceTitle("Pilot"),
        bindings=frozenset({RunBinding(run_id=UUID(int=1))}),
        status=status,
    )


@pytest.mark.unit
@given(clearance_id=st.uuids(), now=aware_datetimes())
def test_start_review_with_none_state_always_raises_not_found(
    clearance_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `ClearanceNotFoundError` with command id."""
    with pytest.raises(ClearanceNotFoundError) as exc:
        start_clearance_review.decide(
            state=None,
            command=StartClearanceReview(
                clearance_id=clearance_id,
                first_reviewer_role=_REVIEWER_ROLE,
            ),
            now=now,
        )
    assert exc.value.clearance_id == clearance_id


@pytest.mark.unit
@given(clearance_id=st.uuids(), now=aware_datetimes())
def test_start_review_from_submitted_emits_single_event(
    clearance_id: UUID,
    now: datetime,
) -> None:
    """Submitted is the only startable source; emits one ClearanceReviewStarted."""
    events = start_clearance_review.decide(
        state=_clearance(clearance_id=clearance_id, status=ClearanceStatus.SUBMITTED),
        command=StartClearanceReview(
            clearance_id=clearance_id,
            first_reviewer_role=_REVIEWER_ROLE,
        ),
        now=now,
    )
    assert events == [
        ClearanceReviewStarted(
            clearance_id=clearance_id,
            first_reviewer_role=_REVIEWER_ROLE,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    clearance_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_start_review_from_disallowed_source_always_raises_cannot_start(
    clearance_id: UUID,
    source: ClearanceStatus,
    now: datetime,
) -> None:
    """Any source other than Submitted raises, carrying the current status."""
    with pytest.raises(ClearanceCannotStartReviewError) as exc:
        start_clearance_review.decide(
            state=_clearance(clearance_id=clearance_id, status=source),
            command=StartClearanceReview(
                clearance_id=clearance_id,
                first_reviewer_role=_REVIEWER_ROLE,
            ),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    state_clearance_id=st.uuids(),
    command_clearance_id=st.uuids(),
    now=aware_datetimes(),
)
def test_start_review_uses_state_id_not_command_clearance_id(
    state_clearance_id: UUID,
    command_clearance_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's clearance_id is state.id, not command.clearance_id."""
    assume(state_clearance_id != command_clearance_id)
    events = start_clearance_review.decide(
        state=_clearance(clearance_id=state_clearance_id, status=ClearanceStatus.SUBMITTED),
        command=StartClearanceReview(
            clearance_id=command_clearance_id,
            first_reviewer_role=_REVIEWER_ROLE,
        ),
        now=now,
    )
    assert events[0].clearance_id == state_clearance_id


@pytest.mark.unit
@given(
    clearance_id=st.uuids(),
    role=printable_ascii_text(max_size=_REVIEWER_ROLE_MAX_LENGTH),
    now=aware_datetimes(),
)
def test_start_review_threads_trimmed_role_into_event(
    clearance_id: UUID,
    role: str,
    now: datetime,
) -> None:
    """Any valid generated role is canonicalized and threaded into the event."""
    events = start_clearance_review.decide(
        state=_clearance(clearance_id=clearance_id, status=ClearanceStatus.SUBMITTED),
        command=StartClearanceReview(clearance_id=clearance_id, first_reviewer_role=role),
        now=now,
    )
    assert events[0].first_reviewer_role == role.strip()


@pytest.mark.unit
@given(clearance_id=st.uuids(), now=aware_datetimes())
def test_start_review_is_pure_same_input_same_output(
    clearance_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _clearance(clearance_id=clearance_id, status=ClearanceStatus.SUBMITTED)
    command = StartClearanceReview(
        clearance_id=clearance_id,
        first_reviewer_role=_REVIEWER_ROLE,
    )
    first = start_clearance_review.decide(state=state, command=command, now=now)
    second = start_clearance_review.decide(state=state, command=command, now=now)
    assert first == second
