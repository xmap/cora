"""Application-handler tests for the `deprecate_agent` slice."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.agent.aggregates.agent import (
    AgentCannotDeprecateError,
    AgentNotFoundError,
    ModelRef,
    event_type_name,
    to_payload,
)
from cora.agent.aggregates.agent.events import (
    AgentDefined,
    AgentDeprecated,
    AgentVersioned,
)
from cora.agent.errors import UnauthorizedError
from cora.agent.features import deprecate_agent
from cora.agent.features.deprecate_agent import DeprecateAgent
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.shared.deprecation import DeprecationReason
from tests.unit._helpers import build_deps as _build_deps_shared

_T0 = datetime(2026, 5, 16, 11, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
_AGENT_ID = UUID("01900000-0000-7000-8000-00000000c001")
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-00000000c002")
_DEPRECATE_EVENT_ID = UUID("01900000-0000-7000-8000-00000000c003")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_DEPRECATE_EVENT_ID],
        now=_T1,
        event_store=event_store,
        deny=deny,
    )


async def _seed_defined_agent(store: InMemoryEventStore) -> None:
    genesis = AgentDefined(
        agent_id=_AGENT_ID,
        kind="RunDebriefer",
        name="Run Debrief",
        version="v1",
        model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        description=None,
        canonical_uri=None,
        prompt_template_id=None,
        capabilities=frozenset(),
        occurred_at=_T0,
    )
    await store.append(
        stream_type="Agent",
        stream_id=_AGENT_ID,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(genesis),
                payload=to_payload(genesis),
                occurred_at=genesis.occurred_at,
                event_id=_GENESIS_EVENT_ID,
                command_name="DefineAgent",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )


async def _seed_versioned_agent(store: InMemoryEventStore) -> None:
    """Defined -> Versioned, so `deprecate` is exercised from the OTHER
    permitted source rather than repeating the Defined path."""
    await _seed_defined_agent(store)
    versioned = AgentVersioned(agent_id=_AGENT_ID, version="v2", occurred_at=_T0)
    await store.append(
        stream_type="Agent",
        stream_id=_AGENT_ID,
        expected_version=1,
        events=[
            to_new_event(
                event_type=event_type_name(versioned),
                payload=to_payload(versioned),
                occurred_at=versioned.occurred_at,
                event_id=uuid4(),
                command_name="VersionAgent",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )


@pytest.mark.unit
async def test_handler_deprecates_a_defined_agent_with_reason() -> None:
    store = InMemoryEventStore()
    await _seed_defined_agent(store)
    deps = _build_deps(event_store=store)
    handler = deprecate_agent.bind(deps)
    await handler(
        DeprecateAgent(agent_id=_AGENT_ID, reason=DeprecationReason.SUPERSEDED),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Agent", _AGENT_ID)
    assert version == 2
    assert events[-1].event_type == "AgentDeprecated"
    assert events[-1].payload["reason"] == "Superseded"


@pytest.mark.unit
async def test_handler_deprecates_a_versioned_agent() -> None:
    store = InMemoryEventStore()
    await _seed_versioned_agent(store)
    deps = _build_deps(event_store=store)
    handler = deprecate_agent.bind(deps)
    await handler(
        DeprecateAgent(agent_id=_AGENT_ID, reason=DeprecationReason.SUPERSEDED),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Agent", _AGENT_ID)
    assert events[-1].payload["reason"] == "Superseded"


@pytest.mark.unit
async def test_handler_raises_not_found_for_unknown_agent() -> None:
    deps = _build_deps()
    handler = deprecate_agent.bind(deps)
    with pytest.raises(AgentNotFoundError):
        await handler(
            DeprecateAgent(agent_id=_AGENT_ID, reason=DeprecationReason.SUPERSEDED),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_deprecate_when_already_deprecated() -> None:
    store = InMemoryEventStore()
    await _seed_defined_agent(store)
    deprecated = AgentDeprecated(agent_id=_AGENT_ID, reason="Superseded", occurred_at=_T1)
    await store.append(
        stream_type="Agent",
        stream_id=_AGENT_ID,
        expected_version=1,
        events=[
            to_new_event(
                event_type=event_type_name(deprecated),
                payload=to_payload(deprecated),
                occurred_at=deprecated.occurred_at,
                event_id=UUID("01900000-0000-7000-8000-00000000c099"),
                command_name="DeprecateAgent",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )
    deps = _build_deps(event_store=store)
    handler = deprecate_agent.bind(deps)
    with pytest.raises(AgentCannotDeprecateError):
        await handler(
            DeprecateAgent(agent_id=_AGENT_ID, reason=DeprecationReason.SUPERSEDED),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_denies_via_authorize_port() -> None:
    deps = _build_deps(deny=True)
    handler = deprecate_agent.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            DeprecateAgent(agent_id=_AGENT_ID, reason=DeprecationReason.SUPERSEDED),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_denied_does_not_write_to_stream() -> None:
    """Authorize-denial MUST NOT mutate the Agent stream.

    Mirrors `test_define_agent_handler.test_handler_denied_does_not_write_either_stream`;
    closes gate-review test-coverage P1 for the transition handler.
    """
    store = InMemoryEventStore()
    await _seed_defined_agent(store)
    deps = _build_deps(event_store=store, deny=True)
    handler = deprecate_agent.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            DeprecateAgent(agent_id=_AGENT_ID, reason=DeprecationReason.SUPERSEDED),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    events, version = await store.load("Agent", _AGENT_ID)
    assert version == 1
    assert len(events) == 1
    assert events[0].event_type == "AgentDefined"
