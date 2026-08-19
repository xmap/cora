"""Argo implementation of `LLM`.

Argonne's Argo gateway is a multi-vendor LLM proxy, internal to ANL,
that fronts Anthropic, OpenAI, and Google models behind one endpoint.
This adapter covers its Anthropic family, which it serves at
`/v1/messages` as the Anthropic Messages API verbatim.

## Why this composes `AnthropicLLM` instead of copying it

Measured against the live gateway from an APS host on 2026-08-18,
`/v1/messages` accepts and honors every mechanism the direct adapter
depends on:

  - Forced tool-use structured output. A request pinning
    `tool_choice` to the synthetic `cora_structured_output` tool came
    back with `stop_reason: tool_use` and schema-conforming input.
  - Prompt caching at the 1-hour TTL, with the
    `extended-cache-ttl-2025-04-11` beta header. A 5990-token prefix
    reported `cache_creation.ephemeral_1h_input_tokens: 5990` on
    write and `cache_read_input_tokens: 5984` on the following call,
    so the tier is genuinely 1h and is not silently downgraded to 5m.
  - The Anthropic `usage` shape, cache counters included.

Duplicating the request assembly, cache-breakpoint validation, error
translation, and usage mapping would mean two copies of logic that
one measured protocol drives. So the gateway concerns that DO differ
live here, and the shared mechanics stay in one place.

## What differs, and is therefore owned here

  - **Base URL and credential.** Argo authenticates with a bare ANL
    domain username in the API-key position; there is no issued key.
    A long-lived deployment should carry a SERVICE ACCOUNT rather than a
    person, so the gateway's usage tracking attributes these calls to
    the application instead of mixing them into someone's personal use.
    A service account is not an unowned identity: it stays tied to the
    ANL account, ALD, and division of whoever registered it. What it
    separates is attribution, not ownership.
  - **Authentication failures arrive as successful responses.** An
    unrecognized username returns HTTP 200 carrying a synthetic
    assistant message that says access was denied, not a 401, so the
    SDK raises nothing. `_reject_auth_notice` catches it and raises
    `LLMAuthenticationError`, because the alternative is a missing
    tool-use block reported as a schema failure, which sends the
    operator to the prompt instead of the credential and, worse, is
    the error class the debrief path defers on rather than retries.
  - **Model identifiers.** The gateway publishes its own handles
    (`claudehaiku45`), which `_ARGO_MODEL_IDS` maps from the upstream
    names the catalog and the pricing table use. The gateway also
    resolves upstream names directly (measured: `claude-haiku-4-5`
    served fine), so the map is not strictly required to reach a
    model. It is kept because `/v1/models` publishes `internal_id` as
    the canonical handle, and because an unknown name should fail
    here with the list of what is available rather than as a gateway
    error whose text names a model nobody asked for.
  - **No snapshot pins.** A request cannot select a dated snapshot
    through Argo, so one is refused rather than quietly ignored. The
    response still REPORTS which snapshot served
    (`claude-haiku-4-5-20251001`), and that lands on `model_id`, so
    the record captures what actually ran even though the request
    could not demand it. This is the concrete meaning of the `Alias`
    archivability tier: observable after the fact, not reproducible
    on demand.

## Routing note

Responses carry `msg_vrtx_` / `toolu_vrtx_` identifiers, so the
gateway reaches Anthropic models by way of Google Vertex AI rather
than Anthropic's first-party API. Feature availability on Vertex is
narrower than first-party in general; everything this port uses was
measured working, but a future port extension (server-side tools,
streaming) must be re-checked against the gateway rather than
assumed from Anthropic's own documentation.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

import anthropic

from cora.agent.adapters.anthropic_llm import AnthropicLLM
from cora.infrastructure.ports.llm import LLMAuthenticationError, LLMInvalidRequestError

if TYPE_CHECKING:
    from cora.infrastructure.ports.llm import LLMChatRequest, LLMResponse, ModelRef

ARGO_BASE_URL = "https://apps.inside.anl.gov/argoapi"
"""Production gateway. The `apps-dev.inside` sibling is unannounced and unstable."""

ARGO_PROVIDER_NAME = "argo"
"""Reported as `gen_ai.provider.name`, and required on `ModelRef.provider`.

Pricing resolves from the ModelRef's own provider field, while span
and histogram attributes come from the adapter. `AnthropicLLM` requires
the two to agree, so a call cannot be served by the gateway and priced
as a direct-vendor purchase at the same time, nor the reverse.
"""

_ARGO_MODEL_IDS = MappingProxyType(
    {
        "claude-opus-5": "claudeopus5",
        "claude-opus-4-8": "claudeopus48",
        "claude-opus-4-7": "claudeopus47",
        "claude-opus-4-6": "claudeopus46",
        "claude-opus-4-5": "claudeopus45",
        "claude-opus-4-1": "claudeopus41",
        "claude-sonnet-5": "claudesonnet5",
        "claude-sonnet-4-6": "claudesonnet46",
        "claude-sonnet-4-5": "claudesonnet45",
        "claude-haiku-4-5": "claudehaiku45",
    }
)
"""Upstream model name to the gateway's own handle.

