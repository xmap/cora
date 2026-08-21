"""Unit tests for register_agent_subscribers."""

# pyright: reportPrivateUsage=false, reportUnknownMemberType=false

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
import structlog.testing

from cora.agent import register_agent_subscribers, report_designated_agents
from cora.agent.seed import RUN_DEBRIEFER_AGENT_ID, RUN_DEBRIEFER_AGENT_KIND
from cora.agent.seed_caution_drafter import CAUTION_DRAFTER_AGENT_ID
from cora.agent.subscribers.caution_drafter import CautionDrafterSubscriber
from cora.agent.subscribers.run_debriefer import RunDebrieferSubscriber
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    FakeClock,
    FakeLLM,
    FixedIdGenerator,
)
from cora.infrastructure.projection.registry import ProjectionRegistry
from tests.unit.agent._helpers import seed_versioned_agent

_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000009900a")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000099001")
_NOW = datetime(2026, 5, 17, 14, 0, 0, tzinfo=UTC)
_DESIGNATED_RUN_DEBRIEFER_ID = UUID("01900000-0000-7000-8000-0000cccc0001")
_DESIGNATED_CAUTION_DRAFTER_ID = UUID("01900000-0000-7000-8000-0000cccc0002")


def _kernel(
    *,
    llm: object | None,
    caution_promoter_enabled: bool = False,
    llm_enabled: bool = False,
    llm_provider: str = "anthropic",
    run_debriefer_agent_id: UUID | None = None,
    caution_drafter_agent_id: UUID | None = None,
    event_store: object | None = None,
) -> object:
    settings = Settings(  # type: ignore[call-arg]
        caution_promoter_enabled=caution_promoter_enabled,
        llm_enabled=llm_enabled,
        llm_provider=llm_provider,  # type: ignore[arg-type]
        run_debriefer_agent_id=run_debriefer_agent_id,
        caution_drafter_agent_id=caution_drafter_agent_id,
    )
    return make_inmemory_kernel(
        settings=settings,
        clock=FakeClock(datetime(2026, 5, 17, 14, 0, 0, tzinfo=UTC)),
        id_generator=FixedIdGenerator([]),
        authz=AllowAllAuthorize(),
        llm=llm,  # type: ignore[arg-type]
        event_store=event_store,  # type: ignore[arg-type]
    )


@pytest.mark.unit
def test_registers_run_debrief_when_llm_configured() -> None:
    registry = ProjectionRegistry()
    kernel = _kernel(llm=FakeLLM())

    register_agent_subscribers(registry, kernel)  # type: ignore[arg-type]

    assert "run_debriefer" in registry.names()


@pytest.mark.unit
def test_skips_run_debrief_when_llm_is_none() -> None:
    """With no LLM wired (the switch off, or no credential), the
    subscriber would crash on every apply(). Skip registration cleanly
    with a warning rather than crash at app boot."""
    registry = ProjectionRegistry()
    kernel = _kernel(llm=None)

    register_agent_subscribers(registry, kernel)  # type: ignore[arg-type]

    assert "run_debriefer" not in registry.names()


@pytest.mark.unit
def test_registers_authority_revocation_holder_unconditionally() -> None:
    """The kill-switch (K3) registers ON BY DEFAULT: even with no LLM and default
    settings (promoter off), the holder must be present. A kill-switch that must
    be turned on is not a kill-switch; this pins the on-by-default contract so a
    regression that gates or drops it fails CI."""
    registry = ProjectionRegistry()
    kernel = _kernel(llm=None)

    register_agent_subscribers(registry, kernel)  # type: ignore[arg-type]

    assert "authority_revocation_holder" in registry.names()


@pytest.mark.unit
def test_registers_ratification_enforcer_unconditionally() -> None:
    """The consequence gate (Gate IV) hold + release subscribers register ON BY
    DEFAULT (no LLM, default settings): without them a refused stop is never parked
    / never un-parked, so the gate's shared-hold discharge would not fire. Pins the
    on-by-default contract for both subscribers."""
    registry = ProjectionRegistry()
    kernel = _kernel(llm=None)

    register_agent_subscribers(registry, kernel)  # type: ignore[arg-type]

    assert "ratification_hold" in registry.names()
    assert "ratification_release" in registry.names()


