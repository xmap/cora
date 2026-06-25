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
  - `{detector}:NumImages`   <- `repetitions` (or `0` for free-run)
  - `{detector}:Acquire`     <- `1` to start
  - `{detector}:Acquire_RBV` -> polled until `0` / `"Done"`
  - `{detector}:DetectorState_RBV` -> read once for final-state evidence

Trigger-mode value mapping translates the substrate-neutral primitive
vocabulary into AD-coded strings: `ExternalEdge` and `ExternalLevel`
both collapse to AD's `"External"`; edge polarity vs level is carried
on the trigger EMITTER (PandABox PCOMP, Aerotech PSO, etc.), not the
detector. Non-AD detectors will land as their own action bodies; promote
a shared shape when 3 detector families exist (rule-of-three).

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

if TYPE_CHECKING:
    from collections.abc import Mapping

    from cora.operation.conductor import ActionContext


_AD_TRIGGER_MODE_VALUES: Mapping[str, str] = {
    "Internal": "Internal",
    "ExternalEdge": "External",
    "ExternalLevel": "External",
}
"""Substrate-neutral trigger_mode value -> areaDetector ADCore string.

AD collapses edge vs level into one `"External"` value; the
distinction is carried at the trigger emitter, not the detector."""


_POLL_INTERVAL_S: float = 0.05
"""Poll period between Acquire_RBV reads inside `collect`'s done-loop.

50ms balances responsiveness against unnecessary CA / PVA traffic for
the typical sub-second to multi-second acquisition durations. The body
relies on caller-side cancellation (Procedure abort) for hard timeout;
no internal bound is enforced at v1."""


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
    sentinel, so `None` is the only way to request free-run.
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
        _AD_TRIGGER_MODE_VALUES[params.trigger_mode],
    )
    await ctx.control_port.write(f"{params.detector}:AcquireTime", params.dwell)
    await ctx.control_port.write(
        f"{params.detector}:NumImages",
        params.repetitions if params.repetitions is not None else 0,
    )
    await ctx.control_port.write(f"{params.detector}:Acquire", 1)

    while True:
        reading = await ctx.control_port.read(f"{params.detector}:Acquire_RBV")
        if reading.value in (0, "Done"):
            break
        await asyncio.sleep(_POLL_INTERVAL_S)

    stopped_at = ctx.clock.now()
    state_reading = await ctx.control_port.read(f"{params.detector}:DetectorState_RBV")

    return {
        "started_at": started_at.isoformat(),
        "stopped_at": stopped_at.isoformat(),
        "repetitions_requested": params.repetitions,
        "trigger_mode": params.trigger_mode,
        "polarity": params.polarity,
        "source": params.source,
        "detector_state_final": state_reading.value,
    }


async def collect(ctx: ActionContext) -> Mapping[str, Any]:
    """Single-detector capture against areaDetector ADCore PV convention.

    Writes TriggerMode / AcquireTime / NumImages, starts Acquire, polls
    Acquire_RBV until `0` / `"Done"`, reads DetectorState_RBV for the
    final-state evidence, returns a Mapping the Conductor records as the
    step entry's `result_data`.

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
        _AD_TRIGGER_MODE_VALUES[params.trigger_mode],
    )
    await ctx.control_port.write(f"{params.detector}:AcquireTime", params.dwell)
    await ctx.control_port.write(
        f"{params.detector}:NumImages",
        params.repetitions if params.repetitions is not None else 0,
    )

    await ctx.control_port.write(params.axis, params.start, wait=True)
    await ctx.control_port.write(f"{params.detector}:Acquire", 1)
    await ctx.control_port.write(params.axis, params.stop, wait=False)

    while True:
        reading = await ctx.control_port.read(f"{params.detector}:Acquire_RBV")
        if reading.value in (0, "Done"):
            break
        await asyncio.sleep(_POLL_INTERVAL_S)

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
    try:
        while True:
            if params.events is not None:
                captured = await ctx.control_port.read(f"{params.detector}:NumCaptured_RBV")
                if captured.value >= params.events:
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
