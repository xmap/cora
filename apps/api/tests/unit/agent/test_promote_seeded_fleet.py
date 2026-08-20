"""The operator gesture that un-strands a deployment's shipped fleet.

A deployment seeded before the bootstrap promoted carries agents stuck
at `Defined`, unable to act and saying nothing about it. This command is
how a person fixes that on purpose.

What these pin: it promotes what it should, leaves alone what it must
not, writes nothing under `dry_run`, and is safe to run twice.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.agent._seeded_fleet import SEEDED_FLEET
from cora.agent.aggregates.agent import AgentStatus, load_agent
from cora.agent.features.suspend_agent import SuspendAgent
from cora.agent.features.suspend_agent import bind as bind_suspend
from cora.agent.promote_seeded_fleet import (
    OUTCOME_ABSENT,
    OUTCOME_ALREADY_READY,
    OUTCOME_PROMOTED,
    OUTCOME_SKIPPED,
    PromotionSummary,
    promote_seeded_fleet,
)
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from tests.unit._helpers import build_deps
from tests.unit.agent._helpers import seed_defined_agent, seed_versioned_agent

_NOW = datetime(2026, 5, 17, 14, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = uuid4()
_CORRELATION_ID = uuid4()

_FIRST = SEEDED_FLEET[0]
_SECOND = SEEDED_FLEET[1]


def _outcome_for(summary: PromotionSummary, agent_id: UUID) -> str:
    return next(item.outcome for item in summary.outcomes if item.agent_id == agent_id)


async def _run(store: InMemoryEventStore, *, dry_run: bool = False) -> PromotionSummary:
    deps = build_deps(ids=[uuid4() for _ in range(64)], now=_NOW, event_store=store)
    return await promote_seeded_fleet(
        deps,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        dry_run=dry_run,
    )


@pytest.mark.unit
async def test_promotes_a_defined_fleet_member() -> None:
    store = InMemoryEventStore()
    await seed_defined_agent(
        store,
        agent_id=_FIRST.agent_id,
        genesis_event_id=uuid4(),
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        occurred_at=_NOW,
    )

    summary = await _run(store)

    assert _outcome_for(summary, _FIRST.agent_id) == OUTCOME_PROMOTED
    agent = await load_agent(store, _FIRST.agent_id)
    assert agent is not None
    assert agent.status is AgentStatus.VERSIONED


@pytest.mark.unit
async def test_dry_run_reports_the_promotion_without_writing_it() -> None:
    store = InMemoryEventStore()
    await seed_defined_agent(
        store,
        agent_id=_FIRST.agent_id,
        genesis_event_id=uuid4(),
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        occurred_at=_NOW,
    )

    summary = await _run(store, dry_run=True)

    assert summary.dry_run is True
    assert _outcome_for(summary, _FIRST.agent_id) == OUTCOME_PROMOTED
    agent = await load_agent(store, _FIRST.agent_id)
    assert agent is not None
    assert agent.status is AgentStatus.DEFINED, "dry_run must not touch the record"


@pytest.mark.unit
async def test_running_twice_promotes_once_and_reports_already_ready() -> None:
    store = InMemoryEventStore()
    await seed_defined_agent(
        store,
        agent_id=_FIRST.agent_id,
        genesis_event_id=uuid4(),
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        occurred_at=_NOW,
    )

    await _run(store)
    second = await _run(store)

    assert _outcome_for(second, _FIRST.agent_id) == OUTCOME_ALREADY_READY
    events, _ = await store.load("Agent", _FIRST.agent_id)
    promotions = [event for event in events if "Versioned" in event.event_type]
    assert len(promotions) == 1, "a second run must not append a second promotion"


@pytest.mark.unit
async def test_a_suspended_member_is_reported_and_left_suspended() -> None:
    """Suspension is a live operator decision, not something to sweep away."""
    store = InMemoryEventStore()
    await seed_versioned_agent(
        store,
        agent_id=_FIRST.agent_id,
        genesis_event_id=uuid4(),
        version_event_id=uuid4(),
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        defined_at=_NOW,
        versioned_at=_NOW,
    )
    deps = build_deps(ids=[uuid4() for _ in range(8)], now=_NOW, event_store=store)
    await bind_suspend(deps)(
        SuspendAgent(agent_id=_FIRST.agent_id, reason="cost overrun"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    summary = await _run(store)

    assert _outcome_for(summary, _FIRST.agent_id) == OUTCOME_SKIPPED
    agent = await load_agent(store, _FIRST.agent_id)
    assert agent is not None
    assert agent.status is AgentStatus.SUSPENDED


@pytest.mark.unit
async def test_an_unseeded_member_is_reported_absent_not_skipped_silently() -> None:
    store = InMemoryEventStore()

    summary = await _run(store)

    assert len(summary.outcomes) == len(SEEDED_FLEET), "every member is accounted for"
    assert summary.count(OUTCOME_ABSENT) == len(SEEDED_FLEET)
    assert _outcome_for(summary, _SECOND.agent_id) == OUTCOME_ABSENT


@pytest.mark.unit
async def test_the_summary_covers_the_whole_fleet_not_just_what_changed() -> None:
    """A count of promotions alone cannot tell an operator what it missed."""
    store = InMemoryEventStore()
    await seed_defined_agent(
        store,
        agent_id=_FIRST.agent_id,
        genesis_event_id=uuid4(),
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        occurred_at=_NOW,
    )
    await seed_versioned_agent(
        store,
        agent_id=_SECOND.agent_id,
        genesis_event_id=uuid4(),
        version_event_id=uuid4(),
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        defined_at=_NOW,
        versioned_at=_NOW,
    )

    summary = await _run(store)

    assert summary.count(OUTCOME_PROMOTED) == 1
    assert summary.count(OUTCOME_ALREADY_READY) == 1
    assert summary.count(OUTCOME_ABSENT) == len(SEEDED_FLEET) - 2
    reported = {item.agent_id for item in summary.outcomes}
    assert reported == {member.agent_id for member in SEEDED_FLEET}
