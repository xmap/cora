"""CaptureBaselineReader: read a witnessed Run's genesis-baseline PVs once.

Slice 12. Closes the conditions-snapshot gap without touching any event
payload: `RecordWitnessedRun`'s `effective_parameters` stays the Plan's
DECLARED defaults (declared intent), and the rows this module appends
are the OBSERVED truth at the instant the capture promoted, discriminated
from `CaptureProgressFeeder`'s `sampling_procedure="monitor"` rows by the
same field, set here to `"baseline"`.

## One read, not a feed

Unlike `CaptureProgressFeeder` (buffer + periodic flush over the whole
capture's lifetime), this is a single read-every-PV-once-and-append call,
invoked exactly once per promotion by `RunWitnessRecorder._promote`
immediately after `record_witnessed_run` returns a `run_id`. There is no
buffer, no tick, and no ongoing liveness claim: a baseline reading is a
snapshot of genesis, not a trail, so there is nothing for a heartbeat to
attest to between readings the way `FeedHeartbeat` attests to
`CaptureProgressFeeder`'s trail.

## Per-PV failure posture mirrors `_capture_progress_feeder.py` exactly

Every exception is caught and logged, never raised into the caller: a
`ControlPort.read()` failure on one PV (dead channel, timeout, access
denial, or a substrate value the adapter cannot even unpack) drops only
that PV's reading and lets the sweep continue over the rest, mirroring
`capture_watch_preflight.py`'s own per-PV independence. The subsequent
`AppendObservations` call's own failures (`UnauthorizedError`,
`RunObservationLogbookClosedError`, anything else) are caught the same
way `CaptureProgressFeeder._flush_observations` catches them: a baseline
read that fails must never prevent or unwind the promotion that
triggered it, because by the time this runs the promotion has already
succeeded and `RunWitnessRecorder._open_captures` already reflects it.

## Three reasons a reading is skipped rather than appended

1. **Bad quality** (`Measurement.quality == "Bad"`, the adapter's
   collapse of EPICS INVALID / Tango ALARM|INVALID / OPC UA's Bad
   grouping): an untrustworthy value must not enter the record. A
   `Quality.Uncertain` reading (EPICS MINOR/MAJOR) is NOT skipped: the
   alarm-vs-fault distinction already shipped elsewhere in this codebase
   says a MAJOR alarm is still a believable value.
2. **No substrate time** (`Measurement.produced_at is None`): the
   port's dual-clock rule forbids substituting CORA's own clock for an
   absent substrate time, the same rule `CaptureProgressFeeder` already
   honors for `sampled_at`.
3. **Non-numeric** (`finite_float` cannot coerce `Measurement.value`):
   `Observation.value` is `float`
   (`cora.run.aggregates.run.entries.Observation`). A deployment could
   declare a `capture_baseline_pvs` entry that turns out to carry text;
   reject rather than coerce, and log it, mirroring
   `finite_float`'s fail-toward-silence posture everywhere else in this
   module's sibling.

Reuses `finite_float` from `cora.api._capture_observer` rather than a
second copy, so the two modules can never drift on what counts as a
usable numeric reading.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from cora.api._capture_observer import finite_float
from cora.infrastructure.logging import get_logger
from cora.operation.ports.control_port import (
    ControlAccessDeniedError,
    ControlNotConnectedError,
    ControlTimeoutError,
    ControlValueCoercionError,
)
from cora.run.aggregates.run import RunObservationLogbookClosedError
from cora.run.errors import UnauthorizedError
from cora.run.features.append_observations import AppendObservations, ObservationInput

if TYPE_CHECKING:
    from collections.abc import Mapping
    from uuid import UUID

    from cora.infrastructure.kernel import Kernel
    from cora.operation.ports.control_port import ControlPort, Measurement
    from cora.run.features.append_observations.handler import Handler as AppendObservationsHandler

_SAMPLING_PROCEDURE = "baseline"

_log = get_logger(__name__)


class CaptureBaselineReader:
    """Reads `baseline_pvs[capture_code]` once and appends them as
    `sampling_procedure="baseline"` observations against `run_id`.

    `baseline_pvs` is code -> channel_name -> PV, matching
    `Settings.capture_baseline_pvs`. A code with no entry (or an empty
    one) makes `read` a no-op, mirroring `ControlPortCaptureObserver`'s
    own per-code optionality.
    """

    def __init__(
        self,
        *,
        deps: Kernel,
        control_port: ControlPort,
        baseline_pvs: Mapping[str, Mapping[str, str]],
        append_observations: AppendObservationsHandler,
        principal_id: UUID,
    ) -> None:
        self._deps = deps
        self._control_port = control_port
        self._baseline_pvs = baseline_pvs
        self._append_observations = append_observations
        self._principal_id = principal_id

    async def read(self, capture_code: str, run_id: UUID) -> None:
        """Read every channel declared for `capture_code`, once, and
        append whatever survives the per-reading checks as one
        `AppendObservations` batch against `run_id`.

        Never raises: every failure mode (a dead PV, an unusable
        reading, or the append itself) is caught and logged here, per
        the module docstring's failure-posture section.
        """
        channels = self._baseline_pvs.get(capture_code)
        if not channels:
            return

        entries: list[ObservationInput] = []
        for channel_name, pv in sorted(channels.items()):
            entry = await self._read_one(capture_code, channel_name, pv)
            if entry is not None:
                entries.append(entry)

        if not entries:
            _log.info(
                "capture_baseline.nothing_to_append",
                capture_code=capture_code,
                run_id=str(run_id),
            )
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
                "capture_baseline.append_unauthorized",
                capture_code=capture_code,
                run_id=str(run_id),
            )
        except RunObservationLogbookClosedError:
            _log.info(
                "capture_baseline.logbook_closed",
                capture_code=capture_code,
                run_id=str(run_id),
            )
        except Exception:
            _log.exception(
                "capture_baseline.append_failed",
                capture_code=capture_code,
                run_id=str(run_id),
            )
        else:
            _log.info(
                "capture_baseline.appended",
                capture_code=capture_code,
                run_id=str(run_id),
                entry_count=len(entries),
            )

    async def _read_one(
        self, capture_code: str, channel_name: str, pv: str
    ) -> ObservationInput | None:
        try:
            reading = await self._control_port.read(pv)
        except asyncio.CancelledError:
            raise
        except (ControlNotConnectedError, ControlTimeoutError, ControlAccessDeniedError) as exc:
            _log.warning(
                "capture_baseline.read_unreachable",
                capture_code=capture_code,
                channel_name=channel_name,
                pv=pv,
                detail=str(exc),
            )
            return None
        except ControlValueCoercionError as exc:
            _log.warning(
                "capture_baseline.read_uncoercible",
                capture_code=capture_code,
                channel_name=channel_name,
                pv=pv,
                detail=str(exc),
            )
            return None
        except Exception:
            _log.exception(
                "capture_baseline.read_failed",
                capture_code=capture_code,
                channel_name=channel_name,
                pv=pv,
            )
            return None
        return self._to_entry(capture_code, channel_name, pv, reading)

    def _to_entry(
        self, capture_code: str, channel_name: str, pv: str, reading: Measurement
    ) -> ObservationInput | None:
        if reading.quality == "Bad":
            _log.info(
                "capture_baseline.bad_quality",
                capture_code=capture_code,
                channel_name=channel_name,
                pv=pv,
                quality_detail=reading.quality_detail,
            )
            return None
        if reading.produced_at is None:
            # The port's dual-clock rule forbids substituting CORA's own
            # clock for an absent substrate time; skip rather than
            # synthesize (see ObservationInput.sampled_at).
            _log.info(
                "capture_baseline.no_substrate_time",
                capture_code=capture_code,
                channel_name=channel_name,
                pv=pv,
            )
            return None
        value = finite_float(reading.value)
        if value is None:
            _log.warning(
                "capture_baseline.non_numeric_reading",
                capture_code=capture_code,
                channel_name=channel_name,
                pv=pv,
                value=repr(reading.value),
            )
            return None
        return ObservationInput(
            event_id=self._deps.id_generator.new_id(),
            channel_name=channel_name,
            value=value,
            sampled_at=reading.produced_at,
            sampling_procedure=_SAMPLING_PROCEDURE,
            units=reading.units,
            is_simulated=False,
        )


__all__ = ["CaptureBaselineReader"]
