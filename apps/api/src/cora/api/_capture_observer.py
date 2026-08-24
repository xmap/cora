"""Composition-root bridge: drive the capture observer from ControlPort.

The Run BC's `CaptureObserver` port is BC-local (`cora.run.ports`) and
the `ControlPort` value-IO it needs is Operation-BC-owned
(`cora.operation.ports`). tach forbids `cora.run -> cora.operation`, so
the adapter that bridges the two lives here at the composition root,
mirroring `_enclosure_permit_observer.py` exactly. If a third cross-BC
`ControlPort` consumer appears, the rule-of-three move is to hoist
`ControlPort` to `cora.infrastructure.ports`.

Maps each configured capture code's `status` PV to a
`CaptureLifecycleObservation` by looking its decoded text up in the
deployment's declared `capture_status_phases` table
(`classify_capture_status`); a literal absent from the table
classifies `UNRECOGNIZED` rather than being dropped or coerced into a
nearby phase. The optional `abort` role layers a direct `ABORTED`
claim on top (slice 9); the optional `images_saved` /
`images_collected` progress roles (slice 10) each pump their own
`CaptureProgressObservation` onto the same merged stream, siblings of
the phase pumps. The optional `testing` role (slice 11) pumps its own
`CapturePreconditionBypassObservation`: a tri-state reading of whether
the substrate is bypassing its own beam preconditions for this capture
code, decoded via the same `binary_code` the `abort` role already
uses (2-BM's `Testing` PV is the identical `DBR_ENUM` record type as
`AbortScan`). The optional `full_file_name` role (slice 13) pumps its
own `CapturePathObservation`: a text reading of the areaDetector file
plugin's own filename readback (`2bmSP2:HDF1:FullFileName_RBV`, NOT
tomoscan's own `FullFileName`, which is written too late relative to
CORA's terminal -- see `_run_witness.py`'s "Capture path pairing"
section for the full argument). `observed_path` is PERSONAL DATA; this
module never logs it, only its length when rejecting a suspect
reading. The optional `orchestrator_ref` role pumps its own
`CaptureOrchestratorRefObservation`: a text reading of an external
orchestrator's own run identifier for this capture code (e.g. a
Bluesky RunEngine start-document uid), so `RunWitnessRecorder` can
attach it to the promoted Run as a second `external_refs` entry,
alongside `capture-code` -- see `_run_witness.py`'s
"Orchestrator-ref pairing" section.

## One deliberate inversion from the Enclosure precedent

`ControlPortEnclosureObserver` synthesizes an `Unknown` STATUS CLAIM on
disconnect, because a dead permit signal must fail the run-start gate
closed rather than leave a stale `Permitted` standing. There is no such
gate here, and reading a disconnect as a real observation would
fabricate one: it would either assert a phase no substrate reading
backs, or, if mapped to `UNRECOGNIZED`, misrepresent a communication
failure as a vocabulary problem. So `_unreached` here carries NO status
claim at all (`reported_status=None`, `phase=None`), the same shape a
probe-only poll tick already uses, exactly mirroring
`CaptureLifecycleObservation`'s own port-level contract for the
probe-only case. A progress pump has no `_unreached` counterpart at
all: `CaptureProgressObservation.value` is a required float with no
"no claim" shape, so its disconnect / clean-end simply stops the pump
rather than fabricating a reading (see `_pump_progress`).

## The bug that would have shipped without checking the real PV, again

Slice 9 caught 2-BM's `AbortScan` resolving to the ENUM label `'No'`,
not `0`. Slice 10 caught the same class of trap on `ImagesSaved` /
`ImagesCollected`: they are `stringout` records at 2-BM, and TomoScan
writes `"<done>/<total>"` onto them (`update_status()` in the upstream
`decarlof/tomoscan` source), never a bare number. `finite_float`'s
first cut assumed a plain float; every real reading would have failed
to parse and the feature would have shipped recording nothing on the
real beamline, with no error anywhere; a deployment can watch a whole
scan complete and never notice the record stayed empty. Caught by
checking the upstream source's own write path rather than trusting the
`Settings.capture_watch_pvs` docstring's example. `progress_counts`
now accepts both shapes and carries both halves onto
`CaptureProgressObservation`, per `commanded_total`'s own docstring for
why it is carried and what it is NOT: a completeness test.

## The denominator is carried, and is not a completeness signal

Slice 10 originally discarded the `"<total>"` half of a `"<reached>/
<total>"` reading, reasoning that a consumer needing the commanded
count should read the Plan's own parameters instead. That reasoning
does not hold on the witnessed path: a witnessed Run's Plan is a
configured stand-in (`Settings.capture_watch_plan_id`), not the
parameters TomoScan was actually given, so "read the Plan" means
guessing at someone else's scan length. The commanded total is now
carried through as `commanded_total`, because a witnessed terminal
(`record_witnessed_run_outcome`) needs the substrate's own target as
evidence when tomoscan reports a clean completion after an abort,
camera timeout, or file-overwrite refusal that never reaches
`ScanStatus` (see tomography/tomoscan#181).

Carrying it does NOT make `value == commanded_total` a valid test.
`wait_camera_done()`'s poll loop (upstream `tomoscan.py`) returns on
`CamAcquireBusy == 0` BEFORE its final `update_status()` call, so a
perfectly healthy scan routinely ends with `value` short of
`commanded_total` by roughly one poll interval's worth of frames. See
`CaptureProgressSnapshot` (`cora.run.aggregates.run.state`) for how the
witnessed terminal records this without asserting a verdict.

## Permit probe trail's sibling-poller shape, reused unchanged

Same reasoning as the Enclosure adapter: `_poll` is a SIBLING of
`_pump`, not nested inside it, because `_pump` returns as soon as its
subscription ends and `_drain` only re-subscribes after every pump has
returned; a poller living inside `_pump` would die with it and could
never observe the PV's recovery.
"""

