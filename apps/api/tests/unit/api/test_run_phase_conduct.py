"""Unit tests for the composition-root `conduct_phase_then_complete_run` glue.

The glue is pure orchestration over three injected handlers, so the
tests drive it with recording fakes (no event store): assert that a
successful phase conduct completes the parent Run carrying the phase's
kind, and that a failed conduct aborts the Run with a derived reason
that still carries the kind.
"""

from typing import Any
from uuid import UUID

import pytest

from cora.api._run_phase_conduct import conduct_phase_then_complete_run
from cora.operation.conductor import ConductorFailure
from cora.operation.features.conduct_procedure.command import ConductProcedureResult
from cora.run.features.abort_run.command import AbortRun
from cora.run.features.complete_run.command import CompleteRun

_RUN_ID = UUID("01900000-0000-7000-8000-0000000000a1")
_PROC_ID = UUID("01900000-0000-7000-8000-0000000000a2")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000000000a3")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000a4")
_SURFACE_ID = UUID("01900000-0000-7000-8000-0000000000a5")


class _Recorder:
    """Async callable that records (command, kwargs) and returns a fixed value."""

    def __init__(self, result: Any = None) -> None:
        self.calls: list[tuple[Any, dict[str, Any]]] = []
        self._result = result

    async def __call__(self, command: Any, **kwargs: Any) -> Any:
        self.calls.append((command, kwargs))
        return self._result


@pytest.mark.unit
async def test_successful_phase_conduct_completes_run_carrying_the_kind() -> None:
    conduct = _Recorder(
        ConductProcedureResult(
            procedure_id=_PROC_ID,
            completed_count=8,
            succeeded=True,
            failure=None,
            actuation_kind="Simulated",
        )
    )
    complete = _Recorder()
    abort = _Recorder()

    result = await conduct_phase_then_complete_run(
        run_id=_RUN_ID,
        procedure_id=_PROC_ID,
        conduct_procedure=conduct,
        complete_run=complete,
        abort_run=abort,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        surface_id=_SURFACE_ID,
    )

    assert result.succeeded is True
    assert result.actuation_kind == "Simulated"
    assert result.completed_count == 8

    # The phase was conducted recipe-driven (empty caller steps).
    conduct_cmd, conduct_env = conduct.calls[0]
    assert conduct_cmd.procedure_id == _PROC_ID
    assert tuple(conduct_cmd.steps) == ()
    assert conduct_env["surface_id"] == _SURFACE_ID

    # Only the complete arm fired, carrying the phase's kind onto the Run.
    assert len(abort.calls) == 0
    complete_cmd, _ = complete.calls[0]
    assert isinstance(complete_cmd, CompleteRun)
    assert complete_cmd.run_id == _RUN_ID
    assert complete_cmd.actuation_kind == "Simulated"


@pytest.mark.unit
async def test_failed_phase_conduct_aborts_run_with_reason_and_kind() -> None:
    failure = ConductorFailure(
        step_index=3,
        source_kind="setpoint",
        target="2bm:m1",
        error_class="ControlWriteError",
        message="soft limit tripped",
    )
    conduct = _Recorder(
        ConductProcedureResult(
            procedure_id=_PROC_ID,
            completed_count=3,
            succeeded=False,
            failure=failure,
            actuation_kind="Simulated",
        )
    )
    complete = _Recorder()
    abort = _Recorder()

    result = await conduct_phase_then_complete_run(
        run_id=_RUN_ID,
        procedure_id=_PROC_ID,
        conduct_procedure=conduct,
        complete_run=complete,
        abort_run=abort,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert result.succeeded is False
    assert result.failure is failure

    # Only the abort arm fired; the reason names the halt and the kind taints the Run.
    assert len(complete.calls) == 0
    abort_cmd, _ = abort.calls[0]
    assert isinstance(abort_cmd, AbortRun)
    assert abort_cmd.run_id == _RUN_ID
    assert abort_cmd.actuation_kind == "Simulated"
    assert "ControlWriteError" in abort_cmd.reason
    assert "setpoint 2bm:m1" in abort_cmd.reason


class _Raising:
    """Async callable that always raises (a Run terminal that rejects)."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc
        self.calls = 0

    async def __call__(self, command: Any, **kwargs: Any) -> Any:
        _ = (command, kwargs)
        self.calls += 1
        raise self._exc


@pytest.mark.unit
async def test_abort_rejection_is_suppressed_so_conduct_failure_survives() -> None:
    failure = ConductorFailure(
        step_index=0,
        source_kind="lifecycle",
        target="start",
        error_class="ProcedureCannotStartError",
        message="already terminal",
    )
    conduct = _Recorder(
        ConductProcedureResult(
            procedure_id=_PROC_ID,
            completed_count=0,
            succeeded=False,
            failure=failure,
            actuation_kind="Simulated",
        )
    )
    complete = _Recorder()
    abort = _Raising(RuntimeError("RunCannotAbortError: Run already terminal"))

    # The Run can't be aborted (already terminal), but the best-effort abort
    # swallows that rejection so the real conduct diagnostic still returns
    # instead of being masked by the terminal-transition error.
    result = await conduct_phase_then_complete_run(
        run_id=_RUN_ID,
        procedure_id=_PROC_ID,
        conduct_procedure=conduct,
        complete_run=complete,
        abort_run=abort,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert result.succeeded is False
    assert result.failure is failure
    assert abort.calls == 1
    assert len(complete.calls) == 0
