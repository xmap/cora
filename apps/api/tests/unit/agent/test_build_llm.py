"""Unit tests for the build_llm composition-root factory (switch + provider).

The switch (`llm_enabled`) is checked before the provider and has no
per-provider exemption, so the local-provider-with-the-switch-off case
below is the load-bearing one: it is what stops an in-house model from
reading "harmless" its way past the deployment's one LLM posture.
"""

import pytest
from pydantic import SecretStr

from cora.agent.adapters.anthropic_llm import AnthropicLLM
from cora.agent.adapters.local_llm import LocalLLM
from cora.agent.build_llm import build_llm, llm_unwired_reason
from cora.infrastructure.config import Settings


@pytest.mark.unit
def test_local_provider_enabled_and_configured_builds_a_local_llm() -> None:
    settings = Settings(  # type: ignore[call-arg]
        llm_enabled=True,
        llm_provider="local",
        local_llm_base_url="http://gpu-host:8000",
        local_llm_model="llama-3.3-70b",
    )
    assert isinstance(build_llm(settings), LocalLLM)


@pytest.mark.unit
def test_local_provider_fully_configured_but_switch_off_returns_none() -> None:
    """The switch gates every serving route, in-house included."""
    settings = Settings(  # type: ignore[call-arg]
        llm_enabled=False,
        llm_provider="local",
        local_llm_base_url="http://gpu-host:8000",
        local_llm_model="llama-3.3-70b",
    )
    assert build_llm(settings) is None


@pytest.mark.unit
def test_local_provider_without_an_endpoint_returns_none() -> None:
    """A misconfigured local provider fails fast (None), not a blind adapter."""
    settings = Settings(  # type: ignore[call-arg]
        llm_enabled=True,
        llm_provider="local",
        local_llm_base_url=None,
        local_llm_model=None,
    )
    assert build_llm(settings) is None


@pytest.mark.unit
def test_local_provider_with_only_a_base_url_returns_none() -> None:
    settings = Settings(  # type: ignore[call-arg]
        llm_enabled=True,
        llm_provider="local",
        local_llm_base_url="http://gpu-host:8000",
        local_llm_model=None,
    )
    assert build_llm(settings) is None


@pytest.mark.unit
def test_anthropic_provider_enabled_with_a_key_builds_anthropic_llm() -> None:
    settings = Settings(  # type: ignore[call-arg]
        llm_enabled=True,
        llm_provider="anthropic",
        anthropic_api_key=SecretStr("sk-not-a-real-key"),
    )
    assert isinstance(build_llm(settings), AnthropicLLM)


@pytest.mark.unit
def test_anthropic_provider_with_a_key_but_switch_off_returns_none() -> None:
    settings = Settings(  # type: ignore[call-arg]
        llm_enabled=False,
        llm_provider="anthropic",
        anthropic_api_key=SecretStr("sk-not-a-real-key"),
    )
    assert build_llm(settings) is None


@pytest.mark.unit
def test_anthropic_provider_without_a_key_returns_none() -> None:
    settings = Settings(  # type: ignore[call-arg]
        llm_enabled=True, llm_provider="anthropic", anthropic_api_key=None
    )
    assert build_llm(settings) is None


@pytest.mark.unit
def test_unwired_reason_with_switch_off_surfaces_the_switch_remedy() -> None:
    settings = Settings(llm_enabled=False, llm_provider="local")  # type: ignore[call-arg]
    reason = llm_unwired_reason(settings)
    assert "LLM_ENABLED is false" in reason
    assert "ANTHROPIC_API_KEY" not in reason


@pytest.mark.unit
def test_unwired_reason_for_local_surfaces_the_endpoint_remedy() -> None:
    """Naming the Anthropic key sends a local deployment to a credential it never reads."""
    settings = Settings(  # type: ignore[call-arg]
        llm_enabled=True, llm_provider="local", local_llm_base_url=None
    )
    reason = llm_unwired_reason(settings)
    assert "LOCAL_LLM_BASE_URL" in reason
    assert "ANTHROPIC_API_KEY" not in reason


@pytest.mark.unit
def test_unwired_reason_for_anthropic_surfaces_the_api_key_remedy() -> None:
    settings = Settings(  # type: ignore[call-arg]
        llm_enabled=True, llm_provider="anthropic", anthropic_api_key=None
    )
    assert "ANTHROPIC_API_KEY" in llm_unwired_reason(settings)
