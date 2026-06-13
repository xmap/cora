"""Procedure evolver tests (10c-a genesis arm + 10c-b transition arms)."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.operation.aggregates.procedure import (
    STEPS_LOGBOOK_SCHEMA,
    Procedure,
    ProcedureAborted,
    ProcedureActivitiesLogbookOpened,
    ProcedureCompleted,
    ProcedureEvent,
    ProcedureIterationEnded,
    ProcedureIterationStarted,
    ProcedureName,
    ProcedureRegistered,
    ProcedureStarted,
    ProcedureStatus,
    ProcedureTruncated,
    evolve,
    fold,
)

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)


def _defined(
    *,
    procedure_id: UUID | None = None,
    name: str = "Vessel-A bakeout",
    kind: str = "bakeout",
    target_asset_ids: tuple[UUID, ...] | None = None,
    parent_run_id: UUID | None = None,
    capability_id: UUID | None = None,
) -> Procedure:
    """Build a Procedure in DEFINED state via fold of ProcedureRegistered."""
    state = fold(
        [
            ProcedureRegistered(
                procedure_id=procedure_id or uuid4(),
                name=name,
                kind=kind,
                target_asset_ids=target_asset_ids or (),
                parent_run_id=parent_run_id,
                capability_id=capability_id,
                occurred_at=_NOW,
            )
        ]
    )
    assert state is not None
    return state


@pytest.mark.unit
def test_evolve_procedure_registered_sets_status_to_defined() -> None:
    procedure_id = uuid4()
    asset1 = uuid4()
    asset2 = uuid4()
    state = evolve(
        None,
        ProcedureRegistered(
            procedure_id=procedure_id,
            name="2-BM rotation-axis alignment",
            kind="alignment",
            target_asset_ids=(asset1, asset2),
            parent_run_id=None,
            occurred_at=_NOW,
        ),
    )
    assert state == Procedure(
        id=procedure_id,
        name=ProcedureName("2-BM rotation-axis alignment"),
        kind="alignment",
        target_asset_ids=frozenset({asset1, asset2}),
        status=ProcedureStatus.DEFINED,
        parent_run_id=None,
    )


@pytest.mark.unit
def test_evolve_procedure_registered_with_parent_run_id() -> None:
    procedure_id = uuid4()
    parent_run = uuid4()
    state = evolve(
        None,
        ProcedureRegistered(
            procedure_id=procedure_id,
            name="Mid-run calibration sweep",
            kind="calibration",
            target_asset_ids=(),
            parent_run_id=parent_run,
            occurred_at=_NOW,
        ),
    )
    assert state.parent_run_id == parent_run
    assert state.target_asset_ids == frozenset()


@pytest.mark.unit
def test_evolve_procedure_registered_converts_target_assets_to_frozenset() -> None:
    """target_asset_ids stored as list in payload, frozenset in state."""
    asset1 = uuid4()
    state = evolve(
        None,
        ProcedureRegistered(
            procedure_id=uuid4(),
            name="X",
            kind="bakeout",
            target_asset_ids=(asset1, asset1),  # dup
            parent_run_id=None,
            occurred_at=_NOW,
        ),
    )
    assert isinstance(state.target_asset_ids, frozenset)
    assert state.target_asset_ids == frozenset({asset1})


@pytest.mark.unit
def test_fold_empty_event_list_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_single_procedure_registered_returns_procedure() -> None:
    procedure_id = uuid4()
    state = fold(
        [
            ProcedureRegistered(
                procedure_id=procedure_id,
                name="X",
                kind="bakeout",
                target_asset_ids=(),
                parent_run_id=None,
                occurred_at=_NOW,
            )
        ]
    )
    assert state is not None
    assert state.id == procedure_id
    assert state.status is ProcedureStatus.DEFINED


@pytest.mark.unit
def test_fold_is_pure_same_input_same_output() -> None:
    events = [
        ProcedureRegistered(
            procedure_id=uuid4(),
            name="X",
            kind="bakeout",
            target_asset_ids=(),
            parent_run_id=None,
            occurred_at=_NOW,
        )
    ]
    assert fold(events) == fold(events)


# --- 10c-b transition arms ---


@pytest.mark.unit
def test_evolve_procedure_started_sets_status_to_running() -> None:
    prior = _defined()
    state = evolve(prior, ProcedureStarted(procedure_id=prior.id, occurred_at=_NOW))
    assert state.status is ProcedureStatus.RUNNING


@pytest.mark.unit
def test_evolve_procedure_completed_sets_status_to_completed() -> None:
    prior = _defined()
    started = evolve(prior, ProcedureStarted(procedure_id=prior.id, occurred_at=_NOW))
    state = evolve(started, ProcedureCompleted(procedure_id=prior.id, occurred_at=_NOW))
    assert state.status is ProcedureStatus.COMPLETED


@pytest.mark.unit
def test_evolve_procedure_aborted_sets_status_to_aborted() -> None:
    prior = _defined()
    started = evolve(prior, ProcedureStarted(procedure_id=prior.id, occurred_at=_NOW))
    state = evolve(
        started, ProcedureAborted(procedure_id=prior.id, reason="quench", occurred_at=_NOW)
    )
    assert state.status is ProcedureStatus.ABORTED


@pytest.mark.unit
def test_evolve_procedure_started_preserves_all_fields() -> None:
    """Critical invariant: transition arms must NOT silently wipe additive state.

    Mirrors the per-transition preserve-fields tests in Run BC; pinned by
    the evolver docstring's "Critical invariant" note.
    """
    asset = uuid4()
    parent_run = uuid4()
    prior = _defined(
        name="2-BM rotation-axis alignment",
        kind="alignment",
        target_asset_ids=(asset,),
        parent_run_id=parent_run,
    )
    state = evolve(prior, ProcedureStarted(procedure_id=prior.id, occurred_at=_NOW))
    assert state.id == prior.id
    assert state.name == prior.name
    assert state.kind == "alignment"
    assert state.target_asset_ids == frozenset({asset})
    assert state.parent_run_id == parent_run


@pytest.mark.unit
def test_evolve_procedure_completed_preserves_all_fields() -> None:
    asset = uuid4()
    parent_run = uuid4()
    prior = _defined(
        name="2-BM rotation-axis alignment",
        kind="alignment",
        target_asset_ids=(asset,),
        parent_run_id=parent_run,
    )
    started = evolve(prior, ProcedureStarted(procedure_id=prior.id, occurred_at=_NOW))
    state = evolve(started, ProcedureCompleted(procedure_id=prior.id, occurred_at=_NOW))
    assert state.id == prior.id
    assert state.name == prior.name
    assert state.kind == "alignment"
    assert state.target_asset_ids == frozenset({asset})
    assert state.parent_run_id == parent_run


@pytest.mark.unit
def test_evolve_procedure_aborted_preserves_all_fields() -> None:
    asset = uuid4()
    prior = _defined(target_asset_ids=(asset,))
    started = evolve(prior, ProcedureStarted(procedure_id=prior.id, occurred_at=_NOW))
    state = evolve(started, ProcedureAborted(procedure_id=prior.id, reason="x", occurred_at=_NOW))
    assert state.id == prior.id
    assert state.name == prior.name
    assert state.kind == prior.kind
    assert state.target_asset_ids == frozenset({asset})


@pytest.mark.unit
def test_fold_full_happy_path_yields_completed() -> None:
    pid = uuid4()
    events = [
        ProcedureRegistered(
            procedure_id=pid,
            name="X",
            kind="bakeout",
            target_asset_ids=(),
            parent_run_id=None,
            occurred_at=_NOW,
        ),
        ProcedureStarted(procedure_id=pid, occurred_at=_NOW),
        ProcedureCompleted(procedure_id=pid, occurred_at=_NOW),
    ]
    state = fold(events)
    assert state is not None
    assert state.status is ProcedureStatus.COMPLETED


@pytest.mark.unit
def test_fold_aborted_path_yields_aborted() -> None:
    pid = uuid4()
    events = [
        ProcedureRegistered(
            procedure_id=pid,
            name="X",
            kind="bakeout",
            target_asset_ids=(),
            parent_run_id=None,
            occurred_at=_NOW,
        ),
        ProcedureStarted(procedure_id=pid, occurred_at=_NOW),
        ProcedureAborted(procedure_id=pid, reason="quench", occurred_at=_NOW),
    ]
    state = fold(events)
    assert state is not None
    assert state.status is ProcedureStatus.ABORTED


@pytest.mark.unit
def test_evolve_procedure_started_on_empty_state_raises() -> None:
    """Transition events applied to None state are well-formed-stream violations."""
    with pytest.raises(ValueError, match="ProcedureStarted"):
        evolve(None, ProcedureStarted(procedure_id=uuid4(), occurred_at=_NOW))


@pytest.mark.unit
def test_evolve_procedure_completed_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="ProcedureCompleted"):
        evolve(None, ProcedureCompleted(procedure_id=uuid4(), occurred_at=_NOW))


@pytest.mark.unit
def test_evolve_procedure_aborted_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="ProcedureAborted"):
        evolve(None, ProcedureAborted(procedure_id=uuid4(), reason="x", occurred_at=_NOW))


# --- ProcedureActivitiesLogbookOpened arm ---


@pytest.mark.unit
def test_genesis_state_has_no_steps_logbook_id() -> None:
    """Procedure starts with activity_logbook_id=None; lazy-opened on first step."""
    state = _defined()
    assert state.activity_logbook_id is None


@pytest.mark.unit
def test_evolve_steps_logbook_opened_sets_logbook_id() -> None:
    prior = _defined()
    started = evolve(prior, ProcedureStarted(procedure_id=prior.id, occurred_at=_NOW))
    logbook_id = uuid4()
    state = evolve(
        started,
        ProcedureActivitiesLogbookOpened(
            procedure_id=prior.id,
            logbook_id=logbook_id,
            kind="steps",
            schema=STEPS_LOGBOOK_SCHEMA,
            occurred_at=_NOW,
        ),
    )
    assert state.activity_logbook_id == logbook_id


@pytest.mark.unit
def test_evolve_steps_logbook_opened_does_not_change_status() -> None:
    """Lazy-open is orthogonal to lifecycle; status preserved exactly."""
    prior = _defined()
    started = evolve(prior, ProcedureStarted(procedure_id=prior.id, occurred_at=_NOW))
    state = evolve(
        started,
        ProcedureActivitiesLogbookOpened(
            procedure_id=prior.id,
            logbook_id=uuid4(),
            kind="steps",
            schema=STEPS_LOGBOOK_SCHEMA,
            occurred_at=_NOW,
        ),
    )
    assert state.status is ProcedureStatus.RUNNING


@pytest.mark.unit
def test_evolve_steps_logbook_opened_preserves_all_other_fields() -> None:
    asset = uuid4()
    parent_run = uuid4()
    prior = _defined(
        name="2-BM rotation-axis alignment",
        kind="alignment",
        target_asset_ids=(asset,),
        parent_run_id=parent_run,
    )
    started = evolve(prior, ProcedureStarted(procedure_id=prior.id, occurred_at=_NOW))
    logbook_id = uuid4()
    state = evolve(
        started,
        ProcedureActivitiesLogbookOpened(
            procedure_id=prior.id,
            logbook_id=logbook_id,
            kind="steps",
            schema=STEPS_LOGBOOK_SCHEMA,
            occurred_at=_NOW,
        ),
    )
    assert state.id == prior.id
    assert state.name == prior.name
    assert state.kind == "alignment"
    assert state.target_asset_ids == frozenset({asset})
    assert state.parent_run_id == parent_run
    assert state.activity_logbook_id == logbook_id


@pytest.mark.unit
def test_evolve_transition_arms_preserve_steps_logbook_id() -> None:
    """Critical invariant extension: once activity_logbook_id is set,
    later transitions (Complete, Abort) must preserve it. Otherwise the additive
    field gets silently wiped on terminal transitions."""
    prior = _defined()
    started = evolve(prior, ProcedureStarted(procedure_id=prior.id, occurred_at=_NOW))
    logbook_id = uuid4()
    after_open = evolve(
        started,
        ProcedureActivitiesLogbookOpened(
            procedure_id=prior.id,
            logbook_id=logbook_id,
            kind="steps",
            schema=STEPS_LOGBOOK_SCHEMA,
            occurred_at=_NOW,
        ),
    )
    completed = evolve(after_open, ProcedureCompleted(procedure_id=prior.id, occurred_at=_NOW))
    assert completed.activity_logbook_id == logbook_id
    # And same on the abort terminal:
    aborted = evolve(
        after_open,
        ProcedureAborted(procedure_id=prior.id, reason="x", occurred_at=_NOW),
    )
    assert aborted.activity_logbook_id == logbook_id


@pytest.mark.unit
def test_fold_lazy_open_then_complete_yields_completed_with_logbook_id() -> None:
    pid = uuid4()
    logbook_id = uuid4()
    events = [
        ProcedureRegistered(
            procedure_id=pid,
            name="X",
            kind="bakeout",
            target_asset_ids=(),
            parent_run_id=None,
            occurred_at=_NOW,
        ),
        ProcedureStarted(procedure_id=pid, occurred_at=_NOW),
        ProcedureActivitiesLogbookOpened(
            procedure_id=pid,
            logbook_id=logbook_id,
            kind="steps",
            schema=STEPS_LOGBOOK_SCHEMA,
            occurred_at=_NOW,
        ),
        ProcedureCompleted(procedure_id=pid, occurred_at=_NOW),
    ]
    state = fold(events)
    assert state is not None
    assert state.status is ProcedureStatus.COMPLETED
    assert state.activity_logbook_id == logbook_id


@pytest.mark.unit
def test_evolve_steps_logbook_opened_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="ProcedureActivitiesLogbookOpened"):
        evolve(
            None,
            ProcedureActivitiesLogbookOpened(
                procedure_id=uuid4(),
                logbook_id=uuid4(),
                kind="steps",
                schema=STEPS_LOGBOOK_SCHEMA,
                occurred_at=_NOW,
            ),
        )


# --- ProcedureTruncated arm ---


@pytest.mark.unit
def test_evolve_procedure_truncated_sets_status_to_truncated() -> None:
    prior = _defined()
    started = evolve(prior, ProcedureStarted(procedure_id=prior.id, occurred_at=_NOW))
    state = evolve(
        started,
        ProcedureTruncated(
            procedure_id=prior.id,
            reason="weekend power loss",
            interrupted_at=None,
            occurred_at=_NOW,
        ),
    )
    assert state.status is ProcedureStatus.TRUNCATED


@pytest.mark.unit
def test_evolve_procedure_truncated_preserves_all_fields() -> None:
    asset = uuid4()
    parent_run = uuid4()
    prior = _defined(
        name="2-BM rotation-axis alignment",
        kind="alignment",
        target_asset_ids=(asset,),
        parent_run_id=parent_run,
    )
    started = evolve(prior, ProcedureStarted(procedure_id=prior.id, occurred_at=_NOW))
    state = evolve(
        started,
        ProcedureTruncated(
            procedure_id=prior.id, reason="r", interrupted_at=None, occurred_at=_NOW
        ),
    )
    assert state.id == prior.id
    assert state.name == prior.name
    assert state.kind == "alignment"
    assert state.target_asset_ids == frozenset({asset})
    assert state.parent_run_id == parent_run


@pytest.mark.unit
def test_evolve_procedure_truncated_preserves_steps_logbook_id() -> None:
    """Critical-invariant extension: truncate must preserve activity_logbook_id."""
    prior = _defined()
    started = evolve(prior, ProcedureStarted(procedure_id=prior.id, occurred_at=_NOW))
    logbook_id = uuid4()
    after_open = evolve(
        started,
        ProcedureActivitiesLogbookOpened(
            procedure_id=prior.id,
            logbook_id=logbook_id,
            kind="steps",
            schema=STEPS_LOGBOOK_SCHEMA,
            occurred_at=_NOW,
        ),
    )
    state = evolve(
        after_open,
        ProcedureTruncated(
            procedure_id=prior.id, reason="r", interrupted_at=None, occurred_at=_NOW
        ),
    )
    assert state.activity_logbook_id == logbook_id


@pytest.mark.unit
def test_fold_truncated_path_yields_truncated() -> None:
    pid = uuid4()
    events = [
        ProcedureRegistered(
            procedure_id=pid,
            name="X",
            kind="bakeout",
            target_asset_ids=(),
            parent_run_id=None,
            occurred_at=_NOW,
        ),
        ProcedureStarted(procedure_id=pid, occurred_at=_NOW),
        ProcedureTruncated(
            procedure_id=pid,
            reason="weekend crash",
            interrupted_at=_NOW,
            occurred_at=_NOW,
        ),
    ]
    state = fold(events)
    assert state is not None
    assert state.status is ProcedureStatus.TRUNCATED


@pytest.mark.unit
def test_evolve_procedure_truncated_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="ProcedureTruncated"):
        evolve(
            None,
            ProcedureTruncated(
                procedure_id=uuid4(), reason="x", interrupted_at=None, occurred_at=_NOW
            ),
        )


# ---------- capability_id additive evolution ----------


@pytest.mark.unit
def test_evolve_procedure_registered_sets_capability_id_when_present() -> None:
    """Genesis: ProcedureRegistered with capability_id populates
    state.capability_id. Pinned because the additive field is what the
    cross-BC affordance contract reads back."""
    capability_id = uuid4()
    state = _defined(capability_id=capability_id)
    assert state.capability_id == capability_id


@pytest.mark.unit
def test_evolve_procedure_registered_capability_id_defaults_to_none() -> None:
    """Additive: legacy Procedures + ceremony Procedures with
    no Capability binding have `capability_id=None` after genesis."""
    state = _defined()
    assert state.capability_id is None


@pytest.mark.unit
def test_evolve_procedure_started_preserves_capability_id() -> None:
    """Invariant: ProcedureStarted MUST carry capability_id
    through from prior state. The Procedure(...) constructor without
    explicit `capability_id=` would silently wipe the additive field
    to None — same risk as the activity_logbook_id preservation invariant
    pinned by the analogous test at line ~373."""
    capability_id = uuid4()
    prior = _defined(capability_id=capability_id)
    started = evolve(prior, ProcedureStarted(procedure_id=prior.id, occurred_at=_NOW))
    assert started.capability_id == capability_id


@pytest.mark.unit
def test_evolve_procedure_completed_preserves_capability_id() -> None:
    """Invariant: Completed terminal preserves capability_id."""
    capability_id = uuid4()
    prior = _defined(capability_id=capability_id)
    started = evolve(prior, ProcedureStarted(procedure_id=prior.id, occurred_at=_NOW))
    completed = evolve(started, ProcedureCompleted(procedure_id=prior.id, occurred_at=_NOW))
    assert completed.capability_id == capability_id


@pytest.mark.unit
def test_evolve_procedure_aborted_preserves_capability_id() -> None:
    """Invariant: Aborted terminal preserves capability_id."""
    capability_id = uuid4()
    prior = _defined(capability_id=capability_id)
    started = evolve(prior, ProcedureStarted(procedure_id=prior.id, occurred_at=_NOW))
    aborted = evolve(started, ProcedureAborted(procedure_id=prior.id, reason="x", occurred_at=_NOW))
    assert aborted.capability_id == capability_id


@pytest.mark.unit
def test_evolve_procedure_truncated_preserves_capability_id() -> None:
    """Invariant: Truncated terminal preserves capability_id."""
    capability_id = uuid4()
    prior = _defined(capability_id=capability_id)
    started = evolve(prior, ProcedureStarted(procedure_id=prior.id, occurred_at=_NOW))
    truncated = evolve(
        started,
        ProcedureTruncated(
            procedure_id=prior.id, reason="x", interrupted_at=None, occurred_at=_NOW
        ),
    )
    assert truncated.capability_id == capability_id


@pytest.mark.unit
def test_evolve_steps_logbook_opened_preserves_capability_id() -> None:
    """Invariant: lazy-open envelope event preserves capability_id.
    Pinned because StepsLogbookOpened sets a different additive field
    (activity_logbook_id) without touching the lifecycle status, so its
    handler had to carry every other additive field through manually."""
    capability_id = uuid4()
    prior = _defined(capability_id=capability_id)
    started = evolve(prior, ProcedureStarted(procedure_id=prior.id, occurred_at=_NOW))
    after_open = evolve(
        started,
        ProcedureActivitiesLogbookOpened(
            procedure_id=prior.id,
            logbook_id=uuid4(),
            kind="steps",
            schema=STEPS_LOGBOOK_SCHEMA,
            occurred_at=_NOW,
        ),
    )
    assert after_open.capability_id == capability_id


# --- iteration boundary pair (ProcedureIterationStarted / Ended) ---


def _running(*, procedure_id: UUID | None = None) -> Procedure:
    """Build a Procedure in RUNNING via Registered + Started fold."""
    prior = _defined(procedure_id=procedure_id)
    return evolve(prior, ProcedureStarted(procedure_id=prior.id, occurred_at=_NOW))


@pytest.mark.unit
def test_genesis_state_has_zero_iteration_count_and_none_open() -> None:
    state = _defined()
    assert state.iteration_count == 0
    assert state.current_iteration_index is None


@pytest.mark.unit
def test_evolve_iteration_started_bumps_count_and_sets_open_index() -> None:
    running = _running()
    state = evolve(
        running,
        ProcedureIterationStarted(procedure_id=running.id, iteration_index=1, occurred_at=_NOW),
    )
    assert state.iteration_count == 1
    assert state.current_iteration_index == 1
    assert state.status is ProcedureStatus.RUNNING  # iteration is orthogonal to lifecycle


@pytest.mark.unit
def test_evolve_iteration_ended_clears_open_index_keeps_count() -> None:
    running = _running()
    started = evolve(
        running,
        ProcedureIterationStarted(procedure_id=running.id, iteration_index=1, occurred_at=_NOW),
    )
    ended = evolve(
        started,
        ProcedureIterationEnded(
            procedure_id=running.id,
            iteration_index=1,
            converged=True,
            reason=None,
            occurred_at=_NOW,
        ),
    )
    assert ended.current_iteration_index is None
    assert ended.iteration_count == 1
    assert ended.status is ProcedureStatus.RUNNING


@pytest.mark.unit
def test_fold_iteration_sequence_yields_expected_count_and_open_marker() -> None:
    pid = uuid4()
    state = fold(
        [
            ProcedureRegistered(
                procedure_id=pid,
                name="2-BM center alignment",
                kind="center_alignment",
                target_asset_ids=(),
                parent_run_id=None,
                occurred_at=_NOW,
            ),
            ProcedureStarted(procedure_id=pid, occurred_at=_NOW),
            ProcedureIterationStarted(procedure_id=pid, iteration_index=1, occurred_at=_NOW),
            ProcedureIterationEnded(
                procedure_id=pid, iteration_index=1, converged=False, reason=None, occurred_at=_NOW
            ),
            ProcedureIterationStarted(procedure_id=pid, iteration_index=2, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.iteration_count == 2
    assert state.current_iteration_index == 2  # iteration 2 still open


@pytest.mark.unit
def test_evolve_iteration_started_preserves_all_other_fields() -> None:
    asset = uuid4()
    parent_run = uuid4()
    capability_id = uuid4()
    prior = _defined(
        name="2-BM center alignment",
        kind="center_alignment",
        target_asset_ids=(asset,),
        parent_run_id=parent_run,
        capability_id=capability_id,
    )
    running = evolve(prior, ProcedureStarted(procedure_id=prior.id, occurred_at=_NOW))
    state = evolve(
        running,
        ProcedureIterationStarted(procedure_id=prior.id, iteration_index=1, occurred_at=_NOW),
    )
    assert state.name == prior.name
    assert state.kind == "center_alignment"
    assert state.target_asset_ids == frozenset({asset})
    assert state.parent_run_id == parent_run
    assert state.capability_id == capability_id


@pytest.mark.unit
def test_transition_arms_preserve_iteration_fields() -> None:
    """A terminal transition after an open iteration keeps count + open index.

    Iteration is orthogonal to the lifecycle FSM: the terminal deciders
    (complete / abort / truncate) gate only on status==Running and do NOT
    forbid terminating with an iteration still open, so a terminal
    Procedure can retain a non-None current_iteration_index. That is
    benign (the projection never reads current_iteration_index and
    iteration_count stays correct); the evolver must still carry both
    fields through every arm, pinned per the critical-invariant note."""
    running = _running()
    started = evolve(
        running,
        ProcedureIterationStarted(procedure_id=running.id, iteration_index=1, occurred_at=_NOW),
    )
    aborted = evolve(
        started, ProcedureAborted(procedure_id=running.id, reason="x", occurred_at=_NOW)
    )
    assert aborted.iteration_count == 1
    assert aborted.current_iteration_index == 1


@pytest.mark.unit
def test_evolve_iteration_started_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="ProcedureIterationStarted"):
        evolve(
            None,
            ProcedureIterationStarted(procedure_id=uuid4(), iteration_index=1, occurred_at=_NOW),
        )


@pytest.mark.unit
def test_evolve_iteration_ended_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="ProcedureIterationEnded"):
        evolve(
            None,
            ProcedureIterationEnded(
                procedure_id=uuid4(),
                iteration_index=1,
                converged=True,
                reason=None,
                occurred_at=_NOW,
            ),
        )


# --- patience cap: max_consecutive_unconverged_iterations + streak fold ---


def _ie(pid: UUID, index: int, converged: bool | None) -> ProcedureIterationEnded:
    return ProcedureIterationEnded(
        procedure_id=pid, iteration_index=index, converged=converged, reason=None, occurred_at=_NOW
    )


@pytest.mark.unit
def test_genesis_reads_patience_cap_and_zero_streak() -> None:
    pid = uuid4()
    state = fold(
        [
            ProcedureRegistered(
                procedure_id=pid,
                name="center",
                kind="center_alignment",
                target_asset_ids=(),
                parent_run_id=None,
                occurred_at=_NOW,
                max_consecutive_unconverged_iterations=3,
            )
        ]
    )
    assert state is not None
    assert state.max_consecutive_unconverged_iterations == 3
    assert state.consecutive_unconverged_iterations == 0


@pytest.mark.unit
def test_genesis_without_cap_defaults_to_none() -> None:
    assert _defined().max_consecutive_unconverged_iterations is None
    assert _defined().consecutive_unconverged_iterations == 0


@pytest.mark.unit
def test_iteration_ended_folds_consecutive_unconverged_streak() -> None:
    pid = uuid4()
    running = _running(procedure_id=pid)

    def _open_then_end(prev: Procedure, index: int, converged: bool | None) -> Procedure:
        opened = evolve(
            prev,
            ProcedureIterationStarted(procedure_id=pid, iteration_index=index, occurred_at=_NOW),
        )
        return evolve(opened, _ie(pid, index, converged))

    s1 = _open_then_end(running, 1, False)
    assert s1.consecutive_unconverged_iterations == 1
    s2 = _open_then_end(s1, 2, None)  # None counts as a miss
    assert s2.consecutive_unconverged_iterations == 2
    s3 = _open_then_end(s2, 3, True)  # a win resets
    assert s3.consecutive_unconverged_iterations == 0
    s4 = _open_then_end(s3, 4, False)
    assert s4.consecutive_unconverged_iterations == 1


@pytest.mark.unit
def test_transition_arms_preserve_cap_and_streak() -> None:
    pid = uuid4()
    state = fold(
        [
            ProcedureRegistered(
                procedure_id=pid,
                name="center",
                kind="center_alignment",
                target_asset_ids=(),
                parent_run_id=None,
                occurred_at=_NOW,
                max_consecutive_unconverged_iterations=2,
            ),
            ProcedureStarted(procedure_id=pid, occurred_at=_NOW),
            ProcedureIterationStarted(procedure_id=pid, iteration_index=1, occurred_at=_NOW),
            _ie(pid, 1, False),
        ]
    )
    assert state is not None
    assert state.consecutive_unconverged_iterations == 1
    aborted = evolve(state, ProcedureAborted(procedure_id=pid, reason="x", occurred_at=_NOW))
    assert aborted.max_consecutive_unconverged_iterations == 2
    assert aborted.consecutive_unconverged_iterations == 1


# --- carry-forward guard: the evolver's "critical invariant" pinned per arm ---


def _rich_running_state(pid: UUID) -> Procedure:
    """A mid-flight Running Procedure with EVERY additive field non-default:
    bound Capability + Recipe, an open iteration, a non-zero count, and a
    non-zero unconverged streak under a cap. Used to prove each
    carry-forward arm preserves every additive field."""
    capability_id, recipe_id = uuid4(), uuid4()
    state = fold(
        [
            ProcedureRegistered(
                procedure_id=pid,
                name="center",
                kind="center_alignment",
                target_asset_ids=(),
                parent_run_id=None,
                occurred_at=_NOW,
                capability_id=capability_id,
                recipe_id=recipe_id,
                max_consecutive_unconverged_iterations=3,
            ),
            ProcedureStarted(procedure_id=pid, occurred_at=_NOW),
            ProcedureActivitiesLogbookOpened(
                procedure_id=pid,
                logbook_id=uuid4(),
                kind="steps",
                schema=STEPS_LOGBOOK_SCHEMA,
                occurred_at=_NOW,
            ),
            ProcedureIterationStarted(procedure_id=pid, iteration_index=1, occurred_at=_NOW),
            _ie(pid, 1, False),  # streak -> 1
            ProcedureIterationStarted(procedure_id=pid, iteration_index=2, occurred_at=_NOW),
        ]
    )
    assert state is not None
    # Precondition: every additive field is non-default before the arm runs.
    assert state.capability_id is not None
    assert state.recipe_id is not None
    assert state.activity_logbook_id is not None
    assert state.current_iteration_index == 2
    assert state.iteration_count == 2
    assert state.consecutive_unconverged_iterations == 1
    assert state.max_consecutive_unconverged_iterations == 3
    return state


def _carry_forward_event(arm: str, pid: UUID) -> ProcedureEvent:
    """Build one non-iteration carry-forward event by arm name."""
    if arm == "started":
        return ProcedureStarted(procedure_id=pid, occurred_at=_NOW)
    if arm == "completed":
        return ProcedureCompleted(procedure_id=pid, occurred_at=_NOW)
    if arm == "aborted":
        return ProcedureAborted(procedure_id=pid, reason="x", occurred_at=_NOW)
    if arm == "truncated":
        return ProcedureTruncated(
            procedure_id=pid, reason="x", interrupted_at=None, occurred_at=_NOW
        )
    return ProcedureActivitiesLogbookOpened(
        procedure_id=pid,
        logbook_id=uuid4(),
        kind="steps",
        schema=STEPS_LOGBOOK_SCHEMA,
        occurred_at=_NOW,
    )


@pytest.mark.unit
@pytest.mark.parametrize("arm", ["started", "completed", "aborted", "truncated", "logbook_opened"])
def test_carry_forward_arms_preserve_every_additive_field(arm: str) -> None:
    """Each non-iteration arm carries ALL additive fields through unchanged.

    Pins the evolver's "critical invariant" across every arm (not just
    Aborted), so dropping a field from any arm fails loudly. The iteration
    arms mutate the iteration fields by design and are covered separately.
    """
    pid = uuid4()
    prior = _rich_running_state(pid)
    result = evolve(prior, _carry_forward_event(arm, pid))
    assert result.capability_id == prior.capability_id
    assert result.recipe_id == prior.recipe_id
    assert result.current_iteration_index == prior.current_iteration_index
    assert result.iteration_count == prior.iteration_count
    assert result.consecutive_unconverged_iterations == prior.consecutive_unconverged_iterations
    assert (
        result.max_consecutive_unconverged_iterations
        == prior.max_consecutive_unconverged_iterations
    )
