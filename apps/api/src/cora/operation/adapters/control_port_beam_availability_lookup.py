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
Any read that fails (disconnect / timeout) or returns non-Good quality
sets `quality_ok=False` AND that flag to its fail-closed value, so a dead
gateway can never read as "beam open".

All three PVs are `bi` records at 2-BM, so a real read arrives as
`kind="Categorical"` with `EpicsCaControlPort` having already resolved
the DBR_ENUM index to its label; the index never reaches this module.
`_binary_code` resolves that label (or a plain numeric reading) to 0 / 1
before `_read_open` / `_read_permit` apply the polarity above. See
`_binary_code` for the label set and `cora.api._enclosure_permit_observer`
for the sibling occurrence of this same mapping.
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

if TYPE_CHECKING:
    from collections.abc import Mapping

    from cora.infrastructure.ports.beam_availability_lookup import BeamAvailabilityLookup
    from cora.operation.ports.control_port import ControlPort

# Conventional EPICS binary state labels. A DBR_ENUM reading reaches
# this module as its resolved label, never as its index, so the label
# is the only thing left to compare against. Second occurrence of this
# mapping; see `cora.api._enclosure_permit_observer._binary_code` for
# the first. A third occurrence should hoist both into a shared module.
_ONE_LABELS = frozenset({"1", "ON", "TRUE", "YES"})
_ZERO_LABELS = frozenset({"0", "OFF", "FALSE", "NO"})


def _binary_code(value: object) -> int | None:
    """Resolve a beam PV reading to 1 / 0, or None when it is neither.

    Polarity is NOT decided here: this only turns a raw reading (an
    int, an integral float, or an EPICS enum label) into 0 / 1. The
    caller (`_read_open` / `_read_permit`) applies the per-PV meaning.

    A numeric reading outside {0, 1} (e.g. a stray 2) also resolves to
    None, not to its raw value. The old `int(raw)` had no such floor,
    so a PV reading 2 used to come back trusted (`quality_ok=True`)
    and simply compare unequal to the open/permit code. These PVs are
    `bi` records with exactly two states, so a reading outside {0, 1}
    is not a third state to interpret, it is a signal that something
    upstream is wrong, and that should fail closed like any other
    unbelievable reading rather than be read with confidence.
    """
    if isinstance(value, str):
        token = value.strip().upper()
        if token in _ONE_LABELS:
            return 1
        if token in _ZERO_LABELS:
            return 0
        return None
    try:
        code = int(value)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return None
    return code if code in (0, 1) else None


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
        if reading.quality != "Good":
            return None, False
        raw = reading.value
        # A fractional reading on a binary shutter / permit PV (e.g. a
        # 0.4 BeamBlockingM) is not trustworthy: int() would truncate it
        # to 0 and read it as "open", a fail-OPEN hole. Treat any
        # non-integral float the same as a bad read (fail closed).
        if isinstance(raw, float) and not raw.is_integer():
            return None, False
        value = _binary_code(raw)
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
