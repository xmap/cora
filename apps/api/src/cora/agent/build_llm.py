"""Agent BC's `LLMFactory` for the composition root.

Bound from `cora.api.main` into `build_kernel` the same way
`cora.trust.build_authorize.build_authorize` is bound. Lives in Agent BC
because the production implementors (`AnthropicLLM`, and the in-house
`LocalLLM`) live here too (cross-BC adapter-ownership convention; Safety
BC owns `PostgresClearanceLookup`, Caution BC owns `PostgresCautionLookup`).

`build_llm` returns `None` when the selected provider is unconfigured (no
Anthropic key, or a `local` provider without a base URL and model), so
the Kernel ends up with `llm=None` and Agent subscribers fail-fast at
registration. This is intentional: a misconfigured prod deployment should
not silently downgrade to a no-LLM mode where RunDebriefer goes silent.
The subscriber-registration step fail-fasts on `kernel.llm is None`.
"""

from cora.agent._gpu_metrics import make_gpu_usage_sink
from cora.agent.adapters.anthropic_llm import AnthropicLLM
from cora.agent.adapters.local_llm import LocalLLM
from cora.agent.adapters.openai_compatible_backend import OpenAICompatibleBackend
from cora.infrastructure.config import Settings
from cora.infrastructure.ports import LLM
from cora.infrastructure.ports.clock import SystemMonotonicClock


def build_llm(settings: Settings) -> LLM | None:
    """Construct the production LLM for the selected provider, or None.

    `settings.llm_provider` chooses the adapter: `anthropic` (the
    external, token-billed default) builds `AnthropicLLM` from the API
    key; `local` builds the in-house `LocalLLM` over an OpenAI-compatible
    endpoint, metered by the GPU serving sink. Either returns None when
    its provider is unconfigured, so a misconfigured deployment fail-fasts
    at subscriber registration rather than running blind.

    `SecretStr.get_secret_value()` is the ONLY place in the codebase that
    unwraps the Anthropic API key; passing the raw string to the adapter
    constructor is the boundary at which "secret material" becomes "live
    credential". Adapter scope is responsible for not re-exposing it.
    """
    if settings.llm_provider == "local":
        return _build_local_llm(settings)
    if settings.anthropic_api_key is None:
        return None
    return AnthropicLLM(api_key=settings.anthropic_api_key.get_secret_value())


def _build_local_llm(settings: Settings) -> LLM | None:
    """Build the in-house `LocalLLM`, or None when its endpoint is unset.

    The GPU time each call consumes is metered to the shadow-cost
    observability signal at `settings.local_llm_gpu_usd_per_hour`; it
    never debits the budget (in-house serving is metered-free by default).
    A real serving engine is stood up out of band; this only needs its
    base URL and served model name.
    """
    if settings.local_llm_base_url is None or settings.local_llm_model is None:
        return None
    return LocalLLM(
        backend=OpenAICompatibleBackend(
            base_url=settings.local_llm_base_url,
            model=settings.local_llm_model,
        ),
        monotonic_clock=SystemMonotonicClock(),
        on_measure=make_gpu_usage_sink(settings.local_llm_gpu_usd_per_hour),
        device_id=settings.local_llm_device_id,
    )


__all__ = ["build_llm"]
