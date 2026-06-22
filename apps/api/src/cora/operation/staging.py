"""Sample-staging action bodies for the Conductor (composition, not primitives).

The scan primitives in `cora.operation.acquisitions` (`collect` /
`discrete` / `continuous`) are the acquisition-MOTION taxonomy: single /
stepped / swept capture. This module holds a different KIND of action: a
ceremony STAGING composition that brackets an acquisition with a
save-and-restore of an axis. `flats` is `collect` plus sample retraction,
not a fourth scan primitive, so it lives here rather than alongside the
primitives.

## Why staging needs a body at all (the conduct variable-binding gap)

A flat-field capture retracts the sample off the beam, collects, then
restores the sample to its aligned centre. The restore target is the
position read at runtime, and CORA has no relative-move primitive, so the
restore is an absolute write of the read-back value. The conduct step
model is static: `RecipeSetpointStep.value` is a literal or a `BindingRef`,
never "the value I just read at runtime". So a read-then-restore cannot be
expressed as recipe steps today and must live inside a body.

`flats` is therefore a pragmatic stand-in for a missing conduct capability.
The principled fix is conduct-level runtime VARIABLE BINDING (read a value
into a binding, reference it in a later setpoint step), which would turn
the save-and-restore into three ordinary recipe steps (read axis -> collect
-> setpoint from the read) and RETIRE this body. Variable binding is the
designated next design; see [[project_flat_dark_prologue_design]]. Until it
lands, keep staging compositions here and out of the scan-primitive family.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from pydantic import Field, model_validator

from cora.operation.acquisitions import CollectParams, run_collect_cycle
from cora.operation.ports.control_port import ControlValueCoercionError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from cora.operation.conductor import ActionContext


def _require_numeric(value: Any, address: str) -> float:
    """Return `value` as a number or raise a Conductor-recordable failure.

    The save-and-restore arithmetic (`saved + clearance`) needs a numeric
    axis read. `Reading.value` is typed `Any`; a non-numeric read (a
    mis-addressed or categorical leaf) would otherwise raise a bare
    `TypeError` that escapes the Conductor's `_CONTROL_ERRORS`-only catch
    and strands the Procedure in Running. Mapping it to
    `ControlValueCoercionError` (in `_CONTROL_ERRORS`) lets the Conductor
    record a structured step failure instead. The read precedes any axis
    move, so nothing has actuated when this raises.

    Non-finite floats (NaN / +-inf) are also rejected: a NaN/inf axis read
    (EPICS UDF, uninitialized record) would otherwise propagate through the
    `saved + clearance` arithmetic into an absolute write of an undefined
    setpoint with no recorded failure.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ControlValueCoercionError(address, type(value).__name__, "number")
    if not math.isfinite(value):
        raise ControlValueCoercionError(address, repr(value), "finite number")
    return value


class FlatsParams(CollectParams):
    """Validated parameters for the `flats` staging action body.

    Extends `CollectParams` with the sample-retraction definition (`axis`
    + `clearance`). Inherits the detector / trigger / dwell / repetitions
    fields and the three conditional `@model_validator` rules unchanged: a
    flat capture runs the same collect cycle as `collect`, just with the
    sample retracted.

    `clearance` is a SIGNED NONZERO offset added to the saved position to
    form the off-centre target. CORA has no relative-move primitive, so the
    retract and the restore are both absolute writes (read the position, add
    the clearance, write it; later write the saved value back). The sign
    chooses the retraction direction; the magnitude is the clear-of-beam
    travel. Zero is rejected (it would leave the sample in the beam and
    label an in-beam capture a flat-field), mirroring
    `ContinuousParams._check_sweep_range`'s zero-range guard. Per
    [[project_units_design]] both `dwell` (inherited) and `clearance` carry
    the canonical unit annotation; `clearance` is mm.
    """

    axis: str
    clearance: float = Field(
        ...,
        json_schema_extra={"unit": {"system": "udunits", "code": "mm"}},
    )

    @model_validator(mode="after")
    def _check_clearance_nonzero(self) -> FlatsParams:
        if self.clearance == 0:
            raise ValueError("clearance must be nonzero (zero leaves the sample in the beam)")
        return self


async def flats(ctx: ActionContext) -> Mapping[str, Any]:
    """Flat-field capture with the sample retracted, then restored.

    Save-and-restore around one `collect` cycle: read the current `axis`
    position, drive it off the beam centre by `clearance` (an absolute
    write, since CORA has no relative-move primitive), run the collect
    cycle to capture the flat frames, then restore the axis to the saved
    position. Both the retract and the restore are blocking writes
    (`wait=True`) so the frames land at the settled off-centre position and
    the sample is back at its aligned centre before the body returns.

    Runs the shared `run_collect_cycle` with the already-validated
    `FlatsParams` (a `CollectParams` subclass), the same way `discrete` and
    `continuous` compose a collect cycle without re-validating.

    On a `Control*Error` mid-cycle the exception propagates unchanged (no
    rollback try/finally, matching `collect` / `discrete` / `continuous`):
    the Conductor records the step failure and the axis is left retracted
    (off the beam), an acceptable fault state for a sample-out capture.
    Operators reconcile the retracted axis via state inspection, as with
    any halted conduct.

    Evidence shape carries the save-and-restore positions (`saved_value`,
    `offcenter_target`) plus the nested `collect` cycle evidence. The
    restore landing is proven by re-reading the axis (see the integration
    test), not by an echoed field here.
    """
    params = FlatsParams.model_validate(ctx.params)
    saved = await ctx.control_port.read(params.axis)
    saved_value = _require_numeric(saved.value, params.axis)
    offcenter_target = saved_value + params.clearance
    await ctx.control_port.write(params.axis, offcenter_target, wait=True)
    cycle = await run_collect_cycle(ctx, params)
    await ctx.control_port.write(params.axis, saved_value, wait=True)
    return {
        "axis": params.axis,
        "saved_value": saved_value,
        "clearance": params.clearance,
        "offcenter_target": offcenter_target,
        "collect": cycle,
    }


__all__ = [
    "FlatsParams",
    "flats",
]
