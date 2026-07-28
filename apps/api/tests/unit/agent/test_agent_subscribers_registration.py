"""Unit tests for register_agent_subscribers."""

# pyright: reportUnknownMemberType=false

from datetime import UTC, datetime

import pytest
import structlog.testing

from cora.agent import register_agent_subscribers
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    FakeClock,
    FakeLLM,
    FixedIdGenerator,
)
from cora.infrastructure.projection.registry import ProjectionRegistry


def _kernel(
    *,
    llm: object | None,
    caution_promoter_enabled: bool = False,
    llm_enabled: bool = False,
) -> object:
    settings = Settings(  # type: ignore[call-arg]
        caution_promoter_enabled=caution_promoter_enabled,
        llm_enabled=llm_enabled,
    )
    return make_inmemory_kernel(
        settings=settings,
        clock=FakeClock(datetime(2026, 5, 17, 14, 0, 0, tzinfo=UTC)),
        id_generator=FixedIdGenerator([]),
        authz=AllowAllAuthorize(),
        llm=llm,  # type: ignore[arg-type]
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
