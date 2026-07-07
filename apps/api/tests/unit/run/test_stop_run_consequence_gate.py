"""Unit tests for the consequence gate (Gate IV) arm on the stop_run decider.

StopRun is in the declared consequence class, so the decider refuses with
RunRequiresRatificationError when coverage is absent, and admits (falls through to
the normal transition) when coverage is present. The gate is the OUTER
precondition: it is checked before state/status, and it is kind-blind (no actor
kind is read).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.run.aggregates.run import (
    Run,
    RunName,
    RunRequiresRatificationError,
    RunStatus,
    RunStopped,
)
from cora.run.features.stop_run import decide
from cora.run.features.stop_run.command import StopRun

_NOW = datetime(2026, 7, 6, 12, 0, 0, tzinfo=UTC)


def _running_run(run_id: UUID) -> Run:
    return Run(
        id=run_id,
        name=RunName("test run"),
        plan_id=uuid4(),
        subject_id=None,
        status=RunStatus.RUNNING,
    )


@pytest.mark.unit
def test_uncovered_stop_is_refused_with_ratification_error() -> None:
    run_id = uuid4()
    with pytest.raises(RunRequiresRatificationError) as exc:
        decide(
            state=_running_run(run_id),
            command=StopRun(run_id=run_id, reason="end session early"),
            now=_NOW,
            ratification_covered=False,
        )
    assert exc.value.run_id == run_id
    assert exc.value.command_name == "StopRun"


@pytest.mark.unit
def test_covered_stop_is_admitted() -> None:
    run_id = uuid4()
    events = decide(
        state=_running_run(run_id),
        command=StopRun(run_id=run_id, reason="end session early"),
        now=_NOW,
        ratification_covered=True,
    )
    assert len(events) == 1
    assert isinstance(events[0], RunStopped)
    assert events[0].run_id == run_id


@pytest.mark.unit
def test_gate_precedes_state_check() -> None:
    """The consequence gate is the OUTER precondition: an uncovered stop on a
    missing run raises RunRequiresRatificationError (the gate), NOT
    RunNotFoundError. Admission is decided before existence."""
    run_id = uuid4()
    with pytest.raises(RunRequiresRatificationError):
        decide(
            state=None,
            command=StopRun(run_id=run_id, reason="x"),
            now=_NOW,
            ratification_covered=False,
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "status",
    [RunStatus.RUNNING, RunStatus.HELD, RunStatus.COMPLETED, RunStatus.ABORTED, RunStatus.STOPPED],
)
@pytest.mark.parametrize("reason", ["ok reason", "", "x" * 999])
def test_uncovered_stop_always_refuses_regardless_of_state(status: RunStatus, reason: str) -> None:
    """The gate is TOTAL and OUTERMOST: for any run status and any reason (even a
    malformed one), an uncovered StopRun raises RunRequiresRatificationError before
    the reason-validation / status-transition checks can raise anything else."""
    run_id = uuid4()
    state = Run(id=run_id, name=RunName("r"), plan_id=uuid4(), subject_id=None, status=status)
    with pytest.raises(RunRequiresRatificationError):
        decide(
            state=state,
            command=StopRun(run_id=run_id, reason=reason),
            now=_NOW,
            ratification_covered=False,
        )
