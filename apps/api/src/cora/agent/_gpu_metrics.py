"""GPU-serving observability: the visibility half of the build path.

In the locked design in-house serving is metered-free by default, so the
GPU time a served call consumes never debits the budget. This module is
where a facility nonetheless gets to SEE that cost: it turns each call's
occupancy-share GPU-seconds (from the serving meter,
`cora.infrastructure.observability.gpu_accounting`) into two OpenTelemetry
metrics, tagged by model and device:

  - `cora.agent.llm.gpu.seconds`      -- per-call GPU-seconds. Summed per
                                         device over wall-time, this is the
                                         capacity signal (how busy the pool
                                         is); it is also the raw input to
                                         the shadow cost.
  - `cora.agent.llm.gpu.shadow_cost.usd` -- the same seconds priced at the
                                         facility's amortized GPU-hour rate.
                                         An INDICATIVE figure so a facility
                                         can watch what its metered-free
                                         serving really costs and re-base
                                         the token rate when volume grows.
                                         It is never debited.

The `usd_per_gpu_hour` rate is a facility figure supplied at the
composition root (it is deliberately NOT on the catalog entry: a
single-valued `cost_basis` cannot hold both a debiting token price and the
GPU-hour primitive, so the primitive lives here as observability input).
`make_gpu_usage_sink` binds it into the `on_measure` callable the `LocalLLM`
adapter drives once per call.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from opentelemetry import metrics

if TYPE_CHECKING:
    from collections.abc import Callable

    from cora.agent.adapters.local_llm import GpuUsageRecord

_meter = metrics.get_meter("cora.gpu_serving")
_gpu_seconds_histogram = _meter.create_histogram(
    name="cora.agent.llm.gpu.seconds",
    unit="s",
    description="Per-call GPU-seconds attributed to a served call by occupancy share",
)
_gpu_shadow_cost_histogram = _meter.create_histogram(
    name="cora.agent.llm.gpu.shadow_cost.usd",
    unit="USD",
    description="Indicative GPU-hour shadow cost of a served call (visibility, never debited)",
)


def gpu_shadow_cost_usd(gpu_seconds: float, usd_per_gpu_hour: float) -> float:
    """Price attributed GPU-seconds at a facility GPU-hour rate (visibility only).

    The facility's amortized `usd_per_gpu_hour` times the call's
    occupancy-share GPU-seconds, in USD. This is what the meter reports so a
    facility can see the real cost of its metered-free in-house serving and
    decide when to re-base the token rate; it never debits the envelope.
    """
    if not math.isfinite(usd_per_gpu_hour) or usd_per_gpu_hour < 0.0:
        msg = f"usd_per_gpu_hour must be finite and non-negative, got {usd_per_gpu_hour}"
        raise ValueError(msg)
    return gpu_seconds / 3600.0 * usd_per_gpu_hour


def record_gpu_usage(record: GpuUsageRecord, *, usd_per_gpu_hour: float) -> float:
    """Emit the GPU-seconds and shadow-cost metrics for one served call.

    Returns the computed shadow cost (the histograms are the durable
    surface; the return is a convenience for callers that want to log it).
    Safe to call when no MeterProvider is installed: the histograms are
    no-ops then, exactly like the token-cost histogram in `gen_ai`.
    """
    shadow_cost = gpu_shadow_cost_usd(record.gpu_seconds, usd_per_gpu_hour)
    attributes = {
        "gen_ai.request.model": record.model,
        "gpu.device_id": record.device_id,
    }
    _gpu_seconds_histogram.record(record.gpu_seconds, attributes=attributes)
    _gpu_shadow_cost_histogram.record(shadow_cost, attributes=attributes)
    return shadow_cost


def make_gpu_usage_sink(usd_per_gpu_hour: float) -> Callable[[GpuUsageRecord], None]:
    """Bind a facility GPU-hour rate into an `on_measure` sink for `LocalLLM`.

    The composition root reads the facility's `usd_per_gpu_hour` and hands the
    resulting sink to the `LocalLLM` adapter, which calls it once per served
    call. The sink emits the GPU-seconds and shadow-cost metrics.
    """

    def sink(record: GpuUsageRecord) -> None:
        record_gpu_usage(record, usd_per_gpu_hour=usd_per_gpu_hour)

    return sink


__all__ = [
    "gpu_shadow_cost_usd",
    "make_gpu_usage_sink",
    "record_gpu_usage",
]
