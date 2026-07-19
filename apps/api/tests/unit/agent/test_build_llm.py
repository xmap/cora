"""Unit tests for the build_llm composition-root factory (provider branch)."""

import pytest
from pydantic import SecretStr

from cora.agent.adapters.anthropic_llm import AnthropicLLM
from cora.agent.adapters.local_llm import LocalLLM
from cora.agent.build_llm import build_llm
from cora.infrastructure.config import Settings


@pytest.mark.unit
def test_local_provider_builds_a_local_llm() -> None:
    settings = Settings(  # type: ignore[call-arg]
        llm_provider="local",
        local_llm_base_url="http://gpu-host:8000",
        local_llm_model="llama-3.3-70b",
    )
    assert isinstance(build_llm(settings), LocalLLM)


@pytest.mark.unit
def test_local_provider_without_an_endpoint_returns_none() -> None:
    """A misconfigured local provider fails fast (None), not a blind adapter."""
    settings = Settings(  # type: ignore[call-arg]
        llm_provider="local", local_llm_base_url=None, local_llm_model=None
    )
    assert build_llm(settings) is None


@pytest.mark.unit
def test_anthropic_provider_with_a_key_builds_anthropic_llm() -> None:
    settings = Settings(  # type: ignore[call-arg]
        llm_provider="anthropic", anthropic_api_key=SecretStr("sk-not-a-real-key")
    )
    assert isinstance(build_llm(settings), AnthropicLLM)


@pytest.mark.unit
def test_anthropic_provider_without_a_key_returns_none() -> None:
    settings = Settings(  # type: ignore[call-arg]
        llm_provider="anthropic", anthropic_api_key=None
    )
    assert build_llm(settings) is None
