"""Unit tests for the Run aggregate's evolver."""

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.run.aggregates.run import (
    Run,
    RunName,
    RunStatus,
    evolve,
    fold,
)
from cora.run.aggregates.run.events import (
    RunAborted,
    RunCompleted,
    RunHeld,
    RunResumed,
    RunStarted,
    RunStopped,
    RunTruncated,
)

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)


def _run_started(
    *,
    run_id: UUID | None = None,
    plan_id: UUID | None = None,
    subject_id: UUID | None = None,
) -> RunStarted:
    """Test helper: RunStarted with sensible defaults."""
    return RunStarted(
        run_id=run_id or uuid4(),
        name="32-ID FlyScan",
        plan_id=plan_id or uuid4(),
        subject_id=subject_id,
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_evolve_run_started_sets_status_to_running_with_subject() -> None:
    """RunStarted is the genesis event; status=Running, all fields preserved."""
    run_id = uuid4()
    plan_id = uuid4()
    subject_id = uuid4()
    state = evolve(
        None,
        RunStarted(
            run_id=run_id,
            name="32-ID FlyScan",
            plan_id=plan_id,
            subject_id=subject_id,
            occurred_at=_NOW,
        ),
    )
    assert state == Run(
        id=run_id,
        name=RunName("32-ID FlyScan"),
        plan_id=plan_id,
        subject_id=subject_id,
        status=RunStatus.RUNNING,
    )


@pytest.mark.unit
def test_evolve_run_started_without_subject_sets_subject_id_to_none() -> None:
    """Calibration / dark-field runs fold with subject_id=None."""
    state = evolve(None, _run_started(subject_id=None))
    assert state.subject_id is None
    assert state.status is RunStatus.RUNNING


@pytest.mark.unit
def test_fold_empty_event_list_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_single_run_started_returns_run() -> None:
    run_id = uuid4()
    state = fold([_run_started(run_id=run_id)])
    assert state is not None
    assert state.id == run_id
    assert state.status is RunStatus.RUNNING


@pytest.mark.unit
def test_fold_is_pure_same_input_same_output() -> None:
    events = [_run_started()]
    assert fold(events) == fold(events)


# ---------- terminal transitions ----------


@pytest.mark.unit
def test_evolve_run_completed_transitions_to_completed_preserving_other_fields() -> None:
    started = _run_started()
    state = evolve(None, started)
    completed = evolve(state, RunCompleted(run_id=started.run_id, occurred_at=_NOW))
    assert completed == replace(state, status=RunStatus.COMPLETED)
    assert completed.status is RunStatus.COMPLETED


@pytest.mark.unit
def test_evolve_run_aborted_transitions_to_aborted_preserving_other_fields() -> None:
    started = _run_started()
    state = evolve(None, started)
    aborted = evolve(
        state,
        RunAborted(run_id=started.run_id, reason="detector overheating", occurred_at=_NOW),
    )
    assert aborted == replace(state, status=RunStatus.ABORTED)
    assert aborted.status is RunStatus.ABORTED


@pytest.mark.unit
def test_evolve_run_completed_on_none_state_raises() -> None:
    """Defensive guard: a transition event before a genesis means
    the stream is contaminated. Fail loud rather than silently fold."""
    with pytest.raises(ValueError, match="RunCompleted cannot be applied to empty state"):
        evolve(None, RunCompleted(run_id=uuid4(), occurred_at=_NOW))


@pytest.mark.unit
def test_evolve_run_aborted_on_none_state_raises() -> None:
    with pytest.raises(ValueError, match="RunAborted cannot be applied to empty state"):
        evolve(None, RunAborted(run_id=uuid4(), reason="X", occurred_at=_NOW))


@pytest.mark.unit
def test_fold_started_then_completed_yields_completed() -> None:
    started = _run_started()
    state = fold([started, RunCompleted(run_id=started.run_id, occurred_at=_NOW)])
    assert state is not None
    assert state.status is RunStatus.COMPLETED


@pytest.mark.unit
def test_fold_started_then_aborted_yields_aborted_and_preserves_run_fields() -> None:
    run_id = uuid4()
    plan_id = uuid4()
    subject_id = uuid4()
    started = _run_started(run_id=run_id, plan_id=plan_id, subject_id=subject_id)
    state = fold([started, RunAborted(run_id=run_id, reason="beam dump", occurred_at=_NOW)])
    assert state is not None
    assert state.id == run_id
    assert state.plan_id == plan_id
    assert state.subject_id == subject_id
    assert state.status is RunStatus.ABORTED


# ---------- Held / Resumed / Stopped ----------


@pytest.mark.unit
def test_evolve_run_held_transitions_to_held_preserving_other_fields() -> None:
    started = _run_started()
    state = evolve(None, started)
    held = evolve(state, RunHeld(run_id=started.run_id, occurred_at=_NOW))
    assert held == replace(state, status=RunStatus.HELD)
    assert held.status is RunStatus.HELD


@pytest.mark.unit
def test_evolve_run_resumed_transitions_held_back_to_running() -> None:
    started = _run_started()
    running = evolve(None, started)
    held = evolve(running, RunHeld(run_id=started.run_id, occurred_at=_NOW))
    resumed = evolve(held, RunResumed(run_id=started.run_id, occurred_at=_NOW))
    assert resumed.status is RunStatus.RUNNING
    # The Run identity / plan / subject survive the round trip.
    assert resumed == replace(held, status=RunStatus.RUNNING)


@pytest.mark.unit
def test_evolve_run_stopped_transitions_to_stopped_preserving_other_fields() -> None:
    started = _run_started()
    state = evolve(None, started)
    stopped = evolve(
        state,
        RunStopped(run_id=started.run_id, reason="hit time budget", occurred_at=_NOW),
    )
    assert stopped == replace(state, status=RunStatus.STOPPED)
    assert stopped.status is RunStatus.STOPPED


@pytest.mark.unit
def test_evolve_run_held_on_none_state_raises() -> None:
    with pytest.raises(ValueError, match="RunHeld cannot be applied to empty state"):
        evolve(None, RunHeld(run_id=uuid4(), occurred_at=_NOW))


@pytest.mark.unit
def test_evolve_run_resumed_on_none_state_raises() -> None:
    with pytest.raises(ValueError, match="RunResumed cannot be applied to empty state"):
        evolve(None, RunResumed(run_id=uuid4(), occurred_at=_NOW))


@pytest.mark.unit
def test_evolve_run_stopped_on_none_state_raises() -> None:
    with pytest.raises(ValueError, match="RunStopped cannot be applied to empty state"):
        evolve(None, RunStopped(run_id=uuid4(), reason="X", occurred_at=_NOW))


@pytest.mark.unit
def test_fold_multi_cycle_hold_resume_then_complete_yields_completed() -> None:
    """Hold ⇄ Resume is unlimited-cycle. After [held, resumed, held,
    resumed, completed] the fold lands in Completed. Per-cycle audit
    lives in the event stream itself."""
    run_id = uuid4()
    started = _run_started(run_id=run_id)
    state = fold(
        [
            started,
            RunHeld(run_id=run_id, occurred_at=_NOW),
            RunResumed(run_id=run_id, occurred_at=_NOW),
            RunHeld(run_id=run_id, occurred_at=_NOW),
            RunResumed(run_id=run_id, occurred_at=_NOW),
            RunCompleted(run_id=run_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status is RunStatus.COMPLETED


@pytest.mark.unit
def test_fold_started_then_held_then_aborted_yields_aborted() -> None:
    """Abort source set widens to Running | Held: Held → Aborted folds correctly."""
    run_id = uuid4()
    started = _run_started(run_id=run_id)
    state = fold(
        [
            started,
            RunHeld(run_id=run_id, occurred_at=_NOW),
            RunAborted(run_id=run_id, reason="emergency during hold", occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status is RunStatus.ABORTED


@pytest.mark.unit
def test_fold_started_then_held_then_stopped_yields_stopped() -> None:
    """stop_run accepts Held source: Held → Stopped folds correctly."""
    run_id = uuid4()
    started = _run_started(run_id=run_id)
    state = fold(
        [
            started,
            RunHeld(run_id=run_id, occurred_at=_NOW),
            RunStopped(run_id=run_id, reason="ending early during hold", occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status is RunStatus.STOPPED


# ---------- 7d: raid preservation across transitions ----------


@pytest.mark.unit
def test_evolve_run_started_preserves_raid() -> None:
    """7d retrofit: raid carried verbatim into Run state on RunStarted."""
    state = evolve(
        None,
        _run_started_with_raid(raid="https://raid.org/10.7935/cora-test"),
    )
    assert state.raid == "https://raid.org/10.7935/cora-test"


@pytest.mark.unit
def test_evolve_run_started_without_raid_yields_state_with_raid_none() -> None:
    """Raid is optional; legacy-style RunStarted folds with raid=None."""
    state = evolve(None, _run_started())
    assert state.raid is None


# ---------- additive RunStarted payload (overrides + effective + trigger_source) ----------


@pytest.mark.unit
def test_evolve_run_started_folds_parameter_fields() -> None:
    """Additive payload: override_parameters + effective_parameters
    + trigger_source carry verbatim from RunStarted into Run state."""
    overrides = {"energy": 12.0}
    effective = {"energy": 12.0, "exposure": 100}
    state = evolve(
        None,
        RunStarted(
            run_id=uuid4(),
            name="X",
            plan_id=uuid4(),
            subject_id=None,
            occurred_at=_NOW,
            override_parameters=overrides,
            effective_parameters=effective,
            trigger_source="operator:opid:5",
        ),
    )
    assert state.override_parameters == overrides
    assert state.effective_parameters == effective
    assert state.trigger_source == "operator:opid:5"


@pytest.mark.unit
def test_evolve_run_started_without_parameter_fields_yields_state_defaults() -> None:
    """Legacy-style RunStarted (defaults via additive-state pattern)
    folds with empty dicts and None trigger_source."""
    state = evolve(None, _run_started())
    assert state.override_parameters == {}
    assert state.effective_parameters == {}
    assert state.trigger_source is None


@pytest.mark.unit
def test_evolve_held_then_resumed_preserves_parameter_fields() -> None:
    """Critical pin: every transition uses dataclass.replace which
    preserves all fields. override_parameters + effective_parameters
    + trigger_source must survive Hold → Resume cycles unchanged."""
    overrides = {"energy": 12.0}
    effective = {"energy": 12.0, "exposure": 100}
    state = evolve(
        None,
        RunStarted(
            run_id=uuid4(),
            name="X",
            plan_id=uuid4(),
            subject_id=None,
            occurred_at=_NOW,
            override_parameters=overrides,
            effective_parameters=effective,
            trigger_source="scheduler:auto",
        ),
    )
    held = evolve(state, RunHeld(run_id=state.id, occurred_at=_NOW))
    resumed = evolve(held, RunResumed(run_id=state.id, occurred_at=_NOW))
    assert resumed.override_parameters == overrides
    assert resumed.effective_parameters == effective
    assert resumed.trigger_source == "scheduler:auto"
    assert resumed.status is RunStatus.RUNNING


@pytest.mark.unit
@pytest.mark.parametrize(
    "transitions",
    [
        [RunHeld],
        [RunHeld, RunResumed],
        [RunCompleted],
        [RunAborted],
        [RunStopped],
        [RunTruncated],
        [RunHeld, RunAborted],
        [RunHeld, RunStopped],
        [RunHeld, RunTruncated],
        [RunHeld, RunResumed, RunCompleted],
    ],
)
def test_fold_preserves_raid_across_every_transition_path(
    transitions: list[type],
) -> None:
    """Structural property: replace(state, status=...) in evolver
    transition arms preserves the raid field by dataclass semantics.
    A future evolver refactor that constructs Run() from scratch in
    a transition arm would silently drop raid; this test guards it.

    Covers every reachable terminal (Completed / Aborted / Stopped /
    Truncated) plus the bidirectional Hold cycle, from the genesis
    raid being set on RunStarted.
    """
    run_id = uuid4()
    raid_value = "https://raid.org/10.7935/cora-fold-test"
    events: list[object] = [_run_started_with_raid(run_id=run_id, raid=raid_value)]
    for cls in transitions:
        if cls is RunAborted or cls is RunStopped:
            events.append(cls(run_id=run_id, reason="X", occurred_at=_NOW))
        elif cls is RunTruncated:
            events.append(
                RunTruncated(
                    run_id=run_id,
                    reason="X",
                    interrupted_at=None,
                    occurred_at=_NOW,
                )
            )
        else:
            events.append(cls(run_id=run_id, occurred_at=_NOW))
    state = fold(events)  # type: ignore[arg-type]
    assert state is not None
    assert state.raid == raid_value


def _run_started_with_raid(
    *,
    run_id: UUID | None = None,
    raid: str | None,
) -> RunStarted:
    return RunStarted(
        run_id=run_id or uuid4(),
        name="32-ID FlyScan",
        plan_id=uuid4(),
        subject_id=None,
        occurred_at=_NOW,
        raid=raid,
    )


# ---------- RunReadingLogbookOpened ----------

from cora.run.aggregates.run import (  # noqa: E402
    LOGBOOK_KIND_READING,
    READING_LOGBOOK_SCHEMA,
)
from cora.run.aggregates.run.events import RunReadingLogbookOpened  # noqa: E402


@pytest.mark.unit
def test_evolve_run_reading_logbook_opened_sets_logbook_id() -> None:
    """Lazy-open arm: RunReadingLogbookOpened sets reading_logbook_id
    while preserving status and all other fields."""
    run_id = uuid4()
    plan_id = uuid4()
    state_after_start = evolve(
        None,
        RunStarted(
            run_id=run_id,
            name="32-ID FlyScan",
            plan_id=plan_id,
            subject_id=None,
            occurred_at=_NOW,
        ),
    )
    assert state_after_start.reading_logbook_id is None  # baseline before open

    logbook_id = uuid4()
    open_event = RunReadingLogbookOpened(
        run_id=run_id,
        logbook_id=logbook_id,
        kind=LOGBOOK_KIND_READING,
        schema=READING_LOGBOOK_SCHEMA,
        occurred_at=_NOW,
    )
    state = evolve(state_after_start, open_event)
    assert state.reading_logbook_id == logbook_id
    # Status is orthogonal to logbook lifecycle; not touched.
    assert state.status is RunStatus.RUNNING
    # All other fields preserved.
    assert state.id == run_id
    assert state.plan_id == plan_id
    assert state.name == state_after_start.name


@pytest.mark.unit
def test_evolve_run_reading_logbook_opened_raises_on_empty_state() -> None:
    """Defensive: opening a logbook against an unstarted Run is
    stream corruption (the open event can never appear before
    RunStarted in a well-formed stream)."""
    open_event = RunReadingLogbookOpened(
        run_id=uuid4(),
        logbook_id=uuid4(),
        kind=LOGBOOK_KIND_READING,
        schema=READING_LOGBOOK_SCHEMA,
        occurred_at=_NOW,
    )
    with pytest.raises(ValueError, match="RunReadingLogbookOpened"):
        evolve(None, open_event)


@pytest.mark.unit
def test_evolve_terminal_after_logbook_opened_preserves_logbook_id() -> None:
    """Critical preserve-fields invariant: RunCompleted (and other
    terminals) MUST carry reading_logbook_id through. A regression
    that wiped it would lose the audit anchor for which logbook the
    Run's readings belong to."""
    run_id = uuid4()
    logbook_id = uuid4()
    state = fold(
        [
            RunStarted(
                run_id=run_id,
                name="32-ID FlyScan",
                plan_id=uuid4(),
                subject_id=None,
                occurred_at=_NOW,
            ),
            RunReadingLogbookOpened(
                run_id=run_id,
                logbook_id=logbook_id,
                kind=LOGBOOK_KIND_READING,
                schema=READING_LOGBOOK_SCHEMA,
                occurred_at=_NOW,
            ),
            RunCompleted(run_id=run_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status is RunStatus.COMPLETED
    assert state.reading_logbook_id == logbook_id


def _make_completed(rid: UUID) -> RunCompleted:
    return RunCompleted(run_id=rid, occurred_at=_NOW)


def _make_aborted(rid: UUID) -> RunAborted:
    return RunAborted(run_id=rid, reason="emergency", occurred_at=_NOW)


def _make_stopped(rid: UUID) -> RunStopped:
    return RunStopped(run_id=rid, reason="controlled stop", occurred_at=_NOW)


def _make_truncated(rid: UUID) -> RunTruncated:
    return RunTruncated(run_id=rid, reason="crash", interrupted_at=None, occurred_at=_NOW)


_TerminalFactory = Callable[[UUID], RunCompleted | RunAborted | RunStopped | RunTruncated]


@pytest.mark.unit
@pytest.mark.parametrize(
    "terminal_factory",
    [_make_completed, _make_aborted, _make_stopped, _make_truncated],
)
def test_evolve_each_terminal_preserves_reading_logbook_id(
    terminal_factory: _TerminalFactory,
) -> None:
    """Every terminal arm carries reading_logbook_id through. Pinned
    per-terminal because the silent-wipe risk applies equally to all
    four terminals (the explicit-construction discipline in the
    evolver is what catches it)."""
    run_id = uuid4()
    logbook_id = uuid4()
    state = fold(
        [
            RunStarted(
                run_id=run_id,
                name="Run",
                plan_id=uuid4(),
                subject_id=None,
                occurred_at=_NOW,
            ),
            RunReadingLogbookOpened(
                run_id=run_id,
                logbook_id=logbook_id,
                kind=LOGBOOK_KIND_READING,
                schema=READING_LOGBOOK_SCHEMA,
                occurred_at=_NOW,
            ),
            terminal_factory(run_id),
        ]
    )
    assert state is not None
    assert state.reading_logbook_id == logbook_id


@pytest.mark.unit
def test_evolve_held_resumed_preserves_reading_logbook_id() -> None:
    """Hold ⇄ Resume cycle preserves reading_logbook_id (orthogonal
    to lifecycle)."""
    run_id = uuid4()
    logbook_id = uuid4()
    state = fold(
        [
            RunStarted(
                run_id=run_id,
                name="Run",
                plan_id=uuid4(),
                subject_id=None,
                occurred_at=_NOW,
            ),
            RunReadingLogbookOpened(
                run_id=run_id,
                logbook_id=logbook_id,
                kind=LOGBOOK_KIND_READING,
                schema=READING_LOGBOOK_SCHEMA,
                occurred_at=_NOW,
            ),
            RunHeld(run_id=run_id, occurred_at=_NOW),
            RunResumed(run_id=run_id, occurred_at=_NOW),
            RunHeld(run_id=run_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status is RunStatus.HELD
    assert state.reading_logbook_id == logbook_id


@pytest.mark.unit
def test_legacy_stream_without_reading_logbook_folds_with_none_reading_logbook_id() -> None:
    """Legacy Runs in the event store have no
    RunReadingLogbookOpened event in the stream. They MUST fold
    cleanly with reading_logbook_id=None — that's the additive
    backward-compat contract."""
    run_id = uuid4()
    state = fold(
        [
            RunStarted(
                run_id=run_id,
                name="Legacy Run",
                plan_id=uuid4(),
                subject_id=None,
                occurred_at=_NOW,
            ),
            RunCompleted(run_id=run_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.reading_logbook_id is None
    assert state.status is RunStatus.COMPLETED


# ---------- campaign_id field + RunAddedToCampaign / RunRemovedFromCampaign arms ----------


@pytest.mark.unit
def test_run_started_genesis_seeds_campaign_id_from_event() -> None:
    """RunStarted carries campaign_id when StartRun.campaign_id was
    supplied. Evolver passes it through to Run.campaign_id."""
    run_id = uuid4()
    campaign_id = uuid4()
    state = evolve(
        None,
        RunStarted(
            run_id=run_id,
            name="campaign-bound run",
            plan_id=uuid4(),
            subject_id=None,
            occurred_at=_NOW,
            campaign_id=campaign_id,
        ),
    )
    assert state.campaign_id == campaign_id


@pytest.mark.unit
def test_run_started_default_campaign_id_is_none() -> None:
    """Standalone Runs (no StartRun.campaign_id) fold with
    campaign_id=None."""
    state = evolve(None, _run_started())
    assert state.campaign_id is None


@pytest.mark.unit
def test_run_added_to_campaign_sets_campaign_id() -> None:
    """Post-hoc add_run_to_campaign writes RunAddedToCampaign to the
    Run stream. Evolver sets campaign_id."""
    from cora.run.aggregates.run.events import RunAddedToCampaign

    run_id = uuid4()
    campaign_id = uuid4()
    state = fold(
        [
            _run_started(run_id=run_id),
            RunAddedToCampaign(
                run_id=run_id,
                campaign_id=campaign_id,
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.campaign_id == campaign_id
    # Status preserved (membership orthogonal to lifecycle).
    assert state.status is RunStatus.RUNNING


@pytest.mark.unit
def test_run_added_to_campaign_on_empty_state_raises() -> None:
    """RunAddedToCampaign requires prior state (Run must have been
    started first; the slice's decider enforces this)."""
    from cora.run.aggregates.run.events import RunAddedToCampaign

    with pytest.raises(ValueError):
        evolve(
            None,
            RunAddedToCampaign(
                run_id=uuid4(),
                campaign_id=uuid4(),
                occurred_at=_NOW,
            ),
        )


@pytest.mark.unit
def test_run_removed_from_campaign_clears_campaign_id() -> None:
    """remove_run_from_campaign writes RunRemovedFromCampaign. Evolver
    clears campaign_id back to None."""
    from cora.run.aggregates.run.events import (
        RunAddedToCampaign,
        RunRemovedFromCampaign,
    )

    run_id = uuid4()
    campaign_id = uuid4()
    state = fold(
        [
            _run_started(run_id=run_id),
            RunAddedToCampaign(
                run_id=run_id,
                campaign_id=campaign_id,
                occurred_at=_NOW,
            ),
            RunRemovedFromCampaign(
                run_id=run_id,
                campaign_id=campaign_id,
                reason="removed",
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.campaign_id is None


@pytest.mark.unit
def test_run_removed_from_campaign_on_empty_state_raises() -> None:
    from cora.run.aggregates.run.events import RunRemovedFromCampaign

    with pytest.raises(ValueError):
        evolve(
            None,
            RunRemovedFromCampaign(
                run_id=uuid4(),
                campaign_id=uuid4(),
                reason="x",
                occurred_at=_NOW,
            ),
        )


@pytest.mark.unit
def test_campaign_id_survives_lifecycle_transitions() -> None:
    """Membership survives Run lifecycle transitions: held -> running
    -> completed keeps the campaign_id intact."""
    run_id = uuid4()
    campaign_id = uuid4()
    state = fold(
        [
            RunStarted(
                run_id=run_id,
                name="r",
                plan_id=uuid4(),
                subject_id=None,
                occurred_at=_NOW,
                campaign_id=campaign_id,
            ),
            RunHeld(run_id=run_id, occurred_at=_NOW),
            RunResumed(run_id=run_id, occurred_at=_NOW),
            RunCompleted(run_id=run_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.campaign_id == campaign_id
    assert state.status is RunStatus.COMPLETED


@pytest.mark.unit
def test_legacy_pre_6i_c_stream_folds_with_none_campaign_id() -> None:
    """Pre-6i-c Runs have no campaign_id on RunStarted (default None).
    They MUST fold cleanly without membership — additive backward-
    compat contract mirrors the reading_logbook_id pattern."""
    run_id = uuid4()
    state = fold(
        [
            RunStarted(
                run_id=run_id,
                name="Pre-6i-c Run",
                plan_id=uuid4(),
                subject_id=None,
                occurred_at=_NOW,
            ),
            RunCompleted(run_id=run_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.campaign_id is None


# ---------- RunAdjusted arm + new state fields ----------


@pytest.mark.unit
def test_run_started_defaults_last_adjusted_and_count() -> None:
    """6j: genesis state defaults last_adjusted_at=None, adjustment_count=0."""
    state = evolve(None, _run_started())
    assert state.last_adjusted_at is None
    assert state.adjustment_count == 0


@pytest.mark.unit
def test_run_adjusted_mutates_effective_and_stamps_denorm() -> None:
    """6j: RunAdjusted replaces effective_parameters with the event's
    post-merge snapshot; sets last_adjusted_at; increments count."""
    from cora.run.aggregates.run.events import RunAdjusted

    run_id = uuid4()
    started = RunStarted(
        run_id=run_id,
        name="Run",
        plan_id=uuid4(),
        subject_id=None,
        occurred_at=_NOW,
        effective_parameters={"energy": 10.0},
    )
    later = datetime(2026, 5, 14, 13, 0, 0, tzinfo=UTC)
    state = fold(
        [
            started,
            RunAdjusted(
                run_id=run_id,
                parameters_patch={"energy": 12.0},
                effective_parameters={"energy": 12.0},
                reason="x",
                occurred_at=later,
            ),
        ]
    )
    assert state is not None
    assert state.effective_parameters == {"energy": 12.0}
    assert state.last_adjusted_at == later
    assert state.adjustment_count == 1
    # Status preserved (steering orthogonal to lifecycle).
    assert state.status is RunStatus.RUNNING


@pytest.mark.unit
def test_two_run_adjusted_events_increment_count_cumulatively() -> None:
    from cora.run.aggregates.run.events import RunAdjusted

    run_id = uuid4()
    started = RunStarted(
        run_id=run_id,
        name="Run",
        plan_id=uuid4(),
        subject_id=None,
        occurred_at=_NOW,
        effective_parameters={"a": 1},
    )
    state = fold(
        [
            started,
            RunAdjusted(
                run_id=run_id,
                parameters_patch={"a": 2},
                effective_parameters={"a": 2},
                reason="first",
                occurred_at=_NOW,
            ),
            RunAdjusted(
                run_id=run_id,
                parameters_patch={"b": 3},
                effective_parameters={"a": 2, "b": 3},
                reason="second",
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.adjustment_count == 2
    assert state.effective_parameters == {"a": 2, "b": 3}


@pytest.mark.unit
def test_run_adjusted_on_empty_state_raises() -> None:
    from cora.run.aggregates.run.events import RunAdjusted

    with pytest.raises(ValueError, match="RunAdjusted"):
        evolve(
            None,
            RunAdjusted(
                run_id=uuid4(),
                parameters_patch={"x": 1},
                effective_parameters={"x": 1},
                reason="x",
                occurred_at=_NOW,
            ),
        )


@pytest.mark.unit
def test_held_then_resumed_preserves_adjustment_denorm() -> None:
    """6j: Hold ⇄ Resume cycles preserve last_adjusted_at +
    adjustment_count (orthogonal to lifecycle)."""
    from cora.run.aggregates.run.events import RunAdjusted

    run_id = uuid4()
    started = RunStarted(
        run_id=run_id,
        name="Run",
        plan_id=uuid4(),
        subject_id=None,
        occurred_at=_NOW,
        effective_parameters={"a": 1},
    )
    adjusted_at = datetime(2026, 5, 14, 13, 0, 0, tzinfo=UTC)
    state = fold(
        [
            started,
            RunAdjusted(
                run_id=run_id,
                parameters_patch={"a": 2},
                effective_parameters={"a": 2},
                reason="first",
                occurred_at=adjusted_at,
            ),
            RunHeld(run_id=run_id, occurred_at=_NOW),
            RunResumed(run_id=run_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.last_adjusted_at == adjusted_at
    assert state.adjustment_count == 1
    assert state.effective_parameters == {"a": 2}


@pytest.mark.unit
@pytest.mark.parametrize(
    "terminal_factory",
    [_make_completed, _make_aborted, _make_stopped, _make_truncated],
)
def test_each_terminal_preserves_adjustment_denorm(
    terminal_factory: _TerminalFactory,
) -> None:
    """6j critical preserve-fields invariant: every terminal arm carries
    last_adjusted_at + adjustment_count through. A regression that wiped
    them would lose the "last steered before close" audit anchor."""
    from cora.run.aggregates.run.events import RunAdjusted

    run_id = uuid4()
    adjusted_at = datetime(2026, 5, 14, 13, 0, 0, tzinfo=UTC)
    state = fold(
        [
            RunStarted(
                run_id=run_id,
                name="Run",
                plan_id=uuid4(),
                subject_id=None,
                occurred_at=_NOW,
            ),
            RunAdjusted(
                run_id=run_id,
                parameters_patch={"a": 1},
                effective_parameters={"a": 1},
                reason="adjust",
                occurred_at=adjusted_at,
            ),
            terminal_factory(run_id),
        ]
    )
    assert state is not None
    assert state.last_adjusted_at == adjusted_at
    assert state.adjustment_count == 1


@pytest.mark.unit
def test_legacy_pre_6j_stream_folds_with_default_adjustment_fields() -> None:
    """Pre-6j Runs have no RunAdjusted event in the stream. They MUST
    fold cleanly with last_adjusted_at=None + adjustment_count=0 —
    additive backward-compat contract."""
    run_id = uuid4()
    state = fold(
        [
            RunStarted(
                run_id=run_id,
                name="Pre-6j Run",
                plan_id=uuid4(),
                subject_id=None,
                occurred_at=_NOW,
            ),
            RunCompleted(run_id=run_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.last_adjusted_at is None
    assert state.adjustment_count == 0


# ---------- Calibration AsShot anchor immutability ----------


@pytest.mark.unit
def test_run_started_genesis_populates_pinned_calibration_ids_as_frozenset() -> None:
    """RunStarted carries the tuple-form on the event payload; the
    evolver coerces to frozenset for in-memory equality semantics."""
    pin_a = UUID("01900000-0000-7000-8000-00000000ca01")
    pin_b = UUID("01900000-0000-7000-8000-00000000ca02")
    run_id = uuid4()
    state = fold(
        [
            RunStarted(
                run_id=run_id,
                name="Pinned run",
                plan_id=uuid4(),
                subject_id=None,
                occurred_at=_NOW,
                pinned_calibration_ids=(pin_a, pin_b),
            ),
        ]
    )
    assert state is not None
    assert state.pinned_calibration_ids == frozenset({pin_a, pin_b})


@pytest.mark.unit
def test_legacy_pre_12b_run_folds_with_empty_pinned_calibration_ids() -> None:
    """Pre-12b Runs have no pinned_calibration_ids on RunStarted. They MUST
    fold to an empty frozenset — additive backward-compat contract."""
    run_id = uuid4()
    state = fold(
        [
            RunStarted(
                run_id=run_id,
                name="Pre-12b Run",
                plan_id=uuid4(),
                subject_id=None,
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.pinned_calibration_ids == frozenset()


@pytest.mark.unit
@pytest.mark.parametrize(
    "terminal_factory",
    [_make_completed, _make_aborted, _make_stopped, _make_truncated],
)
def test_each_terminal_preserves_pinned_calibration_ids_asshot_invariant(
    terminal_factory: _TerminalFactory,
) -> None:
    """Critical invariant: every terminal arm preserves the
    pinned_calibration_ids set verbatim. A regression that wiped them would
    silently break "what calibration was this scan acquired against?"
    queries forever — DNG AsShot lesson."""
    pin_a = UUID("01900000-0000-7000-8000-00000000ca01")
    pin_b = UUID("01900000-0000-7000-8000-00000000ca02")
    run_id = uuid4()
    state = fold(
        [
            RunStarted(
                run_id=run_id,
                name="Run",
                plan_id=uuid4(),
                subject_id=None,
                occurred_at=_NOW,
                pinned_calibration_ids=(pin_a, pin_b),
            ),
            terminal_factory(run_id),
        ]
    )
    assert state is not None
    assert state.pinned_calibration_ids == frozenset({pin_a, pin_b})


@pytest.mark.unit
def test_hold_resume_cycle_preserves_pinned_calibration_ids() -> None:
    """Hold + Resume are routine mid-flight; they must NOT touch the
    AsShot anchor."""
    from cora.run.aggregates.run.events import RunHeld, RunResumed

    pin_a = UUID("01900000-0000-7000-8000-00000000ca01")
    run_id = uuid4()
    state = fold(
        [
            RunStarted(
                run_id=run_id,
                name="Run",
                plan_id=uuid4(),
                subject_id=None,
                occurred_at=_NOW,
                pinned_calibration_ids=(pin_a,),
            ),
            RunHeld(run_id=run_id, occurred_at=_NOW),
            RunResumed(run_id=run_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.pinned_calibration_ids == frozenset({pin_a})


@pytest.mark.unit
def test_adjust_run_preserves_pinned_calibration_ids() -> None:
    """Even mid-flight parameter steering (adjust_run) MUST preserve the
    AsShot anchor — the design memo's strongest form of the rule."""
    from cora.run.aggregates.run.events import RunAdjusted

    pin_a = UUID("01900000-0000-7000-8000-00000000ca01")
    run_id = uuid4()
    state = fold(
        [
            RunStarted(
                run_id=run_id,
                name="Run",
                plan_id=uuid4(),
                subject_id=None,
                occurred_at=_NOW,
                pinned_calibration_ids=(pin_a,),
            ),
            RunAdjusted(
                run_id=run_id,
                parameters_patch={"a": 1},
                effective_parameters={"a": 1},
                reason="adjust",
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.pinned_calibration_ids == frozenset({pin_a})


@pytest.mark.unit
def test_reading_logbook_opened_preserves_pinned_calibration_ids() -> None:
    """Orthogonal arm: lazy logbook open MUST preserve the AsShot
    anchor. Same silent-wipe risk as the terminal arms — pinned
    explicitly because the field-add review surface is in the evolver,
    not the slice."""
    pin_a = UUID("01900000-0000-7000-8000-00000000ca01")
    pin_b = UUID("01900000-0000-7000-8000-00000000ca02")
    run_id = uuid4()
    state = fold(
        [
            RunStarted(
                run_id=run_id,
                name="Run",
                plan_id=uuid4(),
                subject_id=None,
                occurred_at=_NOW,
                pinned_calibration_ids=(pin_a, pin_b),
            ),
            RunReadingLogbookOpened(
                run_id=run_id,
                logbook_id=uuid4(),
                kind=LOGBOOK_KIND_READING,
                schema=READING_LOGBOOK_SCHEMA,
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.pinned_calibration_ids == frozenset({pin_a, pin_b})


@pytest.mark.unit
def test_run_added_to_campaign_preserves_pinned_calibration_ids() -> None:
    """Orthogonal arm: post-hoc Campaign membership assignment MUST
    preserve the AsShot anchor."""
    from cora.run.aggregates.run.events import RunAddedToCampaign

    pin_a = UUID("01900000-0000-7000-8000-00000000ca01")
    run_id = uuid4()
    state = fold(
        [
            RunStarted(
                run_id=run_id,
                name="Run",
                plan_id=uuid4(),
                subject_id=None,
                occurred_at=_NOW,
                pinned_calibration_ids=(pin_a,),
            ),
            RunAddedToCampaign(
                run_id=run_id,
                campaign_id=uuid4(),
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.pinned_calibration_ids == frozenset({pin_a})


@pytest.mark.unit
def test_run_removed_from_campaign_preserves_pinned_calibration_ids() -> None:
    """Orthogonal arm: post-hoc Campaign membership removal MUST
    preserve the AsShot anchor."""
    from cora.run.aggregates.run.events import (
        RunAddedToCampaign,
        RunRemovedFromCampaign,
    )

    pin_a = UUID("01900000-0000-7000-8000-00000000ca01")
    run_id = uuid4()
    campaign_id = uuid4()
    state = fold(
        [
            RunStarted(
                run_id=run_id,
                name="Run",
                plan_id=uuid4(),
                subject_id=None,
                occurred_at=_NOW,
                pinned_calibration_ids=(pin_a,),
            ),
            RunAddedToCampaign(
                run_id=run_id,
                campaign_id=campaign_id,
                occurred_at=_NOW,
            ),
            RunRemovedFromCampaign(
                run_id=run_id,
                campaign_id=campaign_id,
                reason="removed",
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.pinned_calibration_ids == frozenset({pin_a})


@pytest.mark.unit
def test_decision_debrief_requested_is_audit_only_no_state_mutation() -> None:
    """The lease marker emitted by Agent BC subscribers is provenance-only
    on the Run aggregate. Folding it must return the prior state
    unchanged. Per [[project-run-debriefer-lease-design]]: the lease's
    existence on the stream IS the lease; no Run aggregate state field
    tracks debrief authorization."""
    from cora.run.aggregates.run.events import DecisionDebriefRequested

    run_id = uuid4()
    started = _run_started(run_id=run_id)
    pre_lease = fold([started])
    assert pre_lease is not None
    post_lease = fold(
        [
            started,
            DecisionDebriefRequested(
                run_id=run_id,
                debriefer_agent_id=uuid4(),
                terminal_event_id=uuid4(),
                occurred_at=_NOW,
            ),
        ]
    )
    assert post_lease == pre_lease


@pytest.mark.unit
def test_decision_debrief_requested_on_empty_state_raises() -> None:
    """The lease event requires prior state (a Run must exist). An
    Agent BC subscriber attempting to lease a non-existent Run would
    be a serious orchestration bug; require_state surfaces it loudly."""
    from cora.run.aggregates.run.events import DecisionDebriefRequested

    with pytest.raises(ValueError):
        evolve(
            None,
            DecisionDebriefRequested(
                run_id=uuid4(),
                debriefer_agent_id=uuid4(),
                terminal_event_id=uuid4(),
                occurred_at=_NOW,
            ),
        )
