"""Application-handler tests for the `update_agent_budget` slice."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.agent.aggregates.agent import (
    AgentBudgetUpdated,
    AgentNotFoundError,
    event_type_name,
    to_payload,
)
from cora.agent.errors import UnauthorizedError
from cora.agent.features import update_agent_budget
from cora.agent.features.update_agent_budget import UpdateAgentBudget
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.agent._helpers import seed_versioned_agent

_T0 = datetime(2026, 5, 17, 10, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 5, 17, 11, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_AGENT_ID = UUID("01900000-0000-7000-8000-00000000b101")
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-00000000b102")
_VERSION_EVENT_ID = UUID("01900000-0000-7000-8000-00000000b103")
_FIRST_UPDATE_EVENT_ID = UUID("01900000-0000-7000-8000-00000000b104")
_NEXT_EVENT_ID = UUID("01900000-0000-7000-8000-00000000b105")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_NEXT_EVENT_ID],
        now=_T2,
        event_store=event_store,
        deny=deny,
    )


async def _append_initial_budget(store: InMemoryEventStore) -> None:
    """Append a baseline AgentBudgetUpdated event at version 2."""
    updated = AgentBudgetUpdated(
        agent_id=_AGENT_ID,
        monthly_usd_cap=100.0,
        daily_token_cap=500_000,
        occurred_at=_T1,
    )
    await store.append(
        stream_type="Agent",
        stream_id=_AGENT_ID,
        expected_version=2,
        events=[
            to_new_event(
                event_type=event_type_name(updated),
                payload=to_payload(updated),
                occurred_at=updated.occurred_at,
                event_id=_FIRST_UPDATE_EVENT_ID,
                command_name="UpdateAgentBudget",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )


@pytest.mark.unit
async def test_handler_sets_budget_on_a_versioned_agent() -> None:
    store = InMemoryEventStore()
    await seed_versioned_agent(
        store,
        agent_id=_AGENT_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        version_event_id=_VERSION_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        defined_at=_T0,
        versioned_at=_T1,
    )
    deps = _build_deps(event_store=store)
    handler = update_agent_budget.bind(deps)
    await handler(
        UpdateAgentBudget(
            agent_id=_AGENT_ID,
            monthly_usd_cap=50.0,
            daily_token_cap=100_000,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Agent", _AGENT_ID)
    assert version == 3
    assert events[-1].event_type == "AgentBudgetUpdated"
    assert events[-1].payload["monthly_usd_cap"] == 50.0
    assert events[-1].payload["daily_token_cap"] == 100_000


@pytest.mark.unit
async def test_handler_idempotent_update_to_same_budget_does_not_append() -> None:
    store = InMemoryEventStore()
    await seed_versioned_agent(
        store,
        agent_id=_AGENT_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        version_event_id=_VERSION_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        defined_at=_T0,
        versioned_at=_T1,
    )
    await _append_initial_budget(store)
    deps = _build_deps(event_store=store)
    handler = update_agent_budget.bind(deps)
    await handler(
        UpdateAgentBudget(
            agent_id=_AGENT_ID,
            monthly_usd_cap=100.0,
            daily_token_cap=500_000,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    _, version = await store.load("Agent", _AGENT_ID)
    assert version == 3  # untouched after idempotent no-op update


@pytest.mark.unit
async def test_handler_clears_budget() -> None:
    store = InMemoryEventStore()
    await seed_versioned_agent(
        store,
        agent_id=_AGENT_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        version_event_id=_VERSION_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        defined_at=_T0,
        versioned_at=_T1,
    )
    await _append_initial_budget(store)
    deps = _build_deps(event_store=store)
    handler = update_agent_budget.bind(deps)
    await handler(
        UpdateAgentBudget(agent_id=_AGENT_ID, monthly_usd_cap=None, daily_token_cap=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Agent", _AGENT_ID)
    assert version == 4
    assert events[-1].payload["monthly_usd_cap"] is None
    assert events[-1].payload["daily_token_cap"] is None


@pytest.mark.unit
async def test_handler_raises_not_found_for_unknown_agent() -> None:
    deps = _build_deps()
    handler = update_agent_budget.bind(deps)
    with pytest.raises(AgentNotFoundError):
        await handler(
            UpdateAgentBudget(agent_id=_AGENT_ID, monthly_usd_cap=10.0, daily_token_cap=None),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_denied_does_not_write_to_stream() -> None:
    store = InMemoryEventStore()
    await seed_versioned_agent(
        store,
        agent_id=_AGENT_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        version_event_id=_VERSION_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        defined_at=_T0,
        versioned_at=_T1,
    )
    deps = _build_deps(event_store=store, deny=True)
    handler = update_agent_budget.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            UpdateAgentBudget(agent_id=_AGENT_ID, monthly_usd_cap=10.0, daily_token_cap=None),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version = await store.load("Agent", _AGENT_ID)
    assert version == 2  # untouched
