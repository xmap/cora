"""Unit tests for the `adjust_run` slice's pure decider.

Mid-flight parameter steering for in-progress Runs (Running | Held).
The decider validates source-state, patch shape, merged-result-against-
schema, reason length; returns `[RunAdjusted(...)]`.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.run.aggregates.run import (
    InvalidRunAdjustPatchError,
    InvalidRunAdjustReasonError,
    InvalidRunAdjustSchemaError,
    Run,
    RunCannotAdjustError,
    RunName,
    RunNotFoundError,
    RunStatus,
)
from cora.run.features.adjust_run import RunAdjustContext, decide
from cora.run.features.adjust_run.command import AdjustRun
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_ACTOR = ActorId(UUID("01900000-0000-7000-8000-0000000000ac"))
_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _run(
    *,
    run_id: UUID | None = None,
    status: RunStatus = RunStatus.RUNNING,
    effective: dict[str, Any] | None = None,
) -> Run:
    return Run(
        id=run_id or uuid4(),
        name=RunName("Run"),
        plan_id=uuid4(),
        subject_id=uuid4(),
        status=status,
        effective_parameters=effective or {},
    )


def _energy_schema() -> dict[str, Any]:
    return {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {
            "energy": {
                "type": "number",
                "minimum": 5,
                "maximum": 50,
                "unit": {"system": "udunits", "code": "keV"},
            },
            "exposure": {
                "type": "number",
                "minimum": 1,
                "unit": {"system": "udunits", "code": "ms"},
            },
        },
    }


# ---------- Happy paths ----------


@pytest.mark.unit
def test_decide_emits_run_adjusted_for_valid_patch_against_schema() -> None:
    state = _run(effective={"energy": 10.0, "exposure": 100})
    cmd = AdjustRun(
        run_id=state.id,
        parameters_patch={"energy": 12.0},
        reason="narrow ROI",
    )
    ctx = RunAdjustContext(run=state, method_parameters_schema=_energy_schema())

    events = decide(state=state, command=cmd, context=ctx, adjusted_by=_ACTOR, now=_NOW)

    assert len(events) == 1
    event = events[0]
    assert event.run_id == state.id
    assert event.parameters_patch == {"energy": 12.0}
    assert event.effective_parameters == {"energy": 12.0, "exposure": 100}
    assert event.reason == "narrow ROI"
    assert event.adjusted_by == _ACTOR
    assert event.decided_by_decision_id is None
    assert event.occurred_at == _NOW


@pytest.mark.unit
def test_decide_threads_decision_id_through_to_event() -> None:
    state = _run(effective={"energy": 10.0})
    decision_id = uuid4()
    cmd = AdjustRun(
        run_id=state.id,
        parameters_patch={"energy": 12.0},
        reason="agent decided",
        decided_by_decision_id=decision_id,
    )
    ctx = RunAdjustContext(run=state, method_parameters_schema=_energy_schema())

    events = decide(state=state, command=cmd, context=ctx, adjusted_by=_ACTOR, now=_NOW)
    assert events[0].decided_by_decision_id == decision_id


@pytest.mark.unit
def test_decide_accepts_held_state() -> None:
    """Multi-source guard accepts Held in addition to Running."""
    state = _run(status=RunStatus.HELD, effective={"energy": 10.0})
    cmd = AdjustRun(
        run_id=state.id,
        parameters_patch={"energy": 12.0},
        reason="adjust during pause",
    )
    ctx = RunAdjustContext(run=state, method_parameters_schema=None)

    events = decide(state=state, command=cmd, context=ctx, adjusted_by=_ACTOR, now=_NOW)
    assert len(events) == 1


@pytest.mark.unit
def test_decide_skips_schema_validation_when_schemaless() -> None:
    """STRICT-by-default per 5g-c is RELAXED for adjust on schemaless
    Methods: operator-responsibility territory (per design memo)."""
    state = _run(effective={})
    cmd = AdjustRun(
        run_id=state.id,
        parameters_patch={"undeclared_key": "any value"},
        reason="agent steering",
    )
    ctx = RunAdjustContext(run=state, method_parameters_schema=None)

    events = decide(state=state, command=cmd, context=ctx, adjusted_by=_ACTOR, now=_NOW)
    assert events[0].effective_parameters == {"undeclared_key": "any value"}


@pytest.mark.unit
def test_decide_preserves_prior_keys_untouched_by_patch() -> None:
    """RFC 7396 merge semantics: keys not in patch survive verbatim."""
    state = _run(effective={"energy": 10.0, "exposure": 100, "rotation": 180.0})
    cmd = AdjustRun(
        run_id=state.id,
        parameters_patch={"energy": 12.0},
        reason="re-energize only",
    )
    ctx = RunAdjustContext(run=state, method_parameters_schema=None)

    events = decide(state=state, command=cmd, context=ctx, adjusted_by=_ACTOR, now=_NOW)
    merged = events[0].effective_parameters
    assert merged == {"energy": 12.0, "exposure": 100, "rotation": 180.0}


@pytest.mark.unit
def test_decide_clears_key_when_patch_value_is_null() -> None:
    """RFC 7396 semantic: null in patch deletes the key."""
    state = _run(effective={"energy": 10.0, "exposure": 100})
    cmd = AdjustRun(
        run_id=state.id,
        parameters_patch={"exposure": None},
        reason="drop exposure override",
    )
    ctx = RunAdjustContext(run=state, method_parameters_schema=None)

    events = decide(state=state, command=cmd, context=ctx, adjusted_by=_ACTOR, now=_NOW)
    assert events[0].effective_parameters == {"energy": 10.0}


# ---------- Source-state guard ----------


@pytest.mark.unit
@pytest.mark.parametrize(
    "bad_status",
    [
        RunStatus.COMPLETED,
        RunStatus.ABORTED,
        RunStatus.STOPPED,
        RunStatus.TRUNCATED,
    ],
)
def test_decide_raises_cannot_adjust_for_terminal_states(
    bad_status: RunStatus,
) -> None:
    state = _run(status=bad_status, effective={"energy": 10.0})
    cmd = AdjustRun(
        run_id=state.id,
        parameters_patch={"energy": 12.0},
        reason="x",
    )
    ctx = RunAdjustContext(run=state, method_parameters_schema=None)

    with pytest.raises(RunCannotAdjustError) as exc_info:
        decide(state=state, command=cmd, context=ctx, adjusted_by=_ACTOR, now=_NOW)
    assert exc_info.value.run_id == state.id
    assert exc_info.value.current_status is bad_status


# ---------- Rejections ----------


@pytest.mark.unit
def test_decide_raises_run_not_found_when_state_is_none() -> None:
    cmd = AdjustRun(
        run_id=uuid4(),
        parameters_patch={"energy": 12.0},
        reason="x",
    )
    placeholder = _run()
    ctx = RunAdjustContext(run=placeholder, method_parameters_schema=None)

    with pytest.raises(RunNotFoundError) as exc_info:
        decide(state=None, command=cmd, context=ctx, adjusted_by=_ACTOR, now=_NOW)
    assert exc_info.value.run_id == cmd.run_id


@pytest.mark.unit
def test_decide_raises_invalid_patch_for_empty_patch() -> None:
    state = _run(effective={"energy": 10.0})
    cmd = AdjustRun(
        run_id=state.id,
        parameters_patch={},
        reason="x",
    )
    ctx = RunAdjustContext(run=state, method_parameters_schema=None)

    with pytest.raises(InvalidRunAdjustPatchError):
        decide(state=state, command=cmd, context=ctx, adjusted_by=_ACTOR, now=_NOW)


@pytest.mark.unit
def test_decide_raises_invalid_schema_for_post_merge_violation() -> None:
    state = _run(effective={"energy": 10.0})
    cmd = AdjustRun(
        run_id=state.id,
        parameters_patch={"energy": 1.0},  # below minimum=5
        reason="x",
    )
    ctx = RunAdjustContext(run=state, method_parameters_schema=_energy_schema())

    with pytest.raises(InvalidRunAdjustSchemaError):
        decide(state=state, command=cmd, context=ctx, adjusted_by=_ACTOR, now=_NOW)


@pytest.mark.unit
def test_decide_raises_invalid_reason_for_whitespace_only() -> None:
    state = _run(effective={"energy": 10.0})
    cmd = AdjustRun(
        run_id=state.id,
        parameters_patch={"energy": 12.0},
        reason="   ",
    )
    ctx = RunAdjustContext(run=state, method_parameters_schema=None)

    with pytest.raises(InvalidRunAdjustReasonError):
        decide(state=state, command=cmd, context=ctx, adjusted_by=_ACTOR, now=_NOW)


@pytest.mark.unit
def test_decide_raises_invalid_reason_for_too_long() -> None:
    state = _run(effective={"energy": 10.0})
    cmd = AdjustRun(
        run_id=state.id,
        parameters_patch={"energy": 12.0},
        reason="x" * 501,
    )
    ctx = RunAdjustContext(run=state, method_parameters_schema=None)

    with pytest.raises(InvalidRunAdjustReasonError):
        decide(state=state, command=cmd, context=ctx, adjusted_by=_ACTOR, now=_NOW)


@pytest.mark.unit
def test_decide_trims_reason_before_event_emission() -> None:
    state = _run(effective={})
    cmd = AdjustRun(
        run_id=state.id,
        parameters_patch={"a": 1},
        reason="  re-centering  ",
    )
    ctx = RunAdjustContext(run=state, method_parameters_schema=None)

    events = decide(state=state, command=cmd, context=ctx, adjusted_by=_ACTOR, now=_NOW)
    assert events[0].reason == "re-centering"


# ---------- Boundary + RFC 7396 explicit pins ----------


@pytest.mark.unit
def test_decide_accepts_reason_at_exactly_max_length() -> None:
    """Exact max-length boundary (500 chars after trim) is accepted."""
    state = _run(effective={})
    cmd = AdjustRun(
        run_id=state.id,
        parameters_patch={"a": 1},
        reason="x" * 500,
    )
    ctx = RunAdjustContext(run=state, method_parameters_schema=None)

    events = decide(state=state, command=cmd, context=ctx, adjusted_by=_ACTOR, now=_NOW)
    assert len(events) == 1
    assert events[0].reason == "x" * 500


@pytest.mark.unit
def test_decide_accepts_reason_at_exactly_one_char() -> None:
    """Exact min-length boundary (1 char after trim) is accepted."""
    state = _run(effective={})
    cmd = AdjustRun(
        run_id=state.id,
        parameters_patch={"a": 1},
        reason="x",
    )
    ctx = RunAdjustContext(run=state, method_parameters_schema=None)

    events = decide(state=state, command=cmd, context=ctx, adjusted_by=_ACTOR, now=_NOW)
    assert len(events) == 1
    assert events[0].reason == "x"


@pytest.mark.unit
def test_decide_adds_new_key_when_patch_introduces_one() -> None:
    """RFC 7396 add semantic: keys present only in the patch are added
    to the merged result alongside prior keys."""
    state = _run(effective={"a": 1})
    cmd = AdjustRun(
        run_id=state.id,
        parameters_patch={"b": 2},
        reason="add new key",
    )
    ctx = RunAdjustContext(run=state, method_parameters_schema=None)

    events = decide(state=state, command=cmd, context=ctx, adjusted_by=_ACTOR, now=_NOW)
    assert events[0].effective_parameters == {"a": 1, "b": 2}


# ---------- _ADJUSTABLE_STATUSES constant pin ----------


@pytest.mark.unit
def test_adjustable_statuses_constant_is_exactly_running_and_held() -> None:
    """Pin the source-state guard set against accidental widening if
    RunStatus enum grows. Adjust accepts ONLY Running and Held: Idle/
    Starting use override_parameters at start, terminal states are
    frozen."""
    from cora.run.features.adjust_run.decider import (
        _ADJUSTABLE_STATUSES,  # pyright: ignore[reportPrivateUsage]
    )

    assert set(_ADJUSTABLE_STATUSES) == {RunStatus.RUNNING, RunStatus.HELD}