from __future__ import annotations

import asyncio
import math
from typing import TYPE_CHECKING

from cora.infrastructure.logging import get_logger
from cora.operation.ports.control_port import ControlNotConnectedError
from cora.run.ports.capture_observer import (
    AnyCaptureObservation,
    CaptureLifecycleObservation,
    CaptureObserverScope,
    CaptureOrchestratorRefObservation,
    CapturePathObservation,
    CapturePhase,
    CapturePreconditionBypassObservation,
    CaptureProgressObservation,
)
from cora.shared.binary_signal import binary_code
from cora.shared.identifier import IDENTIFIER_VALUE_MAX_LENGTH
from cora.shared.reach import ReachTier

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Mapping

    from cora.operation.ports.control_port import ControlPort, Measurement

_log = get_logger(__name__)

_SOURCE_KIND = "EpicsPv"
ROLE_STATUS = "status"
ROLE_ABORT = "abort"
ROLE_IMAGES_SAVED = "images_saved"
ROLE_IMAGES_COLLECTED = "images_collected"
ROLE_TESTING = "testing"
ROLE_FULL_FILE_NAME = "full_file_name"
ROLE_ORCHESTRATOR_REF = "orchestrator_ref"
"""CORA-owned role keys, matching `Settings.capture_watch_pvs`'s documented
example. Module-public (not `_`-prefixed) because other composition-root
modules read observations back out, or dispatch decoders, by these same
keys and must not carry their own copy of the literal strings:
`RunWitnessRecorder._build_progress_snapshot` (`_run_witness.py`) reads
`ROLE_IMAGES_SAVED` / `ROLE_IMAGES_COLLECTED`, and `capture_watch_preflight`
dispatches its per-role decode check on all seven. Import these, not
`_PROGRESS_ROLES` below, so a rename or a new role here cannot silently
desync from either reader. `server_running` stays declared-and-unread:
tool liveness is a different concern from capture progress (slice 10).

`ROLE_FULL_FILE_NAME` (slice 13) names the raw substrate PV
(`FullFileName_RBV`) rather than the semantic concept it feeds
(`CapturePathObservation`, a `run_capture_path` vault row): matches the
existing style, where a role key mirrors the wire (`abort`, `testing`,
`images_saved`) and the domain type it produces is named for the fact,
not the PV.

`ROLE_ORCHESTRATOR_REF` names the domain fact directly, not a PV: unlike
`full_file_name` / `images_saved`, which are literal 2-BM PV suffixes,
no single wire name for "an external orchestrator's run uid" exists
across deployments, so the role key is CORA's own vocabulary from the
start (mirrors `testing`, whose PV-facing name coincides with the
domain word only by 2-BM's own coincidence, not by a rule this codebase
follows).
"""
_PROGRESS_ROLES = (ROLE_IMAGES_SAVED, ROLE_IMAGES_COLLECTED)

