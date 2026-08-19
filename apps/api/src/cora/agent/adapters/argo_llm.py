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
    It must be a person's username: service accounts are documented for
    Argo but are not usable at Argonne as of 2026-08, so a long-lived
    deployment runs under a named individual and the gateway's audit
    trail is tied to them. Plan for that rather than around it, and
    revisit if service accounts become available.
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
and histogram attributes come from the adapter. `chat` requires the
two to agree so a call cannot be served by the gateway and priced as
a direct-vendor purchase at the same time.
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

_AUTH_NOTICE_MARKER = "NOTICE FROM ARGO"
"""Substring of the gateway's denial text, which it returns with HTTP 200.

Matched alongside a zero-token usage report, which no served call
produces, so a legitimate response that merely quotes this phrase is
not mistaken for a denial.
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
    if message.usage.input_tokens != 0 or message.usage.output_tokens != 0:
        return
    text = "".join(block.text for block in message.content if block.type == "text")
    if _AUTH_NOTICE_MARKER not in text:
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
    authenticates against. `ac.*` accounts are not authorized, and
    neither, today, is a service account.

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
        if request.model_ref.provider != ARGO_PROVIDER_NAME:
            msg = (
                f"ArgoLLM was handed a model_ref with provider "
                f"{request.model_ref.provider!r}, but cost resolves from that "
                f"field while the call is served by the gateway. Price the "
                f"entry as {ARGO_PROVIDER_NAME!r} in the catalog, or select "
                "the direct-vendor adapter."
            )
            raise LLMInvalidRequestError(msg)
        return await self._inner.chat(request)


__all__ = ["ARGO_BASE_URL", "ARGO_PROVIDER_NAME", "ArgoLLM", "resolve_argo_model_id"]
