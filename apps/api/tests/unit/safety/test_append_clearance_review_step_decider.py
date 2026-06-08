"""Pure-decider tests for `append_clearance_review_step` slice."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.safety.aggregates.clearance import (
    Clearance,
    ClearanceCannotAppendReviewStepError,
    ClearanceKind,
    ClearanceNotFoundError,
    ClearanceReviewStepAppended,
    ClearanceStatus,
    ClearanceTitle,
    InvalidClearanceReviewerNotesError,
    InvalidClearanceReviewerRoleError,
    InvalidClearanceReviewStepDecidedAtError,
    InvalidClearanceReviewStepIndexError,
    ReviewStep,
    RunBinding,
)
from cora.safety.aggregates.clearance.state import (
    CLEARANCE_REVIEWER_NOTES_MAX_LENGTH,
)
from cora.safety.features import append_clearance_review_step
from cora.safety.features.append_clearance_review_step import AppendClearanceReviewStep
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_DECIDED = datetime(2026, 5, 15, 11, 0, 0, tzinfo=UTC)


def _clearance(
    *,
    status: ClearanceStatus = ClearanceStatus.UNDER_REVIEW,
    review_steps: tuple[ReviewStep, ...] = (),
) -> Clearance:
    return Clearance(
        id=uuid4(),
        kind=ClearanceKind.ESAF,
        facility_asset_id=uuid4(),
        title=ClearanceTitle("Pilot"),
        bindings=frozenset({RunBinding(run_id=uuid4())}),
        review_steps=review_steps,
        status=status,
    )


@pytest.mark.unit
def test_decide_emits_review_step_recorded_at_index_zero() -> None:
    state = _clearance()
    actor = uuid4()
    events = append_clearance_review_step.decide(
        state=state,
        command=AppendClearanceReviewStep(
            clearance_id=state.id,
            step_index=0,
            role="BeamlineScientist",
            actor_id=actor,
            decision="Approved",
            decided_at=_DECIDED,
            notes="LGTM",
        ),
        now=_NOW,
    )
    assert events == [
        ClearanceReviewStepAppended(
            clearance_id=state.id,
            step_index=0,
            role="BeamlineScientist",
            decided_by=ActorId(actor),
            decision="Approved",
            decided_at=_DECIDED,
            notes="LGTM",
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_appends_at_correct_index_when_chain_has_prior_steps() -> None:
    prior = ReviewStep(
        step_index=0,
        role="BeamlineScientist",
        decided_by=ActorId(uuid4()),
        decision="Approved",
        decided_at=_DECIDED,
    )
    state = _clearance(review_steps=(prior,))
    actor = uuid4()
    events = append_clearance_review_step.decide(
        state=state,
        command=AppendClearanceReviewStep(
            clearance_id=state.id,
            step_index=1,
            role="ESH",
            actor_id=actor,
            decision="Approved",
            decided_at=_DECIDED,
        ),
        now=_NOW,
    )
    assert events[0].step_index == 1


@pytest.mark.unit
def test_decide_rejects_wrong_step_index() -> None:
    state = _clearance()
    with pytest.raises(InvalidClearanceReviewStepIndexError):
        append_clearance_review_step.decide(
            state=state,
            command=AppendClearanceReviewStep(
                clearance_id=state.id,
                step_index=1,  # state has 0 review_steps; expected index 0
                role="x",
                actor_id=uuid4(),
                decision="Approved",
                decided_at=_DECIDED,
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_empty_role() -> None:
    state = _clearance()
    with pytest.raises(InvalidClearanceReviewerRoleError):
        append_clearance_review_step.decide(
            state=state,
            command=AppendClearanceReviewStep(
                clearance_id=state.id,
                step_index=0,
                role="   ",
                actor_id=uuid4(),
                decision="Approved",
                decided_at=_DECIDED,
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_oversized_notes() -> None:
    state = _clearance()
    with pytest.raises(InvalidClearanceReviewerNotesError):
        append_clearance_review_step.decide(
            state=state,
            command=AppendClearanceReviewStep(
                clearance_id=state.id,
                step_index=0,
                role="x",
                actor_id=uuid4(),
                decision="Approved",
                decided_at=_DECIDED,
                notes="z" * (CLEARANCE_REVIEWER_NOTES_MAX_LENGTH + 1),
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_normalizes_whitespace_only_notes_to_none() -> None:
    state = _clearance()
    events = append_clearance_review_step.decide(
        state=state,
        command=AppendClearanceReviewStep(
            clearance_id=state.id,
            step_index=0,
            role="x",
            actor_id=uuid4(),
            decision="Approved",
            decided_at=_DECIDED,
            notes="   ",
        ),
        now=_NOW,
    )
    assert events[0].notes is None


@pytest.mark.unit
def test_decide_rejects_when_state_none() -> None:
    cid = uuid4()
    with pytest.raises(ClearanceNotFoundError):
        append_clearance_review_step.decide(
            state=None,
            command=AppendClearanceReviewStep(
                clearance_id=cid,
                step_index=0,
                role="x",
                actor_id=uuid4(),
                decision="Approved",
                decided_at=_DECIDED,
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_when_status_not_under_review() -> None:
    state = _clearance(status=ClearanceStatus.SUBMITTED)
    with pytest.raises(ClearanceCannotAppendReviewStepError):
        append_clearance_review_step.decide(
            state=state,
            command=AppendClearanceReviewStep(
                clearance_id=state.id,
                step_index=0,
                role="x",
                actor_id=uuid4(),
                decision="Approved",
                decided_at=_DECIDED,
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_future_dated_decided_at() -> None:
    """#21: decided_at strictly greater than now is refused."""
    state = _clearance()
    future = datetime(2026, 5, 15, 13, 0, 0, tzinfo=UTC)  # 1h after _NOW
    with pytest.raises(InvalidClearanceReviewStepDecidedAtError, match="future-dated"):
        append_clearance_review_step.decide(
            state=state,
            command=AppendClearanceReviewStep(
                clearance_id=state.id,
                step_index=0,
                role="ESH",
                actor_id=uuid4(),
                decision="Approved",
                decided_at=future,
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_accepts_decided_at_equal_to_now() -> None:
    """#21: boundary value (decided_at == now) accepted; only strictly greater fails."""
    state = _clearance()
    events = append_clearance_review_step.decide(
        state=state,
        command=AppendClearanceReviewStep(
            clearance_id=state.id,
            step_index=0,
            role="ESH",
            actor_id=uuid4(),
            decision="Approved",
            decided_at=_NOW,
        ),
        now=_NOW,
    )
    assert events[0].decided_at == _NOW


@pytest.mark.unit
def test_decide_rejects_decided_at_earlier_than_prior_step() -> None:
    """#21: chain monotonicity - step N+1's decided_at must be >= step N's."""
    prior_decided = datetime(2026, 5, 15, 11, 30, 0, tzinfo=UTC)
    earlier = datetime(2026, 5, 15, 11, 0, 0, tzinfo=UTC)  # 30min before prior
    prior = ReviewStep(
        step_index=0,
        role="BeamlineScientist",
        decided_by=ActorId(uuid4()),
        decision="Approved",
        decided_at=prior_decided,
    )
    state = _clearance(review_steps=(prior,))
    with pytest.raises(InvalidClearanceReviewStepDecidedAtError, match="monotonicity"):
        append_clearance_review_step.decide(
            state=state,
            command=AppendClearanceReviewStep(
                clearance_id=state.id,
                step_index=1,
                role="ESH",
                actor_id=uuid4(),
                decision="Approved",
                decided_at=earlier,
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_accepts_decided_at_equal_to_prior_step() -> None:
    """#21: monotonicity is non-strict; equal timestamps are allowed
    (a reviewer can record their decision at the same instant as the prior)."""
    prior_decided = datetime(2026, 5, 15, 11, 30, 0, tzinfo=UTC)
    prior = ReviewStep(
        step_index=0,
        role="BeamlineScientist",
        decided_by=ActorId(uuid4()),
        decision="Approved",
        decided_at=prior_decided,
    )
    state = _clearance(review_steps=(prior,))
    events = append_clearance_review_step.decide(
        state=state,
        command=AppendClearanceReviewStep(
            clearance_id=state.id,
            step_index=1,
            role="ESH",
            actor_id=uuid4(),
            decision="Approved",
            decided_at=prior_decided,
        ),
        now=_NOW,
    )
    assert events[0].decided_at == prior_decided
