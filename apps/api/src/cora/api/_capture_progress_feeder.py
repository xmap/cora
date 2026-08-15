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
rests entirely on `open_captures` (supplied by the caller, in practice
`RunWitnessRecorder.open_captures`) only ever naming a Run the RunWitness
runtime itself promoted. See `cora.agent.seed_capture_progress_feeder`
for the full security note; this is the same structural residual
already accepted for `TruncateRun` in `seed_run_witness.py`.

## The heartbeat fires whenever a Run is open, buffer or no buffer

`FeedHeartbeat`'s own docstring: "A feeder runtime inserts one
heartbeat per drain tick (regardless of whether any observation
flowed) so the stall rule can tell a genuinely quiet channel from a
dead feeder." `flush()` therefore enumerates every capture_code the
`open_captures` callback currently reports open, NOT just the codes
with something buffered: a PV that has gone quiet mid-capture (no CA
callbacks at all) must still get a heartbeat, or the heartbeat becomes
a proxy for the very signal the stall rule exists to detect the
absence of. Only `UnauthorizedError` suppresses the heartbeat (see
`_flush_observations`); every other outcome, including "nothing was
buffered this tick," still heartbeats.

## A lock, not just an atomic pop, guards each flush

Two independent callers can invoke `flush_capture` for the SAME code:
`run_witness_loop`'s flush-before-recorder-acts call, and this
module's own periodic `capture_progress_flush_loop`. The buffer pop
alone prevents a double-write of the SAME buffered readings, but not a
window where one caller's in-flight `AppendObservations` /
`FeedHeartbeat` write is still awaiting while the other's flush for the
same code sees an empty buffer and returns as a no-op, silently
dropping readings that arrived between the two. `_flush_lock` (one
lock, not per-code: flushes are infrequent and cheap, and per-code
locking would not remove any real contention this design has) makes
every `flush_capture` call fully sequential, closing that window.

## Every failure is caught, never raised into the loop

A dead observation logbook (`RunObservationLogbookClosedError`, the Run
terminated between buffer and flush) and a revoked grant
(`UnauthorizedError`) are both routine, logged conditions, not bugs.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from cora.infrastructure.logging import get_logger
from cora.run.aggregates.run import FeedHeartbeat, RunObservationLogbookClosedError
from cora.run.errors import UnauthorizedError
from cora.run.features.append_observations import AppendObservations, ObservationInput

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
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

    `open_captures` returns a snapshot of every capture_code currently
    open, mapped to its run_id; in production this is
    `RunWitnessRecorder.open_captures`, so the feeder's write scope is
    exactly the witness's own promotions (this process's, or a prior
    one's via the boot-time restart rebuild), never a run_id from
    anywhere else.
    """

    def __init__(
        self,
        *,
        deps: Kernel,
        append_observations: AppendObservationsHandler,
        feed_heartbeat_store: FeedHeartbeatStore,
        open_captures: Callable[[], Mapping[str, UUID]],
        principal_id: UUID,
        source_id: str = _DEFAULT_SOURCE_ID,
    ) -> None:
        self._deps = deps
        self._append_observations = append_observations
        self._heartbeat_store = feed_heartbeat_store
        self._open_captures = open_captures
        self._principal_id = principal_id
        self._source_id = source_id
        self._buffer: dict[str, dict[str, CaptureProgressObservation]] = {}
        self._flush_lock = asyncio.Lock()

    def offer(self, observation: CaptureProgressObservation) -> None:
        """Buffer a reading, overwriting any prior reading for the same
        (capture_code, role). Synchronous and non-blocking."""
        self._buffer.setdefault(observation.capture_code, {})[observation.role] = observation

    async def flush(self) -> None:
        """Flush every currently-open capture, per `open_captures`, not
        just the codes with something buffered (see module docstring:
        the heartbeat must still fire for a quiet-but-open capture)."""
        for capture_code in list(self._open_captures()):
            await self.flush_capture(capture_code)

    async def flush_capture(self, capture_code: str) -> None:
        """Flush one capture_code's buffered readings (if any), then its
        heartbeat (if a Run is open for it and the write was authorized).

        Pops the buffer unconditionally: a capture with no open Run has
        nothing to attribute its readings to, and the buffer must not
        accumulate forever behind a closed capture. Serialized by
        `_flush_lock`; see the module docstring.
        """
        async with self._flush_lock:
            buffered = self._buffer.pop(capture_code, None)
            run_id = self._open_captures().get(capture_code)
            if run_id is None:
                if buffered:
                    _log.info(
                        "capture_progress.dropped_no_open_run",
                        capture_code=capture_code,
                        role_count=len(buffered),
                    )
                return

            authorized = True
            if buffered:
                authorized = await self._flush_observations(capture_code, run_id, buffered)
            if authorized:
                await self._flush_heartbeat(capture_code, run_id)

    async def _flush_observations(
        self,
        capture_code: str,
        run_id: UUID,
        buffered: dict[str, CaptureProgressObservation],
    ) -> bool:
        """Write the batch; returns whether the heartbeat may still fire.

        Only `UnauthorizedError` returns `False`: a revoked grant means
        this principal cannot write to the record at all, and a
        heartbeat is itself a coverage claim (`FeedHeartbeat`'s own
        docstring: "feeder-liveness ping"). Firing it anyway would
        assert coverage over exactly the window nothing was recorded,
        the worst of the two failure states, and the heartbeat store
        has no authz check of its own to catch that independently.
        Every other outcome -- success, an empty entry list, a closed
        logbook, an unexpected exception -- returns `True`: those are
        conditions where this principal COULD write, so the coverage
        claim stays honest even when nothing landed this tick.
        """
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
            return True

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
            return False
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
        return True

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
