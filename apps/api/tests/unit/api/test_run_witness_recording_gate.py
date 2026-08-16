# pyright: reportPrivateUsage=false
"""Unit tests for the RunWitness recording boot guard.

`_enforce_run_witness_recording_gate` refuses to boot with
`run_witness_recording_enabled=True` unless both `run_witness_enabled`
and `capture_watch_plan_id` are also set: promotion has no shadow
observer to promote from, or no Plan to bind the promoted Run to,
without both. Unlike the production signing/principal guards, this one
is not keyed on `app_env`: a half-configured recording gate is a
misconfiguration in every environment.

Slice 10 adds a THIRD gate: `capture_progress_recording_enabled=True`
requires `run_witness_recording_enabled=True`, checked ahead of (and
independent of) the first gate's own prerequisites.

Slice 12 adds a FOURTH gate, same shape: `capture_baseline_recording_enabled=True`
requires `run_witness_recording_enabled=True`.

Slice 13 adds a FIFTH gate, same shape: `capture_path_recording_enabled=True`
requires `run_witness_recording_enabled=True`.
"""

from uuid import UUID, uuid4

import pytest

from cora.api.main import _enforce_run_witness_recording_gate
from cora.infrastructure.config import Settings


def _settings(
    *,
    run_witness_enabled: bool = False,
    capture_watch_plan_id: UUID | None = None,
    run_witness_recording_enabled: bool = False,
    capture_progress_recording_enabled: bool = False,
    capture_baseline_recording_enabled: bool = False,
    capture_path_recording_enabled: bool = False,
) -> Settings:
    return Settings(  # type: ignore[call-arg]
        run_witness_enabled=run_witness_enabled,
        capture_watch_plan_id=capture_watch_plan_id,
        run_witness_recording_enabled=run_witness_recording_enabled,
        capture_progress_recording_enabled=capture_progress_recording_enabled,
        capture_baseline_recording_enabled=capture_baseline_recording_enabled,
        capture_path_recording_enabled=capture_path_recording_enabled,
    )


def test_recording_disabled_is_always_a_no_op() -> None:
    for run_witness_enabled in (True, False):
        for capture_watch_plan_id in (None, uuid4()):
            _enforce_run_witness_recording_gate(
                _settings(
                    run_witness_enabled=run_witness_enabled,
                    capture_watch_plan_id=capture_watch_plan_id,
                    run_witness_recording_enabled=False,
                )
            )


def test_recording_enabled_without_witness_enabled_refuses_boot() -> None:
    with pytest.raises(RuntimeError, match="RUN_WITNESS_ENABLED=true"):
        _enforce_run_witness_recording_gate(
            _settings(
                run_witness_enabled=False,
                capture_watch_plan_id=uuid4(),
                run_witness_recording_enabled=True,
            )
        )


def test_recording_enabled_without_plan_id_refuses_boot() -> None:
    with pytest.raises(RuntimeError, match="CAPTURE_WATCH_PLAN_ID"):
        _enforce_run_witness_recording_gate(
            _settings(
                run_witness_enabled=True,
                capture_watch_plan_id=None,
                run_witness_recording_enabled=True,
            )
        )


def test_recording_enabled_missing_both_refuses_boot_naming_both_vars() -> None:
    with pytest.raises(RuntimeError) as exc:
        _enforce_run_witness_recording_gate(
            _settings(
                run_witness_enabled=False,
                capture_watch_plan_id=None,
                run_witness_recording_enabled=True,
            )
        )
    message = str(exc.value)
    assert "RUN_WITNESS_ENABLED=true" in message
    assert "CAPTURE_WATCH_PLAN_ID" in message


def test_recording_enabled_with_both_prerequisites_passes() -> None:
    _enforce_run_witness_recording_gate(
        _settings(
            run_witness_enabled=True,
            capture_watch_plan_id=uuid4(),
            run_witness_recording_enabled=True,
        )
    )


