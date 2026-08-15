"""Unit tests for the CaptureProgressFeeder Agent bootstrap seed.

CaptureProgressFeeder is another DETERMINISTIC agent: no prompt
template and a sentinel ModelRef (it is rule-based, never builds an
LLM). These tests pin that shape alongside the shared seed scaffolding,
mirroring `test_run_witness_seed.py`.
"""

from datetime import UTC, datetime

import pytest

from cora.agent.aggregates.agent import load_agent
from cora.agent.seed_capture_progress_feeder import (
    CAPTURE_PROGRESS_FEEDER_AGENT_ID,
    CAPTURE_PROGRESS_FEEDER_AGENT_KIND,
    CAPTURE_PROGRESS_FEEDER_AGENT_NAME,
    CAPTURE_PROGRESS_FEEDER_AGENT_VERSION,
    seed_capture_progress_feeder_agent,
)
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import AllowAllAuthorize, FakeClock, FixedIdGenerator


def _kernel() -> Kernel:
    settings = Settings()  # type: ignore[call-arg]
    return make_inmemory_kernel(
        settings=settings,
        clock=FakeClock(datetime(2026, 8, 15, 14, 0, 0, tzinfo=UTC)),
        id_generator=FixedIdGenerator([]),
        authz=AllowAllAuthorize(),
    )


@pytest.mark.unit
async def test_seed_creates_capture_progress_feeder_at_pinned_id() -> None:
    kernel = _kernel()
    await seed_capture_progress_feeder_agent(kernel)

    agent = await load_agent(kernel.event_store, CAPTURE_PROGRESS_FEEDER_AGENT_ID)
    assert agent is not None
    assert agent.id == CAPTURE_PROGRESS_FEEDER_AGENT_ID
    assert agent.name.value == CAPTURE_PROGRESS_FEEDER_AGENT_NAME
    assert agent.kind.value == CAPTURE_PROGRESS_FEEDER_AGENT_KIND
    assert agent.version.value == CAPTURE_PROGRESS_FEEDER_AGENT_VERSION


@pytest.mark.unit
async def test_seed_is_deterministic_no_prompt_sentinel_model() -> None:
    """Deterministic agent: no prompt template, sentinel (non-LLM) model_ref."""
    kernel = _kernel()
    await seed_capture_progress_feeder_agent(kernel)

    agent = await load_agent(kernel.event_store, CAPTURE_PROGRESS_FEEDER_AGENT_ID)
    assert agent is not None
    assert agent.prompt_template_id is None
    assert agent.model_ref.provider == "deterministic"
    assert agent.model_ref.model == "agent:CaptureProgressFeeder:v1"


@pytest.mark.unit
async def test_seed_creates_co_registered_actor() -> None:
    """The cross-BC genesis: Actor (kind=agent) at the pinned id."""
    from cora.access.aggregates.actor import load_actor

    kernel = _kernel()
    await seed_capture_progress_feeder_agent(kernel)

    actor = await load_actor(kernel.event_store, CAPTURE_PROGRESS_FEEDER_AGENT_ID)
    assert actor is not None
    assert actor.id == CAPTURE_PROGRESS_FEEDER_AGENT_ID
    assert actor.kind.value == "agent"


@pytest.mark.unit
async def test_seed_is_idempotent() -> None:
    """Re-running the seed is a no-op (ConcurrencyError-as-success pattern)."""
    kernel = _kernel()
    await seed_capture_progress_feeder_agent(kernel)
    await seed_capture_progress_feeder_agent(kernel)


@pytest.mark.unit
async def test_capture_progress_feeder_id_distinct_from_run_witness() -> None:
    """A SEPARATE principal from RunWitness, deliberately: an operator
    can revoke progress-writing without blinding the witness."""
    from cora.agent.seed_run_witness import RUN_WITNESS_AGENT_ID

    assert CAPTURE_PROGRESS_FEEDER_AGENT_ID != RUN_WITNESS_AGENT_ID