@pytest.mark.unit
def test_registers_caution_promoter_when_enabled() -> None:
    """The deterministic promoter registers independently of the LLM, gated by
    its own off-by-default setting."""
    registry = ProjectionRegistry()
    kernel = _kernel(llm=None, caution_promoter_enabled=True)

    register_agent_subscribers(registry, kernel)  # type: ignore[arg-type]

    assert "caution_promoter" in registry.names()


@pytest.mark.unit
def test_skips_caution_promoter_when_disabled_by_default() -> None:
    """Default settings leave the promoter off (the retirement-memory guard is
    the prerequisite to enable it operationally)."""
    registry = ProjectionRegistry()
    kernel = _kernel(llm=FakeLLM())

    register_agent_subscribers(registry, kernel)  # type: ignore[arg-type]

    assert "caution_promoter" not in registry.names()


@pytest.mark.unit
def test_registration_is_idempotent_safe_for_one_registry() -> None:
    """Double-registration of the same registry would raise
    DuplicateProjectionError on the second call (the framework's
    invariant). Pin that we register only ONCE."""
    registry = ProjectionRegistry()
    kernel = _kernel(llm=FakeLLM())
    register_agent_subscribers(registry, kernel)  # type: ignore[arg-type]

    # Second call should raise (registry already has the subscriber).
    from cora.infrastructure.projection.registry import DuplicateProjectionError

    with pytest.raises(DuplicateProjectionError):
        register_agent_subscribers(registry, kernel)  # type: ignore[arg-type]


def _skip_reason(kernel: object) -> str:
    """The `reason` field of the LLM-subscriber skip warning."""
    with structlog.testing.capture_logs() as captured:
        register_agent_subscribers(ProjectionRegistry(), kernel)  # type: ignore[arg-type]
    skips = [entry for entry in captured if entry.get("event") == "agent_subscriber.skipped"]
    assert len(skips) == 1, f"expected exactly one skip warning, got {skips}"
    return str(skips[0]["reason"])


@pytest.mark.unit
def test_skip_warning_names_the_switch_when_the_llm_is_turned_off() -> None:
    """The two causes call for opposite remedies, so the warning must
    distinguish them. A deployment that deliberately runs LLM-off should
    not read a warning telling it a credential is missing."""
    reason = _skip_reason(_kernel(llm=None, llm_enabled=False))

    # Names the switch as the CAUSE. It may still mention the key as part
    # of the remedy (turning the LLM on needs both), but it must not tell
    # a deliberately-off deployment that its credential is missing.
    assert "LLM_ENABLED is false" in reason
    assert "ANTHROPIC_API_KEY is not configured" not in reason


@pytest.mark.unit
def test_skip_warning_names_the_credential_when_the_switch_is_on() -> None:
    """Switched on but unconfigured is a real misconfiguration; say so."""
    reason = _skip_reason(_kernel(llm=None, llm_enabled=True))

    assert "ANTHROPIC_API_KEY is not configured" in reason
    assert "LLM_ENABLED is true" in reason


# ---------------------------------------------------------------------------
# Subscriber agent designation
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_run_debriefer_designation_setting_threads_into_subscriber() -> None:
    """`settings.run_debriefer_agent_id` reaches the constructed subscriber."""
    registry = ProjectionRegistry()
    kernel = _kernel(llm=FakeLLM(), run_debriefer_agent_id=_DESIGNATED_RUN_DEBRIEFER_ID)

    register_agent_subscribers(registry, kernel)  # type: ignore[arg-type]

    subscriber = registry.get("run_debriefer")
    assert isinstance(subscriber, RunDebrieferSubscriber)
    assert subscriber._agent_id == _DESIGNATED_RUN_DEBRIEFER_ID


@pytest.mark.unit
def test_run_debriefer_unset_designation_uses_seeded_singleton() -> None:
    """Unset means the seeded singleton, so nothing changes on upgrade."""
    registry = ProjectionRegistry()
    kernel = _kernel(llm=FakeLLM())

    register_agent_subscribers(registry, kernel)  # type: ignore[arg-type]

    subscriber = registry.get("run_debriefer")
    assert isinstance(subscriber, RunDebrieferSubscriber)
    assert subscriber._agent_id == RUN_DEBRIEFER_AGENT_ID