def test_progress_recording_enabled_without_run_witness_recording_refuses_boot() -> None:
    with pytest.raises(RuntimeError, match="RUN_WITNESS_RECORDING_ENABLED=true"):
        _enforce_run_witness_recording_gate(
            _settings(
                run_witness_enabled=True,
                capture_watch_plan_id=uuid4(),
                run_witness_recording_enabled=False,
                capture_progress_recording_enabled=True,
            )
        )


def test_progress_recording_enabled_checked_before_the_first_gates_prerequisites() -> None:
    """The third gate's own message must appear even when the FIRST
    gate's prerequisites are also missing: the two checks are
    independent, not layered."""
    with pytest.raises(RuntimeError, match="RUN_WITNESS_RECORDING_ENABLED=true"):
        _enforce_run_witness_recording_gate(
            _settings(
                run_witness_enabled=False,
                capture_watch_plan_id=None,
                run_witness_recording_enabled=False,
                capture_progress_recording_enabled=True,
            )
        )


def test_progress_recording_enabled_with_run_witness_recording_passes() -> None:
    _enforce_run_witness_recording_gate(
        _settings(
            run_witness_enabled=True,
            capture_watch_plan_id=uuid4(),
            run_witness_recording_enabled=True,
            capture_progress_recording_enabled=True,
        )
    )


def test_baseline_recording_enabled_without_run_witness_recording_refuses_boot() -> None:
    with pytest.raises(RuntimeError, match="RUN_WITNESS_RECORDING_ENABLED=true"):
        _enforce_run_witness_recording_gate(
            _settings(
                run_witness_enabled=True,
                capture_watch_plan_id=uuid4(),
                run_witness_recording_enabled=False,
                capture_baseline_recording_enabled=True,
            )
        )


def test_baseline_recording_enabled_checked_before_the_first_gates_prerequisites() -> None:
    """Same independence property as the progress gate: the baseline
    gate's own message must appear even when the FIRST gate's
    prerequisites are also missing."""
    with pytest.raises(RuntimeError, match="RUN_WITNESS_RECORDING_ENABLED=true"):
        _enforce_run_witness_recording_gate(
            _settings(
                run_witness_enabled=False,
                capture_watch_plan_id=None,
                run_witness_recording_enabled=False,
                capture_baseline_recording_enabled=True,
            )
        )


def test_baseline_recording_enabled_with_run_witness_recording_passes() -> None:
    _enforce_run_witness_recording_gate(
        _settings(
            run_witness_enabled=True,
            capture_watch_plan_id=uuid4(),
            run_witness_recording_enabled=True,
            capture_baseline_recording_enabled=True,
        )
    )


def test_path_recording_enabled_without_run_witness_recording_refuses_boot() -> None:
    with pytest.raises(RuntimeError, match="RUN_WITNESS_RECORDING_ENABLED=true"):
        _enforce_run_witness_recording_gate(
            _settings(
                run_witness_enabled=True,
                capture_watch_plan_id=uuid4(),
                run_witness_recording_enabled=False,
                capture_path_recording_enabled=True,
            )
        )


def test_path_recording_enabled_checked_before_the_first_gates_prerequisites() -> None:
    """Same independence property as the progress / baseline gates: the
    path gate's own message must appear even when the FIRST gate's
    prerequisites are also missing."""
    with pytest.raises(RuntimeError, match="RUN_WITNESS_RECORDING_ENABLED=true"):
        _enforce_run_witness_recording_gate(
            _settings(
                run_witness_enabled=False,
                capture_watch_plan_id=None,
                run_witness_recording_enabled=False,
                capture_path_recording_enabled=True,
            )
        )


def test_path_recording_enabled_with_run_witness_recording_passes() -> None:
    _enforce_run_witness_recording_gate(
        _settings(
            run_witness_enabled=True,
            capture_watch_plan_id=uuid4(),
            run_witness_recording_enabled=True,
            capture_path_recording_enabled=True,
        )
    )
