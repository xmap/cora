"""Tests for the RunInitiator standing daemon (cora.api._run_initiator).

Covers the lifespan gate (disabled is a clean no-op; enabled spawns the loop),
the per-tick active-Plan resolution (runtime designation over the env fallback),
the idle path (enabled but no Plan resolved yet), the running path (a Plan
resolved -> the drains are exercised), and loop survival of a failing tick. The
selection brain `initiate_tick` is tested end-to-end in the integration
scenario; here the drains are faked so the loop machinery is exercised without a
real start.
"""

# white-box test of the runtime internals (private functions / constants)
# pyright: reportPrivateUsage=false

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.agent.features.set_agent_target_plan import SetAgentTargetPlan
from cora.agent.features.set_agent_target_plan import bind as bind_set_target_plan
from cora.agent.seed_run_initiator import RUN_INITIATOR_AGENT_ID, seed_run_initiator_agent
from cora.api._run_initiator import _resolve_active_plan, run_initiator_lifespan
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
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")


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
async def test_lifespan_idles_when_enabled_without_any_plan() -> None:
    """Enabled but no Plan (no designation, no fallback): the loop spawns but
    idles, never draining runs/subjects, and exits cleanly."""
    kernel = _kernel(enabled=True, plan_id=None)
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

    assert run_calls == []
    assert subject_calls == []


@pytest.mark.unit
async def test_lifespan_with_fallback_plan_drains_each_tick() -> None:
    """Enabled + the env fallback Plan: the lifespan spawns the loop, which ticks
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
async def test_lifespan_with_runtime_designation_drains_without_fallback() -> None:
    """No env fallback, but a runtime designation on the agent: the loop resolves
    the designated Plan each tick and drains. Proves designation drives the daemon."""
    kernel = _kernel(enabled=True, plan_id=None)
    await seed_run_initiator_agent(kernel)
    await bind_set_target_plan(kernel)(
        SetAgentTargetPlan(agent_id=RUN_INITIATOR_AGENT_ID, target_plan_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
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
async def test_resolve_active_plan_prefers_designation_over_fallback() -> None:
    """The runtime designation on the agent wins over the env fallback."""
    fallback = uuid4()
    designated = uuid4()
    kernel = _kernel(enabled=True, plan_id=fallback)
    await seed_run_initiator_agent(kernel)
    await bind_set_target_plan(kernel)(
        SetAgentTargetPlan(agent_id=RUN_INITIATOR_AGENT_ID, target_plan_id=designated),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert await _resolve_active_plan(kernel) == designated


@pytest.mark.unit
async def test_resolve_active_plan_uses_fallback_when_no_designation() -> None:
    """With no designation, resolution falls back to the env setting."""
    fallback = uuid4()
    kernel = _kernel(enabled=True, plan_id=fallback)
    await seed_run_initiator_agent(kernel)
    assert await _resolve_active_plan(kernel) == fallback


@pytest.mark.unit
async def test_resolve_active_plan_none_when_neither_designated_nor_fallback() -> None:
    """No designation and no fallback resolves to None (loop idles)."""
    kernel = _kernel(enabled=True, plan_id=None)
    await seed_run_initiator_agent(kernel)
    assert await _resolve_active_plan(kernel) is None


@pytest.mark.unit
async def test_record_initiation_decision_signs_the_agent_decision() -> None:
    """The initiator's agent-authored DecisionRegistered is signed at write time.

    DecisionRegistered is in SIGNED_EVENT_TYPES, so an agent row must carry a
    signature (an unsigned agent row trips the strict audit sweep). Pins the
    signing the proactive path previously omitted.
    """
    import dataclasses

    from cora.api._run_initiator import _record_initiation_decision
    from cora.infrastructure.signing import verify_signature
    from tests.unit.agent._helpers import Ed25519FakeSigner

    signer = Ed25519FakeSigner(kid="kid-run-initiator")
    kernel = dataclasses.replace(_kernel(), signer=signer)
    decision_id = uuid4()
    await _record_initiation_decision(
        kernel, decision_id=decision_id, plan_id=uuid4(), subject_id=None
    )

    events, _ = await kernel.event_store.load("Decision", decision_id)
    stored = events[0]
    assert stored.signature is not None
    assert stored.signature_kid == "kid-run-initiator"
    assert signer.received_actor_ids == [RUN_INITIATOR_AGENT_ID]

    async def _resolver(kid: str) -> bytes:
        assert kid == "kid-run-initiator"
        return signer.public_key_bytes

    await verify_signature(
        event_type=stored.event_type,
        payload=stored.payload,
        signature=stored.signature,
        kid=stored.signature_kid,
        resolve_public_key=_resolver,
    )


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
