"""Property-based tests for `adjust_run.decide` (Run BC).

Complements the example-based `test_adjust_run_decider.py` with
universal claims across generated inputs. The decider is pure

    (state, command, context, adjusted_by, now) -> list[RunAdjusted]

mid-flight parameter steering. Load-bearing properties:

  - state=None always raises `RunNotFoundError` carrying command.run_id.
  - The source-state guard is total over `RunStatus`: only
    `{Running, Held}` are adjustable; every terminal status raises
    `RunCannotAdjustError` carrying the current status.
  - An empty `parameters_patch` from an adjustable state always raises
    `InvalidRunAdjustPatchError`.
  - On the happy path (adjustable state, non-empty patch, valid reason,
    schemaless Method) the single `RunAdjusted` carries the threaded
    inputs: run_id=state.id, the patch verbatim, the merged effective
    set, the trimmed reason, the injected `adjusted_by`, the command's
    `decided_by_decision_id`, occurred_at=now.
  - Pure: same inputs return equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.run.aggregates.run import (
    InvalidRunAdjustPatchError,
    Run,
    RunAdjusted,
    RunCannotAdjustError,
    RunName,
    RunNotFoundError,
    RunStatus,
)
from cora.run.features import adjust_run
from cora.run.features.adjust_run import RunAdjustContext
from cora.run.features.adjust_run.command import AdjustRun
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_PLAN_ID = UUID(int=1)
_SUBJECT_ID = UUID(int=2)
_REASON = printable_ascii_text(min_size=1, max_size=500)
# Non-empty patch of non-null values: merge_patch over an empty base
# yields the patch verbatim (RFC 7396; null would delete, so excluded).
_PATCH = st.dictionaries(
    keys=printable_ascii_text(min_size=1, max_size=20),
    values=st.integers(),
    min_size=1,
    max_size=5,
)
_DECISION_ID = st.one_of(st.none(), st.uuids())

_ADJUSTABLE_SOURCES = (RunStatus.RUNNING, RunStatus.HELD)
_DISALLOWED_SOURCES = tuple(s for s in RunStatus if s not in frozenset(_ADJUSTABLE_SOURCES))


def _run(*, run_id: UUID, status: RunStatus, effective: dict[str, Any] | None = None) -> Run:
    return Run(
        id=run_id,
        name=RunName("32-ID FlyScan"),
        plan_id=_PLAN_ID,
        subject_id=_SUBJECT_ID,
        status=status,
        effective_parameters=effective or {},
    )


@pytest.mark.unit
@given(
    run_id=st.uuids(),
    patch=_PATCH,
    reason=_REASON,
    adjusted_by_uuid=st.uuids(),
    now=aware_datetimes(),
)
def test_adjust_with_none_state_always_raises_not_found(
    run_id: UUID,
    patch: dict[str, Any],
    reason: str,
    adjusted_by_uuid: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `RunNotFoundError` carrying command.run_id."""
    placeholder = _run(run_id=run_id, status=RunStatus.RUNNING)
    with pytest.raises(RunNotFoundError) as exc:
        adjust_run.decide(
            state=None,
            command=AdjustRun(run_id=run_id, parameters_patch=patch, reason=reason),
            context=RunAdjustContext(run=placeholder, method_parameters_schema=None),
            adjusted_by=ActorId(adjusted_by_uuid),
            now=now,
        )
    assert exc.value.run_id == run_id


@pytest.mark.unit
@given(
    run_id=st.uuids(),
    source=st.sampled_from(_ADJUSTABLE_SOURCES),
    patch=_PATCH,
    reason=_REASON,
    decision_id=_DECISION_ID,
    adjusted_by_uuid=st.uuids(),
    now=aware_datetimes(),
)
def test_adjust_from_adjustable_source_emits_single_event(
    run_id: UUID,
    source: RunStatus,
    patch: dict[str, Any],
    reason: str,
    decision_id: UUID | None,
    adjusted_by_uuid: UUID,
    now: datetime,
) -> None:
    """Running and Held both emit one RunAdjusted with threaded fields."""
    adjusted_by = ActorId(adjusted_by_uuid)
    state = _run(run_id=run_id, status=source, effective={})
    events = adjust_run.decide(
        state=state,
        command=AdjustRun(
            run_id=run_id,
            parameters_patch=patch,
            reason=reason,
            decided_by_decision_id=decision_id,
        ),
        context=RunAdjustContext(run=state, method_parameters_schema=None),
        adjusted_by=adjusted_by,
        now=now,
    )
    assert events == [
        RunAdjusted(
            run_id=run_id,
            parameters_patch=patch,
            effective_parameters=patch,
            reason=reason,
            adjusted_by=adjusted_by,
            decided_by_decision_id=decision_id,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    run_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    patch=_PATCH,
    reason=_REASON,
    adjusted_by_uuid=st.uuids(),
    now=aware_datetimes(),
)
def test_adjust_from_terminal_source_always_raises_cannot_adjust(
    run_id: UUID,
    source: RunStatus,
    patch: dict[str, Any],
    reason: str,
    adjusted_by_uuid: UUID,
    now: datetime,
) -> None:
    """Any terminal source raises RunCannotAdjustError carrying the status."""
    state = _run(run_id=run_id, status=source)
    with pytest.raises(RunCannotAdjustError) as exc:
        adjust_run.decide(
            state=state,
            command=AdjustRun(run_id=run_id, parameters_patch=patch, reason=reason),
            context=RunAdjustContext(run=state, method_parameters_schema=None),
            adjusted_by=ActorId(adjusted_by_uuid),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    run_id=st.uuids(),
    source=st.sampled_from(_ADJUSTABLE_SOURCES),
    reason=_REASON,
    adjusted_by_uuid=st.uuids(),
    now=aware_datetimes(),
)
def test_adjust_with_empty_patch_always_raises_invalid_patch(
    run_id: UUID,
    source: RunStatus,
    reason: str,
    adjusted_by_uuid: UUID,
    now: datetime,
) -> None:
    """An empty patch from an adjustable state raises InvalidRunAdjustPatchError."""
    state = _run(run_id=run_id, status=source)
    with pytest.raises(InvalidRunAdjustPatchError):
        adjust_run.decide(
            state=state,
            command=AdjustRun(run_id=run_id, parameters_patch={}, reason=reason),
            context=RunAdjustContext(run=state, method_parameters_schema=None),
            adjusted_by=ActorId(adjusted_by_uuid),
            now=now,
        )


@pytest.mark.unit
@given(
    run_id=st.uuids(),
    patch=_PATCH,
    reason=_REASON,
    adjusted_by_uuid=st.uuids(),
    now=aware_datetimes(),
)
def test_adjust_is_pure_same_input_same_output(
    run_id: UUID,
    patch: dict[str, Any],
    reason: str,
    adjusted_by_uuid: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _run(run_id=run_id, status=RunStatus.RUNNING)
    command = AdjustRun(run_id=run_id, parameters_patch=patch, reason=reason)
    context = RunAdjustContext(run=state, method_parameters_schema=None)
    adjusted_by = ActorId(adjusted_by_uuid)
    first = adjust_run.decide(
        state=state, command=command, context=context, adjusted_by=adjusted_by, now=now
    )
    second = adjust_run.decide(
        state=state, command=command, context=context, adjusted_by=adjusted_by, now=now
    )
    assert first == second
