"""Unit tests for the `hold_run` slice's pure decider.

Pause transition: `Running | Held -> Held`, placing one hold claim.
Re-holding under the SAME cause raises (alternation is per claim);
holding from any terminal or before Run-start raises. A different
concern claiming an already-held run is admitted.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.run.aggregates.run import (
    HOLD_CAUSE_AUTHORITY_REVOCATION,
    HOLD_CAUSE_OPERATOR,
    HOLD_CAUSE_RATIFICATION,
    Run,
    RunCannotHoldError,
    RunHeld,
    RunName,
    RunNotFoundError,
    RunStatus,
    derive_claim_id,
)
from cora.run.features import hold_run
from cora.run.features.hold_run import HoldRun

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)


def _run(
    *,
    status: RunStatus = RunStatus.RUNNING,
    run_id: UUID | None = None,
    hold_claims: tuple[tuple[UUID, str], ...] = (),
) -> Run:
    return Run(
        id=run_id if run_id is not None else uuid4(),
        name=RunName("32-ID FlyScan"),
        plan_id=uuid4(),
        subject_id=uuid4(),
        status=status,
        hold_claims=hold_claims,
    )


@pytest.mark.unit
def test_decide_emits_run_held_for_running_state() -> None:
    state = _run(status=RunStatus.RUNNING)
    events = hold_run.decide(
        state=state,
        command=HoldRun(run_id=state.id),
        now=_NOW,
    )
    assert events == [
        RunHeld(
            run_id=state.id,
            occurred_at=_NOW,
            claim_id=derive_claim_id(state.id, HOLD_CAUSE_OPERATOR),
            cause=HOLD_CAUSE_OPERATOR,
        )
    ]


@pytest.mark.unit
def test_decide_raises_run_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(RunNotFoundError) as exc_info:
        hold_run.decide(
            state=None,
            command=HoldRun(run_id=target_id),
            now=_NOW,
        )
    assert exc_info.value.run_id == target_id


@pytest.mark.unit
def test_decide_raises_cannot_hold_when_this_cause_already_holds() -> None:
    """Alternation is per CLAIM: the same concern cannot hold twice."""
    run_id = uuid4()
    state = _run(
        run_id=run_id,
        status=RunStatus.HELD,
        hold_claims=((derive_claim_id(run_id, HOLD_CAUSE_OPERATOR), HOLD_CAUSE_OPERATOR),),
    )
    with pytest.raises(RunCannotHoldError) as exc_info:
        hold_run.decide(
            state=state,
            command=HoldRun(run_id=state.id, cause=HOLD_CAUSE_OPERATOR),
            now=_NOW,
        )
    assert exc_info.value.current_status is RunStatus.HELD


@pytest.mark.unit
def test_decide_admits_a_second_concern_holding_an_already_held_run() -> None:
    """The fault this admits. A run held by one concern must still accept another
    concern's claim, or that concern's cause goes unenforced when the first
    releases."""
    run_id = uuid4()
    state = _run(
        run_id=run_id,
        status=RunStatus.HELD,
        hold_claims=((derive_claim_id(run_id, HOLD_CAUSE_RATIFICATION), HOLD_CAUSE_RATIFICATION),),
    )
    events = hold_run.decide(
        state=state,
        command=HoldRun(run_id=run_id, cause=HOLD_CAUSE_AUTHORITY_REVOCATION),
        now=_NOW,
    )
    assert events == [
        RunHeld(
            run_id=run_id,
            occurred_at=_NOW,
            claim_id=derive_claim_id(run_id, HOLD_CAUSE_AUTHORITY_REVOCATION),
            cause=HOLD_CAUSE_AUTHORITY_REVOCATION,
        )
    ]


@pytest.mark.unit
def test_decide_rejects_an_unknown_cause() -> None:
    state = _run(status=RunStatus.RUNNING)
    with pytest.raises(ValueError, match="Unknown hold cause"):
        hold_run.decide(
            state=state,
            command=HoldRun(run_id=state.id, cause="whatever-i-like"),
            now=_NOW,
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "terminal",
    [RunStatus.COMPLETED, RunStatus.ABORTED, RunStatus.STOPPED],
)
def test_decide_raises_cannot_hold_from_any_terminal(terminal: RunStatus) -> None:
    state = _run(status=terminal)
    with pytest.raises(RunCannotHoldError) as exc_info:
        hold_run.decide(
            state=state,
            command=HoldRun(run_id=state.id),
            now=_NOW,
        )
    assert exc_info.value.current_status is terminal


@pytest.mark.unit
def test_decide_error_message_names_required_running_status() -> None:
    state = _run(status=RunStatus.COMPLETED)
    with pytest.raises(RunCannotHoldError) as exc_info:
        hold_run.decide(
            state=state,
            command=HoldRun(run_id=state.id),
            now=_NOW,
        )
    assert "Running" in str(exc_info.value)


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _run()
    command = HoldRun(run_id=state.id)
    first = hold_run.decide(state=state, command=command, now=_NOW)
    second = hold_run.decide(state=state, command=command, now=_NOW)
    assert first == second


@pytest.mark.unit
def test_decide_defaults_decided_by_decision_id_to_none_when_omitted() -> None:
    """Default for the optional Decision-causation link is None (operator route)."""
    state = _run(status=RunStatus.RUNNING)
    events = hold_run.decide(
        state=state,
        command=HoldRun(run_id=state.id),
        now=_NOW,
    )
    assert events[0].decided_by_decision_id is None


@pytest.mark.unit
def test_decide_threads_decided_by_decision_id_through_to_event() -> None:
    """When an agent runtime supplies it, decided_by_decision_id flows verbatim."""
    state = _run(status=RunStatus.RUNNING)
    decision_id = uuid4()
    events = hold_run.decide(
        state=state,
        command=HoldRun(run_id=state.id, decided_by_decision_id=decision_id),
        now=_NOW,
    )
    assert events[0].decided_by_decision_id == decision_id
