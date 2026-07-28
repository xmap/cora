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
(`cora.agent._subscribers`) and `regenerate_run_debrief` answers
unavailable. The `llm` decide substrate cannot be selected by a remote
caller at all (`WireDecideSubstrate` admits only `in_memory` and
`grid_walk`), so `build_decide_port`'s `llm is None` guard is an
internal-caller guard, not a request-reachable path.

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


def llm_unwired_reason(settings: Settings) -> str:
    """Say WHICH of the two settings left `kernel.llm` unwired.

    One source of truth for every surface that has to explain the
    unwired state: the subscriber-registration warning, the REST 503
    body, and the MCP tool's error. They must agree, and each must send
    the operator to the remedy that actually applies. Naming the
    credential when the switch is simply off is the more likely mistake
    now, because off is the default.

    Callers are expected to have already established that the LLM is
    unwired; this only explains why.
    """
    if not settings.llm_enabled:
        return (
            "LLM_ENABLED is false, so this deployment calls no external model. "
            "Set LLM_ENABLED=true (and ANTHROPIC_API_KEY) to turn the LLM features on."
        )
    return (
        "LLM_ENABLED is true but ANTHROPIC_API_KEY is not configured. "
        "Supply the credential and restart."
    )


__all__ = ["build_llm", "llm_unwired_reason"]
