"""Application-handler tests for the `grant_tool_to_agent` slice."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.agent.aggregates.agent import (
    AgentCannotGrantToolError,
    AgentNotFoundError,
)
from cora.agent.errors import UnauthorizedError
from cora.agent.features import grant_tool_to_agent
from cora.agent.features.grant_tool_to_agent import GrantToolToAgent
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.agent._helpers import (
    append_tool_grant,
    seed_versioned_agent,
)

_T0 = datetime(2026, 5, 17, 10, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 5, 17, 11, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_AGENT_ID = UUID("01900000-0000-7000-8000-00000000f001")
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-00000000f002")
_VERSION_EVENT_ID = UUID("01900000-0000-7000-8000-00000000f003")
_FIRST_GRANT_EVENT_ID = UUID("01900000-0000-7000-8000-00000000f004")
_NEXT_EVENT_ID = UUID("01900000-0000-7000-8000-00000000f005")
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


@pytest.mark.unit
async def test_handler_grants_a_tool() -> None:
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
    handler = grant_tool_to_agent.bind(deps)
    await handler(
        GrantToolToAgent(agent_id=_AGENT_ID, tool_name="read_run"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Agent", _AGENT_ID)
    assert version == 3
    assert events[-1].event_type == "AgentToolGranted"
    assert events[-1].payload["tool_name"] == "read_run"


@pytest.mark.unit
async def test_handler_idempotent_re_grant_does_not_append() -> None:
    """Re-granting an already-granted tool MUST NOT touch the stream."""
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
    await append_tool_grant(
        store,
        agent_id=_AGENT_ID,
        expected_version=2,
        event_id=_FIRST_GRANT_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        tool_name="read_run",
        occurred_at=_T1,
    )
    deps = _build_deps(event_store=store)
    handler = grant_tool_to_agent.bind(deps)
    await handler(
        GrantToolToAgent(agent_id=_AGENT_ID, tool_name="read_run"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    _, version = await store.load("Agent", _AGENT_ID)
    assert version == 3  # untouched after idempotent re-grant


@pytest.mark.unit
async def test_handler_raises_not_found_for_unknown_agent() -> None:
    deps = _build_deps()
    handler = grant_tool_to_agent.bind(deps)
    with pytest.raises(AgentNotFoundError):
        await handler(
            GrantToolToAgent(agent_id=_AGENT_ID, tool_name="read_run"),
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
    handler = grant_tool_to_agent.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            GrantToolToAgent(agent_id=_AGENT_ID, tool_name="read_run"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version = await store.load("Agent", _AGENT_ID)
    assert version == 2  # untouched after Defined + Versioned seed


@pytest.mark.unit
async def test_handler_cannot_grant_after_deprecation() -> None:
    """A deprecated Agent rejects grants with AgentCannotGrantToolError."""
    from cora.agent.aggregates.agent import (
        AgentDeprecated,
        event_type_name,
        to_payload,
    )
    from cora.infrastructure.event_envelope import to_new_event

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
    deprecated = AgentDeprecated(agent_id=_AGENT_ID, reason="Superseded", occurred_at=_T2)
    await store.append(
        stream_type="Agent",
        stream_id=_AGENT_ID,
        expected_version=2,
        events=[
            to_new_event(
                event_type=event_type_name(deprecated),
                payload=to_payload(deprecated),
                occurred_at=deprecated.occurred_at,
                event_id=UUID("01900000-0000-7000-8000-00000000f099"),
                command_name="DeprecateAgent",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )
    deps = _build_deps(event_store=store)
    handler = grant_tool_to_agent.bind(deps)
    with pytest.raises(AgentCannotGrantToolError):
        await handler(
            GrantToolToAgent(agent_id=_AGENT_ID, tool_name="read_run"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
