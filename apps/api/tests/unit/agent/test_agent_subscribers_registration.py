"""Unit tests for register_agent_subscribers."""

# pyright: reportUnknownMemberType=false

from datetime import UTC, datetime

import pytest

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


def _kernel(*, llm: object | None, caution_promoter_enabled: bool = False) -> object:
    settings = Settings(caution_promoter_enabled=caution_promoter_enabled)  # type: ignore[call-arg]
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
    """If ANTHROPIC_API_KEY is unset, the subscriber would crash on
    every apply() (no LLM to call). Skip registration cleanly with
    a warning rather than crash at app boot."""
    registry = ProjectionRegistry()
    kernel = _kernel(llm=None)

    register_agent_subscribers(registry, kernel)  # type: ignore[arg-type]

    assert "run_debriefer" not in registry.names()


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
