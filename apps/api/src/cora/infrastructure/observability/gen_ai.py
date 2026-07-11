"""GenAI telemetry helpers per OpenTelemetry semantic conventions.

Used by `AnthropicLLM` (and any future LLM adapter) to set
the standard `gen_ai.*` span attributes and emit token + cost
metrics from one place. Keeps the adapter free of OTel imports
beyond a single helper call.

## OTel GenAI semantic conventions

Reference: https://opentelemetry.io/docs/specs/semconv/gen-ai/
Current status: experimental. Per the design memo's watch item, opt
in is via `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental`
in production deploy config. Attribute names below match the spec as
of July 2026 (`gen_ai.system` was deprecated in favour of
`gen_ai.provider.name`; the durable Decision-side record was already
on the new name, this module now matches it); if the spec renames
again, this module is the single edit point.

Attributes set on the active span:
  - `gen_ai.provider.name`     ("anthropic")
  - `gen_ai.operation.name`    ("chat")
  - `gen_ai.request.model`     (the model identifier from `ModelRef`)
  - `gen_ai.request.max_tokens`
  - `gen_ai.response.model`    (the snapshot the provider chose)
  - `gen_ai.response.finish_reasons` (list with one entry today)
  - `gen_ai.usage.input_tokens`
  - `gen_ai.usage.output_tokens`

Anthropic-specific (not in spec yet, included per their cookbook):
  - `gen_ai.usage.cache_creation_input_tokens`
  - `gen_ai.usage.cache_read_input_tokens`

## Cost

`cora.agent.llm.cost.usd` is a custom histogram (no OTel spec
equivalent today). Computed in `compute_cost_usd` from `PRICING`
indexed by `(provider, model)`. Unknown models cost 0.0 with a
warning logged once per process (the adapter alerts so operators
notice unpriced models in dashboards rather than discovering it
silently at billing reconciliation).

The pricing table is intentionally a plain `dict` rather than a
config file: cadence is too low for runtime overrides, and the
git history of edits IS the audit trail. Update when Anthropic
publishes a new model or revises a price.

## Metrics

Two histograms:
  - `gen_ai.client.token.usage`  (per OTel spec: bucketed token counts;
                                  type attribute distinguishes input
                                  vs output vs cache_create vs cache_read)
  - `cora.agent.llm.cost.usd`    (custom; USD per call)

A meter named `cora.gen_ai` is created lazily on first use so
modules that import this file without calling its functions don't
register orphan instruments.
"""

from __future__ import annotations

from dataclasses import dataclass
from logging import getLogger
from typing import TYPE_CHECKING

from opentelemetry import metrics

if TYPE_CHECKING:
    from opentelemetry.trace import Span

    from cora.infrastructure.ports.llm import LLMUsage, ModelRef

_log = getLogger(__name__)


@dataclass(frozen=True)
class ModelPricing:
    """Per-million-token USD prices for one LLM model.

    `cache_write_per_mtok` is the price of bytes WRITTEN to the
    Anthropic prompt cache at the TTL tier the producers use (2x base
    input for the 1-hour TTL; 1.25x for the 5-minute tier).
    `cache_read_per_mtok` is the price of bytes READ from cache
    (usually ~10% of base input).

    Providers that don't expose cache pricing (or that don't support
    caching) set both cache fields equal to `input_per_mtok` so the
    cost computation degrades cleanly.
    """

    input_per_mtok: float
    output_per_mtok: float
    cache_write_per_mtok: float
    cache_read_per_mtok: float


PRICING: dict[tuple[str, str], ModelPricing] = {
    # Anthropic public pricing (Jul 2026). Cache writes are priced at
    # the 1-HOUR TTL tier (2x base input), because that is the TTL the
    # producers pin on their cache breakpoints; the 5-minute tier would
    # be 1.25x. If a producer ever drops to 5m TTL, model per-TTL write
    # prices instead of repricing the table.
    # Opus dropped to $5/$25 per MTok with the 4.7/4.8 generation.
    ("anthropic", "claude-opus-4-8"): ModelPricing(
        input_per_mtok=5.00,
        output_per_mtok=25.00,
        cache_write_per_mtok=10.00,
        cache_read_per_mtok=0.50,
    ),
    ("anthropic", "claude-opus-4-7"): ModelPricing(
        input_per_mtok=5.00,
        output_per_mtok=25.00,
        cache_write_per_mtok=10.00,
        cache_read_per_mtok=0.50,
    ),
    ("anthropic", "claude-sonnet-4-5"): ModelPricing(
        input_per_mtok=3.00,
        output_per_mtok=15.00,
        cache_write_per_mtok=6.00,
        cache_read_per_mtok=0.30,
    ),
    ("anthropic", "claude-sonnet-4-6"): ModelPricing(
        input_per_mtok=3.00,
        output_per_mtok=15.00,
        cache_write_per_mtok=6.00,
        cache_read_per_mtok=0.30,
    ),
    ("anthropic", "claude-haiku-4-5"): ModelPricing(
        input_per_mtok=1.00,
        output_per_mtok=5.00,
        cache_write_per_mtok=2.00,
        cache_read_per_mtok=0.10,
    ),
}

