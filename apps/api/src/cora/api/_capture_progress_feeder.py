"""CaptureProgressFeeder: buffer and flush RunWitness's progress readings.

Slice 10. `sim_observation_feeder.py`'s docstring states the shape this
follows: "each DEPLOYMENT writes its real EPICS ... feeder against the
SAME write path (the AppendObservations command + the
FeedHeartbeatStore). There is no new ingest port: a feeder is a runtime
over the existing write contract." This is CORA's first real feeder.

## Buffering is the decimation

`offer()` is synchronous and non-blocking: it just overwrites the
latest reading per (capture_code, role) in an in-memory dict. Fidelity
above one row per channel per flush tick is a deliberate, structural
choice, not a missing feature: for a monotonic counter (images saved,
images collected), the last value in a window is a complete summary of
that window, so what a flush drops is time-resolution, never what was
reached. Memory is bounded by (codes x roles) from the deployment's own
config, never by substrate rate, so a frame-rate firehose costs one
dict assignment per reading and nothing else.

## Flush ordering matters, and lives in the caller

`flush_capture(code)` must run BEFORE the RunWitness recorder acts on a
BEGUN / ENDED / ABORTED observation for that same code, or a capture's
tail of progress readings loses its Run before it can be attributed
(the observation logbook closes on completion, and a truncated Run's
new BEGUN opens a DIFFERENT run_id). This module has no opinion on when
that is; `run_witness_loop` (`_run_witness.py`) is the coordinator that
calls `flush_capture` at the right moments and owns the ordering.

## No conduct_mode gate on the write path

`AppendObservations` accepts any Running or Held Run, driven ones
included; there is no `conduct_mode` check the way
`RecordWitnessedRunOutcome`'s decider has one. This feeder's safety
rests entirely on `open_run_id` (supplied by the caller, in practice
`RunWitnessRecorder.open_run_id`) only ever naming a Run the RunWitness
runtime itself promoted. See `cora.agent.seed_capture_progress_feeder`
for the full security note; this is the same structural residual
already accepted for `TruncateRun` in `seed_run_witness.py`.

## Every failure is caught, never raised into the loop

A dead observation logbook (`RunObservationLogbookClosedError`, the Run
terminated between buffer and flush) and a revoked grant
(`UnauthorizedError`) are both routine, logged conditions, not bugs.
The progress append and the heartbeat append get INDEPENDENT
try/except blocks: a failed observation write must not suppress the
heartbeat, and vice versa, because the heartbeat is coverage evidence
in its own right regardless of whether any reading was due.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from cora.infrastructure.logging import get_logger
from cora.run.aggregates.run import FeedHeartbeat, RunObservationLogbookClosedError
from cora.run.errors import UnauthorizedError
from cora.run.features.append_observations import AppendObservations, ObservationInput

if TYPE_CHECKING:
    from collections.abc import Callable
    from uuid import UUID

    from cora.infrastructure.kernel import Kernel
    from cora.run.aggregates.run import FeedHeartbeatStore
    from cora.run.features.append_observations.handler import Handler as AppendObservationsHandler
    from cora.run.ports.capture_observer import CaptureProgressObservation

_SAMPLING_PROCEDURE = "monitor"
_DEFAULT_SOURCE_ID = "capture-progress"

_log = get_logger(__name__)


class CaptureProgressFeeder:
    """Buffers `CaptureProgressObservation` readings and flushes them as
    `AppendObservations` batches plus one `FeedHeartbeat` per open Run.

    `open_run_id` resolves a capture_code to the Run currently open for
    it, or `None` if none is open; in production this is
    `RunWitnessRecorder.open_run_id`, so the feeder's write scope is
    exactly the witness's own promotions, never a run_id from anywhere
    else.
    """

    def __init__(
        self,
        *,
        deps: Kernel,
        append_observations: AppendObservationsHandler,
        feed_heartbeat_store: FeedHeartbeatStore,
        open_run_id: Callable[[str], UUID | None],
        principal_id: UUID,
        source_id: str = _DEFAULT_SOURCE_ID,
    ) -> None:
        self._deps = deps
        self._append_observations = append_observations
        self._heartbeat_store = feed_heartbeat_store
        self._open_run_id = open_run_id
        self._principal_id = principal_id
        self._source_id = source_id
        self._buffer: dict[str, dict[str, CaptureProgressObservation]] = {}

    def offer(self, observation: CaptureProgressObservation) -> None:
        """Buffer a reading, overwriting any prior reading for the same
        (capture_code, role). Synchronous and non-blocking."""
        self._buffer.setdefault(observation.capture_code, {})[observation.role] = observation

    async def flush(self) -> None:
        """Flush every capture_code with a non-empty buffer."""
        for capture_code in list(self._buffer):
            await self.flush_capture(capture_code)

    async def flush_capture(self, capture_code: str) -> None:
        """Flush one capture_code's buffered readings, then its heartbeat.

        A cheap no-op when nothing is buffered. Pops the buffer
        unconditionally before resolving `run_id`: a capture with no
        open Run has nothing to attribute its readings to, and the
        buffer must not accumulate forever behind a closed capture.
        """
        buffered = self._buffer.pop(capture_code, None)
        if not buffered:
            return

        run_id = self._open_run_id(capture_code)
        if run_id is None:
            _log.info(
                "capture_progress.dropped_no_open_run",
                capture_code=capture_code,
                role_count=len(buffered),
            )
            return

        await self._flush_observations(capture_code, run_id, buffered)
        await self._flush_heartbeat(capture_code, run_id)

    async def _flush_observations(
        self,
        capture_code: str,
        run_id: UUID,
        buffered: dict[str, CaptureProgressObservation],
    ) -> None:
        entries: list[ObservationInput] = []
        for role in sorted(buffered):
            observation = buffered[role]
            if observation.observed_at is None:
                # The port's dual-clock rule forbids substituting CORA's
                # own clock for an absent substrate time; skip rather
                # than synthesize (see ObservationInput.sampled_at).
                _log.info(
                    "capture_progress.no_substrate_time",
                    capture_code=capture_code,
                    role=role,
                )
                continue
            entries.append(
                ObservationInput(
                    event_id=self._deps.id_generator.new_id(),
                    channel_name=role,
                    value=observation.value,
                    sampled_at=observation.observed_at,
                    sampling_procedure=_SAMPLING_PROCEDURE,
                    units=None,
                    is_simulated=False,
                )
            )
        if not entries:
            return

        try:
            await self._append_observations(
                AppendObservations(run_id=run_id, entries=tuple(entries)),
                principal_id=self._principal_id,
                correlation_id=self._deps.id_generator.new_id(),
            )
        except asyncio.CancelledError:
            raise
        except UnauthorizedError:
            _log.warning(
                "capture_progress.append_unauthorized",
                capture_code=capture_code,
                run_id=str(run_id),
            )
        except RunObservationLogbookClosedError:
            _log.info(
                "capture_progress.logbook_closed",
                capture_code=capture_code,
                run_id=str(run_id),
            )
        except Exception:
            _log.exception(
                "capture_progress.append_failed",
                capture_code=capture_code,
                run_id=str(run_id),
            )
        else:
            _log.info(
                "capture_progress.appended",
                capture_code=capture_code,
                run_id=str(run_id),
                entry_count=len(entries),
            )

    async def _flush_heartbeat(self, capture_code: str, run_id: UUID) -> None:
        try:
            await self._heartbeat_store.append(
                [
                    FeedHeartbeat(
                        event_id=self._deps.id_generator.new_id(),
                        run_id=run_id,
                        source_id=self._source_id,
                        heartbeat_at=self._deps.clock.now(),
                    )
                ]
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            _log.exception(
                "capture_progress.heartbeat_failed",
                capture_code=capture_code,
                run_id=str(run_id),
            )


async def capture_progress_flush_loop(
    feeder: CaptureProgressFeeder,
    *,
    interval_seconds: float,
) -> None:
    """Flush every open capture's buffered progress readings on a fixed
    cadence, independent of the drain loop's own pace. A single bad
    flush is logged and the loop continues; cancellation propagates."""
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            await feeder.flush()
        except asyncio.CancelledError:
            raise
        except Exception:
            _log.exception("capture_progress.flush_loop_failed")


__all__ = ["CaptureProgressFeeder", "capture_progress_flush_loop"]
