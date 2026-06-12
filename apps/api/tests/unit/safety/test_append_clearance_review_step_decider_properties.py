"""Property-based tests for `append_clearance_review_step.decide` (Safety BC).

Complements the example-based `test_append_clearance_review_step_decider.py`
with universal claims across generated inputs. The decider is a pure
append-into-tuple step with no status change

    (state, command, now) -> list[ClearanceReviewStepAppended]

Load-bearing properties:

  - state=None always raises `ClearanceNotFoundError` carrying
    command.clearance_id.
  - The source-state partition is total over `ClearanceStatus`: only
    `UnderReview` admits an append; every other status raises
    `ClearanceCannotAppendReviewStepError` carrying the current status,
    so a future status value cannot silently fall through.
  - A `step_index` not equal to `len(state.review_steps)` always raises
    `InvalidClearanceReviewStepIndexError`.
  - Happy path (UnderReview + correct next index + valid decided_at/notes)
    emits exactly one event whose clearance_id is `state.id`, threading the
    injected fields and `occurred_at=now`.
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
    ClearanceCannotAppendReviewStepError,
    ClearanceNotFoundError,
    ClearanceReviewStepAppended,
    ClearanceStatus,
    ClearanceTitle,
    InvalidClearanceReviewStepIndexError,
    ReviewStep,
    RunBinding,
)
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateId,
    clearance_template_stream_id,
)
from cora.safety.features import append_clearance_review_step
from cora.safety.features.append_clearance_review_step import AppendClearanceReviewStep
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_TEMPLATE_ID = ClearanceTemplateId(clearance_template_stream_id("aps", "ESAF"))
_DECISION = "Approved"

_APPENDABLE_SOURCES = (ClearanceStatus.UNDER_REVIEW,)
_DISALLOWED_SOURCES = tuple(s for s in ClearanceStatus if s not in frozenset(_APPENDABLE_SOURCES))


def _clearance(
    *,
    clearance_id: UUID,
    status: ClearanceStatus = ClearanceStatus.UNDER_REVIEW,
    review_steps: tuple[ReviewStep, ...] = (),
) -> Clearance:
    return Clearance(
        id=clearance_id,
        template_id=_TEMPLATE_ID,
        facility_code=FacilityCode("aps"),
        title=ClearanceTitle("Pilot"),
        bindings=frozenset({RunBinding(run_id=UUID(int=7))}),
        review_steps=review_steps,
        status=status,
    )


def _command(
    *,
    clearance_id: UUID,
    step_index: int,
    actor_id: UUID,
    role: str,
    decided_at: datetime,
) -> AppendClearanceReviewStep:
    return AppendClearanceReviewStep(
        clearance_id=clearance_id,
        step_index=step_index,
        role=role,
        actor_id=actor_id,
        decision=_DECISION,
        decided_at=decided_at,
        notes=None,
    )


@pytest.mark.unit
@given(clearance_id=st.uuids(), now=aware_datetimes())
def test_append_with_none_state_always_raises_not_found(
    clearance_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `ClearanceNotFoundError` carrying clearance_id."""
    with pytest.raises(ClearanceNotFoundError) as exc:
        append_clearance_review_step.decide(
            state=None,
            command=_command(
                clearance_id=clearance_id,
                step_index=0,
                actor_id=UUID(int=1),
                role="ESH",
                decided_at=now,
            ),
            now=now,
        )
    assert exc.value.clearance_id == clearance_id


@pytest.mark.unit
@given(
    clearance_id=st.uuids(),
    actor_id=st.uuids(),
    role=printable_ascii_text(max_size=50),
    now=aware_datetimes(),
)
def test_append_from_under_review_emits_single_event(
    clearance_id: UUID,
    actor_id: UUID,
    role: str,
    now: datetime,
) -> None:
    """UnderReview is the only appendable source; emits one event at next index."""
    events = append_clearance_review_step.decide(
        state=_clearance(clearance_id=clearance_id, status=ClearanceStatus.UNDER_REVIEW),
        command=_command(
            clearance_id=clearance_id,
            step_index=0,
            actor_id=actor_id,
            role=role,
            decided_at=now,
        ),
        now=now,
    )
    assert events == [
        ClearanceReviewStepAppended(
            clearance_id=clearance_id,
            step_index=0,
            role=role,
            decided_by=ActorId(actor_id),
            decision=_DECISION,
            decided_at=now,
            notes=None,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    clearance_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_append_from_disallowed_source_always_raises_cannot_append(
    clearance_id: UUID,
    source: ClearanceStatus,
    now: datetime,
) -> None:
    """Any source other than UnderReview raises, carrying the current status."""
    with pytest.raises(ClearanceCannotAppendReviewStepError) as exc:
        append_clearance_review_step.decide(
            state=_clearance(clearance_id=clearance_id, status=source),
            command=_command(
                clearance_id=clearance_id,
                step_index=0,
                actor_id=UUID(int=1),
                role="ESH",
                decided_at=now,
            ),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    clearance_id=st.uuids(),
    step_index=st.integers(min_value=0, max_value=50),
    now=aware_datetimes(),
)
def test_append_with_wrong_step_index_always_raises_invalid_index(
    clearance_id: UUID,
    step_index: int,
    now: datetime,
) -> None:
    """A step_index not equal to len(review_steps) raises, carrying the expected count."""
    assume(step_index != 0)
    with pytest.raises(InvalidClearanceReviewStepIndexError) as exc:
        append_clearance_review_step.decide(
            state=_clearance(clearance_id=clearance_id, status=ClearanceStatus.UNDER_REVIEW),
            command=_command(
                clearance_id=clearance_id,
                step_index=step_index,
                actor_id=UUID(int=1),
                role="ESH",
                decided_at=now,
            ),
            now=now,
        )
    assert exc.value.expected == 0
    assert exc.value.got == step_index


@pytest.mark.unit
@given(
    state_id=st.uuids(),
    command_clearance_id=st.uuids(),
    actor_id=st.uuids(),
    now=aware_datetimes(),
)
def test_append_emitted_event_uses_state_id_not_command_clearance_id(
    state_id: UUID,
    command_clearance_id: UUID,
    actor_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's clearance_id is state.id, not command.clearance_id."""
    assume(state_id != command_clearance_id)
    events = append_clearance_review_step.decide(
        state=_clearance(clearance_id=state_id, status=ClearanceStatus.UNDER_REVIEW),
        command=_command(
            clearance_id=command_clearance_id,
            step_index=0,
            actor_id=actor_id,
            role="ESH",
            decided_at=now,
        ),
        now=now,
    )
    assert events[0].clearance_id == state_id


@pytest.mark.unit
@given(clearance_id=st.uuids(), actor_id=st.uuids(), now=aware_datetimes())
def test_append_is_pure_same_input_same_output(
    clearance_id: UUID,
    actor_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _clearance(clearance_id=clearance_id, status=ClearanceStatus.UNDER_REVIEW)
    command = _command(
        clearance_id=clearance_id,
        step_index=0,
        actor_id=actor_id,
        role="ESH",
        decided_at=now,
    )
    first = append_clearance_review_step.decide(state=state, command=command, now=now)
    second = append_clearance_review_step.decide(state=state, command=command, now=now)
    assert first == second
