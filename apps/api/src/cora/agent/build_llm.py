"""Agent BC's `LLMFactory` for the composition root.

Bound from `cora.api.main` into `build_kernel` the same way
`cora.trust.build_authorize.build_authorize` is bound. Lives in
Agent BC because the production implementor (`AnthropicLLM`)
lives here too (cross-BC adapter-ownership convention; Safety BC
owns `PostgresClearanceLookup`, Caution BC owns
`PostgresCautionLookup`).

Returns `None` unless BOTH `Settings.llm_enabled` (the switch) and
`Settings.anthropic_api_key` (the credential) are set, so the Kernel
carries `llm=None` and no external model is ever called.

`llm=None` is a fully supported state, not a degraded one: every
consumer already handles it because the key-absent case always
produced it. The LLM-backed subscribers log-and-skip
(`cora.agent._subscribers`), `regenerate_run_debrief` answers
unavailable, and a conduct command that explicitly asks for the `llm`
decide substrate gets a `ValueError` mapped to HTTP 422 at
construction, before any FSM transition.

(An earlier version of this docstring claimed subscriber registration
"fail-fasts" on `kernel.llm is None`. It does not, and never did:
`register_agent_subscribers` logs a warning and skips, deliberately,
so a deployment may defer Agent rollout without refusing to boot.)
"""

from cora.agent.adapters.anthropic_llm import AnthropicLLM
from cora.infrastructure.config import Settings
from cora.infrastructure.ports import LLM


def build_llm(settings: Settings) -> LLM | None:
    """Construct the production LLM, or `None` when off or unconfigured.

    Two independent reasons to return `None`, and the switch is checked
    first so an operator who turns the LLM off gets that answer even
    with a credential present in the environment:

      - `llm_enabled` is False (the default): this deployment does not
        call an external model, so no experiment metadata leaves the
        facility through this seam and no tokens are spent.
      - no `anthropic_api_key`: nothing to call it with.

    Today the credential branch reads `settings.anthropic_api_key`; a
    future multi-provider deployment would branch on a
    `settings.llm_provider` field with `anthropic` as one variant.

    `SecretStr.get_secret_value()` is the ONLY place in the codebase
    that unwraps the API key; passing the raw string to the adapter
    constructor is the boundary at which "secret material" becomes
    "live credential". Adapter scope is responsible for not re-
    exposing it (eg. via `repr(adapter)` or `str(adapter._client)`).
    """
    if not settings.llm_enabled:
        return None
    if settings.anthropic_api_key is None:
        return None
    return AnthropicLLM(api_key=settings.anthropic_api_key.get_secret_value())


__all__ = ["build_llm"]