FULL_FILE_NAME_TRUNCATION_THRESHOLD = 511
"""The areaDetector file plugin's `FullFileName_RBV` is a DBR_CHAR
waveform with `NELM=512` (confirmed against ADCore's `NDFile.template`,
2026-08-16 -- NOT the 256 tomoscan's own `FullFileName` uses; the two
PVs share no wire-shape assumption). Up to 511 usable characters remain
after the NUL terminator. EPICS gives no separate "this got truncated"
flag: a decoded string that fills the whole buffer is indistinguishable
from one that was cut off mid-path. Rather than risk a truncated path
silently looking like a good one, ANY decoded value at or over this
length is treated as suspect and rejected (see
`_from_full_file_name_reading`). Conservative: a genuine 511-character
path would false-reject, but real 2-BM paths are far under this bound.

Module-public (not `_`-prefixed): `capture_watch_preflight` imports this
directly so its own truncation check can never drift from production's.
"""

# `binary_code` (imported above from `cora.shared.binary_signal`) is
# re-exported by this module's `__all__`: it moved there once a fourth
# occurrence (the BLEPS supply observer) made it the rule-of-three hoist
# trigger, but `capture_watch_preflight` imports it from this module by
# name and must not carry a second copy of the logic.


def finite_float(value: object) -> float | None:
    """Coerce a single reading to a finite float, or `None`.

    Fail-toward-silence, mirroring `binary_code`: a value that cannot
    coerce, or resolves to NaN/Infinity, returns `None` rather than
    reaching `append_observations`, which raises
    `InvalidObservationValueError` on NaN/Inf and would fail an entire
    batch over one bad reading.
    """
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def progress_counts(value: object) -> tuple[float, float | None] | None:
    """Split a progress-role reading into `(reached, commanded_total)`.

    Two accepted shapes: a bare number, and 2-BM's REAL format, a
    `"<reached>/<commanded>"` string. `ImagesSaved` / `ImagesCollected`
    are `stringout` records at 2-BM (not numeric ones): TomoScan's
    `update_status()` writes `f"{num_saved}/{num_to_save}"` /
    `f"{num_collected}/{num_images}"` onto them, confirmed against the
    upstream `decarlof/tomoscan` source, `tomoScan.template` (both
    declared `record(stringout, ...)`) and `tomoscan.py`'s
    `update_status`. A bare-number reading returns `commanded_total`
    `None`, for a future substrate or role that IS numeric.

    Only the numerator's coercibility gates the whole reading, matching
    `finite_float`'s fail-toward-silence posture: a garbled, missing,
    or absent denominator (`"2987/"`, `"2987/abc"`, a bare `2987`) still
    returns the reached count with `commanded_total=None`, since the
    reached count is a true progress fact on its own. Returns `None`
    only when the numerator itself does not coerce to a finite float.

    Module-public (not `_`-prefixed): `capture_watch_preflight` calls this
    directly to report whether a progress role's reading decodes.
    """
    numerator: object = value
    denominator: object = None
    if isinstance(value, str) and "/" in value:
        numerator, _, denominator = value.partition("/")
    reached = finite_float(numerator)
    if reached is None:
        return None
    # `denominator is None` on a bare-number reading (no "/") is a
    # normal, expected shape, not a coercion failure to route through
    # `finite_float`'s try/except: skip the call rather than raise and
    # catch a `TypeError` on every single bare-number reading.
    commanded_total = finite_float(denominator) if denominator is not None else None
    return reached, commanded_total


def classify_capture_status(reported_status: str, status_phases: Mapping[str, str]) -> CapturePhase:
    """Classify a decoded status literal against the deployment's declared table.

    A literal absent from `status_phases` classifies as
    `CapturePhase.UNRECOGNIZED`. This also covers the Bad-quality-reading
    case with no special handling needed: an unresolvable or garbled
    string is exceedingly unlikely to match a declared literal, so it
    naturally falls to UNRECOGNIZED, which is the correct signal ("the
    substrate said something CORA cannot classify"), rather than a
    fabricated phase.
    """
    mapped = status_phases.get(reported_status)
    if mapped is None:
        return CapturePhase.UNRECOGNIZED
    return CapturePhase(mapped)


class _PumpDone:
    """Per-PV sentinel pushed onto the merge queue when a pump exits."""

    __slots__ = ()


_PUMP_DONE = _PumpDone()


