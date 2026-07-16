"""TracerProvider configuration and per-app FastAPI instrumentation.

Two public entrypoints:

- `build_tracing(settings)` is pure: builds a `TracerProvider` and a
  `teardown` callable per `settings.otel_exporter`, mutates no global
  state. Used by tests so unit-level coverage of exporter selection
  doesn't flip the process-wide global (OTel's `set_tracer_provider`
  is one-shot per process).
- `configure_tracing(settings)` calls `build_tracing` and additionally
  installs the provider as the global, plus instruments process-wide
  libraries (asyncpg). Returns the same `teardown` callable.

`instrument_app(app, settings)` attaches `FastAPIInstrumentor` to a
specific FastAPI instance with `excluded_urls` matching CORA's
operational endpoints (probes + scrape + docs) so they don't flood
the trace exporter under normal traffic.

Exporter selection (`settings.otel_exporter`):

- `none`    — no provider installed; the global default no-op tracer
              stays active. Default for `app_env=test` so spans don't
              accumulate across many `create_app()` instances in the
              test process. Also the package-level default (Settings
              field) so unconfigured deployments are observable-when-
              chosen rather than observable-by-accident.
- `console` — `ConsoleSpanExporter` with `SimpleSpanProcessor`. Spans
              print to stdout immediately. Recommended for local dev.
- `otlp`    — `OTLPSpanExporter` (HTTP/protobuf) with
              `BatchSpanProcessor`. Recommended for production. The
              endpoint is read from the standard `OTEL_EXPORTER_OTLP_*`
              env vars (we do NOT shadow them with a custom setting,
              so existing OTel deployment tooling Just Works).

Sampler is `ParentBased(AlwaysOn)` for `console` (development is
loud by design), and `ParentBased(TraceIdRatioBased(ratio))` for
`otlp` so root spans are sampled at the configured ratio while child
spans inherit the root's sampling decision.

Resource attributes follow OTel semantic conventions:
`service.name`, `service.version`, `service.namespace`,
`deployment.environment`. Set once on the provider; every span
inherits them.
"""

from collections.abc import Callable
from logging import getLogger
from typing import TYPE_CHECKING

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from opentelemetry.sdk.trace.sampling import (
    ALWAYS_ON,
    ParentBased,
    Sampler,
    TraceIdRatioBased,
)
from opentelemetry.semconv._incubating.attributes.deployment_attributes import (
    DEPLOYMENT_ENVIRONMENT,
)
from opentelemetry.semconv.attributes.service_attributes import (
    SERVICE_NAME,
    SERVICE_NAMESPACE,
    SERVICE_VERSION,
)

from cora import __version__

if TYPE_CHECKING:
    from cora.infrastructure.config import Settings

# Endpoints that get hit by infrastructure (probes + scrape + docs)
# rather than by user-facing traffic. Tracing them produces noise
# proportional to the probe interval, not the request rate. Comma-
# separated regex patterns per FastAPIInstrumentor's excluded_urls
# contract; substring match is sufficient for these stable paths.
_EXCLUDED_URLS = "health,readyz,metrics,docs,openapi.json,redoc"

_log = getLogger(__name__)

Teardown = Callable[[], None]


def build_tracing(settings: "Settings") -> tuple[TracerProvider | None, Teardown]:
    """Build a TracerProvider per `settings.otel_exporter` without installing it.

    Returns `(provider, teardown)`. `provider` is `None` for `none`
    (no work to do); `teardown` is always callable. Pure: no global
    state mutated, safe to call repeatedly in tests.

    For `otlp`, `OTLPSpanExporter()` is constructed without an explicit
    `endpoint` so it picks up `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` (or
    falls back to `OTEL_EXPORTER_OTLP_ENDPOINT`, with `/v1/traces`
    appended) from the environment per the OTel SDK convention.
    """
    if settings.otel_exporter == "none":
        return None, _noop_teardown

    resource = Resource.create(
        {
            SERVICE_NAME: settings.otel_service_name,
            SERVICE_VERSION: __version__,
            SERVICE_NAMESPACE: "cora",
            DEPLOYMENT_ENVIRONMENT: settings.app_env,
        }
    )

    sampler: Sampler
    if settings.otel_exporter == "console":
        sampler = ParentBased(root=ALWAYS_ON)
    else:  # "otlp"
        sampler = ParentBased(root=TraceIdRatioBased(settings.otel_sampler_ratio))

    provider = TracerProvider(resource=resource, sampler=sampler)

    if settings.otel_exporter == "console":
        # SimpleSpanProcessor exports synchronously per finished span —
        # acceptable for local dev where latency doesn't matter and
        # immediate visibility does.
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    else:  # "otlp"
        # BatchSpanProcessor batches spans and flushes asynchronously to
        # the OTLP collector. force_flush() on shutdown drains the queue.
        # Endpoint resolved by the exporter from OTEL_EXPORTER_OTLP_*
        # env vars; our Settings doesn't shadow those.
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))

    def teardown() -> None:
        # force_flush gives in-flight spans a chance to ship; shutdown
        # tears down processors and exporters cleanly.
        provider.force_flush()
        provider.shutdown()

    return provider, teardown


def configure_tracing(settings: "Settings") -> Teardown:
    """Install a global TracerProvider per `settings.otel_exporter`.

    Also instruments process-wide libraries (asyncpg) when tracing is on;
    the asyncpg instrumentor is idempotent (guarded by its own
    `is_instrumented_by_opentelemetry` flag) so calling this from many
    `create_app()` invocations in tests is safe.

    Returns a `teardown()` callable to flush pending spans on shutdown.
    Calling teardown is idempotent and safe even when `none` was selected
    (it returns immediately).

    OTel's `set_tracer_provider` is one-shot per process. If a SDK
    provider is already installed (eg. by an earlier `create_app()` in
    the test suite, or by an external auto-instrumentation agent), the
    install step is skipped and a warning is logged so an operator
    debugging "why aren't my spans appearing" has a breadcrumb. The
    new provider's teardown is still wired so pending spans flush on
    shutdown.
    """
    provider, teardown = build_tracing(settings)
    if provider is None:
        return teardown

    if isinstance(trace.get_tracer_provider(), TracerProvider):
        # Pre-existing SDK provider; respect it. The new provider's
        # processors will not see traffic, but its teardown is still
        # safe to call.
        _log.warning(
            "configure_tracing: a TracerProvider was already installed; "
            "skipping our installation. Spans will be exported to that "
            "provider's processors, not the one we built (exporter=%s).",
            settings.otel_exporter,
        )
        return teardown

    trace.set_tracer_provider(provider)

    # Instrument process-wide libraries. AsyncPGInstrumentor patches the
    # asyncpg module; instrument() is guarded by its own
    # is_instrumented_by_opentelemetry flag so repeat calls (per
    # create_app() in tests) are no-ops.
    AsyncPGInstrumentor().instrument()

    return teardown


def instrument_app(app: FastAPI, settings: "Settings") -> None:
    """Attach FastAPIInstrumentor to a specific app instance.

    Per-app (not process-wide) so each `create_app()` in the test suite
    can be cleanly torn down with the app instance. Skipped when tracing
    is off so tests don't pay span-creation overhead.

    `excluded_urls` keeps probe + scrape + docs traffic out of the trace
    exporter; production proxies hit `/health` and Prometheus hits
    `/metrics` on a fixed cadence, generating spans that vastly
    outnumber user traffic if not filtered.
    """
    if settings.otel_exporter == "none":
        return
    FastAPIInstrumentor.instrument_app(app, excluded_urls=_EXCLUDED_URLS)


def _noop_teardown() -> None:
    return None
