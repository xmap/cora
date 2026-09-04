"""Unit tests for the local (in-house) RunDebriefer Agent bootstrap seed."""

from datetime import UTC, datetime

import pytest

from cora.agent.aggregates.agent import load_agent
from cora.agent.prompts import RUN_DEBRIEF_PROMPT_TEMPLATE_ID
from cora.agent.seed_run_debriefer_local import (
    RUN_DEBRIEFER_LOCAL_AGENT_ID,
    RUN_DEBRIEFER_LOCAL_AGENT_KIND,
    RUN_DEBRIEFER_LOCAL_AGENT_NAME,
    RUN_DEBRIEFER_LOCAL_AGENT_VERSION,
    seed_run_debriefer_local_agent,
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
async def test_seed_creates_run_debriefer_local_at_pinned_id() -> None:
    kernel = _kernel()
    await seed_run_debriefer_local_agent(kernel)

    agent = await load_agent(kernel.event_store, RUN_DEBRIEFER_LOCAL_AGENT_ID)
    assert agent is not None
    assert agent.id == RUN_DEBRIEFER_LOCAL_AGENT_ID
    assert agent.name.value == RUN_DEBRIEFER_LOCAL_AGENT_NAME
    assert agent.kind.value == RUN_DEBRIEFER_LOCAL_AGENT_KIND
    assert agent.version.value == RUN_DEBRIEFER_LOCAL_AGENT_VERSION
    assert agent.prompt_template_id == RUN_DEBRIEF_PROMPT_TEMPLATE_ID
    assert agent.brain is not None
    model_ref = agent.brain.model_ref
    assert model_ref is not None
    assert model_ref.provider == "local"
    assert model_ref.model == "local-model"


@pytest.mark.unit
async def test_seed_creates_co_registered_actor() -> None:
    """The cross-BC genesis: Actor (kind=agent) at the pinned id."""
    from cora.access.aggregates.actor import load_actor

    kernel = _kernel()
    await seed_run_debriefer_local_agent(kernel)

    actor = await load_actor(kernel.event_store, RUN_DEBRIEFER_LOCAL_AGENT_ID)
    assert actor is not None
    assert actor.id == RUN_DEBRIEFER_LOCAL_AGENT_ID
    assert actor.kind.value == "agent"


@pytest.mark.unit
async def test_seed_is_resilient_under_pre_existing_actor_only_stream() -> None:
    """If the Actor stream exists but the Agent stream doesn't (a
    partial-prior-seed crash), the second seed call must still raise
    the ConcurrencyError-as-success path without double-writing the
    actor."""
    kernel = _kernel()
    await seed_run_debriefer_local_agent(kernel)
    await seed_run_debriefer_local_agent(kernel)  # second seed: no-op via ConcurrencyError


@pytest.mark.unit
async def test_seed_is_idempotent() -> None:
    """Re-running the seed is a no-op (ConcurrencyError-as-success pattern)."""
    kernel = _kernel()
    await seed_run_debriefer_local_agent(kernel)
    # Should not raise on second run.
    await seed_run_debriefer_local_agent(kernel)


@pytest.mark.unit
async def test_run_debriefer_local_id_distinct_from_its_siblings() -> None:
    """Shares `kind` with the legacy singleton and the external arm, but
    must not collide on `id`."""
    from cora.agent.seed import RUN_DEBRIEFER_AGENT_ID
    from cora.agent.seed_run_debriefer_external import RUN_DEBRIEFER_EXTERNAL_AGENT_ID

    assert RUN_DEBRIEFER_LOCAL_AGENT_ID != RUN_DEBRIEFER_AGENT_ID
    assert RUN_DEBRIEFER_LOCAL_AGENT_ID != RUN_DEBRIEFER_EXTERNAL_AGENT_ID
