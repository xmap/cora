"""Substrate-neutral data-acquisition action bodies for the Conductor.

The four primitives `collect` / `discrete` / `continuous` / `stream`
register as named `ActionBody` callables in the `InMemoryActionRegistry`
the `Conductor` consumes. `collect` is the single-detector capture cycle;
`discrete` walks a trajectory of axis points and runs a `collect` cycle
at each; `continuous` drives the axis from `start` to `stop` while the
detector receives external trigger pulses fired by an emitter during
motion; `stream` records a DAQ-owned high-rate frame stream to an
external file, terminal on a frame count or a wall-clock duration (the
event-stream acquisition axis, for XPCS and XFEL per-shot DAQ).

See `project_scan_primitives_design` for the design lock and
`project_scan_primitives_research` for the corpus that backs the
substrate-neutral parameter shapes.

## v1 contract: areaDetector ADCore PV convention

`collect` integrates with areaDetector's ADCore PV layout. `params.detector`
is the areaDetector root prefix (e.g., `"2bma:cam1"`); the body writes
to sibling PVs:

  - `{detector}:TriggerMode` <- mapped from `trigger_mode`
  - `{detector}:AcquireTime` <- `dwell` (seconds)
  - `{detector}:ImageMode`   <- `"Multiple"`, unconditionally
  - `{detector}:NumImages`   <- `repetitions`
  - `{detector}:Acquire`     <- `1` to start
  - `{detector}:Acquire_RBV` -> polled until Done
  - `{detector}:DetectorState_RBV` -> read once for final-state evidence

`ImageMode` is written explicitly rather than inherited from whatever
state the camera was last left in: areaDetector's `NumImages` only
takes effect under `Multiple` (or is irrelevant under `Single`), and
under `Continuous` the detector free-runs and `Acquire_RBV` never
returns to Done, so a body that waits for completion must never let
`Continuous` stand. `repetitions=None` ("free run") is refused before
any PV write (`UnboundedAcquisitionError`) rather than translated to
an `ImageMode` this body would then wait on forever; see
`_arm_bounded_repetitions`.

Trigger-mode value mapping translates the substrate-neutral primitive
vocabulary into detector-driver-coded strings via `_TRIGGER_MODE_VALUES`,
keyed by `ctx.trigger_dialect` (a DEPLOYMENT fact, `Settings.detector_trigger_dialect`,
not a recipe fact): `ExternalEdge` and `ExternalLevel` always collapse to
one External value; edge polarity vs level is carried on the trigger
EMITTER (PandABox PCOMP, Aerotech PSO, etc.), not the detector. The
`ADCore` dialect writes `"Internal"`/`"External"`; the `ADSpinnaker`
dialect (APS 2-BM's FLIR camera) writes the INVERTED `"Off"`/`"On"` --
see `_TRIGGER_MODE_VALUES`'s docstring for why. Non-AD detectors will
land as their own action bodies; promote a shared shape when 3 detector
families exist (rule-of-three).

## `Acquire_RBV` is read by index, not by the word "Done"

A real areaDetector `Acquire_RBV` is a `bi` record (DBR_ENUM), so it
arrives as `kind="Categorical"` carrying a facility/build-authored
label, with the index it resolved from on `Measurement.ordinal`.
`"Done"` is ADCore's default `ZNAM`, nothing more: a relabelled record,
or a build whose defaults differ, produces a value the poll cannot
recognise, and the loop then waits forever on a detector that already
finished. This is the fourth instance of a defect family fixed three
times already this month (the hutch permit, the BLEPS interlock flags,
the beam-availability gate): `_acquisition_finished` reads
`Measurement.ordinal` via `cora.shared.binary_signal.binary_code`, the
same decoder those three use, and treats the conventional label set as
the fallback for a reading with no index.

The floor is `cora.shared.quality.believable`, not `actionable`, and
picking the strict one would recreate the same failure at one remove: a
detector carrying a standing `Uncertain` alarm for a reason unrelated to
whether it finished (a temperature warning, a nearly-full file-writer
disk) would then never be readable as Done, so every acquisition on it
would hang instead of finish. An alarm on `Acquire_RBV` says nothing
about whether the acquisition is over; only `Bad` (the value itself is
untrustworthy) may withhold a conclusion.

An unreadable `Acquire_RBV` (unbelievable quality, or a value
`binary_code` cannot resolve) does not conclude "still running": it logs
once per continuous stretch of unreadability and keeps polling. Silently
treating it as "not yet Done" would look identical to a slow detector
until someone reads the log, which is the whole point: the wait staying
unbounded is a stated v1 choice (see `_POLL_INTERVAL_S`), so the fix
here is to stop that choice from making an ordinary label mismatch
silent, not to bound the wait.

## v1 detector-side / emitter-side split

`collect` writes ONLY the detector-side trigger PVs. The `polarity` and
`source` fields are validated by Pydantic and recorded in the returned
evidence mapping, but they are NOT written to PVs by `collect`. The
trigger EMITTER (the device named by `source`) is configured by the
caller via setpoint steps that precede the action step in the Procedure,
or by a future Capability template that expands trigger configuration
into the step list. This split keeps the primitive substrate-neutral on
the emitter side, where addressing conventions vary by hardware (PCOMP
PV layout differs from PSO PV layout differs from software clock).
Revisit at first PandABox-or-Aerotech integration.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field, model_validator

from cora.infrastructure.logging import get_logger
from cora.operation.errors import UnboundedAcquisitionError, UnknownTriggerDialectError
from cora.shared.binary_signal import binary_code
from cora.shared.quality import believable

if TYPE_CHECKING:
    from collections.abc import Mapping

    from cora.operation.conductor import ActionContext
    from cora.operation.ports.control_port import Measurement

_log = get_logger(__name__)


_TRIGGER_MODE_VALUES: Mapping[str, Mapping[str, str]] = {
    "ADCore": {
        "Internal": "Internal",
        "ExternalEdge": "External",
        "ExternalLevel": "External",
    },
    "ADSpinnaker": {
        "Internal": "Off",
        "ExternalEdge": "On",
        "ExternalLevel": "On",
    },
}
"""Substrate-neutral trigger_mode value -> detector-driver TriggerMode string, per dialect.

