"""Unit tests for the CaptureScanIngestor Agent bootstrap seed.

CaptureScanIngestor is another DETERMINISTIC agent: no prompt template
and a Rule brain (`CaptureScanIngestor:v1`) (it is rule-based, never builds an LLM). These
tests pin that shape alongside the shared seed scaffolding, mirroring
`test_capture_progress_feeder_seed.py`.
"""

from datetime import UTC, datetime

import pytest

from cora.agent.aggregates.agent import BrainRef, load_agent
from cora.agent.seed_capture_scan_ingestor import (
    CAPTURE_SCAN_INGESTOR_AGENT_ID,
    CAPTURE_SCAN_INGESTOR_AGENT_KIND,
    CAPTURE_SCAN_INGESTOR_AGENT_NAME,
    CAPTURE_SCAN_INGESTOR_AGENT_VERSION,
    seed_capture_scan_ingestor_agent,
)
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import AllowAllAuthorize, FakeClock, FixedIdGenerator


def _kernel() -> Kernel:
    settings = Settings()  # type: ignore[call-arg]
    return make_inmemory_kernel(
        settings=settings,
        clock=FakeClock(datetime(2026, 8, 18, 14, 0, 0, tzinfo=UTC)),
        id_generator=FixedIdGenerator([]),
        authz=AllowAllAuthorize(),
    )


@pytest.mark.unit
async def test_seed_creates_capture_scan_ingestor_at_pinned_id() -> None:
    kernel = _kernel()
    await seed_capture_scan_ingestor_agent(kernel)

    agent = await load_agent(kernel.event_store, CAPTURE_SCAN_INGESTOR_AGENT_ID)
    assert agent is not None
    assert agent.id == CAPTURE_SCAN_INGESTOR_AGENT_ID
    assert agent.name.value == CAPTURE_SCAN_INGESTOR_AGENT_NAME
    assert agent.kind.value == CAPTURE_SCAN_INGESTOR_AGENT_KIND
    assert agent.version.value == CAPTURE_SCAN_INGESTOR_AGENT_VERSION


@pytest.mark.unit
async def test_seed_is_deterministic_no_prompt_rule_brain() -> None:
    """Deterministic agent: no prompt template, and a Rule brain rather
    than a model it does not have."""
    kernel = _kernel()
    await seed_capture_scan_ingestor_agent(kernel)

    agent = await load_agent(kernel.event_store, CAPTURE_SCAN_INGESTOR_AGENT_ID)
    assert agent is not None
    assert agent.prompt_template_id is None
    assert agent.model_ref is None
    assert agent.brain == BrainRef.for_rule("CaptureScanIngestor:v1")


@pytest.mark.unit
async def test_seed_creates_co_registered_actor() -> None:
    """The cross-BC genesis: Actor (kind=agent) at the pinned id."""
    from cora.access.aggregates.actor import load_actor

    kernel = _kernel()
    await seed_capture_scan_ingestor_agent(kernel)

    actor = await load_actor(kernel.event_store, CAPTURE_SCAN_INGESTOR_AGENT_ID)
    assert actor is not None
    assert actor.id == CAPTURE_SCAN_INGESTOR_AGENT_ID
    assert actor.kind.value == "agent"


@pytest.mark.unit
async def test_seed_is_idempotent() -> None:
    """Re-running the seed is a no-op (ConcurrencyError-as-success pattern)."""
    kernel = _kernel()
    await seed_capture_scan_ingestor_agent(kernel)
    await seed_capture_scan_ingestor_agent(kernel)


@pytest.mark.unit
async def test_capture_scan_ingestor_id_distinct_from_siblings() -> None:
    """A SEPARATE principal from RunWitness, CaptureProgressFeeder, and
    CaptureBaselineReader, deliberately: an operator can revoke
    scan-ingest without blinding any of the other three."""
    from cora.agent.seed_capture_baseline_reader import CAPTURE_BASELINE_READER_AGENT_ID
    from cora.agent.seed_capture_progress_feeder import CAPTURE_PROGRESS_FEEDER_AGENT_ID
    from cora.agent.seed_run_witness import RUN_WITNESS_AGENT_ID

    others = {
        RUN_WITNESS_AGENT_ID,
        CAPTURE_PROGRESS_FEEDER_AGENT_ID,
        CAPTURE_BASELINE_READER_AGENT_ID,
    }
    assert CAPTURE_SCAN_INGESTOR_AGENT_ID not in others
