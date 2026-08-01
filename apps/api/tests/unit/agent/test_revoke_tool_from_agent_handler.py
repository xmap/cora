"""Application-handler tests for the `revoke_tool_from_agent` slice."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.agent.aggregates.agent import AgentNotFoundError
from cora.agent.errors import UnauthorizedError
from cora.agent.features import revoke_tool_from_agent
from cora.agent.features.revoke_tool_from_agent import RevokeToolFromAgent
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.agent._helpers import append_tool_grant, seed_versioned_agent

_T0 = datetime(2026, 5, 17, 10, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 5, 17, 11, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_AGENT_ID = UUID("01900000-0000-7000-8000-00000000a001")
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-00000000a002")
_VERSION_EVENT_ID = UUID("01900000-0000-7000-8000-00000000a003")
_GRANT_EVENT_ID = UUID("01900000-0000-7000-8000-00000000a004")
_NEXT_EVENT_ID = UUID("01900000-0000-7000-8000-00000000a005")
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
async def test_handler_revokes_an_existing_tool() -> None:
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
        event_id=_GRANT_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        tool_name="read_run",
        occurred_at=_T1,
    )
    deps = _build_deps(event_store=store)
    handler = revoke_tool_from_agent.bind(deps)
    await handler(
        RevokeToolFromAgent(
            reason="tool no longer needed", agent_id=_AGENT_ID, tool_name="read_run"
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Agent", _AGENT_ID)
    assert version == 4
    assert events[-1].event_type == "AgentToolRevoked"
    assert events[-1].payload["tool_name"] == "read_run"


@pytest.mark.unit
async def test_handler_idempotent_revoke_of_non_granted_does_not_append() -> None:
    """Revoking a tool the Agent doesn't have MUST NOT touch the stream."""
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
    handler = revoke_tool_from_agent.bind(deps)
    await handler(
        RevokeToolFromAgent(
            reason="tool no longer needed", agent_id=_AGENT_ID, tool_name="read_run"
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    _, version = await store.load("Agent", _AGENT_ID)
    assert version == 2  # untouched after Defined + Versioned seed


@pytest.mark.unit
async def test_handler_raises_not_found_for_unknown_agent() -> None:
    deps = _build_deps()
    handler = revoke_tool_from_agent.bind(deps)
    with pytest.raises(AgentNotFoundError):
        await handler(
            RevokeToolFromAgent(
                reason="tool no longer needed", agent_id=_AGENT_ID, tool_name="read_run"
            ),
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
    await append_tool_grant(
        store,
        agent_id=_AGENT_ID,
        expected_version=2,
        event_id=_GRANT_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        tool_name="read_run",
        occurred_at=_T1,
    )
    deps = _build_deps(event_store=store, deny=True)
    handler = revoke_tool_from_agent.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            RevokeToolFromAgent(
                reason="tool no longer needed", agent_id=_AGENT_ID, tool_name="read_run"
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version = await store.load("Agent", _AGENT_ID)
    assert version == 3  # untouched: Defined + Versioned + first grant
