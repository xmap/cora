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

## The stdlib handler targets LIVE `sys.stdout`, not a snapshot of it

`logging.StreamHandler(sys.stdout)` would capture whatever object `sys.stdout`
IS at the moment `configure_logging()` runs, not a live reference to the name
`sys.stdout`. That distinction is invisible in production, where `sys.stdout`
never changes identity after process start, but it is a real bug under
pytest's `capsys` fixture, which monkeypatches `sys.stdout` to a fresh object
for every test. A handler built while an EARLIER test's `capsys` patch was
active keeps writing to that test's now-torn-down capture buffer; the
CURRENT test's own `capsys.readouterr()` then sees nothing, while the JSON
line still lands wherever the earlier buffer's underlying stream actually
is (typically the real terminal), which is indistinguishable from the log
line never having been emitted at all unless someone goes looking for it
elsewhere.

This bit `test_run_debriefer_seed.py`'s `capsys`-based assertion: it passed
in isolation and failed only in a full-suite run, because `configure_logging`
is called from `build_kernel` (the production kernel factory) but NOT from
`make_inmemory_kernel` (the lighter one most unit tests use), so a test built
on `make_inmemory_kernel` inherits whichever handler an EARLIER, unrelated
test's `build_kernel()` call last installed in the same worker process --
built under THAT test's `capsys`, not this one's.

`_LiveStdout` below is the standard fix for this class of bug: instead of
handing the handler an object, hand it a proxy whose `write` / `flush` look
up `sys.stdout` FRESH on every call, so the handler is correct regardless of
when it was constructed relative to whichever test's `capsys` is currently
active. This makes calling `configure_logging()` from every kernel
constructor unnecessary, not just unlikely: the handler self-corrects
either way.
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


class _LiveStdout:
    """A write target that always resolves to the CURRENT `sys.stdout`.

    `logging.StreamHandler` stores whatever object it is given at
    construction time and never looks at `sys.stdout` again. Handing it
    this proxy instead of `sys.stdout` directly defers that lookup to
    every individual write, so the handler stays correct even when
    `sys.stdout` is later swapped out from under it (pytest's `capsys`
    fixture does exactly that, once per test). See the module
    docstring's "live `sys.stdout`" section for the failure this fixes.
    """

    def write(self, message: str) -> int:
        return sys.stdout.write(message)

    def flush(self) -> None:
        sys.stdout.flush()


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

    handler = logging.StreamHandler(_LiveStdout())
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
