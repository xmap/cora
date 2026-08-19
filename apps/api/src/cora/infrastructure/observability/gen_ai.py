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
indexed by `(provider, model)`. Unknown models cost 0.0, with a
warning logged once per process so it cannot flood, and the
`cora.agent.llm.unpriced_calls` counter incremented on every such
call so the condition is alertable rather than only visible as a
flat $0 series someone has to notice at billing reconciliation.

`cora.agent.llm.concurrent_calls` counts calls that begin while
another is still in flight, via `track_in_flight_call`. It exists to
answer one question the budget enforcement ladder cannot answer from
the code alone: the shared-envelope race is characterized at its
worst case, but its incidence is unmeasured. See that tracker's
docstring for how to read a zero.

The pricing table is intentionally a plain `dict` rather than a
config file: cadence is too low for runtime overrides, and the
git history of edits IS the audit trail. Update when Anthropic
publishes a new model or revises a price.

The catalog overlay sits in front of the table: the agent BC's
LanguageModel catalog is the governance home of pricing, and its
loader feeds a process-local overlay via `set_pricing_overlay` at
startup. The static table is the fallback and the day-1 content
(the fleet seeds mirror it, pinned by test). A runtime catalog
pricing change takes effect at next boot; the in-process refresh
subscriber is the recorded follow-up.

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

from contextlib import contextmanager
from dataclasses import dataclass
from logging import getLogger
from typing import TYPE_CHECKING

from opentelemetry import metrics

if TYPE_CHECKING:
    from collections.abc import Generator, Mapping

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

# Argo serves these same vendor models, so the same list rates carry
# over unchanged. This is a counterfactual price, not an invoice: the
# facility absorbs the gateway's cost rather than the deployment, and
# what the envelope debits is what the call WOULD have cost bought
# directly. That is the point of a source-agnostic envelope, since a
# route someone else funds is not a free one. A negotiated or
# facility-specific rate belongs in the catalog overlay, which is
# consulted first.
#
# Mirroring the table also gives the gateway the same safety net the
# direct path has. Every call is gated at registration on an Approved
# catalog entry, and approval refuses a GPU-hour basis, so the overlay
# normally answers. Without these entries a retired catalog entry would
# drop an Argo call to zero while the identical Anthropic call stayed
# priced.
PRICING.update(
    {
        ("argo", model): pricing
        for (provider, model), pricing in list(PRICING.items())
        if provider == "anthropic"
    }
)

# Track which (provider, model) pairs we've already warned about,
# so unpriced-model warnings fire once per process per pair rather
# than per call (would flood the log under steady traffic).
_warned_missing_pricing: set[tuple[str, str]] = set()

# Process-local catalog overlay, consulted before PRICING. Replaced
# wholesale by set_pricing_overlay; never mutated in place.
_pricing_overlay: dict[tuple[str, str], ModelPricing] = {}


def set_pricing_overlay(pricing: Mapping[tuple[str, str], ModelPricing]) -> None:
    """Replace the catalog pricing overlay atomically.

    Called by the agent BC's loader at startup with every Approved
    token-priced catalog entry. The whole overlay is REPLACED (a new
    dict is assigned, never mutated in place), so an entry removed
    from the catalog falls back to the static table on the next set
    rather than lingering at a withdrawn price.
    """
    global _pricing_overlay
    _pricing_overlay = dict(pricing)


def _resolve_pricing(key: tuple[str, str]) -> ModelPricing | None:
    """Catalog overlay first (the governed price), then the static table."""
    overlay = _pricing_overlay.get(key)
    if overlay is not None:
        return overlay
    return PRICING.get(key)


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
_unpriced_call_counter = _meter.create_counter(
    name="cora.agent.llm.unpriced_calls",
    unit="{call}",
    description="LLM calls recorded at $0 because no catalog or static pricing entry resolved",
)
_concurrent_call_counter = _meter.create_counter(
    name="cora.agent.llm.concurrent_calls",
    unit="{call}",
    description="LLM calls started while another was already in flight in this process",
)

# Process-local in-flight depth. A plain int is sound here because the LLM
# callers share one event loop (the projection worker runs its subscribers as
# concurrent tasks in a single TaskGroup) and nothing awaits between the read
# and the increment in the tracker below.
_in_flight_calls = 0


