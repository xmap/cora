"""Tests for the RunInitiator standing daemon (cora.api._run_initiator).

Covers the lifespan gate (disabled and enabled-without-plan are clean no-ops),
the loop spawning + ticking + clean cancel when enabled with a configured Plan,
and loop survival of a failing tick. The selection brain `initiate_tick` is
tested end-to-end in the integration scenario; here the drains are faked so the
loop machinery is exercised without a real start.
"""

# white-box test of the runtime internals (private functions / constants)
# pyright: reportPrivateUsage=false

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.agent.seed_run_initiator import seed_run_initiator_agent
from cora.api._run_initiator import run_initiator_lifespan
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import AllowAllAuthorize, FakeClock, UUIDv7Generator
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.run.features.list_runs import ListRuns, RunListPage
from cora.run.features.list_runs.handler import Handler as ListRunsHandler
from cora.subject.features.list_subjects import ListSubjects, SubjectListPage
from cora.subject.features.list_subjects.handler import Handler as ListSubjectsHandler

_NOW = datetime(2026, 6, 20, 12, 0, 0, tzinfo=UTC)


def _kernel(*, enabled: bool = False, plan_id: UUID | None = None) -> Kernel:
    settings = Settings(  # type: ignore[call-arg]
        run_initiator_enabled=enabled,
        run_initiator_plan_id=plan_id,
    )
    return make_inmemory_kernel(
        settings=settings,
        clock=FakeClock(_NOW),
        id_generator=UUIDv7Generator(),
        authz=AllowAllAuthorize(),
    )


def _make_recording_list_runs() -> tuple[ListRunsHandler, list[ListRuns]]:
    calls: list[ListRuns] = []

    async def list_runs(
        query: ListRuns,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> RunListPage:
        calls.append(query)
        return RunListPage(items=[], next_cursor=None)

    return list_runs, calls


def _make_recording_list_subjects() -> tuple[ListSubjectsHandler, list[ListSubjects]]:
    calls: list[ListSubjects] = []

    async def list_subjects(
        query: ListSubjects,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> SubjectListPage:
        calls.append(query)
        return SubjectListPage(items=[], next_cursor=None)

    return list_subjects, calls


def _make_failing_list_runs() -> ListRunsHandler:
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
async def test_lifespan_starts_nothing_when_disabled() -> None:
    """Default settings (run_initiator_enabled=False): clean no-op, no drain calls."""
    kernel = _kernel()
    list_runs, run_calls = _make_recording_list_runs()
    list_subjects, subject_calls = _make_recording_list_subjects()

    async with run_initiator_lifespan(kernel, list_runs=list_runs, list_subjects=list_subjects):
        pass

    assert run_calls == []
    assert subject_calls == []


@pytest.mark.unit
async def test_lifespan_starts_nothing_when_enabled_without_plan() -> None:
    """Enabled but no configured Plan: inert no-op, the loop is not spawned."""
    kernel = _kernel(enabled=True, plan_id=None)
    list_runs, run_calls = _make_recording_list_runs()
    list_subjects, subject_calls = _make_recording_list_subjects()

    async with run_initiator_lifespan(kernel, list_runs=list_runs, list_subjects=list_subjects):
        await asyncio.sleep(0.05)

    assert run_calls == []
    assert subject_calls == []


@pytest.mark.unit
async def test_lifespan_runs_the_loop_when_enabled_with_plan() -> None:
    """Enabled + a configured Plan: the lifespan spawns the loop, which ticks
    (draining runs + subjects) on the cadence, then cancels cleanly on exit."""
    kernel = _kernel(enabled=True, plan_id=uuid4())
    await seed_run_initiator_agent(kernel)
    list_runs, run_calls = _make_recording_list_runs()
    list_subjects, subject_calls = _make_recording_list_subjects()

    async with run_initiator_lifespan(
        kernel,
        list_runs=list_runs,
        list_subjects=list_subjects,
        interval_seconds=0.01,
    ):
        await asyncio.sleep(0.1)

    assert len(run_calls) >= 1
    assert len(subject_calls) >= 1


@pytest.mark.unit
async def test_loop_survives_a_failing_tick() -> None:
    """A tick that raises is logged and the loop keeps going; the lifespan exits
    cleanly (no exception escapes the context)."""
    kernel = _kernel(enabled=True, plan_id=uuid4())
    await seed_run_initiator_agent(kernel)
    list_runs = _make_failing_list_runs()
    list_subjects, _ = _make_recording_list_subjects()

    async with run_initiator_lifespan(
        kernel,
        list_runs=list_runs,
        list_subjects=list_subjects,
        interval_seconds=0.01,
    ):
        await asyncio.sleep(0.05)
