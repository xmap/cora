"""Application-handler tests for the `set_agent_target_plan` slice."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.agent.aggregates.agent import (
    AgentNotFoundError,
    AgentTargetPlanSet,
    event_type_name,
    to_payload,
)
from cora.agent.errors import UnauthorizedError
from cora.agent.features import set_agent_target_plan
from cora.agent.features.set_agent_target_plan import SetAgentTargetPlan
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.agent._helpers import seed_versioned_agent

_T0 = datetime(2026, 5, 17, 10, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 5, 17, 11, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_AGENT_ID = UUID("01900000-0000-7000-8000-00000000c101")
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-00000000c102")
_VERSION_EVENT_ID = UUID("01900000-0000-7000-8000-00000000c103")
_FIRST_SET_EVENT_ID = UUID("01900000-0000-7000-8000-00000000c104")
_NEXT_EVENT_ID = UUID("01900000-0000-7000-8000-00000000c105")
_PLAN_A = UUID("01900000-0000-7000-8000-00000000c201")
_PLAN_B = UUID("01900000-0000-7000-8000-00000000c202")
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


async def _append_initial_target(store: InMemoryEventStore) -> None:
    """Append a baseline AgentTargetPlanSet event at version 2."""
    was_set = AgentTargetPlanSet(agent_id=_AGENT_ID, target_plan_id=_PLAN_A, occurred_at=_T1)
    await store.append(
        stream_type="Agent",
        stream_id=_AGENT_ID,
        expected_version=2,
        events=[
            to_new_event(
                event_type=event_type_name(was_set),
                payload=to_payload(was_set),
                occurred_at=was_set.occurred_at,
                event_id=_FIRST_SET_EVENT_ID,
                command_name="SetAgentTargetPlan",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )


async def _seed(store: InMemoryEventStore) -> None:
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


@pytest.mark.unit
async def test_handler_sets_target_plan_on_a_versioned_agent() -> None:
    store = InMemoryEventStore()
    await _seed(store)
    deps = _build_deps(event_store=store)
    handler = set_agent_target_plan.bind(deps)
    await handler(
        SetAgentTargetPlan(agent_id=_AGENT_ID, target_plan_id=_PLAN_A),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Agent", _AGENT_ID)
    assert version == 3
    assert events[-1].event_type == "AgentTargetPlanSet"
    assert events[-1].payload["target_plan_id"] == str(_PLAN_A)


@pytest.mark.unit
async def test_handler_idempotent_set_to_same_plan_does_not_append() -> None:
    store = InMemoryEventStore()
    await _seed(store)
    await _append_initial_target(store)
    deps = _build_deps(event_store=store)
    handler = set_agent_target_plan.bind(deps)
    await handler(
        SetAgentTargetPlan(agent_id=_AGENT_ID, target_plan_id=_PLAN_A),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    _, version = await store.load("Agent", _AGENT_ID)
    assert version == 3  # untouched after idempotent no-op


@pytest.mark.unit
async def test_handler_changes_to_a_different_plan() -> None:
    store = InMemoryEventStore()
    await _seed(store)
    await _append_initial_target(store)
    deps = _build_deps(event_store=store)
    handler = set_agent_target_plan.bind(deps)
    await handler(
        SetAgentTargetPlan(agent_id=_AGENT_ID, target_plan_id=_PLAN_B),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Agent", _AGENT_ID)
    assert version == 4
    assert events[-1].payload["target_plan_id"] == str(_PLAN_B)


@pytest.mark.unit
async def test_handler_clears_target_plan() -> None:
    store = InMemoryEventStore()
    await _seed(store)
    await _append_initial_target(store)
    deps = _build_deps(event_store=store)
    handler = set_agent_target_plan.bind(deps)
    await handler(
        SetAgentTargetPlan(agent_id=_AGENT_ID, target_plan_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Agent", _AGENT_ID)
    assert version == 4
    assert events[-1].payload["target_plan_id"] is None


@pytest.mark.unit
async def test_handler_raises_not_found_for_unknown_agent() -> None:
    deps = _build_deps()
    handler = set_agent_target_plan.bind(deps)
    with pytest.raises(AgentNotFoundError):
        await handler(
            SetAgentTargetPlan(agent_id=_AGENT_ID, target_plan_id=_PLAN_A),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_denied_does_not_write_to_stream() -> None:
    store = InMemoryEventStore()
    await _seed(store)
    deps = _build_deps(event_store=store, deny=True)
    handler = set_agent_target_plan.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            SetAgentTargetPlan(agent_id=_AGENT_ID, target_plan_id=_PLAN_A),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version = await store.load("Agent", _AGENT_ID)
    assert version == 2  # untouched
