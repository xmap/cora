"""Application-handler tests for the `restate_agent_definition` slice."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.agent.aggregates.agent import (
    AgentNotFoundError,
    BrainKind,
    BrainRef,
    load_agent,
)
from cora.agent.errors import UnauthorizedError
from cora.agent.features import restate_agent_definition
from cora.agent.features.restate_agent_definition import RestateAgentDefinition
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.agent._helpers import seed_versioned_agent

_T0 = datetime(2026, 9, 5, 10, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 9, 5, 11, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 9, 5, 12, 0, 0, tzinfo=UTC)
_AGENT_ID = UUID("01900000-0000-7000-8000-00000000d101")
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-00000000d102")
_VERSION_EVENT_ID = UUID("01900000-0000-7000-8000-00000000d103")
_NEXT_EVENT_ID = UUID("01900000-0000-7000-8000-00000000d104")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_REASON = "restated after the brain migration"


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
async def test_handler_appends_the_restatement_and_folds_the_new_brain() -> None:
    store = InMemoryEventStore()
    await _seed(store)
    handler = restate_agent_definition.bind(_build_deps(event_store=store))

    await handler(
        RestateAgentDefinition(
            agent_id=_AGENT_ID,
            reason=_REASON,
            brain=BrainRef.for_rule("ProcedureWatcher:v1"),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Agent", _AGENT_ID)
    assert version == 3
    assert events[-1].event_type == "AgentDefinitionRestated"
    assert events[-1].payload["reason"] == _REASON

    agent = await load_agent(store, _AGENT_ID)
    assert agent is not None
    assert agent.brain == BrainRef.for_rule("ProcedureWatcher:v1")


@pytest.mark.unit
async def test_handler_leaves_the_genesis_model_ref_untouched() -> None:
    """The point of the whole migration: an agent stops DEPENDING on the
    legacy slot without its original record being rewritten."""
    store = InMemoryEventStore()
    await _seed(store)
    before = await load_agent(store, _AGENT_ID)
    assert before is not None
    handler = restate_agent_definition.bind(_build_deps(event_store=store))

    await handler(
        RestateAgentDefinition(
            agent_id=_AGENT_ID,
            reason=_REASON,
            brain=BrainRef.for_rule("ProcedureWatcher:v1"),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    after = await load_agent(store, _AGENT_ID)
    assert after is not None
    assert after.model_ref == before.model_ref


@pytest.mark.unit
async def test_handler_renames_without_touching_the_brain() -> None:
    """The rename path: `name` supplied, `brain` omitted and so unchanged."""
    store = InMemoryEventStore()
    await _seed(store)
    before = await load_agent(store, _AGENT_ID)
    assert before is not None
    handler = restate_agent_definition.bind(_build_deps(event_store=store))

    await handler(
        RestateAgentDefinition(agent_id=_AGENT_ID, reason=_REASON, name="Campaign Coordinator"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    after = await load_agent(store, _AGENT_ID)
    assert after is not None
    assert after.name.value == "Campaign Coordinator"
    assert after.brain == before.brain
    assert after.id == before.id  # attribution of past Decisions survives


@pytest.mark.unit
async def test_handler_idempotent_restatement_does_not_append() -> None:
    store = InMemoryEventStore()
    await _seed(store)
    existing = await load_agent(store, _AGENT_ID)
    assert existing is not None
    handler = restate_agent_definition.bind(_build_deps(event_store=store))

    await handler(
        RestateAgentDefinition(agent_id=_AGENT_ID, reason=_REASON, name=existing.name.value),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    _, version = await store.load("Agent", _AGENT_ID)
    assert version == 2  # untouched after the idempotent no-op


@pytest.mark.unit
async def test_handler_raises_for_a_missing_agent() -> None:
    handler = restate_agent_definition.bind(_build_deps(event_store=InMemoryEventStore()))

    with pytest.raises(AgentNotFoundError):
        await handler(
            RestateAgentDefinition(agent_id=_AGENT_ID, reason=_REASON, name="Ghost"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_refuses_a_denied_principal() -> None:
    store = InMemoryEventStore()
    await _seed(store)
    handler = restate_agent_definition.bind(_build_deps(event_store=store, deny=True))

    with pytest.raises(UnauthorizedError):
        await handler(
            RestateAgentDefinition(agent_id=_AGENT_ID, reason=_REASON, name="Denied"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    _, version = await store.load("Agent", _AGENT_ID)
    assert version == 2


@pytest.mark.unit
async def test_handler_restates_a_language_model_brain() -> None:
    """A restatement can also name an LLM brain. Note there is no approval
    gate on this path, unlike `define_agent` and `seed_agent`; the handler
    docstring records that gap deliberately."""
    store = InMemoryEventStore()
    await _seed(store)
    handler = restate_agent_definition.bind(_build_deps(event_store=store))
    from cora.agent.aggregates.agent import ModelRef

    await handler(
        RestateAgentDefinition(
            agent_id=_AGENT_ID,
            reason=_REASON,
            brain=BrainRef.for_model(ModelRef(provider="anthropic", model="claude-sonnet-4-6")),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    agent = await load_agent(store, _AGENT_ID)
    assert agent is not None
    assert agent.brain is not None
    assert agent.brain.kind is BrainKind.LANGUAGE_MODEL