# Track which (provider, model) pairs we've already warned about,
# so unpriced-model warnings fire once per process per pair rather
# than per call (would flood the log under steady traffic).
_warned_missing_pricing: set[tuple[str, str]] = set()

_meter = metrics.get_meter("cora.gen_ai")
_token_histogram = _meter.create_histogram(
    name="gen_ai.client.token.usage",
    unit="{token}",
    description="Token counts per LLM call, by token-type attribute",
)
_cost_histogram = _meter.create_histogram(
    name="cora.agent.llm.cost.usd",
    unit="USD",
    description="Per-call LLM cost in USD computed from usage tokens and provider pricing",
)


def compute_cost_usd(model_ref: ModelRef, usage: LLMUsage) -> float:
    """Compute the dollar cost of one LLM call.

    Returns 0.0 with a one-time warning when `(provider, model)`
    isn't in `PRICING`. The 0.0 is intentional: dashboards then
    show a flat $0 series for unpriced models, which is easier to
    notice than raising and breaking the call. Operators add a
    `PRICING` entry when they see the warning.

    Cache-read tokens are billed at ~10% of base input; cache-write
    tokens are billed at 2x base input (the 1-hour TTL tier the
    producers pin; the 5-minute tier would be 1.25x). Plain input
    tokens (`usage.input_tokens` minus cache hits/misses) are billed
    at base. The Anthropic SDK reports `input_tokens` exclusive of
    cache tokens, so the three add up to the actual chargeable input.
    """
    key = (model_ref.provider, model_ref.model)
    pricing = PRICING.get(key)
    if pricing is None:
        if key not in _warned_missing_pricing:
            _warned_missing_pricing.add(key)
            _log.warning(
                "gen_ai.compute_cost_usd: no PRICING entry for %s; "
                "reporting $0 until cora.infrastructure.observability.gen_ai.PRICING "
                "is updated. Cost dashboards will show $0 for this model.",
                key,
            )
        return 0.0

    return (
        (usage.input_tokens / 1_000_000.0) * pricing.input_per_mtok
        + (usage.output_tokens / 1_000_000.0) * pricing.output_per_mtok
        + (usage.cache_creation_input_tokens / 1_000_000.0) * pricing.cache_write_per_mtok
        + (usage.cache_read_input_tokens / 1_000_000.0) * pricing.cache_read_per_mtok
    )


def record_llm_call(
    span: Span,
    *,
    provider_name: str,
    request_model_ref: ModelRef,
    response_model_id: str,
    usage: LLMUsage,
    stop_reason: str,
    max_tokens: int,
) -> float:
    """Annotate the active span and emit metrics for one LLM call.

    Returns the computed cost in USD so the caller (the adapter)
    can also surface it on the response or in a structlog line if
    it wants. Span attributes set per the OpenTelemetry GenAI
    semantic conventions module docstring.

    The four token-usage metrics are recorded with a `token_type`
    attribute (`input` / `output` / `cache_create` / `cache_read`)
    per the OTel spec convention so a single histogram series can
    be queried by type.

    SAFE TO CALL when the span is the no-op span (the OTel default
    when tracing is disabled): set_attribute is a no-op and the
    histograms are no-op too when no MeterProvider is installed.
    """
    span.set_attribute("gen_ai.provider.name", provider_name)
    span.set_attribute("gen_ai.operation.name", "chat")
    span.set_attribute("gen_ai.request.model", request_model_ref.model)
    span.set_attribute("gen_ai.request.max_tokens", max_tokens)
    span.set_attribute("gen_ai.response.model", response_model_id)
    span.set_attribute("gen_ai.response.finish_reasons", [stop_reason])
    span.set_attribute("gen_ai.usage.input_tokens", usage.input_tokens)
    span.set_attribute("gen_ai.usage.output_tokens", usage.output_tokens)
    span.set_attribute(
        "gen_ai.usage.cache_creation_input_tokens",
        usage.cache_creation_input_tokens,
    )
    span.set_attribute(
        "gen_ai.usage.cache_read_input_tokens",
        usage.cache_read_input_tokens,
    )

    base_attrs = {
        "gen_ai.provider.name": provider_name,
        "gen_ai.request.model": request_model_ref.model,
        "gen_ai.response.model": response_model_id,
    }
    _token_histogram.record(
        usage.input_tokens,
        attributes={**base_attrs, "token_type": "input"},
    )
    _token_histogram.record(
        usage.output_tokens,
        attributes={**base_attrs, "token_type": "output"},
    )
    if usage.cache_creation_input_tokens:
        _token_histogram.record(
            usage.cache_creation_input_tokens,
            attributes={**base_attrs, "token_type": "cache_create"},
        )
    if usage.cache_read_input_tokens:
        _token_histogram.record(
            usage.cache_read_input_tokens,
            attributes={**base_attrs, "token_type": "cache_read"},
        )

    cost = compute_cost_usd(request_model_ref, usage)
    _cost_histogram.record(cost, attributes=base_attrs)
    return cost


__all__ = [
    "PRICING",
    "ModelPricing",
    "compute_cost_usd",
    "record_llm_call",
]