@contextmanager
def track_in_flight_call(model_ref: ModelRef) -> Generator[None]:
    """Count LLM calls that begin while another is already in flight.

    This measures the PRECONDITION for the shared-envelope race, which is the
    one quantity the enforcement ladder could not supply. The allocation
    gate's post-hoc arm reads recorded spend and admits; a caller reaching the
    gate before an earlier caller has posted reads a stale total and is
    admitted against spend already committed. The worst case is characterized
    (two callers leak two calls through a ceiling that should have stopped
    one). What was never known is how often the window actually opens.

    A nonzero `cora.agent.llm.concurrent_calls` rate says the window opens and
    the residual is real. A flat zero across a representative period says the
    race is theoretical in this deployment, and the reserve-post-void tier's
    trigger can then be retired on evidence rather than on argument.

    Scope: process-local, which is the scope of the observed race. Calls
    racing from separate replicas are not counted; seeing those would need
    the ledger to carry a call start time, which it does not.
    """
    global _in_flight_calls
    if _in_flight_calls > 0:
        _concurrent_call_counter.add(
            1,
            {
                "gen_ai.provider.name": model_ref.provider,
                "gen_ai.request.model": model_ref.model,
            },
        )
    _in_flight_calls += 1
    try:
        yield
    finally:
        _in_flight_calls -= 1


@dataclass(frozen=True)
class LlmCallCeiling:
    """Upper-bound cost and token count for one not-yet-made LLM call."""

    cost_usd: float
    tokens: int


def estimate_llm_call_ceiling(
    model_ref: ModelRef, *, input_chars: int, max_output_tokens: int
) -> LlmCallCeiling | None:
    """Estimate the most one LLM call can cost, before making it.

    The pre-estimate enforcement tier refuses a call whose projected
    spend would breach a cap, so this estimate must be a CEILING: its
    error must point toward refusing a call the balance could barely
    afford, never toward permitting one it cannot. Two deliberate
    high-side biases deliver that. Input tokens are estimated at one
    token per three characters (real English and JSON run closer to
    four); and the whole input estimate is priced at the model's
    cache-WRITE rate, the dearest input tier, as if every byte missed
    the cache. Output is priced at the full `max_output_tokens`, which
    the provider enforces as a hard cap.

    Returns None when `(provider, model)` has no entry in the catalog
    overlay or `PRICING`: no price means no ceiling, and the caller
    skips the gate (permissive, matching `compute_cost_usd`'s
    $0-for-unpriced posture) rather than refusing calls it cannot cost.
    """
    pricing = _resolve_pricing((model_ref.provider, model_ref.model))
    if pricing is None:
        return None
    input_tokens = -(-input_chars // 3)
    cost = (
        input_tokens / 1_000_000 * pricing.cache_write_per_mtok
        + max_output_tokens / 1_000_000 * pricing.output_per_mtok
    )
    return LlmCallCeiling(cost_usd=cost, tokens=input_tokens + max_output_tokens)


def compute_cost_usd(model_ref: ModelRef, usage: LLMUsage) -> float:
    """Compute the dollar cost of one LLM call.

    Returns 0.0 when `(provider, model)` is in neither the catalog
    overlay nor `PRICING`. The 0.0 is intentional: dashboards then
    show a flat $0 series for unpriced models, which is easier to
    notice than raising and breaking the call. Operators add a
    `PRICING` entry (or approve a catalog entry) when they see it.

    Two signals fire on that path and they carry different weight.
    The log warning is deduplicated to once per process per identity
    so it cannot flood, which is also why it cannot carry an alert.
    The `cora.agent.llm.unpriced_calls` counter increments on EVERY
    unpriced call, so a nonzero rate is alertable. That matters
    because an unpriced model does not merely mis-report a dashboard:
    it makes the USD arm of both enforcement tiers inert (the
    post-hoc gate sums $0 forever and the pre-estimate guard projects
    $0), while the daily token cap keeps working and masks it.

    Cache-read tokens are billed at ~10% of base input; cache-write
    tokens are billed at 2x base input (the 1-hour TTL tier the
    producers pin; the 5-minute tier would be 1.25x). Plain input
    tokens (`usage.input_tokens` minus cache hits/misses) are billed
    at base. The Anthropic SDK reports `input_tokens` exclusive of
    cache tokens, so the three add up to the actual chargeable input.
    """
    key = (model_ref.provider, model_ref.model)
    pricing = _resolve_pricing(key)
    if pricing is None:
        _unpriced_call_counter.add(
            1,
            {
                "gen_ai.provider.name": model_ref.provider,
                "gen_ai.request.model": model_ref.model,
            },
        )
        if key not in _warned_missing_pricing:
            _warned_missing_pricing.add(key)
            _log.warning(
                "gen_ai.compute_cost_usd: no PRICING entry for %s; "
                "reporting $0 until a catalog entry is approved or "
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
    "set_pricing_overlay",
]
