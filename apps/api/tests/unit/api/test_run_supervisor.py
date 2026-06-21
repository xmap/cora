"""Tests for the RunSupervisor runtime (cora.api._run_supervisor).

Covers the pure v1 rule (decide_supervision) across every branch, plus a
fakes-driven tick that exercises the full decide -> Decision -> authorized
HoldRun loop, the Actor.active revocation gate, and the disabled no-op.
"""

# white-box test of the runtime internals (private functions / constants)
# pyright: reportPrivateUsage=false

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import structlog
from hypothesis import given
from hypothesis import strategies as st

from cora.agent.seed_run_supervisor import (
    RUN_SUPERVISOR_AGENT_ID,
    seed_run_supervisor_agent,
)
from cora.api._run_supervisor import (
    _MEM_DEFERRED,
    _MEM_HELD,
    EnvelopeCheck,
    ObservationRuleConfig,
    _assemble_and_check_envelope,
    _issue_resume,
    _supervise_tick,
    decide_quality_signal,
    decide_signal_stall,
    decide_supervision,
    is_run_stale,
    run_supervisor_lifespan,
)
from cora.decision.aggregates.decision import load_decision
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import AllowAllAuthorize, FakeClock, UUIDv7Generator
from cora.infrastructure.ports.beam_availability_lookup import (
    BeamAvailabilityLookup,
    BeamAvailabilityLookupResult,
)
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.run.aggregates.run import RunCannotResumeError, RunNotFoundError, RunStatus
from cora.run.errors import UnauthorizedError
from cora.run.features.hold_run import HoldRun
from cora.run.features.hold_run.handler import Handler as HoldRunHandler
from cora.run.features.list_runs import ListRuns, RunListPage, RunSummaryItem
from cora.run.features.list_runs.handler import Handler as ListRunsHandler
from cora.run.features.resume_run import ResumeRun
from cora.run.features.resume_run.handler import Handler as ResumeRunHandler
from cora.run.ports import InMemoryRunChannelLookup, RunChannelLookup
from cora.shared.identity import ActorId

_NOW = datetime(2026, 6, 20, 12, 0, 0, tzinfo=UTC)


def _beam(
    *, fes: bool = True, sbs: bool = True, permit: bool = True, quality: bool = True
) -> BeamAvailabilityLookupResult:
    return BeamAvailabilityLookupResult(
        fes_open=fes, sbs_open=sbs, fes_permit=permit, quality_ok=quality
    )


# ---------- pure rule: decide_supervision ----------


@pytest.mark.unit
def test_beam_open_running_continues() -> None:
    out = decide_supervision(run_status="Running", beam=_beam(), prior=None)
    assert out.choice == "Continue"
    assert out.record is False
    assert out.issue_hold is False
    assert out.new_memory is None


@pytest.mark.unit
def test_beam_down_running_fresh_holds() -> None:
    out = decide_supervision(run_status="Running", beam=_beam(fes=False), prior=None)
    assert out.choice == "Hold"
    assert out.record is True
    assert out.issue_hold is True
    assert out.new_memory == _MEM_HELD


@pytest.mark.unit
def test_beam_down_running_after_our_hold_defers_to_operator() -> None:
    """Operator resumed a Run we held while beam is still down: respect them."""
    out = decide_supervision(run_status="Running", beam=_beam(sbs=False), prior=_MEM_HELD)
    assert out.choice == "SupervisionDeferred"
    assert out.record is True
    assert out.issue_hold is False
    assert out.new_memory == _MEM_DEFERRED


@pytest.mark.unit
def test_beam_down_running_already_deferred_is_quiet() -> None:
    out = decide_supervision(run_status="Running", beam=_beam(permit=False), prior=_MEM_DEFERRED)
    assert out.choice == "SupervisionDeferred"
    assert out.record is False
    assert out.issue_hold is False


@pytest.mark.unit
def test_beam_unknown_takes_no_action_and_keeps_prior() -> None:
    out = decide_supervision(run_status="Running", beam=_beam(quality=False), prior=_MEM_HELD)
    assert out.choice == "Continue"
    assert out.record is False
    assert out.issue_hold is False
    assert out.new_memory == _MEM_HELD


@pytest.mark.unit
def test_non_running_is_no_op() -> None:
    out = decide_supervision(run_status="Held", beam=_beam(fes=False), prior=_MEM_HELD)
    assert out.choice == "Continue"
    assert out.record is False
    assert out.issue_hold is False


# ---------- pure rule: gated wind-up (Resume) ----------


@pytest.mark.unit
def test_held_ours_envelope_safe_and_settled_resumes() -> None:
    """A Run the supervisor held, whose envelope is safe again and stable,
    is resumed and drops to DEFERRED (anti-flap)."""
    out = decide_supervision(
        run_status="Held",
        beam=_beam(),
        prior=_MEM_HELD,
        envelope_ok=True,
        settle_ticks_met=True,
    )
    assert out.choice == "Resume"
    assert out.record is True
    assert out.issue_resume is True
    assert out.issue_hold is False
    assert out.new_memory == _MEM_DEFERRED


@pytest.mark.unit
def test_held_ours_envelope_safe_but_not_settled_waits() -> None:
    """Envelope good but the settle window has not elapsed: keep watching,
    do not resume (anti-flap)."""
    out = decide_supervision(
        run_status="Held",
        beam=_beam(),
        prior=_MEM_HELD,
        envelope_ok=True,
        settle_ticks_met=False,
    )
    assert out.choice == "Continue"
    assert out.issue_resume is False
    assert out.record is False
    assert out.new_memory == _MEM_HELD


@pytest.mark.unit
def test_held_ours_envelope_unsafe_stays_held() -> None:
    """Settled but the envelope is not safe: never resume into a state a
    fresh start would refuse."""
    out = decide_supervision(
        run_status="Held",
        beam=_beam(),
        prior=_MEM_HELD,
        envelope_ok=False,
        settle_ticks_met=True,
    )
    assert out.choice == "Continue"
    assert out.issue_resume is False
    assert out.new_memory == _MEM_HELD


@pytest.mark.unit
def test_held_envelope_unknown_stays_held() -> None:
    """Fail-safe: an uncomputed/unknown envelope (None) never resumes."""
    out = decide_supervision(
        run_status="Held",
        beam=_beam(),
        prior=_MEM_HELD,
        envelope_ok=None,
        settle_ticks_met=True,
    )
    assert out.choice == "Continue"
    assert out.issue_resume is False


