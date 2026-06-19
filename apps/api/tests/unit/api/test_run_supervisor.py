"""Tests for the RunSupervisor runtime (cora.api._run_supervisor).

Covers the pure v1 rule (decide_supervision) across every branch, plus a
fakes-driven tick that exercises the full decide -> Decision -> authorized
HoldRun loop, the Actor.active revocation gate, and the disabled no-op.
"""

# white-box test of the runtime internals (private functions / constants)
# pyright: reportPrivateUsage=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.agent.seed_run_supervisor import (
    RUN_SUPERVISOR_AGENT_ID,
    seed_run_supervisor_agent,
)
from cora.api._run_supervisor import (
    _MEM_DEFERRED,
    _MEM_HELD,
    decide_supervision,
    run_supervisor_lifespan,
)
from cora.decision.aggregates.decision import load_decision
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import AllowAllAuthorize, FakeClock, UUIDv7Generator
from cora.infrastructure.ports.beam_availability_lookup import BeamAvailabilityLookupResult
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.run.features.hold_run import HoldRun
from cora.run.features.list_runs import ListRuns, RunListPage, RunSummaryItem
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


# ---------- tick: full loop with fakes ----------


def _kernel() -> Kernel:
    settings = Settings()  # type: ignore[call-arg]
    return make_inmemory_kernel(
        settings=settings,
        clock=FakeClock(_NOW),
        id_generator=UUIDv7Generator(),
        authz=AllowAllAuthorize(),
    )


class _BeamDown:
    async def read_beam_availability(self) -> BeamAvailabilityLookupResult:
        return _beam(fes=False)


def _running_item(run_id: UUID) -> RunSummaryItem:
    return RunSummaryItem(
        run_id=run_id,
        name="streaming tomo",
        plan_id=uuid4(),
        subject_id=None,
        raid=None,
        status="Running",
        created_at=_NOW,
        override_parameters_present=False,
        campaign_id=None,
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


@pytest.mark.unit
async def test_tick_holds_running_run_when_beam_down_and_records_decision() -> None:
    from cora.api._run_supervisor import _supervise_tick

    kernel = _kernel()
    await seed_run_supervisor_agent(kernel)
    run_id = uuid4()
    list_runs = _make_list_runs([_running_item(run_id)])
    hold_run, hold_calls = _make_recording_hold()
    memory: dict[UUID, str] = {}

    await _supervise_tick(
        deps=kernel,
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
    from cora.api._run_supervisor import _supervise_tick

    kernel = _kernel()  # NOT seeded
    list_runs = _make_list_runs([_running_item(uuid4())])
    hold_run, hold_calls = _make_recording_hold()

    await _supervise_tick(
        deps=kernel,
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

    async with run_supervisor_lifespan(kernel, list_runs=list_runs, hold_run=hold_run):
        pass

    assert hold_calls == []