class ControlPortCaptureObserver:
    """`CaptureObserver` over a `ControlPort` (`status` + optional `abort` +
    optional progress PVs per capture code).

    `capture_pvs` is code -> role -> PV, matching
    `Settings.capture_watch_pvs`. The `status` role is required; a code
    whose PV set has no `status` entry cannot be watched and is
    silently excluded from scope, mirroring the Enclosure adapter's
    `if code in self._permit_pvs` filter. The `abort` role is optional
    per code: when declared, a truthy reading on it is a direct
    `ABORTED` phase claim, letting a real abort be distinguished from a
    successful end even where the `status` PV alone cannot (2-BM's
    `fly_scan` writes the identical `'Scan complete'` literal on both).
    A code with no `abort` entry watches `status` only, exactly as
    before this role existed. The `images_saved` / `images_collected`
    progress roles (also optional, independently declared per code)
    each pump `CaptureProgressObservation` readings. The `testing` role
    (also optional, independently declared per code) pumps
    `CapturePreconditionBypassObservation` readings, a tri-state claim
    rather than a phase or a counter; see that dataclass's own
    docstring. The `full_file_name` role (slice 13, also optional,
    independently declared per code) pumps `CapturePathObservation`
    readings, a text claim carrying personal data; see that dataclass's
    own docstring. The `orchestrator_ref` role (also optional,
    independently declared per code) pumps `CaptureOrchestratorRefObservation`
    readings, a text claim naming no person; the `Identifier` scheme it
    mints under comes from `orchestrator_ref_schemes`, a deployment-
    declared `code -> scheme` table, never a hardcoded string.
    `server_running` stays declared and unread (tool liveness, not
    capture progress).
    """

    def __init__(
        self,
        *,
        control_port: ControlPort,
        capture_pvs: Mapping[str, Mapping[str, str]],
        status_phases: Mapping[str, str],
        orchestrator_ref_schemes: Mapping[str, str] | None = None,
        tick_seconds: float | None = None,
    ) -> None:
        self._control_port = control_port
        self._status_pvs = {
            code: roles[ROLE_STATUS] for code, roles in capture_pvs.items() if ROLE_STATUS in roles
        }
        self._abort_pvs = {
            code: roles[ROLE_ABORT] for code, roles in capture_pvs.items() if ROLE_ABORT in roles
        }
        self._testing_pvs = {
            code: roles[ROLE_TESTING]
            for code, roles in capture_pvs.items()
            if ROLE_TESTING in roles
        }
        self._full_file_name_pvs = {
            code: roles[ROLE_FULL_FILE_NAME]
            for code, roles in capture_pvs.items()
            if ROLE_FULL_FILE_NAME in roles
        }
        self._orchestrator_ref_pvs = {
            code: roles[ROLE_ORCHESTRATOR_REF]
            for code, roles in capture_pvs.items()
            if ROLE_ORCHESTRATOR_REF in roles
        }
        self._progress_pvs = {
            code: filtered
            for code, roles in capture_pvs.items()
            if (filtered := {role: pv for role, pv in roles.items() if role in _PROGRESS_ROLES})
        }
        self._status_phases = dict(status_phases)
        self._orchestrator_ref_schemes = dict(orchestrator_ref_schemes or {})
        self._tick_seconds = tick_seconds

    def observe(self, scope: CaptureObserverScope) -> AsyncGenerator[AnyCaptureObservation]:
        return self._drain(scope)

    async def _drain(self, scope: CaptureObserverScope) -> AsyncGenerator[AnyCaptureObservation]:
        pvs = [
            (code, self._status_pvs[code])
            for code in sorted(scope.capture_codes)
            if code in self._status_pvs
        ]
        if not pvs:
            return
        abort_pvs = [
            (code, self._abort_pvs[code])
            for code in sorted(scope.capture_codes)
            if code in self._abort_pvs
        ]
        testing_pvs = [
            (code, self._testing_pvs[code])
            for code in sorted(scope.capture_codes)
            if code in self._testing_pvs
        ]
        full_file_name_pvs = [
            (code, self._full_file_name_pvs[code])
            for code in sorted(scope.capture_codes)
            if code in self._full_file_name_pvs
        ]
        orchestrator_ref_pvs = [
            (code, self._orchestrator_ref_pvs[code])
            for code in sorted(scope.capture_codes)
            if code in self._orchestrator_ref_pvs
        ]
        progress_pvs = [
            (code, role, pv)
            for code in sorted(scope.capture_codes)
            if code in self._progress_pvs
            for role, pv in sorted(self._progress_pvs[code].items())
        ]
        queue: asyncio.Queue[AnyCaptureObservation | _PumpDone] = asyncio.Queue()
        pump_tasks = (
            [asyncio.create_task(self._pump(code, pv, queue)) for code, pv in pvs]
            + [asyncio.create_task(self._pump_abort(code, pv, queue)) for code, pv in abort_pvs]
            + [asyncio.create_task(self._pump_testing(code, pv, queue)) for code, pv in testing_pvs]
            + [
                asyncio.create_task(self._pump_full_file_name(code, pv, queue))
                for code, pv in full_file_name_pvs
            ]
            + [
                asyncio.create_task(self._pump_orchestrator_ref(code, pv, queue))
                for code, pv in orchestrator_ref_pvs
            ]
            + [
                asyncio.create_task(self._pump_progress(code, role, pv, queue))
                for code, role, pv in progress_pvs
            ]
        )
        poll_tasks = (
            [asyncio.create_task(self._poll(code, pv, queue)) for code, pv in pvs]
            if self._tick_seconds is not None
            else []
        )
        tasks = pump_tasks + poll_tasks
        # Only pumps ever signal completion; a poller runs until the
        # `finally` below cancels it, so it must not hold this open.
        remaining = len(pump_tasks)
        try:
            while remaining > 0:
                item = await queue.get()
                if isinstance(item, _PumpDone):
                    remaining -= 1
                    continue
                yield item
            # Every pump has finished, but a still-running poller can have
            # enqueued a probe in the same instant the final _PumpDone was
            # read. Drain exactly what is ALREADY queued right now,
            # synchronously, into a list before yielding any of it: see
            # `ControlPortEnclosureObserver._drain` for the full reasoning.
            pending = queue.qsize()
            leftover = [queue.get_nowait() for _ in range(pending)]
            for item in leftover:
                if not isinstance(item, _PumpDone):
                    yield item
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _pump(
        self,
        code: str,
        pv: str,
        queue: asyncio.Queue[AnyCaptureObservation | _PumpDone],
    ) -> None:
        try:
            async for reading in self._control_port.subscribe(pv):
                queue.put_nowait(self._from_reading(code, pv, reading))
            # Clean stream end: no status claim, mirroring a disconnect.
            queue.put_nowait(self._unreached(code, pv))
        except ControlNotConnectedError:
            queue.put_nowait(self._unreached(code, pv))
        finally:
            queue.put_nowait(_PUMP_DONE)

    async def _pump_abort(
        self,
        code: str,
        pv: str,
        queue: asyncio.Queue[AnyCaptureObservation | _PumpDone],
    ) -> None:
        """Sibling pump for the optional `abort` role.

        Unlike `_pump`, not every reading is enqueued: a falsy value (the
        busy record's idle/reset state) makes no phase claim at all and
        must not be pushed as a no-op observation, per `_from_abort_reading`.
        """
        try:
            async for reading in self._control_port.subscribe(pv):
                observation = self._from_abort_reading(code, pv, reading)
                if observation is not None:
                    queue.put_nowait(observation)
            queue.put_nowait(self._unreached(code, pv))
        except ControlNotConnectedError:
            queue.put_nowait(self._unreached(code, pv))
        finally:
            queue.put_nowait(_PUMP_DONE)

    async def _pump_progress(
        self,
        code: str,
        role: str,
        pv: str,
        queue: asyncio.Queue[AnyCaptureObservation | _PumpDone],
    ) -> None:
        """Sibling pump for an optional progress role (`images_saved`,
        `images_collected`).

        No `_unreached` counterpart: `CaptureProgressObservation.value`
        is a required float with no "no claim" shape (unlike
        `CaptureLifecycleObservation.phase`, which can legitimately be
        `None`), so a disconnect or clean stream end here simply stops
        the pump rather than fabricating a reading.
        """
        try:
            async for reading in self._control_port.subscribe(pv):
                observation = self._from_progress_reading(code, role, pv, reading)
                if observation is not None:
                    queue.put_nowait(observation)
        except ControlNotConnectedError:
            pass
        finally:
            queue.put_nowait(_PUMP_DONE)

    async def _pump_testing(
        self,
        code: str,
        pv: str,
        queue: asyncio.Queue[AnyCaptureObservation | _PumpDone],
    ) -> None:
        """Sibling pump for the optional `testing` role.

        Unlike `_pump_abort`, EVERY reading is enqueued, including one
        that decodes clear or does not decode at all: `testing` is a
        tri-state reading in its own right (see
        `CapturePreconditionBypassObservation`), not a phase claim where
        a clear or unresolvable reading means "nothing happened". No
        `_unreached` counterpart, mirroring `_pump_progress`: a disconnect must not
        erase the last reading `RunWitnessRecorder` retained, since the
        dual-clock (`observed_at`) discipline exists precisely so
        staleness is visible at genesis time rather than papered over by
        a synthesized "unknown" on every reconnect.
        """
        try:
            async for reading in self._control_port.subscribe(pv):
                queue.put_nowait(self._from_testing_reading(code, pv, reading))
        except ControlNotConnectedError:
            pass
        finally:
            queue.put_nowait(_PUMP_DONE)

    async def _pump_full_file_name(
        self,
        code: str,
        pv: str,
        queue: asyncio.Queue[AnyCaptureObservation | _PumpDone],
    ) -> None:
        """Sibling pump for the optional `full_file_name` role (slice 13).

        Mirrors `_pump_testing` exactly, for the same reason: a
        disconnect must not erase the last retained reading, since the
        dual-clock guard `RunWitnessRecorder` applies (comparing this
        reading's `observed_at` against the Run's own BEGUN time) needs
        the last GOOD reading to survive a reconnect, not be replaced by
        a synthesized "unreached". Unlike `_pump_abort` / `_pump`, no
        `_from_full_file_name_reading` result is dropped for being
        "no claim" the way an abort's clear reading is -- it can return
        `None` (see that function), but that is a REJECTION (empty
        string, suspected truncation, non-str value), not a "nothing
        happened" no-op, so it is still correct to enqueue nothing for
        it: there is no partial fact to carry.
        """
        try:
            async for reading in self._control_port.subscribe(pv):
                observation = self._from_full_file_name_reading(code, pv, reading)
                if observation is not None:
                    queue.put_nowait(observation)
        except ControlNotConnectedError:
            pass
        finally:
            queue.put_nowait(_PUMP_DONE)

    async def _pump_orchestrator_ref(
        self,
        code: str,
        pv: str,
        queue: asyncio.Queue[AnyCaptureObservation | _PumpDone],
    ) -> None:
        """Sibling pump for the optional `orchestrator_ref` role.

        Mirrors `_pump_full_file_name`'s shape exactly, for the same
        reason: a disconnect must not erase the last retained reading,
        since `RunWitnessRecorder`'s own consume-once guard needs the
        last GOOD reading to survive a reconnect between the
        orchestrator's write and this capture's own BEGUN. Unlike
        `_pump_abort` / `_pump`, no `_from_orchestrator_ref_reading`
        result is dropped for being "no claim" the way an abort's clear
        reading is -- it can return `None` (empty string, over-length,
        non-str value), which is a REJECTION, not a "nothing happened"
        no-op, so it is still correct to enqueue nothing for it.
        """
        try:
            async for reading in self._control_port.subscribe(pv):
                observation = self._from_orchestrator_ref_reading(code, pv, reading)
                if observation is not None:
                    queue.put_nowait(observation)
        except ControlNotConnectedError:
            pass
        finally:
            queue.put_nowait(_PUMP_DONE)

    async def _poll(
        self,
        code: str,
        pv: str,
        queue: asyncio.Queue[AnyCaptureObservation | _PumpDone],
    ) -> None:
        """Re-affirm reach to `pv` every `_tick_seconds`, independent of push.

        Never pushes `_PumpDone`: a sibling of `_pump`, not a stage in
        its lifecycle. See `ControlPortEnclosureObserver._poll`.
        """
        assert self._tick_seconds is not None
        while True:
            await asyncio.sleep(self._tick_seconds)
            try:
                await self._control_port.read(pv)
            except Exception:  # any read failure is a failed probe, not a bug
                queue.put_nowait(self._probe_only(code, pv, ReachTier.UNREACHED))
            else:
                queue.put_nowait(self._probe_only(code, pv, ReachTier.RELAYED))

    def _from_reading(
        self, code: str, pv: str, reading: Measurement
    ) -> CaptureLifecycleObservation:
        reported_status = str(reading.value)
        phase = classify_capture_status(reported_status, self._status_phases)
        return CaptureLifecycleObservation(
            capture_code=code,
            reported_status=reported_status,
            phase=phase,
            reach_tier=ReachTier.RELAYED,
            observed_at=reading.produced_at,
            source_kind=_SOURCE_KIND,
            source_id=pv,
        )

    def _from_abort_reading(
        self, code: str, pv: str, reading: Measurement
    ) -> CaptureLifecycleObservation | None:
        """An asserted abort-role reading is a direct `ABORTED` claim.

        NOT Python truthiness: 2-BM's `AbortScan` is a DBR_ENUM that
        resolves to the label `'No'` when idle, and `bool('No')` is
        `True`. `binary_code` decodes the conventional EPICS binary
        labels (or a raw 0/1 index) instead, so "No" correctly resolves
        to clear, not asserted.

        A clear or unresolvable reading makes no phase claim: it is not
        "the capture is not aborted" so much as "nothing happened on
        this PV" (or a label this cannot decode), and reporting it as a
        phase would let a stale idle read silently arrive between a
        real `Begun` and its `status` transitions. `None` return means
        the caller enqueues nothing.
        """
        if binary_code(reading.value, ordinal=reading.ordinal) != 1:
            return None
        return CaptureLifecycleObservation(
            capture_code=code,
            reported_status=str(reading.value),
            phase=CapturePhase.ABORTED,
            reach_tier=ReachTier.RELAYED,
            observed_at=reading.produced_at,
            source_kind=_SOURCE_KIND,
            source_id=pv,
        )

    def _from_progress_reading(
        self, code: str, role: str, pv: str, reading: Measurement
    ) -> CaptureProgressObservation | None:
        """A progress-role reading, decoded to a finite float plus an
        optional commanded total (see `progress_counts`).

        `None` return (no coercible reached count) means the caller
        enqueues nothing, matching `_from_abort_reading`'s fail-toward-
        silence posture: a garbled or non-numeric reading is dropped,
        never guessed at. A garbled or absent commanded total does NOT
        drop the reading; it enqueues with `commanded_total=None`.
        """
        counts = progress_counts(reading.value)
        if counts is None:
            return None
        value, commanded_total = counts
        return CaptureProgressObservation(
            capture_code=code,
            role=role,
            value=value,
            commanded_total=commanded_total,
            reach_tier=ReachTier.RELAYED,
            observed_at=reading.produced_at,
            source_kind=_SOURCE_KIND,
            source_id=pv,
        )

    def _from_testing_reading(
        self, code: str, pv: str, reading: Measurement
    ) -> CapturePreconditionBypassObservation:
        """A `testing`-role reading, decoded via `binary_code` exactly as
        the `abort` role's reading is (2-BM's `Testing` PV is the
        identical `DBR_ENUM` record type as `AbortScan`): `1` -> `True`
        (asserted: bypassing beam preconditions), `0` -> `False` (clear:
        a positive claim of a real acquisition), `None` -> `None`
        (unresolved). Unlike `_from_abort_reading`, every reading
        constructs an observation; there is no reading here that means
        "nothing happened".
        """
        code_value = binary_code(reading.value, ordinal=reading.ordinal)
        bypassed = None if code_value is None else code_value == 1
        return CapturePreconditionBypassObservation(
            capture_code=code,
            beam_preconditions_bypassed=bypassed,
            reach_tier=ReachTier.RELAYED,
            observed_at=reading.produced_at,
            source_kind=_SOURCE_KIND,
            source_id=pv,
        )

    def _from_full_file_name_reading(
        self, code: str, pv: str, reading: Measurement
    ) -> CapturePathObservation | None:
        """A `full_file_name`-role reading (slice 13), rejected rather
        than enqueued for three reasons, in order.

        1. Not a string: the adapter's own text-waveform decode
           (`text_addresses`) failed to apply or produced something
           else. Never coerced; a non-text reading on this role is a
           deployment misconfiguration, not a value to guess at.
        2. Empty string: the fresh-IOC-boot state (the file plugin has
           never opened a file since the IOC started). A fine, ordinary
           outcome, not an error -- just nothing to enqueue.
        3. Length at or over `FULL_FILE_NAME_TRUNCATION_THRESHOLD`:
           indistinguishable from a wire truncation (see that
           constant's own docstring). Logs the length only, NEVER the
           value -- `observed_path` is personal data.

        `None` return means the caller enqueues nothing, matching
        `_from_abort_reading` / `_from_progress_reading`'s fail-toward-
        silence posture.
        """
        value = reading.value
        if not isinstance(value, str):
            return None
        if not value:
            return None
        if len(value) >= FULL_FILE_NAME_TRUNCATION_THRESHOLD:
            _log.warning(
                "capture_observer.full_file_name_suspected_truncated",
                capture_code=code,
                length=len(value),
            )
            return None
        return CapturePathObservation(
            capture_code=code,
            observed_path=value,
            reach_tier=ReachTier.RELAYED,
            observed_at=reading.produced_at,
            source_kind=_SOURCE_KIND,
            source_id=pv,
        )

    def _from_orchestrator_ref_reading(
        self, code: str, pv: str, reading: Measurement
    ) -> CaptureOrchestratorRefObservation | None:
        """An `orchestrator_ref`-role reading, rejected rather than
        enqueued for four reasons, in order.

        1. Not a string: a non-text reading on this role is a
           deployment misconfiguration, not a value to guess at.
        2. Empty string: the orchestrator cleared the PV between
           captures (see `_run_witness.py`'s "Orchestrator-ref pairing"
           section on why the writer is expected to clear it). A fine,
           ordinary outcome, not an error -- just nothing to enqueue.
        3. Length over `IDENTIFIER_VALUE_MAX_LENGTH` AFTER TRIMMING:
           `Identifier.__post_init__` (`cora.shared.identifier`) strips
           before bounding, so this check measures the trimmed value
           too -- checking the raw length would reject a
           whitespace-padded reading `Identifier` would have accepted,
           and the reverse would let one through the adapter only to
           fail deep inside `RecordWitnessedRun`'s decider instead.
        4. No scheme declared for `code` in `orchestrator_ref_schemes`:
           a reading with nowhere to mint an `Identifier` under is a
           deployment misconfiguration (the PV is declared, the scheme
           is not), reported loudly rather than guessed at.

        `None` return means the caller enqueues nothing, matching
        `_from_full_file_name_reading`'s fail-toward-silence posture.
        """
        value = reading.value
        if not isinstance(value, str):
            return None
        if not value:
            return None
        if len(value.strip()) > IDENTIFIER_VALUE_MAX_LENGTH:
            _log.warning(
                "capture_observer.orchestrator_ref_over_length",
                capture_code=code,
                length=len(value.strip()),
            )
            return None
        scheme = self._orchestrator_ref_schemes.get(code)
        if scheme is None:
            _log.warning(
                "capture_observer.orchestrator_ref_scheme_not_configured",
                capture_code=code,
            )
            return None
        return CaptureOrchestratorRefObservation(
            capture_code=code,
            scheme=scheme,
            value=value,
            reach_tier=ReachTier.RELAYED,
            observed_at=reading.produced_at,
            source_kind=_SOURCE_KIND,
            source_id=pv,
        )

    def _probe_only(self, code: str, pv: str, reach_tier: ReachTier) -> CaptureLifecycleObservation:
        """A poll tick's result: reach evidence with no status claim."""
        return CaptureLifecycleObservation(
            capture_code=code,
            reported_status=None,
            phase=None,
            reach_tier=reach_tier,
            observed_at=None,
            source_kind=_SOURCE_KIND,
            source_id=pv,
        )

    def _unreached(self, code: str, pv: str) -> CaptureLifecycleObservation:
        """A disconnect or clean stream end: no status claim, no phase.

        See this module's docstring, "One deliberate inversion from the
        Enclosure precedent", for why this must not synthesize a phase.
        """
        return CaptureLifecycleObservation(
            capture_code=code,
            reported_status=None,
            phase=None,
            reach_tier=ReachTier.UNREACHED,
            observed_at=None,
            source_kind=_SOURCE_KIND,
            source_id=pv,
        )


__all__ = [
    "FULL_FILE_NAME_TRUNCATION_THRESHOLD",
    "ROLE_ABORT",
    "ROLE_FULL_FILE_NAME",
    "ROLE_IMAGES_COLLECTED",
    "ROLE_IMAGES_SAVED",
    "ROLE_ORCHESTRATOR_REF",
    "ROLE_STATUS",
    "ROLE_TESTING",
    "ControlPortCaptureObserver",
    "binary_code",
    "classify_capture_status",
    "finite_float",
    "progress_counts",
]
