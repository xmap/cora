"""Unit tests for the RunDebriefer Agent bootstrap seed."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.agent.aggregates.agent import AgentStatus, load_agent
from cora.agent.prompts import RUN_DEBRIEF_PROMPT_TEMPLATE_ID
from cora.agent.seed import (
    RUN_DEBRIEFER_AGENT_ID,
    RUN_DEBRIEFER_AGENT_KIND,
    RUN_DEBRIEFER_AGENT_NAME,
    RUN_DEBRIEFER_AGENT_VERSION,
    seed_run_debriefer_agent,
)
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import AllowAllAuthorize, FakeClock, FixedIdGenerator
from tests.unit.agent._helpers import seed_defined_agent


@pytest.mark.unit
def test_seeded_identity_literals_match_doer_form() -> None:
    """Pin the literal string values that the seed bakes into events.

    Asserting against the imported constant would tautologically pass
    if someone rewrote the constant to a different value. This test
    fixes the doer-form name in place; per [[project_naming_conventions]]
    R5 the agent's identity must read as `<DomainNoun><DoerNoun>`,
    not as the work-product noun (`RunDebrief`). `NAME` carries a
    `" (Legacy)"` qualifier (this id is no longer the compile-time
    default; see `cora.agent.seed_run_debriefer_external`), which does
    not disturb the doer-form root the R5 guard cares about; `KIND`
    stays bare, shared with every sibling of this agent.
    """
    assert RUN_DEBRIEFER_AGENT_NAME == "RunDebriefer (Legacy)"
    assert RUN_DEBRIEFER_AGENT_KIND == "RunDebriefer"


def _kernel() -> Kernel:
    settings = Settings()  # type: ignore[call-arg]
    return make_inmemory_kernel(
        settings=settings,
        clock=FakeClock(datetime(2026, 5, 17, 14, 0, 0, tzinfo=UTC)),
        id_generator=FixedIdGenerator([]),
        authz=AllowAllAuthorize(),
    )


@pytest.mark.unit
async def test_seed_creates_agent_at_pinned_id() -> None:
    kernel = _kernel()
    await seed_run_debriefer_agent(kernel)

    agent = await load_agent(kernel.event_store, RUN_DEBRIEFER_AGENT_ID)
    assert agent is not None
    assert agent.id == RUN_DEBRIEFER_AGENT_ID
    assert agent.name.value == RUN_DEBRIEFER_AGENT_NAME
    assert agent.kind.value == RUN_DEBRIEFER_AGENT_KIND
    assert agent.version.value == RUN_DEBRIEFER_AGENT_VERSION
    assert agent.prompt_template_id == RUN_DEBRIEF_PROMPT_TEMPLATE_ID


@pytest.mark.unit
async def test_seed_creates_co_registered_actor() -> None:
    """The Agent's id is SHARED with Access BC's Actor.id per 8f-a's
    identity-sharing invariant. The seed writes both atomically."""
    from cora.access.aggregates.actor import load_actor

    kernel = _kernel()
    await seed_run_debriefer_agent(kernel)

    actor = await load_actor(kernel.event_store, RUN_DEBRIEFER_AGENT_ID)
    assert actor is not None
    assert actor.id == RUN_DEBRIEFER_AGENT_ID
    assert actor.kind.value == "agent"


@pytest.mark.unit
async def test_seed_is_idempotent_across_calls() -> None:
    """A repeated seed call (on every app boot) MUST NOT raise and
    MUST NOT duplicate the agent. Pins the
    ConcurrencyError-as-no-op semantics."""
    kernel = _kernel()
    await seed_run_debriefer_agent(kernel)
    # Second call must not raise.
    await seed_run_debriefer_agent(kernel)
    # Third call for good measure.
    await seed_run_debriefer_agent(kernel)

    # Still exactly one agent at the pinned id.
    agent = await load_agent(kernel.event_store, RUN_DEBRIEFER_AGENT_ID)
    assert agent is not None
    # Stream version is still 2 (define + promote), not 6: the repeat
    # calls were no-ops, not a second bootstrap.
    events, version = await kernel.event_store.load("Agent", RUN_DEBRIEFER_AGENT_ID)
    assert version == 2
    assert len(events) == 2
    assert agent.status is AgentStatus.VERSIONED


@pytest.mark.unit
async def test_seed_warns_when_an_already_seeded_agent_is_not_promoted(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A deployment seeded before the bootstrap promoted must not stay silent.

    This is the shape that stranded the whole 2-BM fleet: seeded, inert,
    and indistinguishable from healthy in the log.
    """
    kernel = _kernel()
    await seed_defined_agent(
        kernel.event_store,  # type: ignore[arg-type]
        agent_id=RUN_DEBRIEFER_AGENT_ID,
        genesis_event_id=uuid4(),
        correlation_id=uuid4(),
        principal_id=uuid4(),
        occurred_at=datetime(2026, 5, 17, 14, 0, 0, tzinfo=UTC),
    )

    await seed_run_debriefer_agent(kernel)

    # structlog writes to stdout here rather than through stdlib logging,
    # so capsys is the capture that sees it (caplog does not).
    emitted = capsys.readouterr().out
    assert "agent_seed.not_promoted" in emitted
    assert "version_agent" in emitted

    agent = await load_agent(kernel.event_store, RUN_DEBRIEFER_AGENT_ID)
    assert agent is not None
    assert agent.status is AgentStatus.DEFINED, "the warning must not silently promote"


@pytest.mark.unit
async def test_seed_pins_prompt_template_id() -> None:
    """The bootstrap stores the prompt_template_id so the subscriber
    can record it in `Decision.inputs["prompt_template_id"]`
    for audit. Pin the linkage so a misnumbered template would
    surface here."""
    kernel = _kernel()
    await seed_run_debriefer_agent(kernel)

    agent = await load_agent(kernel.event_store, RUN_DEBRIEFER_AGENT_ID)
    assert agent is not None
    assert agent.prompt_template_id == RUN_DEBRIEF_PROMPT_TEMPLATE_ID


@pytest.mark.unit
async def test_seed_uses_system_principal_id_not_agent_self_reference() -> None:
    """Security gate-review: the bootstrap envelope's
    `principal_id` must be `SYSTEM_PRINCIPAL_ID`, NOT the agent's
    own id. The agent doesn't exist yet at boot-time, so self-
    attribution would be a circular-causation lie in the audit
    record."""
    from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID

    kernel = _kernel()
    await seed_run_debriefer_agent(kernel)

    actor_events, _ = await kernel.event_store.load("Actor", RUN_DEBRIEFER_AGENT_ID)
    assert len(actor_events) == 1
    assert actor_events[0].principal_id == SYSTEM_PRINCIPAL_ID
    assert actor_events[0].principal_id != RUN_DEBRIEFER_AGENT_ID

    agent_events, _ = await kernel.event_store.load("Agent", RUN_DEBRIEFER_AGENT_ID)
    assert len(agent_events) == 2
    assert all(event.principal_id == SYSTEM_PRINCIPAL_ID for event in agent_events)
