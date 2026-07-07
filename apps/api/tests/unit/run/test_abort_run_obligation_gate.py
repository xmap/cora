"""Unit tests for the obligation gate (Gate III) on the abort_run decider.

AbortRun is in COMMANDS_REQUIRING_JUSTIFICATION, so the decider requires a
non-empty, bounded justification at admission (fail-closed) BEFORE any state /
reason / status check. The gate is total, outermost, and kind-blind: it reads only
the command name + justification text, never actor kind, so a human and an agent
are held to the identical precondition.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.run.aggregates.run import Run, RunName, RunStatus
from cora.run.features.abort_run import decide
from cora.run.features.abort_run.command import AbortRun
from cora.shared.justification import (
    COMMANDS_REQUIRING_JUSTIFICATION,
    JUSTIFICATION_MAX_LENGTH,
    JustificationRequiredError,
)

_NOW = datetime(2026, 7, 7, 12, 0, 0, tzinfo=UTC)


def _running_run(run_id: UUID) -> Run:
    return Run(
        id=run_id,
        name=RunName("test run"),
        plan_id=uuid4(),
        subject_id=None,
        status=RunStatus.RUNNING,
    )


@pytest.mark.unit
def test_abort_run_is_in_the_declared_class() -> None:
    """The decider gates on the command name "AbortRun"; the allowlist must contain
    it or the gate silently goes inert. Pins the two-place coupling (the decider's
    literal and the allowlist membership live in separate files). The behavioral
    tests below (refuse-when-absent) are the other half of the guard: they fail if
    the decider ever stops calling require_justification."""
    assert "AbortRun" in COMMANDS_REQUIRING_JUSTIFICATION


@pytest.mark.unit
def test_abort_without_justification_is_refused() -> None:
    run_id = uuid4()
    with pytest.raises(JustificationRequiredError) as exc:
        decide(
            _running_run(run_id),
            AbortRun(run_id=run_id, reason="beam dump"),
            now=_NOW,
        )
    assert exc.value.command_name == "AbortRun"


@pytest.mark.unit
def test_abort_with_justification_is_admitted() -> None:
    run_id = uuid4()
    events = decide(
        _running_run(run_id),
        AbortRun(run_id=run_id, reason="beam dump", justification="detector arc, safety abort"),
        now=_NOW,
    )
    assert len(events) == 1
    assert events[0].run_id == run_id
    # The post-hoc reason still lands on the event; justification is admission-only.
    assert events[0].reason == "beam dump"


@pytest.mark.unit
@pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
def test_blank_justification_is_refused(blank: str) -> None:
    run_id = uuid4()
    with pytest.raises(JustificationRequiredError):
        decide(
            _running_run(run_id),
            AbortRun(run_id=run_id, reason="x", justification=blank),
            now=_NOW,
        )


@pytest.mark.unit
def test_over_length_justification_is_refused() -> None:
    run_id = uuid4()
    with pytest.raises(JustificationRequiredError):
        decide(
            _running_run(run_id),
            AbortRun(
                run_id=run_id,
                reason="x",
                justification="j" * (JUSTIFICATION_MAX_LENGTH + 1),
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_gate_precedes_state_check() -> None:
    """The obligation gate is the OUTER precondition: an unjustified abort on a
    missing run raises JustificationRequiredError (the gate), NOT RunNotFoundError.
    Admission is decided before existence."""
    with pytest.raises(JustificationRequiredError):
        decide(None, AbortRun(run_id=uuid4(), reason="x"), now=_NOW)


@pytest.mark.unit
@pytest.mark.parametrize(
    "status",
    [RunStatus.RUNNING, RunStatus.HELD, RunStatus.COMPLETED, RunStatus.ABORTED, RunStatus.STOPPED],
)
def test_unjustified_abort_always_refuses_regardless_of_state(status: RunStatus) -> None:
    """Total + outermost: for ANY run status, an unjustified abort raises the gate
    error before the reason-validation / status-transition checks can raise their
    own (e.g. RunCannotAbortError on a terminal run)."""
    run_id = uuid4()
    state = Run(id=run_id, name=RunName("r"), plan_id=uuid4(), subject_id=None, status=status)
    with pytest.raises(JustificationRequiredError):
        decide(state, AbortRun(run_id=run_id, reason="x"), now=_NOW)


@pytest.mark.unit
def test_gate_is_kind_blind() -> None:
    """The gate reads only command name + text, never actor kind: the decider has
    no actor-kind argument, so a human and an agent abort under the identical
    precondition. This test documents the invariant by exercising the same decide()
    with a justification (admitted) and without (refused): the outcome depends
    only on the justification, never on who is aborting."""
    run_id = uuid4()
    justified = AbortRun(run_id=run_id, reason="x", justification="accounted for")
    assert decide(_running_run(run_id), justified, now=_NOW)  # admitted for anyone
    with pytest.raises(JustificationRequiredError):
        decide(_running_run(run_id), AbortRun(run_id=run_id, reason="x"), now=_NOW)
