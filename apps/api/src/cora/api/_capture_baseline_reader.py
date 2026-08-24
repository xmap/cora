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

## Numeric and categorical readings, one entry kind

A `capture_baseline_pvs` channel is read once and dispatched by
`Measurement.kind`, not by a per-channel decoder: `"Categorical"`
(EPICS `mbbo`/`bo` scan-configuration PVs, e.g. `ScanType`,
`FlatFieldMode`) becomes a `categorical_value` entry carrying the
substrate's own enum LABEL unchanged (`'Fly'`, `'Both'`, never a
CORA-invented code); every other kind is coerced to a numeric `value`
via `finite_float`, as before. `Observation.value` /
`Observation.categorical_value` are mutually exclusive
(`cora.run.aggregates.run.entries.Observation`), so exactly one is
ever set per reading.

## Reasons a reading is skipped rather than appended

1. **Not believable** (fails `cora.shared.quality.believable`, which is
   `Bad` alone: the adapter's collapse of EPICS INVALID / Tango
   ALARM|INVALID / OPC UA's Bad grouping): an untrustworthy value must
   not enter the record. A `Quality.Uncertain` reading (EPICS
   MINOR/MAJOR) is NOT skipped, and that is the loose floor of the two
   named there, chosen because this reader RECORDS what a substrate
   said rather than acting on it: a MAJOR alarm is still a believable
   value.
2. **No substrate time** (`Measurement.produced_at is None`): the
   port's dual-clock rule forbids substituting CORA's own clock for an
   absent substrate time, the same rule `CaptureProgressFeeder` already
   honors for `sampled_at`.
3. **Non-numeric, non-categorical** (`finite_float` cannot coerce
   `Measurement.value`, and `reading.kind != "Categorical"`): a
   deployment could declare a `capture_baseline_pvs` entry that turns
   out to carry text CORA cannot classify either way; reject rather
   than coerce, and log it, mirroring `finite_float`'s
   fail-toward-silence posture everywhere else in this module's
   sibling.
4. **Unusable categorical label** (`reading.kind == "Categorical"` but
   the value is not a non-empty `str`, or exceeds
   `READING_CATEGORICAL_VALUE_MAX_LENGTH`): the label itself, not a
   coercion of it, is what gets stored, so a substrate that returns
   something other than a short string here is a defect to log, not
   guess at.
5. **Oversized units** (`len(Measurement.units) > READING_UNITS_MAX_LENGTH`):
   `PostgresObservationStore.append` writes an entire batch in one
   `executemany` call, so a single row that fails the DB's `units`
   CHECK constraint would fail every OTHER reading in this promotion's
   batch too, not just the offending channel. Checked here, ahead of
   the batch, so one long substrate string cannot erase every valid
   reading for the same promotion. Applies to numeric and categorical
   readings alike.

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
from cora.run.aggregates.run import (
    READING_CATEGORICAL_VALUE_MAX_LENGTH,
    READING_UNITS_MAX_LENGTH,
    RunObservationLogbookClosedError,
)
from cora.run.errors import UnauthorizedError
from cora.run.features.append_observations import AppendObservations, ObservationInput
from cora.shared.quality import believable

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
        """Read every channel declared for `capture_code` CONCURRENTLY,
        once, and append whatever survives the per-reading checks as one
        `AppendObservations` batch against `run_id`.

        Concurrent, not sequential: this runs inline inside
        `RunWitnessRecorder._promote`, itself on `run_witness_loop`'s
        single consumer path, so a slow or partially-unreachable
        control system must not block that loop from reacting to the
        NEXT lifecycle observation (for a different capture_code, or a
        terminal for this one) for the sum of every configured PV's own
        timeout. `_read_one` never raises (see below), so a plain
        `asyncio.gather` is safe with no `return_exceptions` needed.

        Never raises: every failure mode (a dead PV, an unusable
        reading, or the append itself) is caught and logged here, per
        the module docstring's failure-posture section.
        """
        channels = self._baseline_pvs.get(capture_code)
        if not channels:
            return

        readings = await asyncio.gather(
            *(
                self._read_one(capture_code, channel_name, pv)
                for channel_name, pv in sorted(channels.items())
            )
        )
        entries = [entry for entry in readings if entry is not None]

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
        if not believable(reading.quality):
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
        value: float | None
        categorical_value: str | None
        if reading.kind == "Categorical":
            value = None
            categorical_value = self._categorical_label(capture_code, channel_name, pv, reading)
            if categorical_value is None:
                return None
        else:
            categorical_value = None
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
        units = reading.units
        if units is not None and len(units) > READING_UNITS_MAX_LENGTH:
            # `AppendObservations` writes its whole batch in one
            # `executemany` call (`PostgresObservationStore.append`), so
            # ONE row failing the DB's `units` CHECK constraint would
            # fail every other reading in this promotion's batch too,
            # not just this channel's -- exactly the per-PV-independence
            # guarantee this module otherwise holds. Reject here, before
            # the batch is built, rather than let a single oversized
            # substrate string erase every valid reading for a live
            # ExposureTime, RotationStart, etc.
            _log.warning(
                "capture_baseline.units_too_long",
                capture_code=capture_code,
                channel_name=channel_name,
                pv=pv,
                units_length=len(units),
                max_length=READING_UNITS_MAX_LENGTH,
            )
            return None
        return ObservationInput(
            event_id=self._deps.id_generator.new_id(),
            channel_name=channel_name,
            value=value,
            categorical_value=categorical_value,
            sampled_at=reading.produced_at,
            sampling_procedure=_SAMPLING_PROCEDURE,
            units=reading.units,
            is_simulated=False,
        )

    def _categorical_label(
        self, capture_code: str, channel_name: str, pv: str, reading: Measurement
    ) -> str | None:
        """The enum LABEL for a `Categorical` reading, or `None` if it
        cannot be stored as one. The facility's own substrate label is
        stored unchanged; an unrecognized label is data, not an error,
        so there is no allowlist here to reject against."""
        label = reading.value
        if not isinstance(label, str) or not label:
            _log.warning(
                "capture_baseline.non_text_categorical_reading",
                capture_code=capture_code,
                channel_name=channel_name,
                pv=pv,
                value=repr(label),
            )
            return None
        if len(label) > READING_CATEGORICAL_VALUE_MAX_LENGTH:
            _log.warning(
                "capture_baseline.categorical_label_too_long",
                capture_code=capture_code,
                channel_name=channel_name,
                pv=pv,
                label_length=len(label),
                max_length=READING_CATEGORICAL_VALUE_MAX_LENGTH,
            )
            return None
        return label


__all__ = ["CaptureBaselineReader"]