@pytest.mark.unit
def test_caution_drafter_designation_setting_threads_into_subscriber() -> None:
    """`settings.caution_drafter_agent_id` reaches the constructed subscriber."""
    registry = ProjectionRegistry()
    kernel = _kernel(llm=FakeLLM(), caution_drafter_agent_id=_DESIGNATED_CAUTION_DRAFTER_ID)

    register_agent_subscribers(registry, kernel)  # type: ignore[arg-type]

    subscriber = registry.get("caution_drafter")
    assert isinstance(subscriber, CautionDrafterSubscriber)
    assert subscriber._agent_id == _DESIGNATED_CAUTION_DRAFTER_ID


@pytest.mark.unit
def test_caution_drafter_unset_designation_uses_seeded_singleton() -> None:
    """Unset means the seeded singleton, so nothing changes on upgrade."""
    registry = ProjectionRegistry()
    kernel = _kernel(llm=FakeLLM())

    register_agent_subscribers(registry, kernel)  # type: ignore[arg-type]

    subscriber = registry.get("caution_drafter")
    assert isinstance(subscriber, CautionDrafterSubscriber)
    assert subscriber._agent_id == CAUTION_DRAFTER_AGENT_ID


# ---------------------------------------------------------------------------
# report_designated_agents: boot-time REPORT, never a gate
# ---------------------------------------------------------------------------


async def _report_log_events(kernel: object) -> list[Any]:
    with structlog.testing.capture_logs() as captured:
        await report_designated_agents(kernel)  # type: ignore[arg-type]
    return list(captured)


@pytest.mark.unit
async def test_report_designated_agents_warns_when_designated_agent_not_found() -> None:
    """A designated-but-missing Agent logs a warning and moves on; it does
    not raise, and it is not the mechanism that skips subscriber work
    (the subscriber's own per-apply gate does that)."""
    kernel = _kernel(
        llm=None,
        run_debriefer_agent_id=_DESIGNATED_RUN_DEBRIEFER_ID,
        event_store=InMemoryEventStore(),
    )

    events = await _report_log_events(kernel)

    not_found = [
        e for e in events if e.get("event") == "agent_subscriber.designated_agent_not_found"
    ]
    assert any(e["agent_id"] == str(_DESIGNATED_RUN_DEBRIEFER_ID) for e in not_found)


@pytest.mark.unit
async def test_report_designated_agents_no_warning_when_provider_matches() -> None:
    """Provider agrees with `settings.llm_provider`: one INFO line, no warning."""
    store = InMemoryEventStore()
    await seed_versioned_agent(
        store,
        agent_id=RUN_DEBRIEFER_AGENT_ID,
        genesis_event_id=uuid4(),
        version_event_id=uuid4(),
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        defined_at=_NOW,
        versioned_at=_NOW,
        kind=RUN_DEBRIEFER_AGENT_KIND,
    )
    kernel = _kernel(llm=None, llm_provider="anthropic", event_store=store)

    events = await _report_log_events(kernel)

    reports = [e for e in events if e.get("event") == "agent_subscriber.designated_agent"]
    assert any(
        e["subscriber"] == "run_debriefer" and e["agent_id"] == str(RUN_DEBRIEFER_AGENT_ID)
        for e in reports
    )
    mismatches = [
        e
        for e in events
        if e.get("event") == "agent_subscriber.designated_agent_provider_mismatch"
        and e.get("subscriber") == "run_debriefer"
    ]
    assert mismatches == []


@pytest.mark.unit
async def test_report_designated_agents_warns_on_provider_mismatch() -> None:
    """Declared provider disagrees with `settings.llm_provider`: a named
    warning, but the report still returns normally (never a gate)."""
    from cora.agent.aggregates.agent import ModelRef as AgentModelRef

    store = InMemoryEventStore()
    await seed_versioned_agent(
        store,
        agent_id=RUN_DEBRIEFER_AGENT_ID,
        genesis_event_id=uuid4(),
        version_event_id=uuid4(),
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        defined_at=_NOW,
        versioned_at=_NOW,
        kind=RUN_DEBRIEFER_AGENT_KIND,
        model_ref=AgentModelRef(provider="argo", model="claude-haiku-4-5"),
    )
    kernel = _kernel(llm=None, llm_provider="anthropic", event_store=store)

    events = await _report_log_events(kernel)

    mismatches = [
        e for e in events if e.get("event") == "agent_subscriber.designated_agent_provider_mismatch"
    ]
    assert len(mismatches) == 1
    assert mismatches[0]["subscriber"] == "run_debriefer"
    assert mismatches[0]["agent_provider"] == "argo"
    assert mismatches[0]["configured_llm_provider"] == "anthropic"
