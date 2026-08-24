"""ControlPort-backed `BeamAvailabilityLookup` (BEAM-1 pre-flight read).

Reads the configured beam PVs live via the Operation BC's `ControlPort`
at the run / procedure start instant and maps them to a
`BeamAvailabilityLookupResult`. Lives in `cora.operation.adapters` because the
Operation BC owns `ControlPort`; the consumer (Run / Operation start
handlers) depends only on the `BeamAvailabilityLookup` port in
`cora.infrastructure.ports`.

Polarity (per PSS-1):
  - FES / SBS `BeamBlockingM`: INVERTED. `0` = not blocking = open.
  - ACIS `FesPermitM`: `1` = FES-open permitted.

A PV that is not configured does not gate (treated as open / permitted).
Any read that fails (disconnect / timeout) or comes back unbelievable
sets `quality_ok=False` AND that flag to its fail-closed value, so a dead
gateway can never read as "beam open".

## The quality floor is `believable`, and a strict one closed the gate
## permanently

This asks whether the shutter reading can be TRUSTED, not whether it is
free of annotation, so the floor is `cora.shared.quality.believable`.
The distinction is not academic here: the strict floor this used to
carry made the gate impossible to pass at 2-BM, in any state of the
beamline.

Measured on arcturus 2026-08-24, on all three configured PVs:
`ZSV=MAJOR`, `OSV=NO_ALARM`. State 0 alarms, state 1 is silent. Lay that
over the INVERTED `BeamBlockingM` polarity above and the two halves
point opposite ways:

    shutter OPEN   = 0 = MAJOR   the state the gate needs to confirm
    shutter SHUT   = 1 = silent  the state that fails the gate anyway

Under a `!= "Good"` floor, `_read_open` could therefore never return
True. To be believed a shutter had to be silent, which meant state 1,
which is blocking. An open shutter was discarded as unreadable and a
readable one was always closed, so `fes_open` and `sbs_open` were
structurally incapable of being True and the gate refused every run.
Worse than an outage, because it presents as `RunBeamAvailabilityUnknown`
rather than as anything pointing at CORA.

The damage was not only the blocked start path. `witness_safety_envelope`
runs the same predicate and RECORDS rather than raises, so every
witnessed run at 2-BM was being stamped `beam_available=false` whatever
the shutters were actually doing: a false fact in the record, which is
the thing CORA exists to keep.

`SR-ACIS:2BM:FesPermitM` shares the field settings but not the polarity
problem, since 1 (permitted) is the silent state. Its strict-floor cost
was a mislabelled refusal: "beam availability unknown" for a permit CORA
could read perfectly well as not granted.

Believing an alarmed reading is safe here for the reason it is safe in
the permit observers: ACIS and the PSS hold the shutters, CORA holds
nothing. `Bad` (EPICS INVALID) still fails closed, because that is the
one severity saying the number itself is untrustworthy.

All three PVs are `bi` records at 2-BM, so a real read arrives as
`kind="Categorical"` with `EpicsCaControlPort` having resolved the
DBR_ENUM index to its label. Both halves reach this module: the label
on `Measurement.value` and the index on `Measurement.ordinal`.
`cora.shared.binary_signal.binary_code` prefers the index, because the
label is whatever the facility's IOC author typed and the index is
0 / 1 everywhere, and falls back to the label only when no index came
with the reading. `_read_open` / `_read_permit` then apply the polarity
above.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cora.infrastructure.ports.beam_availability_lookup import (
    AllBeamOpenLookup,
    BeamAvailabilityLookupResult,
)
from cora.operation.ports.control_port import (
    ControlNotConnectedError,
    ControlTimeoutError,
)
from cora.shared.binary_signal import binary_code
from cora.shared.quality import believable

if TYPE_CHECKING:
    from collections.abc import Mapping

    from cora.infrastructure.ports.beam_availability_lookup import BeamAvailabilityLookup
    from cora.operation.ports.control_port import ControlPort


class ControlPortBeamAvailabilityLookup:
    """Reads FES / SBS `BeamBlockingM` + the ACIS permit via `ControlPort`."""

    def __init__(self, *, control_port: ControlPort, beam_pvs: Mapping[str, str]) -> None:
        self._control_port = control_port
        self._fes_pv = beam_pvs.get("fes")
        self._sbs_pv = beam_pvs.get("sbs")
        self._fes_permit_pv = beam_pvs.get("fes_permit")

    async def read(self) -> BeamAvailabilityLookupResult:
        fes_open, fes_ok = await self._read_open(self._fes_pv)
        sbs_open, sbs_ok = await self._read_open(self._sbs_pv)
        fes_permit, permit_ok = await self._read_permit(self._fes_permit_pv)
        return BeamAvailabilityLookupResult(
            fes_open=fes_open,
            sbs_open=sbs_open,
            fes_permit=fes_permit,
            quality_ok=fes_ok and sbs_ok and permit_ok,
        )

    async def _read_open(self, pv: str | None) -> tuple[bool, bool]:
        """Return (open, quality_ok). Unconfigured PV does not gate."""
        if pv is None:
            return True, True
        value, ok = await self._read_int(pv)
        if not ok or value is None:
            return False, False  # fail closed: cannot confirm open
        return value == 0, True  # BeamBlockingM == 0 -> open (inverted)

    async def _read_permit(self, pv: str | None) -> tuple[bool, bool]:
        """Return (permitted, quality_ok). Unconfigured PV does not gate."""
        if pv is None:
            return True, True
        value, ok = await self._read_int(pv)
        if not ok or value is None:
            return False, False
        return value == 1, True

    async def _read_int(self, pv: str) -> tuple[int | None, bool]:
        try:
            reading = await self._control_port.read(pv)
        except (ControlNotConnectedError, ControlTimeoutError):
            return None, False
        if not believable(reading.quality):
            return None, False
        raw = reading.value
        # A fractional reading on a binary shutter / permit PV (e.g. a
        # 0.4 BeamBlockingM) is not trustworthy: int() would truncate it
        # to 0 and read it as "open", a fail-OPEN hole. Treat any
        # non-integral float the same as a bad read (fail closed).
        if isinstance(raw, float) and not raw.is_integer():
            return None, False
        value = binary_code(raw, ordinal=reading.ordinal)
        if value is None:
            return None, False
        return value, True


def build_beam_availability_lookup(
    control_port: ControlPort, beam_pvs: Mapping[str, str]
) -> BeamAvailabilityLookup:
    """Build the deployment's `BeamAvailabilityLookup` (BEAM-1).

    Mirrors `build_control_port`'s empty-config default: with no beam
    PVs configured (`BEAM_AVAILABILITY_PVS` unset, generic / non-2BM
    deployments) returns the always-open `AllBeamOpenLookup` stub so the
    start gate passes trivially (beam-by-default); with PVs configured
    returns a `ControlPortBeamAvailabilityLookup` reading them live
    through the shared `ControlPort`.
    """
    if not beam_pvs:
        return AllBeamOpenLookup()
    return ControlPortBeamAvailabilityLookup(control_port=control_port, beam_pvs=beam_pvs)


__all__ = ["ControlPortBeamAvailabilityLookup", "build_beam_availability_lookup"]