@pytest.mark.unit
def test_held_not_ours_never_auto_resumes() -> None:
    """Own-holds-only: a Held Run the supervisor did not hold (prior None,
    e.g. an operator hold or memory lost across restart) is never resumed,
    even with a safe, settled envelope."""
    out = decide_supervision(
        run_status="Held",
        beam=_beam(),
        prior=None,
        envelope_ok=True,
        settle_ticks_met=True,
    )
    assert out.choice == "Continue"
    assert out.issue_resume is False
    assert out.new_memory is None


# ---------- tick: full loop with fakes ----------


def _kernel(*, enabled: bool = False) -> Kernel:
    settings = Settings(run_supervisor_enabled=enabled)  # type: ignore[call-arg]
    return make_inmemory_kernel(
        settings=settings,
        clock=FakeClock(_NOW),
        id_generator=UUIDv7Generator(),
        authz=AllowAllAuthorize(),
    )


class _BeamDown:
    async def read(self) -> BeamAvailabilityLookupResult:
        return _beam(fes=False)


def _running_item(
    run_id: UUID,
    *,
    running_since: datetime | None = _NOW,
    snr_limit: float | None = None,
    expected_observation_interval_seconds: float | None = None,
) -> RunSummaryItem:
    return RunSummaryItem(
        run_id=run_id,
        name="streaming tomo",
        plan_id=uuid4(),
        subject_id=None,
        raid=None,
        status="Running",
        created_at=_NOW,
        running_since=running_since,
        override_parameters_present=False,
        campaign_id=None,
        snr_limit=snr_limit,
        expected_observation_interval_seconds=expected_observation_interval_seconds,
    )


