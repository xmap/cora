"""Unit tests for the RunWitness Agent bootstrap seed.

RunWitness is another DETERMINISTIC agent: no prompt template and a
a Rule brain (`RunWitness:v1`) (it is rule-based, never builds an LLM). These tests
pin that shape alongside the shared seed scaffolding, mirroring
`test_run_supervisor_seed.py`.
"""

from datetime import UTC, datetime

import pytest

from cora.agent.aggregates.agent import BrainRef, load_agent
from cora.agent.seed_run_witness import (
    RUN_WITNESS_AGENT_ID,
    RUN_WITNESS_AGENT_KIND,
    RUN_WITNESS_AGENT_NAME,
    RUN_WITNESS_AGENT_VERSION,
    seed_run_witness_agent,
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
async def test_seed_creates_run_witness_at_pinned_id() -> None:
    kernel = _kernel()
    await seed_run_witness_agent(kernel)

    agent = await load_agent(kernel.event_store, RUN_WITNESS_AGENT_ID)
    assert agent is not None
    assert agent.id == RUN_WITNESS_AGENT_ID
    assert agent.name.value == RUN_WITNESS_AGENT_NAME
    assert agent.kind.value == RUN_WITNESS_AGENT_KIND
    assert agent.version.value == RUN_WITNESS_AGENT_VERSION


@pytest.mark.unit
async def test_seed_is_deterministic_no_prompt_rule_brain() -> None:
    """Deterministic agent: no prompt template, and a Rule brain rather
    than a model it does not have."""
    kernel = _kernel()
    await seed_run_witness_agent(kernel)

    agent = await load_agent(kernel.event_store, RUN_WITNESS_AGENT_ID)
    assert agent is not None
    assert agent.prompt_template_id is None
    assert agent.model_ref is None
    assert agent.brain == BrainRef.for_rule("RunWitness:v1")


@pytest.mark.unit
async def test_seed_creates_co_registered_actor() -> None:
    """The cross-BC genesis: Actor (kind=agent) at the pinned id."""
    from cora.access.aggregates.actor import load_actor

    kernel = _kernel()
    await seed_run_witness_agent(kernel)

    actor = await load_actor(kernel.event_store, RUN_WITNESS_AGENT_ID)
    assert actor is not None
    assert actor.id == RUN_WITNESS_AGENT_ID
    assert actor.kind.value == "agent"


@pytest.mark.unit
async def test_seed_is_idempotent() -> None:
    """Re-running the seed is a no-op (ConcurrencyError-as-success pattern)."""
    kernel = _kernel()
    await seed_run_witness_agent(kernel)
    await seed_run_witness_agent(kernel)


@pytest.mark.unit
async def test_run_witness_id_distinct_from_other_agents() -> None:
    """RunWitness shares the UUID-range scheme with its sibling runtimes
    but must NOT collide with either."""
    from cora.agent.seed_run_initiator import RUN_INITIATOR_AGENT_ID
    from cora.agent.seed_run_supervisor import RUN_SUPERVISOR_AGENT_ID

    assert RUN_WITNESS_AGENT_ID != RUN_SUPERVISOR_AGENT_ID
    assert RUN_WITNESS_AGENT_ID != RUN_INITIATOR_AGENT_ID