Verified against the live `/v1/models` on 2026-08-18: the endpoint
publishes both a display `id` and the `internal_id` the API wants,
and these ten are exactly its Anthropic entries. The gateway's
catalog is NOT Anthropic's published catalog, so a model absent here
should be confirmed against `/v1/models` before being added.
"""

_BLOCKED_MESSAGE_ID_PREFIX = "msg_blocked_"
"""How the gateway stamps a refused call's message id.

Observed as `msg_blocked_<username>_<epoch>` on every denial measured
(2026-08-18 and 2026-08-19). This is the structural signal and is
checked first: an id scheme is far less likely to drift than the prose
below, and a served response never carries it.
"""

_AUTH_NOTICE_MARKER = "NOTICE FROM ARGO"
"""Substring of the gateway's denial text, which it returns with HTTP 200.

The fallback for the id check above, kept because it was the first
signal observed and costs nothing. Matched only alongside a zero-token
usage report, which no served call produces, so a legitimate response
that merely quotes this phrase is not mistaken for a denial.
"""

_DEFAULT_MAX_RETRIES = 2
_DEFAULT_REQUEST_TIMEOUT_SECONDS = 600.0


def resolve_argo_model_id(model_ref: ModelRef) -> str:
    """Translate an upstream model name to the gateway's handle.

    Raises `LLMInvalidRequestError` for an unmapped model, and for any
    snapshot pin, which the gateway cannot honor on a request.
    """
    if model_ref.snapshot_pin is not None:
        msg = (
            f"Argo cannot pin snapshot {model_ref.snapshot_pin!r} for "
            f"{model_ref.model!r}: the gateway selects the snapshot itself and "
            "reports it on the response. Drop the pin and read the served "
            "snapshot from LLMResponse.model_id, or call the vendor directly "
            "if the pin has to be requested."
        )
        raise LLMInvalidRequestError(msg)
    argo_model_id = _ARGO_MODEL_IDS.get(model_ref.model)
    if argo_model_id is None:
        known = ", ".join(sorted(_ARGO_MODEL_IDS))
        msg = (
            f"model {model_ref.model!r} has no Argo identifier. "
            f"Known models: {known}. Check /v1/models on the gateway; its "
            "catalog is not the vendor's published catalog."
        )
        raise LLMInvalidRequestError(msg)
    return argo_model_id


def _reject_auth_notice(message: anthropic.types.Message) -> None:
    """Raise `LLMAuthenticationError` when the gateway denied the username.

    Argo reports an unauthorized username as a normal 200 response whose
    single text block carries the denial, so nothing upstream treats it
    as a failure.
    """
    text = "".join(block.text for block in message.content if block.type == "text")
    blocked_by_id = message.id.startswith(_BLOCKED_MESSAGE_ID_PREFIX)
    spent_no_tokens = message.usage.input_tokens == 0 and message.usage.output_tokens == 0
    if not blocked_by_id and not (spent_no_tokens and _AUTH_NOTICE_MARKER in text):
        return
    msg = (
        "Argo rejected the configured username. The gateway returns this as a "
        "successful response rather than a 401, so it is surfaced here instead. "
        "Check ARGO_USERNAME is a valid ANL domain username (an `ac.*` account "
        f"is not authorized). Gateway said: {' '.join(text.split())}"
    )
    raise LLMAuthenticationError(msg)


class ArgoLLM:
    """`LLM` served through the Argo gateway's Anthropic Messages endpoint.

    `username` is the ANL domain username (not the `@anl.gov` address),
    passed in the API-key position because that is what the gateway
    authenticates against. `ac.*` accounts are not authorized. A service
    account name is accepted and is the right choice here; note that the
    gateway's naming rules may prefix the requested name, so configure
    whatever string the provisioned account actually resolves to rather
    than the name as requested.

    Optionally accepts an explicit `client` so tests can point the
    whole adapter at a local HTTP server without reaching the gateway.
    """

    def __init__(
        self,
        *,
        username: str,
        base_url: str = ARGO_BASE_URL,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        request_timeout_seconds: float = _DEFAULT_REQUEST_TIMEOUT_SECONDS,
        client: anthropic.AsyncAnthropic | None = None,
    ) -> None:
        self._inner = AnthropicLLM(
            api_key=username,
            client=client
            or anthropic.AsyncAnthropic(
                api_key=username,
                base_url=base_url,
                max_retries=max_retries,
                timeout=request_timeout_seconds,
            ),
            provider_name=ARGO_PROVIDER_NAME,
            resolve_model_id=resolve_argo_model_id,
            inspect_response=_reject_auth_notice,
        )

    async def aclose(self) -> None:
        """Release the underlying httpx connection pool at shutdown."""
        await self._inner.aclose()

    async def chat(self, request: LLMChatRequest) -> LLMResponse:
        # The provider-agreement guard is not repeated here. It lives in
        # AnthropicLLM keyed on `provider_name`, which this adapter sets
        # to `argo`, so both the gateway and the direct path are covered
        # by one check rather than by two that could drift apart.
        return await self._inner.chat(request)


__all__ = ["ARGO_BASE_URL", "ARGO_PROVIDER_NAME", "ArgoLLM", "resolve_argo_model_id"]
