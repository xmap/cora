"""Unit tests for the StatusPublisher Agent bootstrap seed.

StatusPublisher is another DETERMINISTIC agent: no prompt template and a
a Rule brain (`StatusPublisher:v1`) (it is rule-based, never builds an LLM). These tests
pin that shape alongside the shared seed scaffolding, mirroring
`test_run_witness_seed.py`.
"""

from datetime import UTC, datetime

import pytest

from cora.agent.aggregates.agent import BrainRef, load_agent
from cora.agent.seed_status_publisher import (
    STATUS_PUBLISHER_AGENT_ID,
    STATUS_PUBLISHER_AGENT_KIND,
    STATUS_PUBLISHER_AGENT_NAME,
    STATUS_PUBLISHER_AGENT_VERSION,
    seed_status_publisher_agent,
)
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import AllowAllAuthorize, FakeClock, FixedIdGenerator


def _kernel() -> Kernel:
    settings = Settings()  # type: ignore[call-arg]
    return make_inmemory_kernel(
        settings=settings,
        clock=FakeClock(datetime(2026, 5, 17, 14, 0, 0, tzinfo=UTC)),
        id_generator=FixedIdGenerator([]),
        authz=AllowAllAuthorize(),
    )


@pytest.mark.unit
async def test_seed_creates_status_publisher_at_pinned_id() -> None:
    kernel = _kernel()
    await seed_status_publisher_agent(kernel)

    agent = await load_agent(kernel.event_store, STATUS_PUBLISHER_AGENT_ID)
    assert agent is not None
    assert agent.id == STATUS_PUBLISHER_AGENT_ID
    assert agent.name.value == STATUS_PUBLISHER_AGENT_NAME
    assert agent.kind.value == STATUS_PUBLISHER_AGENT_KIND
    assert agent.version.value == STATUS_PUBLISHER_AGENT_VERSION


@pytest.mark.unit
async def test_seed_is_deterministic_no_prompt_rule_brain() -> None:
    """Deterministic agent: no prompt template, and a Rule brain rather
    than a model it does not have."""
    kernel = _kernel()
    await seed_status_publisher_agent(kernel)

    agent = await load_agent(kernel.event_store, STATUS_PUBLISHER_AGENT_ID)
    assert agent is not None
    assert agent.prompt_template_id is None
    assert agent.model_ref is None
    assert agent.brain == BrainRef.for_rule("StatusPublisher:v1")


@pytest.mark.unit
async def test_seed_creates_co_registered_actor() -> None:
    """The cross-BC genesis: Actor (kind=agent) at the pinned id."""
    from cora.access.aggregates.actor import load_actor

    kernel = _kernel()
    await seed_status_publisher_agent(kernel)

    actor = await load_actor(kernel.event_store, STATUS_PUBLISHER_AGENT_ID)
    assert actor is not None
    assert actor.id == STATUS_PUBLISHER_AGENT_ID
    assert actor.kind.value == "agent"


@pytest.mark.unit
async def test_seed_is_idempotent() -> None:
    """Re-running the seed is a no-op (ConcurrencyError-as-success pattern)."""
    kernel = _kernel()
    await seed_status_publisher_agent(kernel)
    await seed_status_publisher_agent(kernel)


@pytest.mark.unit
async def test_status_publisher_id_distinct_from_other_agents() -> None:
    """StatusPublisher shares the UUID-range scheme with its sibling runtimes
    but must NOT collide with either."""
    from cora.agent.seed_capture_progress_feeder import CAPTURE_PROGRESS_FEEDER_AGENT_ID
    from cora.agent.seed_run_witness import RUN_WITNESS_AGENT_ID

    assert STATUS_PUBLISHER_AGENT_ID != RUN_WITNESS_AGENT_ID
    assert STATUS_PUBLISHER_AGENT_ID != CAPTURE_PROGRESS_FEEDER_AGENT_ID