The dialect is a DEPLOYMENT fact (which camera driver is installed), not
a recipe fact ("free-running" is true everywhere; "this camera is a
FLIR" is true only of this building), so it rides `ActionContext.trigger_dialect`
(sourced from `Settings.detector_trigger_dialect`), never a `CollectParams` field.

`ADCore` is the plain areaDetector convention: `Internal` stays
`"Internal"`, both External modes collapse to `"External"` (edge vs
level is carried at the trigger emitter, not the detector).

`ADSpinnaker` (the FLIR driver at APS 2-BM) is INVERTED relative to
what a reader would guess: `Internal` maps to `"Off"` and both External
modes map to `"On"`. This is not a naming quirk to normalise away.
ADSpinnaker's `TriggerMode` PV does not ask "is the trigger internal or
external"; it asks "is EXTERNAL triggering enabled". CORA's `Internal`
(free-running, camera's own clock) is the state where external
triggering is disabled, hence `Off`. A future reader who assumes
`Internal -> On` "because On sounds like the trigger is active" has it
exactly backwards. Confirmed live against `2bmSP1:cam1:TriggerMode`
(a two-choice DBF_ENUM, `[0] Off` / `[1] On`, no `"Internal"` string in
the set at all) and against the deployed `tomoscan_2bm.py`, which
writes `CamTriggerMode='Off'` for its own internal-trigger path.
"""


def _resolve_trigger_mode_value(dialect: str, trigger_mode: str) -> str:
    """Look up the detector-driver string for `trigger_mode` under `dialect`.

    Raises `UnknownTriggerDialectError` naming the offending dialect and
    the known ones, rather than letting an unrecognised
    `ctx.trigger_dialect` surface as a bare `KeyError` deep inside a
    write call. A wrong dialect must fail loudly: silently falling back
    to `ADCore` would write a string the real camera's enum does not
    accept, or worse, one it accepts with the inverted meaning.
    """
    table = _TRIGGER_MODE_VALUES.get(dialect)
    if table is None:
        raise UnknownTriggerDialectError(dialect, sorted(_TRIGGER_MODE_VALUES))
    return table[trigger_mode]


_IMAGE_MODE_MULTIPLE = "Multiple"
"""The only `ImageMode` value CORA's v1 acquisition bodies write.

Unlike `TriggerMode`, `ImageMode` is NOT routed through
`_TRIGGER_MODE_VALUES` / `ctx.trigger_dialect`: its three choices
(`Single` / `Multiple` / `Continuous`) are the plain ADCore enum and
are identical on ADSpinnaker (confirmed live against
`2bmSP1:cam1:ImageMode`), so it needs no per-dialect value table. Do
not add one. `Single` is unused at v1 because every write site here
counts frames via `NumImages`, which only takes effect under
`Multiple`; `Continuous` is never written because it never asserts
`Acquire_RBV` Done on its own, and both `collect` and `continuous`
wait for Done unconditionally.
"""


async def _arm_bounded_repetitions(
    ctx: ActionContext, detector: str, repetitions: int | None
) -> None:
    """Write `ImageMode=Multiple` + `NumImages=repetitions`, refusing an unbounded request.

    Shared by `_run_collect_cycle` and `continuous`, both of which wait
    on `_await_acquire_done` with no internal timeout. `repetitions=None`
    used to mean "free run" and wrote `NumImages=0` while leaving
    `ImageMode` at whatever the camera was last set to; at APS 2-BM that
    is `Continuous`, under which `Acquire_RBV` never returns to Done, so
    the poll loop hangs forever against real hardware and the camera is
    left acquiring. Raising here, before either write, keeps a caller
    who wants free-running acquisition from partially arming a camera
    this action body can then never bring back down.
    """
    if repetitions is None:
        raise UnboundedAcquisitionError(detector)
    await ctx.control_port.write(f"{detector}:ImageMode", _IMAGE_MODE_MULTIPLE)
    await ctx.control_port.write(f"{detector}:NumImages", repetitions)


_POLL_INTERVAL_S: float = 0.05
"""Poll period between Acquire_RBV reads inside `collect`'s done-loop.

50ms balances responsiveness against unnecessary CA / PVA traffic for
the typical sub-second to multi-second acquisition durations. The body
relies on caller-side cancellation (Procedure abort) for hard timeout;
no internal bound is enforced at v1."""


def _acquisition_finished(reading: Measurement) -> bool | None:
    """Has `Acquire_RBV` reached its de-asserted (Done) state?

    `None` when the reading cannot settle the question at all: either
    the quality floor (`believable`, `Bad` only disqualifies) rejects it,
    or `binary_code` cannot resolve `reading.value` / `reading.ordinal`
    to 0 or 1. `None` is deliberately distinct from `False` -- "cannot
    tell" must never be folded into "still running", because the two
    poll loops that call this one treat only `True` as a reason to stop
    and treat both `False` and `None` identically (keep polling), so
    collapsing them here would cost the caller the ability to log the
    difference.

    `code == 0` is Done because `Acquire_RBV` is a `bi` record and 0 is
    always a `bi`'s de-asserted / false state by construction; see the
    module docstring's "`Acquire_RBV` is read by index" section for why
    the label itself (`"Done"`, `ZNAM`'s ADCore default) is not trusted.
    """
    if not believable(reading.quality):
        return None
    code = binary_code(reading.value, ordinal=reading.ordinal)
    return None if code is None else code == 0


async def _await_acquire_done(ctx: ActionContext, detector: str) -> None:
    """Poll `{detector}:Acquire_RBV` until Done.

    Shared by `_run_collect_cycle` and `continuous`: both used to carry
    their own copy of this loop, which is how the same undecoded-label
    bug ended up needing to be found and fixed twice. `_acquisition_finished`
    decides; this function owns only the polling cadence and a log line
    for a continuous unreadable stretch, emitted once on entry and once
    on exit rather than every 50ms.

    An unreadable reading (`_acquisition_finished` returns `None`) is
    treated exactly like "not yet Done": the loop keeps polling. The wait
    staying unbounded either way is the documented v1 choice at
    `_POLL_INTERVAL_S`; what changes here is that the caller can now SEE
    the difference between a slow detector and a detector CORA cannot
    read, instead of both looking like silence.
    """
    reported_unreadable = False
    while True:
        reading = await ctx.control_port.read(f"{detector}:Acquire_RBV")
        finished = _acquisition_finished(reading)
        if finished is None:
            if not reported_unreadable:
                reported_unreadable = True
                _log.warning(
                    "acquisitions.acquire_rbv_unreadable",
                    detector=detector,
                    value=repr(reading.value),
                    kind=reading.kind,
                    ordinal=reading.ordinal,
                    quality=reading.quality,
                    detail=(
                        "Acquire_RBV not resolvable to Done/Acquiring "
                        "(unbelievable quality, or an unconventional label "
                        "with no ordinal); polling continues"
                    ),
                )
        elif reported_unreadable:
            reported_unreadable = False
            _log.info("acquisitions.acquire_rbv_restored", detector=detector)
        if finished:
            break
        await asyncio.sleep(_POLL_INTERVAL_S)


def _stream_count_reached(reading: Measurement, target: int) -> bool | None:
    """Has `NumCaptured_RBV` reached `target`? `None` when it cannot be told.

    `NumCaptured_RBV` is a plain numeric readback (AD `longin`), not an
    enum, so there is no label/ordinal question here: the only way this
    reading can fail to answer is an unbelievable quality
    (`cora.shared.quality.believable`, `Bad` only) or a value that is not
    actually numeric. Either way `None`, not `False`: before this guard
    existed, a `Bad`-quality reading whose stale value happened to compare
    `>= target` would end the stream on a count CORA never actually
    confirmed, and a non-numeric value would raise `TypeError` -- not one
    of the Conductor's closed `_CONTROL_ERRORS`, so it would escape the
    Conductor uncaught rather than being recorded as a step failure.
    """
    if not believable(reading.quality):
        return None
    if not isinstance(reading.value, (int, float)):
        return None
    return reading.value >= target


class CollectParams(BaseModel):
    """Validated parameters for the `collect` action body.

    Substrate-neutral field shape per [[project_scan_primitives_design]].
    The `@model_validator` enforces the three conditional rules that the
    JSON-Schema subset cannot express today (per design memo Watch item 3):

      - `polarity` is required iff `trigger_mode == "ExternalEdge"`
      - `source` is required when `trigger_mode != "Internal"`
      - `source` must be `None` when `trigger_mode == "Internal"`

    `dwell` carries the canonical `unit: {system, code}` annotation per
    [[project_units_design]] (no `_seconds` suffix). `repetitions` has a
    `ge=1` floor; `0` collides with the AD `NumImages=0` continuous
    sentinel, so `None` is the schema's only way to express an unbounded
    request. The action bodies refuse that request at runtime rather
    than acting on it: `None` validates here, but `collect` and
    `continuous` both raise `UnboundedAcquisitionError` before writing
    any PV when they see it, because both wait unconditionally for the
    acquisition to finish and a free-running acquisition never does.
    See `_arm_bounded_repetitions`.
    """

    detector: str
    trigger_mode: Literal["Internal", "ExternalEdge", "ExternalLevel"]
    polarity: Literal["Rising", "Falling", "Either"] | None = None
    source: str | None = None
    repetitions: int | None = Field(default=None, ge=1)
    dwell: float = Field(
        ...,
        gt=0,
        json_schema_extra={"unit": {"system": "udunits", "code": "s"}},
    )

    @model_validator(mode="after")
    def _check_trigger_constraints(self) -> CollectParams:
        if self.trigger_mode == "ExternalEdge" and self.polarity is None:
            raise ValueError("polarity required when trigger_mode == ExternalEdge")
        if self.trigger_mode != "Internal" and self.source is None:
            raise ValueError("source required when trigger_mode != Internal")
        if self.trigger_mode == "Internal" and self.source is not None:
            raise ValueError("source must be None when trigger_mode == Internal")
        return self


async def _run_collect_cycle(ctx: ActionContext, params: CollectParams) -> Mapping[str, Any]:
    """One collect cycle: configure detector, arm, poll until Done, read state.

    Shared helper used by the `collect` action body and the composing
    `discrete` / `continuous` bodies. Takes a validated `CollectParams`
    (or any subclass that exposes the same fields, e.g., `DiscreteParams`
    inherits all of them), so the callers don't re-validate or re-wrap
    `ActionContext` per cycle.
    Returns the same evidence Mapping the `collect` action body returns,
    so per-point composition stays uniform.
    """
    started_at = ctx.clock.now()

    await ctx.control_port.write(
        f"{params.detector}:TriggerMode",
        _resolve_trigger_mode_value(ctx.trigger_dialect, params.trigger_mode),
    )
    await ctx.control_port.write(f"{params.detector}:AcquireTime", params.dwell)
    await _arm_bounded_repetitions(ctx, params.detector, params.repetitions)
    await ctx.control_port.write(f"{params.detector}:Acquire", 1)

    await _await_acquire_done(ctx, params.detector)

    stopped_at = ctx.clock.now()
    state_reading = await ctx.control_port.read(f"{params.detector}:DetectorState_RBV")

    return {
        "started_at": started_at.isoformat(),
        "stopped_at": stopped_at.isoformat(),
        "repetitions_requested": params.repetitions,
        "trigger_mode": params.trigger_mode,
        "trigger_dialect": ctx.trigger_dialect,
        "image_mode": _IMAGE_MODE_MULTIPLE,
        "polarity": params.polarity,
        "source": params.source,
        "detector_state_final": state_reading.value,
    }


async def collect(ctx: ActionContext) -> Mapping[str, Any]:
    """Single-detector capture against areaDetector ADCore PV convention.

    Writes TriggerMode / AcquireTime / ImageMode / NumImages, starts
    Acquire, polls Acquire_RBV until `0` / `"Done"`, reads
    DetectorState_RBV for the final-state evidence, returns a Mapping
    the Conductor records as the step entry's `result_data`.

    `params.repetitions is None` raises `UnboundedAcquisitionError`
    before any PV write: this body waits for Acquire_RBV to reach Done
    unconditionally, and a free-running acquisition never reaches Done
    on its own, so an unbounded request combined with that wait would
    hang forever against real hardware. See `_arm_bounded_repetitions`.

    `Control*Error` raised by the underlying `ControlPort` propagates
    unchanged; the Conductor catches it at the action-dispatch site and
    records the step failure per its standard contract.

    See module docstring for the AD-convention v1 contract and the
    detector-side / emitter-side split that leaves `polarity` and
    `source` as evidence-only fields (the trigger EMITTER is configured
    by caller-authored setpoint steps before this action step).
    """
    return await _run_collect_cycle(ctx, CollectParams.model_validate(ctx.params))


class DiscreteParams(CollectParams):
    """Validated parameters for the `discrete` action body.

    Extends `CollectParams` with the trajectory definition (`axis` +
    `points`) and per-point dwell-before-collect `wait`. Inherits the
    detector / trigger / dwell / repetitions fields and the three
    conditional `@model_validator` rules unchanged: `discrete` runs the
    same collect cycle at each point, so the same trigger semantics
    apply.

    `points: tuple[float, ...]` is the data-coded trajectory (vs motor-
    coded `positions`). Works equally well for energy / temperature /
    field axes. `min_length=1` rejects empty trajectories. `wait`
    defaults to `0.0`: per-point settle is opt-in. Per
    [[project_units_design]] both `dwell` (inherited) and `wait` carry
    the canonical unit annotation.
    """

    axis: str
    points: tuple[float, ...] = Field(..., min_length=1)
    wait: float = Field(
        default=0.0,
        ge=0,
        json_schema_extra={"unit": {"system": "udunits", "code": "s"}},
    )


async def discrete(ctx: ActionContext) -> Mapping[str, Any]:
    """Discrete-trajectory scan: for each `points[i]`, write the axis, wait, collect.

    Composes a `collect` cycle at each axis point. The inherited trigger
    fields (`trigger_mode` / `polarity` / `source` / `repetitions` /
    `dwell`) apply uniformly across points: each point runs the same
    detector capture configuration. Per-point `wait` is honored only
    when `> 0` to skip the asyncio.sleep call when no settle is
    requested.

    Evidence shape: `per_point_results` is a list parallel to `points`;
    each entry carries the visited `point` value and the `collect`
    evidence Mapping for the cycle at that point. `axis` and
    `points_visited` are surfaced at the top of the result for
    quick-scan logging.

    Halts on the first `Control*Error` from a write or read; partial
    `per_point_results` is NOT returned in that case (the exception
    propagates up through the Conductor, which records the failure per
    its standard contract).
    """
    params = DiscreteParams.model_validate(ctx.params)
    results: list[Mapping[str, Any]] = []
    for point in params.points:
        await ctx.control_port.write(params.axis, point, wait=True)
        if params.wait > 0:
            await asyncio.sleep(params.wait)
        cycle = await _run_collect_cycle(ctx, params)
        results.append({"point": point, "collect": cycle})
    return {
        "axis": params.axis,
        "points_visited": len(results),
        "per_point_results": results,
    }


class ContinuousParams(CollectParams):
    """Validated parameters for the `continuous` action body.

    Extends `CollectParams` with the axis sweep definition (`axis` +
    `start` + `stop`) plus optional `rate`. Inherits all detector /
    trigger fields and the three conditional `@model_validator` rules.

    The trigger emitter (per `source`) fires `repetitions` pulses
    during the sweep; the detector counts pulses internally. The body
    arms the detector AFTER axis reaches `start` (blocking write) but
    BEFORE motion toward `stop` begins (non-blocking write), so the
    emitter sees motion + arm overlap.

    `start != stop` is enforced at the validator boundary: a continuous
    scan with zero range is meaningless and would deadlock the poll
    loop (detector waits for pulses that never arrive). `rate` is
    `gt=0` when present; the axis-dimensional `unit` declaration lives
    on the Capability template's outer `parameters_schema` (rate units
    vary by axis: deg/s for rotation, eV/s for energy, K/s for
    temperature, T/s for field).

    v1 limitation: `rate` is recorded as evidence but NOT written to
    any axis-rate PV by the body. The substrate-specific rate PV
    convention (EPICS motor `.VELO`, ramp-controller setpoint, etc.)
    is the caller's responsibility via a `SetpointStep` before this
    action step, mirroring the polarity / source emitter-side split
    documented for `collect`.
    """

    axis: str
    start: float
    stop: float
    rate: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _check_sweep_range(self) -> ContinuousParams:
        if self.start == self.stop:
            raise ValueError("continuous scan requires start != stop (zero range)")
        return self


async def continuous(ctx: ActionContext) -> Mapping[str, Any]:
    """Continuous-trajectory scan: arm detector, sweep axis, collect on triggers.

    Fly-scan ordering: configure detector, move axis to `start` (blocking
    so motion completes before arm), arm detector (Acquire=1), start
    motion toward `stop` (non-blocking so the trigger emitter sees
    motion + arm overlap), then poll Acquire_RBV until the detector has
    consumed all expected trigger pulses. The trigger emitter (per
    `source`) fires `repetitions` pulses during the sweep, externally
    coordinated with the axis motion (Aerotech PSO, PandABox PCOMP,
    etc.).

    Evidence shape carries the request (`axis_start_requested`,
    `axis_stop_requested`, `rate_requested`, `repetitions_requested`)
    plus the observed `axis_final_actual` for end-of-sweep verification,
    timestamps, trigger config, and the detector's final state.

    `params.repetitions is None` raises `UnboundedAcquisitionError`
    before any PV write, same as `collect`: see
    `_arm_bounded_repetitions`.

    `Control*Error` from any read or write propagates unchanged; the
    Conductor records the failure per its standard contract. The
    detector is NOT explicitly stopped on the happy path; the
    NumImages=repetitions setting bounds it, so it self-terminates when
    all pulses have been consumed. Detector-side overrun handling
    (motion completes before pulses arrive) is deferred: surfaces as a
    poll-loop hang the caller cancels via Procedure abort. Revisit at
    first deployment that exercises the overrun edge.
    """
    params = ContinuousParams.model_validate(ctx.params)
    started_at = ctx.clock.now()

    await ctx.control_port.write(
        f"{params.detector}:TriggerMode",
        _resolve_trigger_mode_value(ctx.trigger_dialect, params.trigger_mode),
    )
    await ctx.control_port.write(f"{params.detector}:AcquireTime", params.dwell)
    await _arm_bounded_repetitions(ctx, params.detector, params.repetitions)

    await ctx.control_port.write(params.axis, params.start, wait=True)
    await ctx.control_port.write(f"{params.detector}:Acquire", 1)
    await ctx.control_port.write(params.axis, params.stop, wait=False)

    await _await_acquire_done(ctx, params.detector)

    stopped_at = ctx.clock.now()
    state_reading = await ctx.control_port.read(f"{params.detector}:DetectorState_RBV")
    axis_final = await ctx.control_port.read(params.axis)

    return {
        "started_at": started_at.isoformat(),
        "stopped_at": stopped_at.isoformat(),
        "axis": params.axis,
        "axis_start_requested": params.start,
        "axis_stop_requested": params.stop,
        "axis_final_actual": axis_final.value,
        "rate_requested": params.rate,
        "repetitions_requested": params.repetitions,
        "trigger_mode": params.trigger_mode,
        "trigger_dialect": ctx.trigger_dialect,
        "image_mode": _IMAGE_MODE_MULTIPLE,
        "polarity": params.polarity,
        "source": params.source,
        "detector_state_final": state_reading.value,
    }


class StreamParams(BaseModel):
    """Validated parameters for the `stream` action body.

    The event-stream acquisition axis (per-shot / DAQ-owned high-rate
    frame stream) per [[project_event_stream_axis_stage1_design]]. Unlike
    `collect`, the stream is free-running: an external DAQ / file-writer
    records frames and CORA does not pace a per-frame trigger, so there is
    no `trigger_mode` / `Acquire` semantics and this is NOT a
    `CollectParams` subclass.

    Exactly one terminal is required: `events` (stop after N frames ->
    Completed) XOR `duration` (stop after a wall-clock cap -> Truncated),
    enforced by the `@model_validator` mirroring
    `CollectParams._check_trigger_constraints`. `dwell` (per-frame
    exposure) and `duration` carry the canonical `unit: {system, code}`
    annotation per [[project_units_design]].
    """

    detector: str
    events: int | None = Field(default=None, ge=1)
    duration: float | None = Field(
        default=None,
        gt=0,
        json_schema_extra={"unit": {"system": "udunits", "code": "s"}},
    )
    dwell: float = Field(
        ...,
        gt=0,
        json_schema_extra={"unit": {"system": "udunits", "code": "s"}},
    )

    @model_validator(mode="after")
    def _check_terminal(self) -> StreamParams:
        if (self.events is None) == (self.duration is None):
            raise ValueError(
                "exactly one of events or duration is required (count vs time terminal)"
            )
        return self


async def stream(ctx: ActionContext) -> Mapping[str, Any]:
    """DAQ-owned high-rate frame stream against the areaDetector file-writer convention.

    The event-stream acquisition axis. `params.detector` is the DAQ /
    file-writer root prefix (e.g., an areaDetector HDF plugin root); the
    body writes the per-frame exposure and the capture count, starts the
    recording, then runs its OWN terminal loop (NOT a `collect`-style
    `Acquire_RBV` done-poll, and NOT composing `_run_collect_cycle`):

      - `{detector}:AcquireTime` <- `dwell` (per-frame exposure, seconds)
      - `{detector}:NumCapture`  <- `events` (or `0` for the duration cap)
      - `{detector}:Capture`     <- `1` to start recording
      - terminal: `{detector}:NumCaptured_RBV` >= `events` (-> "count"),
        or `clock.now() - started_at` >= `duration` (-> "duration")
      - `{detector}:Capture`     <- `0` to STOP, in a `finally` so an
        aborted (task-cancelled) stream never leaves the DAQ free-running
      - `{detector}:FullFileName_RBV` -> read for the output `uri`

    Data plane: per-frame data stays in the external DAQ file; CORA never
    ingests it. The returned evidence carries the `uri` (matching the
    `register_dataset` field) plus capture provenance; the Dataset is
    registered by the caller via the existing `register_dataset` path
    (`producing_run_id`), which supplies `checksum_*` / `byte_size` from
    the file (a ControlPort body cannot hash a file). This is the same
    caller-driven acquisition -> Dataset path the 2-BM tomography stack
    uses; the stream does NOT ride `RunCompleted.artifact_uri` (a
    compute-only field).

    v1 contract is the areaDetector file-writer PV layout; a non-AD DAQ
    (psdaq, etc.) lands as its own action body when a second arrives
    (rule-of-three), mirroring the `collect` note.

    `Control*Error` from any read or write propagates unchanged; the
    Conductor records the failure per its standard contract.
    """
    params = StreamParams.model_validate(ctx.params)
    started_at = ctx.clock.now()

    await ctx.control_port.write(f"{params.detector}:AcquireTime", params.dwell)
    await ctx.control_port.write(
        f"{params.detector}:NumCapture",
        params.events if params.events is not None else 0,
    )
    await ctx.control_port.write(f"{params.detector}:Capture", 1)

    terminal: str | None = None
    reported_unreadable = False
    try:
        while True:
            if params.events is not None:
                captured = await ctx.control_port.read(f"{params.detector}:NumCaptured_RBV")
                reached = _stream_count_reached(captured, params.events)
                if reached is None:
                    if not reported_unreadable:
                        reported_unreadable = True
                        _log.warning(
                            "acquisitions.num_captured_unreadable",
                            detector=params.detector,
                            value=repr(captured.value),
                            quality=captured.quality,
                            detail=(
                                "NumCaptured_RBV not resolvable to a believable "
                                "count; polling continues"
                            ),
                        )
                elif reported_unreadable:
                    reported_unreadable = False
                    _log.info("acquisitions.num_captured_restored", detector=params.detector)
                if reached:
                    terminal = "count"
                    break
            elif params.duration is not None:
                elapsed = (ctx.clock.now() - started_at).total_seconds()
                if elapsed >= params.duration:
                    terminal = "duration"
                    break
            await asyncio.sleep(_POLL_INTERVAL_S)
    finally:
        await ctx.control_port.write(f"{params.detector}:Capture", 0)

    assert terminal is not None
    stopped_at = ctx.clock.now()
    file_reading = await ctx.control_port.read(f"{params.detector}:FullFileName_RBV")
    captured_reading = await ctx.control_port.read(f"{params.detector}:NumCaptured_RBV")

    return {
        "started_at": started_at.isoformat(),
        "stopped_at": stopped_at.isoformat(),
        "terminal": terminal,
        "frames_captured": captured_reading.value,
        "uri": file_reading.value,
        "events_requested": params.events,
        "duration_requested": params.duration,
        "dwell": params.dwell,
    }


__all__ = [
    "CollectParams",
    "ContinuousParams",
    "DiscreteParams",
    "StreamParams",
    "collect",
    "continuous",
    "discrete",
    "stream",
]
