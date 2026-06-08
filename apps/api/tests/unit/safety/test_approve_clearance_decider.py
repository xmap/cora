"""Pure-decider tests for `approve_clearance` slice."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.safety.aggregates.clearance import (
    Clearance,
    ClearanceApproved,
    ClearanceCannotApproveError,
    ClearanceKind,
    ClearanceNotFoundError,
    ClearanceStatus,
    ClearanceTitle,
    InvalidClearanceValidityWindowError,
    ReviewStep,
    RunBinding,
)
from cora.safety.features import approve_clearance
from cora.safety.features.approve_clearance import ApproveClearance
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)


def _approving_step(step_index: int = 0) -> ReviewStep:
    return ReviewStep(
        step_index=step_index,
        role="ESH",
        decided_by=ActorId(uuid4()),
        decision="Approved",
        decided_at=_NOW,
    )


def _rejected_step(step_index: int = 0) -> ReviewStep:
    return ReviewStep(
        step_index=step_index,
        role="ESH",
        decided_by=ActorId(uuid4()),
        decision="Rejected",
        decided_at=_NOW,
    )


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
def test_decide_emits_approved_when_terminal_step_approved() -> None:
    state = _clearance(review_steps=(_approving_step(),))
    events = approve_clearance.decide(
        state=state,
        command=ApproveClearance(clearance_id=state.id),
        now=_NOW,
    )
    assert events == [
        ClearanceApproved(
            clearance_id=state.id,
            valid_from=None,
            valid_until=None,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_carries_validity_window_when_provided() -> None:
    state = _clearance(review_steps=(_approving_step(),))
    valid_from = datetime(2026, 5, 16, tzinfo=UTC)
    valid_until = datetime(2026, 6, 15, tzinfo=UTC)
    events = approve_clearance.decide(
        state=state,
        command=ApproveClearance(
            clearance_id=state.id,
            valid_from=valid_from,
            valid_until=valid_until,
        ),
        now=_NOW,
    )
    assert events[0].valid_from == valid_from
    assert events[0].valid_until == valid_until


@pytest.mark.unit
def test_decide_rejects_when_terminal_step_not_approved() -> None:
    """[RequestedChanges] chain: terminal step is not Approved -> 409."""
    rejected_step = ReviewStep(
        step_index=0,
        role="ESH",
        decided_by=ActorId(uuid4()),
        decision="RequestedChanges",
        decided_at=_NOW,
    )
    state = _clearance(review_steps=(rejected_step,))
    with pytest.raises(ClearanceCannotApproveError, match="terminal review step"):
        approve_clearance.decide(
            state=state,
            command=ApproveClearance(clearance_id=state.id),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_chain_with_approved_then_rejected() -> None:
    """Terminal-step semantic (#20): a downstream reviewer's Rejected vetoes
    the chain even if an earlier step was Approved. DESY DOOR shape."""
    chain = (_approving_step(step_index=0), _rejected_step(step_index=1))
    state = _clearance(review_steps=chain)
    with pytest.raises(ClearanceCannotApproveError, match="terminal review step"):
        approve_clearance.decide(
            state=state,
            command=ApproveClearance(clearance_id=state.id),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_emits_approved_for_rejected_then_approved_chain() -> None:
    """Inverse of the [Approved, Rejected] veto case: a [Rejected, Approved]
    chain SUCCEEDS because only the terminal step matters under the
    "terminal step wins" semantic. Locks the asymmetry: an early Rejected
    does NOT veto subsequent reapproval (mirrors a re-review flow where
    the operator addressed the rejection and the next reviewer approved).
    """
    chain = (_rejected_step(step_index=0), _approving_step(step_index=1))
    state = _clearance(review_steps=chain)
    events = approve_clearance.decide(
        state=state,
        command=ApproveClearance(clearance_id=state.id),
        now=_NOW,
    )
    assert events == [
        ClearanceApproved(
            clearance_id=state.id,
            valid_from=None,
            valid_until=None,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_rejects_when_chain_empty() -> None:
    state = _clearance(review_steps=())
    with pytest.raises(ClearanceCannotApproveError, match="terminal review step"):
        approve_clearance.decide(
            state=state,
            command=ApproveClearance(clearance_id=state.id),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_inverted_validity_window() -> None:
    state = _clearance(review_steps=(_approving_step(),))
    with pytest.raises(InvalidClearanceValidityWindowError):
        approve_clearance.decide(
            state=state,
            command=ApproveClearance(
                clearance_id=state.id,
                valid_from=datetime(2026, 6, 15, tzinfo=UTC),
                valid_until=datetime(2026, 5, 15, tzinfo=UTC),
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_when_state_none() -> None:
    cid = uuid4()
    with pytest.raises(ClearanceNotFoundError):
        approve_clearance.decide(
            state=None,
            command=ApproveClearance(clearance_id=cid),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_when_status_not_under_review() -> None:
    state = _clearance(status=ClearanceStatus.SUBMITTED, review_steps=(_approving_step(),))
    with pytest.raises(ClearanceCannotApproveError):
        approve_clearance.decide(
            state=state,
            command=ApproveClearance(clearance_id=state.id),
            now=_NOW,
        )
