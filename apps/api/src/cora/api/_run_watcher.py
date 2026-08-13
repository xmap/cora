"""RunWatcher runtime: shadow-observe an external tool's captures.

Background loop draining a `CaptureObserver` and logging each
observation's classified phase. SHADOW ONLY: this module writes
nothing anywhere, ever, by construction, regardless of any Settings
flag. There is no event append, no entries-table write, and no Run
command issued from this file. Promoting from shadow to a real
recorded Run genesis is deliberately a separate, not-yet-built module:
shadow mode exists so a deployment can watch a real capture end to end,
over a real substrate, before any write path exists to get wrong.

Hosted at the composition root (`cora.api`), like `_run_initiator.py`
and `_enclosure_permit_observer.py`: it will later compose a Run BC
command with an Agent principal, and only `cora.api` may depend on both.

## Log lines, one per observation

- `run_watcher.capture_begun`
- `run_watcher.capture_progressing`
- `run_watcher.capture_ended`
- `run_watcher.capture_aborted`
- `run_watcher.capture_unrecognized`: `phase` is `UNRECOGNIZED`, meaning
  `reported_status` did not match the deployment's declared literal
  table. A vocabulary drift (a tool upgrade renaming a status), not
  routine progress; worth an operator's attention.
- `run_watcher.capture_unreached`: `phase` is `None`, meaning this
  observation made no status claim at all (a probe-only re-affirmation
  read, or a disconnect the adapter reported with nothing to classify).

Every line carries `capture_code`, `reported_status`, `source_kind`,
`source_id`, and `observed_at` (nullable; see `CaptureObservation`'s
own docstring on why an adapter must never substitute a synthesized
time for an absent one).

## Retry + resilience

Mirrors `run_enclosure_permit_monitor`: `observe()` ending (stream
terminated or raised) triggers a bounded sleep then re-subscribe. A
single bad observation is logged and skipped so the loop survives it.
Cancellation (lifespan shutdown) propagates.

## No startup-readiness gate

`enclosure_permit_monitor_lifespan` waits for a settled read before
yielding because a real precondition (the run-start preflight) reads
`permit_status` right after boot. Shadow mode makes no claim anything
depends on, so there is no boot race to close and no wait is needed.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

from cora.infrastructure.logging import get_logger
from cora.run.ports.capture_observer import CaptureObserverScope, CapturePhase

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from cora.run.ports.capture_observer import CaptureObservation, CaptureObserver

_RECONNECT_DELAY_SECONDS = 5.0

_log = get_logger(__name__)

_PHASE_LOG_EVENT: dict[CapturePhase, str] = {
    CapturePhase.BEGUN: "run_watcher.capture_begun",
    CapturePhase.PROGRESSING: "run_watcher.capture_progressing",
    CapturePhase.ENDED: "run_watcher.capture_ended",
    CapturePhase.ABORTED: "run_watcher.capture_aborted",
    CapturePhase.UNRECOGNIZED: "run_watcher.capture_unrecognized",
}


def observe_capture(observation: CaptureObservation) -> None:
    """Log one observation. The entire body of shadow mode: no writes."""
    if observation.phase is None:
        event = "run_watcher.capture_unreached"
    else:
        event = _PHASE_LOG_EVENT[observation.phase]
    _log.info(
        event,
        capture_code=observation.capture_code,
        reported_status=observation.reported_status,
        source_kind=observation.source_kind,
        source_id=observation.source_id,
        observed_at=observation.observed_at.isoformat() if observation.observed_at else None,
    )


async def run_run_watcher(
    *,
    observer: CaptureObserver,
    capture_codes: frozenset[str],
    reconnect_delay_seconds: float = _RECONNECT_DELAY_SECONDS,
) -> None:
    """Drain the observer, logging each observation; re-subscribe on stream end."""
    if not capture_codes:
        return
    scope = CaptureObserverScope(capture_codes=capture_codes)
    while True:
        try:
            async for observation in observer.observe(scope):
                try:
                    observe_capture(observation)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    _log.exception(
                        "run_watcher.record_failed",
                        capture_code=observation.capture_code,
                    )
        except asyncio.CancelledError:
            raise
        except Exception:
            _log.exception("run_watcher.iteration_failed")
        await asyncio.sleep(reconnect_delay_seconds)


@contextlib.asynccontextmanager
async def run_watcher_lifespan(
    *,
    observer: CaptureObserver,
    capture_codes: frozenset[str],
) -> AsyncGenerator[None]:
    """Run the shadow watcher as a background task for the app's lifetime.

    No-op when `capture_codes` is empty: yields immediately without
    starting a task, mirroring `enclosure_permit_monitor_lifespan`'s
    no-op-when-unconfigured shape.
    """
    if not capture_codes:
        yield
        return
    task = asyncio.create_task(
        run_run_watcher(observer=observer, capture_codes=capture_codes),
        name="run-watcher",
    )
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


__all__ = ["observe_capture", "run_run_watcher", "run_watcher_lifespan"]
