"""Unit tests for the ExperimentSteerer Agent bootstrap seed.

ExperimentSteerer is a DETERMINISTIC agent (the steering brain is the DecidePort,
not an LLM): no prompt template + a sentinel ModelRef. These tests pin that shape
alongside the shared seed scaffolding, and the idempotency of a re-run seed.
"""

from datetime import UTC, datetime

import pytest

from cora.agent.aggregates.agent import load_agent
from cora.agent.seed_experiment_steerer import (
    EXPERIMENT_STEERER_AGENT_ID,
    EXPERIMENT_STEERER_AGENT_KIND,
    EXPERIMENT_STEERER_AGENT_NAME,
    EXPERIMENT_STEERER_AGENT_VERSION,
    seed_experiment_steerer_agent,
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
async def test_seed_creates_experiment_steerer_at_pinned_id() -> None:
    kernel = _kernel()
    await seed_experiment_steerer_agent(kernel)

    agent = await load_agent(kernel.event_store, EXPERIMENT_STEERER_AGENT_ID)
    assert agent is not None
    assert agent.id == EXPERIMENT_STEERER_AGENT_ID
    assert agent.name.value == EXPERIMENT_STEERER_AGENT_NAME
    assert agent.kind.value == EXPERIMENT_STEERER_AGENT_KIND
    assert agent.version.value == EXPERIMENT_STEERER_AGENT_VERSION


@pytest.mark.unit
async def test_seed_is_deterministic_no_prompt_sentinel_model() -> None:
    """Deterministic agent: no prompt template, sentinel (non-LLM) model_ref."""
    kernel = _kernel()
    await seed_experiment_steerer_agent(kernel)

    agent = await load_agent(kernel.event_store, EXPERIMENT_STEERER_AGENT_ID)
    assert agent is not None
    assert agent.prompt_template_id is None
    assert agent.model_ref.provider == "deterministic"
    assert agent.model_ref.model == "agent:ExperimentSteerer:v1"


@pytest.mark.unit
async def test_seed_co_registers_actor() -> None:
    """The seed atomically co-registers an Actor at the same id (agent-as-actor)."""
    from cora.access.aggregates.actor import load_actor

    kernel = _kernel()
    await seed_experiment_steerer_agent(kernel)

    actor = await load_actor(kernel.event_store, EXPERIMENT_STEERER_AGENT_ID)
    assert actor is not None
    assert actor.id == EXPERIMENT_STEERER_AGENT_ID
    assert actor.active


@pytest.mark.unit
async def test_seed_is_idempotent() -> None:
    """Re-running the seed is a no-op (ConcurrencyError swallowed), not a duplicate."""
    kernel = _kernel()
    await seed_experiment_steerer_agent(kernel)
    await seed_experiment_steerer_agent(kernel)

    events, _ = await kernel.event_store.load("Agent", EXPERIMENT_STEERER_AGENT_ID)
    assert len(events) == 1


@pytest.mark.unit
def test_experiment_steerer_id_distinct_from_other_agents() -> None:
    """The seeded agents share the UUID-range scheme but must NOT collide. Checks
    against the full seeded set so a copy-paste collision is caught."""
    from cora.agent.seed import RUN_DEBRIEFER_AGENT_ID
    from cora.agent.seed_calibration_watcher import CALIBRATION_WATCHER_AGENT_ID
    from cora.agent.seed_campaign_watcher import CAMPAIGN_WATCHER_AGENT_ID
    from cora.agent.seed_caution_drafter import CAUTION_DRAFTER_AGENT_ID
    from cora.agent.seed_caution_promoter import CAUTION_PROMOTER_AGENT_ID
    from cora.agent.seed_clearance_expirer import CLEARANCE_EXPIRER_AGENT_ID
    from cora.agent.seed_clearance_watcher import CLEARANCE_WATCHER_AGENT_ID
    from cora.agent.seed_procedure_watcher import PROCEDURE_WATCHER_AGENT_ID
    from cora.agent.seed_run_initiator import RUN_INITIATOR_AGENT_ID
    from cora.agent.seed_run_supervisor import RUN_SUPERVISOR_AGENT_ID

    others = {
        RUN_DEBRIEFER_AGENT_ID,
        CAUTION_DRAFTER_AGENT_ID,
        RUN_SUPERVISOR_AGENT_ID,
        RUN_INITIATOR_AGENT_ID,
        CAUTION_PROMOTER_AGENT_ID,
        CLEARANCE_EXPIRER_AGENT_ID,
        CLEARANCE_WATCHER_AGENT_ID,
        CALIBRATION_WATCHER_AGENT_ID,
        CAMPAIGN_WATCHER_AGENT_ID,
        PROCEDURE_WATCHER_AGENT_ID,
    }
    assert EXPERIMENT_STEERER_AGENT_ID not in others
