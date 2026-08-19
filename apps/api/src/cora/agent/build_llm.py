"""Agent BC's `LLMFactory` for the composition root.

Bound from `cora.api.main` into `build_kernel` the same way
`cora.trust.build_authorize.build_authorize` is bound. Lives in Agent BC
because the production implementors (`AnthropicLLM`, `ArgoLLM`, and the
in-house `LocalLLM`) live here too (cross-BC adapter-ownership convention; Safety
BC owns `PostgresClearanceLookup`, Caution BC owns `PostgresCautionLookup`).

Returns `None` unless BOTH `Settings.llm_enabled` (the switch) and the
selected provider's own configuration are present, so the Kernel carries
`llm=None` and no model is called at all.

The switch is checked before the provider, and it has no per-provider
exemption. An in-house `local` model sends nothing outside the facility
and buys no vendor tokens, which makes it tempting to let it run with the
switch off; that is the same mistake `is_simulated` exists to prevent on
the control side, where a soft IOC still speaks real Channel Access. A
local model still invokes an LLM, still debits the beamline envelope at
its catalog rate, and still writes inference rows to the experiment
record. The same holds for a gateway the facility already funds: `argo`
buys no tokens on the deployment's own account, and still does all three.
`LLM_ENABLED` is the deployment's one answer to "does this instance run
an LLM at all", so it gates every serving route.

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

from cora.agent._gpu_metrics import make_gpu_usage_sink
from cora.agent.adapters.anthropic_llm import AnthropicLLM
from cora.agent.adapters.argo_llm import ArgoLLM
from cora.agent.adapters.local_llm import LocalLLM
from cora.agent.adapters.openai_compatible_backend import OpenAICompatibleBackend
from cora.infrastructure.config import Settings
from cora.infrastructure.ports import LLM
from cora.infrastructure.ports.clock import SystemMonotonicClock


def build_llm(settings: Settings) -> LLM | None:
    """Construct the production LLM, or `None` when off or unconfigured.

    Two independent reasons to return `None`, and the switch is checked
    first so an operator who turns the LLM off gets that answer even
    with a provider fully configured in the environment:

      - `llm_enabled` is False (the default): this deployment runs no
        model on any serving route, so no experiment metadata leaves the
        facility, no tokens are bought, and no envelope is debited.
      - the selected provider is unconfigured: `anthropic` without
        `anthropic_api_key`, `argo` without `argo_username`, or `local`
        without a base URL and a served model name. Nothing to call it
        with in any of the three cases.

    `settings.llm_provider` chooses the adapter: `anthropic` buys an
    external, token-billed call; `argo` buys the same vendor models
    through Argonne's internal gateway, on facility-funded
    infrastructure rather than the deployment's own account; `local`
    serves a facility-hosted model over an OpenAI-compatible endpoint
    and meters the GPU time it holds. All three debit the same beamline
    envelope through the catalog's price for the entry, which is what
    makes the envelope source-agnostic, and reaching it by one route is
    the design rather than a coincidence.

    The `get_secret_value()` calls below are the only places the
    Anthropic key and the Argo username are unwrapped; passing the raw
    string to an adapter constructor is the boundary at which "secret
    material" becomes "live credential". Adapter scope is responsible
    for not re-exposing it.
    """
    if not settings.llm_enabled:
        return None
    if settings.llm_provider == "argo":
        return _build_argo_llm(settings)
    if settings.llm_provider == "local":
        return _build_local_llm(settings)
    if settings.anthropic_api_key is None:
        return None
    return AnthropicLLM(api_key=settings.anthropic_api_key.get_secret_value())


def _build_argo_llm(settings: Settings) -> LLM | None:
    """Build `ArgoLLM`, or None when no gateway identity is configured.

    The gateway takes an ANL domain username where a vendor takes an
    API key, so the absent-identity case looks the same as the
    absent-key case and returns None the same way.
    """
    if settings.argo_username is None:
        return None
    return ArgoLLM(
        username=settings.argo_username.get_secret_value(),
        base_url=settings.argo_base_url,
    )


def _build_local_llm(settings: Settings) -> LLM | None:
    """Build the in-house `LocalLLM`, or None when its endpoint is unset.

    The GPU time each call consumes is metered to the shadow-cost
    observability signal at `settings.local_llm_gpu_usd_per_hour`; it
    never debits the budget (in-house serving is metered-free by default,
    and what debits is the catalog's per-token rate for the entry). A real
    serving engine is stood up out of band; this only needs its base URL
    and served model name.
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


def llm_unwired_reason(settings: Settings) -> str:
    """Say WHICH setting left `kernel.llm` unwired, per selected provider.

    One source of truth for every surface that has to explain the
    unwired state: the subscriber-registration warning, the REST 503
    body, and the MCP tool's error. They must agree, and each must send
    the operator to the remedy that actually applies. Naming the
    credential when the switch is simply off is the more likely mistake
    now, because off is the default; naming the Anthropic key when the
    deployment selected `argo` or `local` would be worse, because it
    sends the operator to a credential that provider never reads.

    Callers are expected to have already established that the LLM is
    unwired; this only explains why.
    """
    if not settings.llm_enabled:
        return (
            "LLM_ENABLED is false, so this deployment runs no model on any "
            "serving route. Set LLM_ENABLED=true (and configure the provider "
            "named by LLM_PROVIDER) to turn the LLM features on."
        )
    if settings.llm_provider == "argo":
        return (
            "LLM_ENABLED is true and LLM_PROVIDER is argo, but ARGO_USERNAME "
            "is not configured. Supply the ANL domain username the gateway "
            "authenticates: a service account for a long-lived deployment, "
            "so the gateway attributes these calls to the application rather "
            "than to an individual. Supply it and restart."
        )
    if settings.llm_provider == "local":
        return (
            "LLM_ENABLED is true and LLM_PROVIDER is local, but "
            "LOCAL_LLM_BASE_URL and LOCAL_LLM_MODEL are not both configured. "
            "Supply the served endpoint and model name and restart."
        )
    return (
        "LLM_ENABLED is true but ANTHROPIC_API_KEY is not configured. "
        "Supply the credential and restart."
    )


__all__ = ["build_llm", "llm_unwired_reason"]
