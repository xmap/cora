"""Structured logging configuration.

Uses `structlog` with `contextvars` so context bound at the ASGI boundary
and at command-handler entry propagates to every log line emitted inside
the decider, repository, and projection.

OpenTelemetry trace context (`trace_id`, `span_id`, `trace_flags`) is
injected by the `add_trace_context` processor when an active span is
present, letting log-aggregator queries pivot from a log line to the
corresponding distributed trace. The processor is a no-op when no
span is active (default test environment uses the no-op tracer), so
unit tests don't need to set up a TracerProvider.

The structlog wrapper chain ends with `ProcessorFormatter.wrap_for_formatter`
(not a renderer) so the wrapped event_dict reaches the stdlib
`ProcessorFormatter`, which runs `JSONRenderer()` exactly once. Terminating
the wrapper chain with `JSONRenderer()` would render twice and produce
JSON-in-JSON output that log aggregators can't index.

Caching nuance — `cache_logger_on_first_use=True` means structlog binds each
named logger to the live configuration on first use and keeps that binding.
`build_kernel()` calls `configure_logging()` once per `create_app()`, so the
function must be safe to call repeatedly, and it splits along that seam: the
structlog side configures once per process, the stdlib handler is rebuilt on
every call, so log level follows the most recent caller.

Configuring structlog more than once is what the guard exists to prevent, and
the reason is not cosmetic. A second `structlog.configure()` installs a NEW
processor list; loggers already bound and cached against the first list keep
using it. In production the two lists are identical so nothing is visibly
wrong, but `structlog.testing.capture_logs()` works by swapping the live
config's processors, and a cached logger reading the old list never sees the
swap. Any test asserting on captured events then collects nothing, while the
log line still appears on stdout — a failure that looks like a missing log and
is really a stale binding. It surfaces only when a test runs after a second
app is built, so it presents as order-dependent flakiness.

If per-call reconfiguration is ever genuinely needed, set
`cache_logger_on_first_use=False` and accept the per-call binding cost; do not
simply drop the guard.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

import logging
import sys
from typing import TYPE_CHECKING

import structlog
from structlog.contextvars import merge_contextvars

from cora.infrastructure.observability import add_trace_context

if TYPE_CHECKING:
    from structlog.types import Processor


_structlog_configured = False


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog and bridge stdlib logging to it. Call once at startup."""
    global _structlog_configured
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared_processors: list[Processor] = [
        merge_contextvars,
        add_trace_context,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
    ]

    # Configure structlog once per process. `build_kernel()` calls this on every
    # `create_app()`, and a second call installs a NEW processor list: loggers
    # already bound and cached against the first one keep using it and never see
    # the replacement. That is invisible in production, where the two lists are
    # identical, but it silently defeats `structlog.testing.capture_logs()` in
    # any test that runs after a second app is built, because capture swaps the
    # live config's processors and the cached loggers are not reading from it.
    # The stdlib handler below is rebuilt every call, so log level still tracks
    # the most recent caller.
    if not _structlog_configured:
        structlog.configure(
            processors=[
                *shared_processors,
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                # Hand off to the stdlib ProcessorFormatter; do not render here.
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
        _structlog_configured = True

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=shared_processors,
        )
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a logger bound to the given name (typically `__name__`)."""
    return structlog.get_logger(name)