def _make_list_runs(running: list[RunSummaryItem]):
    async def list_runs(
        query: ListRuns,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> RunListPage:
        items = running if query.status == "Running" else []
        return RunListPage(items=items, next_cursor=None)

    return list_runs


def _make_recording_hold():
    calls: list[HoldRun] = []

    async def hold_run(
        command: HoldRun,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        calls.append(command)

    return hold_run, calls


def _make_recording_resume() -> tuple[ResumeRunHandler, list[ResumeRun]]:
    calls: list[ResumeRun] = []

    async def resume_run(
        command: ResumeRun,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        calls.append(command)

    return resume_run, calls


def _rules_off() -> ObservationRuleConfig:
    """Observation rules disabled (channel names None): the default for tests
    that exercise only the beam-Hold / resume / liveness behavior."""
    return ObservationRuleConfig(
        quality_channel_name=None,
        stall_channel_name=None,
        stall_window_factor=3.0,
        stall_hysteresis_ticks=2,
        feed_heartbeat_ceiling_seconds=None,
    )


async def _tick(
    kernel: Kernel,
    *,
    list_runs: ListRunsHandler,
    hold_run: HoldRunHandler,
    beam_lookup: BeamAvailabilityLookup,
    memory: dict[UUID, str],
    resume_run: ResumeRunHandler | None = None,
    settle: dict[UUID, int] | None = None,
    resume_enabled: bool = False,
    resume_settle_ticks: int = 2,
    liveness: set[UUID] | None = None,
    liveness_ceiling_seconds: float | None = None,
    channel_lookup: RunChannelLookup | None = None,
    rules_config: ObservationRuleConfig | None = None,
    quality: set[UUID] | None = None,
    stall: set[UUID] | None = None,
    stall_streak: dict[UUID, int] | None = None,
    feed_dead_warned: set[UUID] | None = None,
) -> None:
    """Call _supervise_tick, defaulting the resume wiring (off) for hold-only tests."""
    if resume_run is None:
        resume_run, _ = _make_recording_resume()
    await _supervise_tick(
        deps=kernel,
        list_runs=list_runs,
        hold_run=hold_run,
        resume_run=resume_run,
        beam_lookup=beam_lookup,
        channel_lookup=channel_lookup if channel_lookup is not None else InMemoryRunChannelLookup(),
        rules_config=rules_config if rules_config is not None else _rules_off(),
        memory=memory,
        settle=settle if settle is not None else {},
        liveness=liveness if liveness is not None else set(),
        quality=quality if quality is not None else set(),
        stall=stall if stall is not None else set(),
        stall_streak=stall_streak if stall_streak is not None else {},
        feed_dead_warned=feed_dead_warned if feed_dead_warned is not None else set(),
        resume_enabled=resume_enabled,
        resume_settle_ticks=resume_settle_ticks,
        liveness_ceiling_seconds=liveness_ceiling_seconds,
    )


@pytest.mark.unit
async def test_tick_holds_running_run_when_beam_down_and_records_decision() -> None:

    kernel = _kernel()
    await seed_run_supervisor_agent(kernel)
    run_id = uuid4()
    list_runs = _make_list_runs([_running_item(run_id)])
    hold_run, hold_calls = _make_recording_hold()
    memory: dict[UUID, str] = {}

    await _tick(
        kernel,
        list_runs=list_runs,
        hold_run=hold_run,
        beam_lookup=_BeamDown(),
        memory=memory,
    )

    assert len(hold_calls) == 1
    held = hold_calls[0]
    assert held.run_id == run_id
    assert held.decided_by_decision_id is not None
    assert memory[run_id] == _MEM_HELD

    decision = await load_decision(kernel.event_store, held.decided_by_decision_id)
    assert decision is not None
    assert decision.context.value == "RunSupervision"
    assert decision.choice.value == "Hold"
    assert decision.decided_by == ActorId(RUN_SUPERVISOR_AGENT_ID)


@pytest.mark.unit
async def test_tick_is_noop_when_supervisor_actor_absent() -> None:
    """Revocation gate: with no seeded (active) supervisor Actor, do nothing."""
    kernel = _kernel()  # NOT seeded
    list_runs = _make_list_runs([_running_item(uuid4())])
    hold_run, hold_calls = _make_recording_hold()

    await _tick(
        kernel,
        list_runs=list_runs,
        hold_run=hold_run,
        beam_lookup=_BeamDown(),
        memory={},
    )

    assert hold_calls == []


@pytest.mark.unit
async def test_lifespan_is_noop_when_disabled() -> None:
    """Default settings (run_supervisor_enabled=False): clean no-op, no task."""
    kernel = _kernel()
    list_runs = _make_list_runs([])
    hold_run, hold_calls = _make_recording_hold()
    resume_run, _ = _make_recording_resume()

    async with run_supervisor_lifespan(
        kernel, list_runs=list_runs, hold_run=hold_run, resume_run=resume_run
    ):
        pass

    assert hold_calls == []


def _make_raising_hold(exc: Exception):
    async def hold_run(
        command: HoldRun,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        raise exc

    return hold_run


def _make_two_page_list_runs(item: RunSummaryItem):
    async def list_runs(
        query: ListRuns,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> RunListPage:
        if query.status != "Running":
            return RunListPage(items=[], next_cursor=None)
        if query.cursor is None:
            return RunListPage(items=[item], next_cursor="page2")
        return RunListPage(items=[], next_cursor=None)

    return list_runs


@pytest.mark.unit
async def test_tick_defers_when_operator_resumed_after_hold() -> None:
    """prior=HELD + beam still down + Running = operator resumed; defer, no re-hold."""
    kernel = _kernel()
    await seed_run_supervisor_agent(kernel)
    run_id = uuid4()
    list_runs = _make_list_runs([_running_item(run_id)])
    hold_run, hold_calls = _make_recording_hold()
    memory: dict[UUID, str] = {run_id: _MEM_HELD}

    await _tick(
        kernel, list_runs=list_runs, hold_run=hold_run, beam_lookup=_BeamDown(), memory=memory
    )

    assert hold_calls == []
    assert memory[run_id] == _MEM_DEFERRED


@pytest.mark.unit
async def test_tick_swallows_state_race_on_hold() -> None:
    """A Run that changed under us (RunNotFoundError) is a benign no-op, not a crash."""
    kernel = _kernel()
    await seed_run_supervisor_agent(kernel)
    run_id = uuid4()
    list_runs = _make_list_runs([_running_item(run_id)])
    hold_run = _make_raising_hold(RunNotFoundError(run_id))

    await _tick(kernel, list_runs=list_runs, hold_run=hold_run, beam_lookup=_BeamDown(), memory={})


@pytest.mark.unit
async def test_tick_swallows_unauthorized_hold() -> None:
    """An Authorize Deny (config fault) is logged, not raised; no autonomous action."""
    kernel = _kernel()
    await seed_run_supervisor_agent(kernel)
    run_id = uuid4()
    list_runs = _make_list_runs([_running_item(run_id)])
    hold_run = _make_raising_hold(UnauthorizedError("promoter not granted HoldRun"))

    await _tick(kernel, list_runs=list_runs, hold_run=hold_run, beam_lookup=_BeamDown(), memory={})


@pytest.mark.unit
async def test_tick_drains_paginated_running_runs() -> None:

    kernel = _kernel()
    await seed_run_supervisor_agent(kernel)
    run_id = uuid4()
    list_runs = _make_two_page_list_runs(_running_item(run_id))
    hold_run, hold_calls = _make_recording_hold()

    await _tick(kernel, list_runs=list_runs, hold_run=hold_run, beam_lookup=_BeamDown(), memory={})

    assert len(hold_calls) == 1
    assert hold_calls[0].run_id == run_id


@pytest.mark.unit
async def test_tick_garbage_collects_memory_for_terminated_runs() -> None:

    kernel = _kernel()
    await seed_run_supervisor_agent(kernel)
    stale_id = uuid4()
    list_runs = _make_list_runs([])  # nothing in flight
    hold_run, hold_calls = _make_recording_hold()
    memory: dict[UUID, str] = {stale_id: _MEM_HELD}

    await _tick(
        kernel, list_runs=list_runs, hold_run=hold_run, beam_lookup=_BeamDown(), memory=memory
    )

    assert stale_id not in memory
    assert hold_calls == []


@pytest.mark.unit
async def test_lifespan_enabled_runs_the_loop_and_holds() -> None:
    """Enabled: the lifespan spawns the loop, which holds a beam-down Run, then cancels on exit."""
    kernel = _kernel(enabled=True)
    await seed_run_supervisor_agent(kernel)
    run_id = uuid4()
    list_runs = _make_list_runs([_running_item(run_id)])
    hold_run, hold_calls = _make_recording_hold()
    resume_run, _ = _make_recording_resume()

    async with run_supervisor_lifespan(
        kernel,
        list_runs=list_runs,
        hold_run=hold_run,
        resume_run=resume_run,
        beam_lookup=_BeamDown(),
        interval_seconds=0.01,
    ):
        await asyncio.sleep(0.1)

    assert len(hold_calls) >= 1


def _make_failing_list_runs():
    async def list_runs(
        query: ListRuns,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> RunListPage:
        raise RuntimeError("list_runs boom")

    return list_runs


@pytest.mark.unit
async def test_record_decision_is_idempotent_on_repeated_id() -> None:
    """A re-derived Decision id (cross-restart) is a ConcurrencyError no-op, not a crash."""
    from cora.api._run_supervisor import _record_decision

    kernel = _kernel()
    decision_id = uuid4()
    run_id = uuid4()
    await _record_decision(
        kernel, decision_id=decision_id, run_id=run_id, choice="Hold", beam=_beam(fes=False)
    )
    await _record_decision(
        kernel, decision_id=decision_id, run_id=run_id, choice="Hold", beam=_beam(fes=False)
    )


@pytest.mark.unit
async def test_loop_survives_a_failing_tick() -> None:
    """A tick that raises is logged and the loop keeps going; the lifespan exits cleanly."""
    kernel = _kernel(enabled=True)
    await seed_run_supervisor_agent(kernel)
    hold_run, hold_calls = _make_recording_hold()
    resume_run, _ = _make_recording_resume()

    async with run_supervisor_lifespan(
        kernel,
        list_runs=_make_failing_list_runs(),
        hold_run=hold_run,
        resume_run=resume_run,
        beam_lookup=_BeamDown(),
        interval_seconds=0.01,
    ):
        await asyncio.sleep(0.05)

    assert hold_calls == []


# ---------- tick: gated resume pass ----------


class _BeamOpen:
    async def read(self) -> BeamAvailabilityLookupResult:
        return _beam()


def _held_item(run_id: UUID) -> RunSummaryItem:
    return RunSummaryItem(
        run_id=run_id,
        name="streaming tomo",
        plan_id=uuid4(),
        subject_id=None,
        raid=None,
        status="Held",
        created_at=_NOW,
        running_since=_NOW,
        override_parameters_present=False,
        campaign_id=None,
        snr_limit=None,
        expected_observation_interval_seconds=None,
    )


def _make_list_runs_split(
    *, running: list[RunSummaryItem] | None = None, held: list[RunSummaryItem] | None = None
):
    running_items = running or []
    held_items = held or []

    async def list_runs(
        query: ListRuns,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> RunListPage:
        if query.status == "Running":
            return RunListPage(items=running_items, next_cursor=None)
        if query.status == "Held":
            return RunListPage(items=held_items, next_cursor=None)
        return RunListPage(items=[], next_cursor=None)

    return list_runs


def _patch_envelope(monkeypatch: pytest.MonkeyPatch, *, ok: bool) -> None:
    """Stub the (I/O-heavy) envelope assembly; the real load + lookups path is
    covered end-to-end by the 2-BM auto-resume scenario."""

    async def _fake(deps: Kernel, item: RunSummaryItem, beam: BeamAvailabilityLookupResult):
        return EnvelopeCheck(ok=ok, failed_gate=None if ok else "clearance")

    monkeypatch.setattr("cora.api._run_supervisor._assemble_and_check_envelope", _fake)


@pytest.mark.unit
async def test_tick_resumes_held_run_after_settle_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """Envelope safe across the settle window: the supervisor resumes the Run it
    held, links a Resume Decision, and drops memory to DEFERRED."""
    _patch_envelope(monkeypatch, ok=True)
    kernel = _kernel()
    await seed_run_supervisor_agent(kernel)
    run_id = uuid4()
    list_runs = _make_list_runs_split(held=[_held_item(run_id)])
    hold_run, _ = _make_recording_hold()
    resume_run, resume_calls = _make_recording_resume()
    memory: dict[UUID, str] = {run_id: _MEM_HELD}
    settle: dict[UUID, int] = {}

    # Tick 1: first good read, settle=1 (< 2): no resume yet.
    await _tick(
        kernel,
        list_runs=list_runs,
        hold_run=hold_run,
        beam_lookup=_BeamOpen(),
        memory=memory,
        resume_run=resume_run,
        settle=settle,
        resume_enabled=True,
        resume_settle_ticks=2,
    )
    assert resume_calls == []
    assert memory[run_id] == _MEM_HELD

    # Tick 2: settle window met: resume.
    await _tick(
        kernel,
        list_runs=list_runs,
        hold_run=hold_run,
        beam_lookup=_BeamOpen(),
        memory=memory,
        resume_run=resume_run,
        settle=settle,
        resume_enabled=True,
        resume_settle_ticks=2,
    )
    assert len(resume_calls) == 1
    resumed = resume_calls[0]
    assert resumed.run_id == run_id
    assert resumed.decided_by_decision_id is not None
    assert memory[run_id] == _MEM_DEFERRED

    decision = await load_decision(kernel.event_store, resumed.decided_by_decision_id)
    assert decision is not None
    assert decision.choice.value == "Resume"
    assert decision.decided_by == ActorId(RUN_SUPERVISOR_AGENT_ID)


@pytest.mark.unit
async def test_tick_does_not_resume_when_envelope_unsafe(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unsafe envelope never resumes and never accrues the settle counter,
    even across many ticks (fail-safe; stays Held)."""
    _patch_envelope(monkeypatch, ok=False)
    kernel = _kernel()
    await seed_run_supervisor_agent(kernel)
    run_id = uuid4()
    list_runs = _make_list_runs_split(held=[_held_item(run_id)])
    hold_run, _ = _make_recording_hold()
    resume_run, resume_calls = _make_recording_resume()
    memory: dict[UUID, str] = {run_id: _MEM_HELD}
    settle: dict[UUID, int] = {}

    for _ in range(3):
        await _tick(
            kernel,
            list_runs=list_runs,
            hold_run=hold_run,
            beam_lookup=_BeamOpen(),
            memory=memory,
            resume_run=resume_run,
            settle=settle,
            resume_enabled=True,
            resume_settle_ticks=2,
        )

    assert resume_calls == []
    assert memory[run_id] == _MEM_HELD
    assert run_id not in settle


@pytest.mark.unit
async def test_tick_resume_disabled_never_resumes(monkeypatch: pytest.MonkeyPatch) -> None:
    """With the wind-up opt-in off, a held-by-us Run is not even a candidate."""
    _patch_envelope(monkeypatch, ok=True)
    kernel = _kernel()
    await seed_run_supervisor_agent(kernel)
    run_id = uuid4()
    list_runs = _make_list_runs_split(held=[_held_item(run_id)])
    hold_run, _ = _make_recording_hold()
    resume_run, resume_calls = _make_recording_resume()
    memory: dict[UUID, str] = {run_id: _MEM_HELD}

    await _tick(
        kernel,
        list_runs=list_runs,
        hold_run=hold_run,
        beam_lookup=_BeamOpen(),
        memory=memory,
        resume_run=resume_run,
        settle={},
        resume_enabled=False,
        resume_settle_ticks=2,
    )

    assert resume_calls == []
    assert memory[run_id] == _MEM_HELD


@pytest.mark.unit
async def test_tick_own_holds_only_skips_operator_held_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Held Run the supervisor did not hold (absent from memory) is never a
    resume candidate, even with the wind-up enabled and a safe envelope."""
    _patch_envelope(monkeypatch, ok=True)
    kernel = _kernel()
    await seed_run_supervisor_agent(kernel)
    run_id = uuid4()
    list_runs = _make_list_runs_split(held=[_held_item(run_id)])
    hold_run, _ = _make_recording_hold()
    resume_run, resume_calls = _make_recording_resume()
    memory: dict[UUID, str] = {}  # supervisor has no record of holding it

    await _tick(
        kernel,
        list_runs=list_runs,
        hold_run=hold_run,
        beam_lookup=_BeamOpen(),
        memory=memory,
        resume_run=resume_run,
        settle={},
        resume_enabled=True,
        resume_settle_ticks=2,
    )

    assert resume_calls == []
    assert run_id not in memory


# ---------- _issue_resume + _assemble_and_check_envelope edges ----------


def _make_raising_resume(exc: Exception) -> ResumeRunHandler:
    async def resume_run(
        command: ResumeRun,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        raise exc

    return resume_run


@pytest.mark.unit
async def test_issue_resume_swallows_state_race() -> None:
    """A Run resumed/terminated under us (RunCannotResume / RunNotFound) is a
    benign no-op, not a crash."""
    kernel = _kernel()
    run_id = uuid4()
    await _issue_resume(
        kernel,
        _make_raising_resume(RunCannotResumeError(run_id, current_status=RunStatus.RUNNING)),
        run_id=run_id,
        decision_id=uuid4(),
    )
    await _issue_resume(
        kernel,
        _make_raising_resume(RunNotFoundError(run_id)),
        run_id=run_id,
        decision_id=uuid4(),
    )


@pytest.mark.unit
async def test_issue_resume_swallows_unauthorized() -> None:
    """A missing ResumeRun grant (config fault) is logged, not raised."""
    kernel = _kernel()
    await _issue_resume(
        kernel,
        _make_raising_resume(UnauthorizedError("supervisor not granted ResumeRun")),
        run_id=uuid4(),
        decision_id=uuid4(),
    )


@pytest.mark.unit
async def test_tick_beam_open_running_is_noop_and_clears_memory() -> None:
    """Beam open on a Running run: Continue, no command, and the memory-clear
    branch (_apply_memory pop) runs."""
    kernel = _kernel()
    await seed_run_supervisor_agent(kernel)
    run_id = uuid4()
    list_runs = _make_list_runs([_running_item(run_id)])
    hold_run, hold_calls = _make_recording_hold()

    await _tick(kernel, list_runs=list_runs, hold_run=hold_run, beam_lookup=_BeamOpen(), memory={})

    assert hold_calls == []


@pytest.mark.unit
async def test_tick_garbage_collects_settle_for_terminated_runs() -> None:
    """A settle counter for a Run no longer in flight is pruned."""
    kernel = _kernel()
    await seed_run_supervisor_agent(kernel)
    stale_id = uuid4()
    list_runs = _make_list_runs([])  # nothing in flight
    hold_run, _ = _make_recording_hold()
    settle: dict[UUID, int] = {stale_id: 1}

    await _tick(
        kernel,
        list_runs=list_runs,
        hold_run=hold_run,
        beam_lookup=_BeamDown(),
        memory={},
        settle=settle,
        resume_enabled=True,
    )

    assert stale_id not in settle


@pytest.mark.unit
async def test_assemble_envelope_plan_missing_is_not_ok() -> None:
    """An unloadable upstream aggregate (corruption for a started Run) is
    fail-safe: not ok, so the supervisor leaves the Run Held."""
    kernel = _kernel()
    item = _held_item(uuid4())  # plan_id points at no events
    check = await _assemble_and_check_envelope(kernel, item, _beam())
    assert check.ok is False
    assert check.failed_gate == "plan_missing"


@pytest.mark.unit
def test_run_supervisor_resume_settle_ticks_rejects_zero() -> None:
    with pytest.raises(ValueError, match="run_supervisor_resume_settle_ticks"):
        Settings(run_supervisor_resume_settle_ticks=0)  # type: ignore[call-arg]


@pytest.mark.unit
def test_run_supervisor_resume_settle_ticks_accepts_valid() -> None:
    assert Settings(run_supervisor_resume_settle_ticks=3).run_supervisor_resume_settle_ticks == 3  # type: ignore[call-arg]


@pytest.mark.unit
def test_run_supervisor_tick_seconds_rejects_sub_floor() -> None:
    with pytest.raises(ValueError, match="run_supervisor_tick_seconds"):
        Settings(run_supervisor_tick_seconds=0.05)  # type: ignore[call-arg]


@pytest.mark.unit
def test_run_supervisor_tick_seconds_accepts_valid() -> None:
    assert Settings(run_supervisor_tick_seconds=5.0).run_supervisor_tick_seconds == 5.0  # type: ignore[call-arg]


# ---------- Run-liveness watchdog (shadow rule) ----------


@pytest.mark.unit
def test_is_run_stale_returns_true_when_running_since_old() -> None:
    assert is_run_stale(_NOW - timedelta(hours=2), _NOW, 3600.0) is True


@pytest.mark.unit
def test_is_run_stale_returns_false_when_running_since_recent() -> None:
    assert is_run_stale(_NOW - timedelta(minutes=1), _NOW, 3600.0) is False


@pytest.mark.unit
def test_is_run_stale_inclusive_at_ceiling() -> None:
    """Elapsed == ceiling FLAGS (inclusive >=); pins the `>`-vs-`>=` mutant."""
    assert is_run_stale(_NOW - timedelta(seconds=3600), _NOW, 3600.0) is True


@pytest.mark.unit
def test_is_run_stale_returns_false_when_running_since_none() -> None:
    assert is_run_stale(None, _NOW, 3600.0) is False


@pytest.mark.unit
async def test_shadow_liveness_flags_stale_run_observe_only() -> None:
    """A Run Running past the ceiling is added to the liveness set (would_flag),
    but the shadow pass issues NO command -- observe-only."""
    kernel = _kernel()
    await seed_run_supervisor_agent(kernel)
    run_id = uuid4()
    list_runs = _make_list_runs([_running_item(run_id, running_since=_NOW - timedelta(hours=2))])
    hold_run, hold_calls = _make_recording_hold()
    resume_run, resume_calls = _make_recording_resume()
    liveness: set[UUID] = set()

    await _tick(
        kernel,
        list_runs=list_runs,
        hold_run=hold_run,
        resume_run=resume_run,
        beam_lookup=_BeamOpen(),
        memory={},
        liveness=liveness,
        liveness_ceiling_seconds=3600.0,
    )

    assert liveness == {run_id}
    assert hold_calls == []  # observe-only: no command issued
    assert resume_calls == []


@pytest.mark.unit
async def test_shadow_liveness_does_not_flag_when_ceiling_none() -> None:
    """No ceiling set (default): even a multi-day-running Run is never flagged."""
    kernel = _kernel()
    await seed_run_supervisor_agent(kernel)
    run_id = uuid4()
    list_runs = _make_list_runs([_running_item(run_id, running_since=_NOW - timedelta(days=5))])
    hold_run, _hold = _make_recording_hold()
    liveness: set[UUID] = set()

    await _tick(
        kernel,
        list_runs=list_runs,
        hold_run=hold_run,
        beam_lookup=_BeamOpen(),
        memory={},
        liveness=liveness,
        liveness_ceiling_seconds=None,
    )

    assert liveness == set()


@pytest.mark.unit
async def test_shadow_liveness_not_flagged_when_running_since_recent() -> None:
    """A recently (re)started Run is not flagged. The rule keys on running_since,
    so a Run resumed after an overnight Held (running_since reset) is safe: the
    false-alarm the running_since column exists to prevent."""
    kernel = _kernel()
    await seed_run_supervisor_agent(kernel)
    run_id = uuid4()
    list_runs = _make_list_runs([_running_item(run_id, running_since=_NOW - timedelta(minutes=1))])
    hold_run, _hold = _make_recording_hold()
    liveness: set[UUID] = set()

    await _tick(
        kernel,
        list_runs=list_runs,
        hold_run=hold_run,
        beam_lookup=_BeamOpen(),
        memory={},
        liveness=liveness,
        liveness_ceiling_seconds=3600.0,
    )

    assert liveness == set()


@pytest.mark.unit
async def test_shadow_liveness_not_flagged_when_running_since_null() -> None:
    """A Run with no running_since (legacy row) is never flagged: cannot evaluate."""
    kernel = _kernel()
    await seed_run_supervisor_agent(kernel)
    run_id = uuid4()
    list_runs = _make_list_runs([_running_item(run_id, running_since=None)])
    hold_run, _hold = _make_recording_hold()
    liveness: set[UUID] = set()

    await _tick(
        kernel,
        list_runs=list_runs,
        hold_run=hold_run,
        beam_lookup=_BeamOpen(),
        memory={},
        liveness=liveness,
        liveness_ceiling_seconds=3600.0,
    )

    assert liveness == set()


@pytest.mark.unit
async def test_shadow_liveness_edge_triggered_across_ticks() -> None:
    """A steadily-stale Run is flagged once: the liveness set is stable across
    ticks (edge-triggered, no duplicate churn)."""
    kernel = _kernel()
    await seed_run_supervisor_agent(kernel)
    run_id = uuid4()
    list_runs = _make_list_runs([_running_item(run_id, running_since=_NOW - timedelta(hours=2))])
    hold_run, _hold = _make_recording_hold()
    liveness: set[UUID] = set()

    for _ in range(2):
        await _tick(
            kernel,
            list_runs=list_runs,
            hold_run=hold_run,
            beam_lookup=_BeamOpen(),
            memory={},
            liveness=liveness,
            liveness_ceiling_seconds=3600.0,
        )

    assert liveness == {run_id}


@pytest.mark.unit
async def test_shadow_liveness_flags_only_the_stale_run_among_running() -> None:
    """With several Running Runs, only the stale one is flagged; a fresh sibling
    is not poisoned."""
    kernel = _kernel()
    await seed_run_supervisor_agent(kernel)
    stale_id = uuid4()
    fresh_id = uuid4()
    list_runs = _make_list_runs(
        [
            _running_item(stale_id, running_since=_NOW - timedelta(hours=2)),
            _running_item(fresh_id, running_since=_NOW - timedelta(minutes=1)),
        ]
    )
    hold_run, _hold = _make_recording_hold()
    liveness: set[UUID] = set()

    await _tick(
        kernel,
        list_runs=list_runs,
        hold_run=hold_run,
        beam_lookup=_BeamOpen(),
        memory={},
        liveness=liveness,
        liveness_ceiling_seconds=3600.0,
    )

    assert liveness == {stale_id}


@pytest.mark.unit
async def test_shadow_liveness_prunes_run_that_left_inflight() -> None:
    """Once a flagged Run is no longer in-flight (terminated), its id is pruned
    from the liveness set (mirrors the memory/settle GC)."""
    kernel = _kernel()
    await seed_run_supervisor_agent(kernel)
    run_id = uuid4()
    hold_run, _hold = _make_recording_hold()
    liveness: set[UUID] = set()

    await _tick(
        kernel,
        list_runs=_make_list_runs([_running_item(run_id, running_since=_NOW - timedelta(hours=2))]),
        hold_run=hold_run,
        beam_lookup=_BeamOpen(),
        memory={},
        liveness=liveness,
        liveness_ceiling_seconds=3600.0,
    )
    assert liveness == {run_id}

    # Next tick: the Run has terminated (no longer returned by list_runs).
    await _tick(
        kernel,
        list_runs=_make_list_runs([]),
        hold_run=hold_run,
        beam_lookup=_BeamOpen(),
        memory={},
        liveness=liveness,
        liveness_ceiling_seconds=3600.0,
    )
    assert liveness == set()


@pytest.mark.unit
async def test_shadow_liveness_rediscards_then_reflags_on_resume() -> None:
    """Stale -> fresh (running_since reset, e.g. a resume) -> stale again: the
    edge-trigger discards on fresh and re-flags when it goes stale again."""
    kernel = _kernel()
    await seed_run_supervisor_agent(kernel)
    run_id = uuid4()
    hold_run, _hold = _make_recording_hold()
    liveness: set[UUID] = set()

    async def tick(running_since: datetime) -> None:
        await _tick(
            kernel,
            list_runs=_make_list_runs([_running_item(run_id, running_since=running_since)]),
            hold_run=hold_run,
            beam_lookup=_BeamOpen(),
            memory={},
            liveness=liveness,
            liveness_ceiling_seconds=3600.0,
        )

    await tick(_NOW - timedelta(hours=2))  # stale -> flagged
    assert liveness == {run_id}
    await tick(_NOW - timedelta(minutes=1))  # fresh (resumed) -> discarded
    assert liveness == set()
    await tick(_NOW - timedelta(hours=2))  # stale again -> re-flagged
    assert liveness == {run_id}


@pytest.mark.unit
def test_run_liveness_ceiling_rejects_non_positive() -> None:
    with pytest.raises(ValueError, match="run_liveness_ceiling_seconds"):
        Settings(run_liveness_ceiling_seconds=0.0)  # type: ignore[call-arg]


@pytest.mark.unit
def test_run_liveness_ceiling_accepts_none_and_positive() -> None:
    assert Settings().run_liveness_ceiling_seconds is None  # type: ignore[call-arg]
    assert (
        Settings(run_liveness_ceiling_seconds=7200.0).run_liveness_ceiling_seconds == 7200.0  # type: ignore[call-arg]
    )


# ---------- pure rules: decide_quality_signal / decide_signal_stall ----------


@pytest.mark.unit
def test_decide_quality_signal_flags_when_value_below_limit() -> None:
    out = decide_quality_signal(latest_value=3.0, snr_limit=5.0)
    assert out.would_flag is True
    assert out.reason == "quality_below_limit"


@pytest.mark.unit
def test_decide_quality_signal_within_limits_does_not_flag() -> None:
    out = decide_quality_signal(latest_value=8.0, snr_limit=5.0)
    assert out.would_flag is False
    assert out.reason == "within_limits"


@pytest.mark.unit
def test_decide_quality_signal_defers_when_limit_none() -> None:
    out = decide_quality_signal(latest_value=3.0, snr_limit=None)
    assert out.would_flag is False
    assert out.reason == "rule_disabled"


@pytest.mark.unit
def test_decide_quality_signal_defers_when_no_observation() -> None:
    out = decide_quality_signal(latest_value=None, snr_limit=5.0)
    assert out.would_flag is False
    assert out.reason == "no_observation"


@pytest.mark.unit
def test_decide_signal_stall_flags_when_zero_arrivals_and_clear() -> None:
    out = decide_signal_stall(
        count_since=0, window_seconds=30.0, expected_interval=10.0, feed_alive=True, beam_open=True
    )
    assert out.would_flag is True
    assert out.reason == "stalled"


@pytest.mark.unit
def test_decide_signal_stall_does_not_flag_when_arrivals_present() -> None:
    out = decide_signal_stall(
        count_since=2, window_seconds=30.0, expected_interval=10.0, feed_alive=True, beam_open=True
    )
    assert out.would_flag is False
    assert out.reason == "arriving"


@pytest.mark.unit
def test_decide_signal_stall_defers_when_feed_dead() -> None:
    out = decide_signal_stall(
        count_since=0, window_seconds=30.0, expected_interval=10.0, feed_alive=False, beam_open=True
    )
    assert out.would_flag is False
    assert out.reason == "feed_dead"


@pytest.mark.unit
def test_decide_signal_stall_defers_when_beam_down() -> None:
    out = decide_signal_stall(
        count_since=0, window_seconds=30.0, expected_interval=10.0, feed_alive=True, beam_open=False
    )
    assert out.would_flag is False
    assert out.reason == "beam_down"


@pytest.mark.unit
def test_decide_signal_stall_defers_when_interval_none() -> None:
    out = decide_signal_stall(
        count_since=0, window_seconds=30.0, expected_interval=None, feed_alive=True, beam_open=True
    )
    assert out.would_flag is False
    assert out.reason == "rule_disabled"


@pytest.mark.unit
def test_decide_signal_stall_defers_when_interval_degenerate() -> None:
    out = decide_signal_stall(
        count_since=0, window_seconds=30.0, expected_interval=0.0, feed_alive=True, beam_open=True
    )
    assert out.would_flag is False
    assert out.reason == "degenerate_interval"


@pytest.mark.unit
def test_decide_signal_stall_defers_when_window_too_short() -> None:
    out = decide_signal_stall(
        count_since=0, window_seconds=5.0, expected_interval=10.0, feed_alive=True, beam_open=True
    )
    assert out.would_flag is False
    assert out.reason == "window_too_short"


# ---------- property-based: the deciders' invariants ----------


@pytest.mark.unit
@given(
    value=st.floats(allow_nan=False, allow_infinity=False, width=32),
    limit=st.floats(min_value=0.001, max_value=1e6, allow_nan=False, allow_infinity=False),
)
def test_decide_quality_signal_flags_iff_below_limit(value: float, limit: float) -> None:
    """With both set, Rule Q flags exactly when the value is below the limit."""
    out = decide_quality_signal(latest_value=value, snr_limit=limit)
    assert out.would_flag == (value < limit)


@pytest.mark.unit
@given(
    count=st.integers(min_value=0, max_value=1000),
    interval=st.floats(min_value=0.1, max_value=1000.0),
    factor=st.floats(min_value=1.0, max_value=10.0),
    beam=st.booleans(),
)
def test_decide_signal_stall_defers_whenever_feed_dead(
    count: int, interval: float, factor: float, beam: bool
) -> None:
    """A dead feeder ALWAYS defers, regardless of count / interval / beam: a
    dead feeder can never be read as a stall (cannot-tell)."""
    out = decide_signal_stall(
        count_since=count,
        window_seconds=interval * factor,
        expected_interval=interval,
        feed_alive=False,
        beam_open=beam,
    )
    assert out.would_flag is False


@pytest.mark.unit
@given(
    count=st.integers(min_value=0, max_value=1000),
    interval=st.floats(min_value=0.1, max_value=1000.0),
    factor=st.floats(min_value=1.0, max_value=10.0),
)
def test_decide_signal_stall_defers_whenever_beam_down(
    count: int, interval: float, factor: float
) -> None:
    """Beam down ALWAYS defers: a data gap while the beam is down is expected,
    never a stall."""
    out = decide_signal_stall(
        count_since=count,
        window_seconds=interval * factor,
        expected_interval=interval,
        feed_alive=True,
        beam_open=False,
    )
    assert out.would_flag is False


@pytest.mark.unit
@given(
    count=st.integers(min_value=0, max_value=1000),
    interval=st.floats(min_value=0.1, max_value=1000.0),
    factor=st.floats(min_value=1.0, max_value=10.0),
)
def test_decide_signal_stall_flags_iff_zero_arrivals_when_clear(
    count: int, interval: float, factor: float
) -> None:
    """When the feed is alive, the beam is up, and the window covers at least
    one interval, the stall flag is exactly 'no arrivals'."""
    out = decide_signal_stall(
        count_since=count,
        window_seconds=interval * factor,
        expected_interval=interval,
        feed_alive=True,
        beam_open=True,
    )
    assert out.would_flag == (count == 0)


# ---------- shadow behavioral: observe-only, no command, no decision ----------


def _rules_quality(channel: str = "snr") -> ObservationRuleConfig:
    return ObservationRuleConfig(
        quality_channel_name=channel,
        stall_channel_name=None,
        stall_window_factor=3.0,
        stall_hysteresis_ticks=2,
        feed_heartbeat_ceiling_seconds=None,
    )


def _rules_stall(
    channel: str = "projection_index", *, hysteresis: int = 2, ceiling: float = 120.0
) -> ObservationRuleConfig:
    return ObservationRuleConfig(
        quality_channel_name=None,
        stall_channel_name=channel,
        stall_window_factor=3.0,
        stall_hysteresis_ticks=hysteresis,
        feed_heartbeat_ceiling_seconds=ceiling,
    )


@pytest.mark.unit
async def test_shadow_quality_flags_below_limit_without_command_or_decision() -> None:
    """Rule Q in shadow: a latest value below the operator limit lands the Run in
    the quality edge-set and logs would_flag, but issues NO command (observe-only)."""
    kernel = _kernel()
    await seed_run_supervisor_agent(kernel)
    run_id = uuid4()
    list_runs = _make_list_runs([_running_item(run_id, snr_limit=5.0)])
    hold_run, hold_calls = _make_recording_hold()
    resume_run, resume_calls = _make_recording_resume()
    lookup = InMemoryRunChannelLookup()
    lookup.register(run_id=run_id, channel_name="snr", value=3.0, recorded_at=_NOW)
    quality: set[UUID] = set()

    await _tick(
        kernel,
        list_runs=list_runs,
        hold_run=hold_run,
        resume_run=resume_run,
        beam_lookup=_BeamOpen(),
        memory={},
        channel_lookup=lookup,
        rules_config=_rules_quality(),
        quality=quality,
    )

    assert quality == {run_id}
    assert hold_calls == []
    assert resume_calls == []


@pytest.mark.unit
async def test_shadow_quality_does_not_flag_within_limits() -> None:
    kernel = _kernel()
    await seed_run_supervisor_agent(kernel)
    run_id = uuid4()
    list_runs = _make_list_runs([_running_item(run_id, snr_limit=5.0)])
    hold_run, _hold = _make_recording_hold()
    lookup = InMemoryRunChannelLookup()
    lookup.register(run_id=run_id, channel_name="snr", value=9.0, recorded_at=_NOW)
    quality: set[UUID] = set()

    await _tick(
        kernel,
        list_runs=list_runs,
        hold_run=hold_run,
        beam_lookup=_BeamOpen(),
        memory={},
        channel_lookup=lookup,
        rules_config=_rules_quality(),
        quality=quality,
    )

    assert quality == set()


@pytest.mark.unit
async def test_shadow_quality_does_not_flag_when_snr_limit_unset() -> None:
    """No precomputed snr_limit on the Run disables Rule Q (cannot-tell)."""
    kernel = _kernel()
    await seed_run_supervisor_agent(kernel)
    run_id = uuid4()
    list_runs = _make_list_runs([_running_item(run_id, snr_limit=None)])
    hold_run, _hold = _make_recording_hold()
    lookup = InMemoryRunChannelLookup()
    lookup.register(run_id=run_id, channel_name="snr", value=0.1, recorded_at=_NOW)
    quality: set[UUID] = set()

    await _tick(
        kernel,
        list_runs=list_runs,
        hold_run=hold_run,
        beam_lookup=_BeamOpen(),
        memory={},
        channel_lookup=lookup,
        rules_config=_rules_quality(),
        quality=quality,
    )

    assert quality == set()


@pytest.mark.unit
async def test_shadow_stall_flags_after_hysteresis_without_command() -> None:
    """Rule R in shadow: a stalled channel (alive feeder, beam up, zero arrivals)
    only flags after the hysteresis streak is met, and issues NO command."""
    kernel = _kernel()
    await seed_run_supervisor_agent(kernel)
    run_id = uuid4()
    list_runs = _make_list_runs([_running_item(run_id, expected_observation_interval_seconds=10.0)])
    hold_run, hold_calls = _make_recording_hold()
    resume_run, resume_calls = _make_recording_resume()
    lookup = InMemoryRunChannelLookup()
    lookup.register_heartbeat(run_id=run_id, recorded_at=_NOW)  # feeder alive, no data
    stall: set[UUID] = set()
    stall_streak: dict[UUID, int] = {}

    async def _one_tick() -> None:
        await _tick(
            kernel,
            list_runs=list_runs,
            hold_run=hold_run,
            resume_run=resume_run,
            beam_lookup=_BeamOpen(),
            memory={},
            channel_lookup=lookup,
            rules_config=_rules_stall(hysteresis=2),
            stall=stall,
            stall_streak=stall_streak,
        )

    await _one_tick()
    assert stall == set()  # streak 1 < 2: not yet
    await _one_tick()
    assert stall == {run_id}  # streak 2 >= 2: flagged
    assert hold_calls == []
    assert resume_calls == []


@pytest.mark.unit
async def test_shadow_stall_defers_when_feed_dead_and_warns() -> None:
    """A dead feeder (stale heartbeat) defers the stall rule and surfaces a loud
    feeder_unhealthy warning instead of a silent forever-defer."""
    kernel = _kernel()
    await seed_run_supervisor_agent(kernel)
    run_id = uuid4()
    list_runs = _make_list_runs([_running_item(run_id, expected_observation_interval_seconds=10.0)])
    hold_run, _hold = _make_recording_hold()
    lookup = InMemoryRunChannelLookup()
    lookup.register_heartbeat(run_id=run_id, recorded_at=_NOW - timedelta(seconds=300))  # stale
    stall: set[UUID] = set()
    stall_streak: dict[UUID, int] = {}
    feed_dead_warned: set[UUID] = set()

    await _tick(
        kernel,
        list_runs=list_runs,
        hold_run=hold_run,
        beam_lookup=_BeamOpen(),
        memory={},
        channel_lookup=lookup,
        rules_config=_rules_stall(ceiling=120.0),
        stall=stall,
        stall_streak=stall_streak,
        feed_dead_warned=feed_dead_warned,
    )

    assert stall == set()
    assert feed_dead_warned == {run_id}


@pytest.mark.unit
async def test_shadow_stall_does_not_flag_when_beam_down() -> None:
    """A data gap while the beam is down is expected: Rule R must not flag even
    with zero arrivals and a live feeder."""
    kernel = _kernel()
    await seed_run_supervisor_agent(kernel)
    run_id = uuid4()
    list_runs = _make_list_runs([_running_item(run_id, expected_observation_interval_seconds=10.0)])
    hold_run, _hold = _make_recording_hold()
    lookup = InMemoryRunChannelLookup()
    lookup.register_heartbeat(run_id=run_id, recorded_at=_NOW)
    stall: set[UUID] = set()

    await _tick(
        kernel,
        list_runs=list_runs,
        hold_run=hold_run,
        beam_lookup=_BeamDown(),
        memory={},
        channel_lookup=lookup,
        rules_config=_rules_stall(hysteresis=1),
        stall=stall,
        stall_streak={},
    )

    assert stall == set()


@pytest.mark.unit
async def test_shadow_quality_flag_leaves_beam_hold_memory_untouched() -> None:
    """The observation rules' edge-sets are walled off from the beam-Hold FSM
    memory: a Rule Q flag (beam open) leaves `memory` empty (no spurious hold)."""
    kernel = _kernel()
    await seed_run_supervisor_agent(kernel)
    run_id = uuid4()
    list_runs = _make_list_runs([_running_item(run_id, snr_limit=5.0)])
    hold_run, hold_calls = _make_recording_hold()
    lookup = InMemoryRunChannelLookup()
    lookup.register(run_id=run_id, channel_name="snr", value=1.0, recorded_at=_NOW)
    memory: dict[UUID, str] = {}
    quality: set[UUID] = set()

    await _tick(
        kernel,
        list_runs=list_runs,
        hold_run=hold_run,
        beam_lookup=_BeamOpen(),
        memory=memory,
        channel_lookup=lookup,
        rules_config=_rules_quality(),
        quality=quality,
    )

    assert quality == {run_id}
    assert memory == {}  # beam-Hold FSM memory untouched by the quality rule
    assert hold_calls == []


@pytest.mark.unit
async def test_shadow_quality_would_flag_log_carries_is_simulated_provenance() -> None:
    """The run_quality.would_flag log carries is_simulated so an operator doing
    forensics can tell a real breach from a simulator rehearsal. Locks the audit
    field in place so a refactor cannot silently drop it."""
    kernel = _kernel()
    await seed_run_supervisor_agent(kernel)
    run_id = uuid4()
    list_runs = _make_list_runs([_running_item(run_id, snr_limit=5.0)])
    hold_run, _hold = _make_recording_hold()
    lookup = InMemoryRunChannelLookup()
    lookup.register(
        run_id=run_id, channel_name="snr", value=2.0, recorded_at=_NOW, is_simulated=True
    )

    with structlog.testing.capture_logs() as logs:
        await _tick(
            kernel,
            list_runs=list_runs,
            hold_run=hold_run,
            beam_lookup=_BeamOpen(),
            memory={},
            channel_lookup=lookup,
            rules_config=_rules_quality(),
            quality=set(),
        )

    flagged = [e for e in logs if e.get("event") == "run_quality.would_flag"]
    assert len(flagged) == 1
    assert flagged[0]["is_simulated"] is True
    assert flagged[0]["run_id"] == str(run_id)
