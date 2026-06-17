"""ControlPort-backed `BeamAvailabilityLookup` (BEAM-1 pre-flight read).

Reads the configured beam PVs live via the Operation BC's `ControlPort`
at the run / procedure start instant and maps them to a
`BeamAvailabilityResult`. Lives in `cora.operation.adapters` because the
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
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cora.infrastructure.ports.beam_availability_lookup import BeamAvailabilityResult
from cora.operation.ports.control_port import (
    ControlNotConnectedError,
    ControlTimeoutError,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from cora.operation.ports.control_port import ControlPort


class ControlPortBeamAvailabilityLookup:
    """Reads FES / SBS `BeamBlockingM` + the ACIS permit via `ControlPort`."""

    def __init__(self, *, control_port: ControlPort, beam_pvs: Mapping[str, str]) -> None:
        self._control_port = control_port
        self._fes_pv = beam_pvs.get("fes")
        self._sbs_pv = beam_pvs.get("sbs")
        self._fes_permit_pv = beam_pvs.get("fes_permit")

    async def read_beam_availability(self) -> BeamAvailabilityResult:
        fes_open, fes_ok = await self._read_open(self._fes_pv)
        sbs_open, sbs_ok = await self._read_open(self._sbs_pv)
        fes_permit, permit_ok = await self._read_permit(self._fes_permit_pv)
        return BeamAvailabilityResult(
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
        try:
            return int(reading.value), True
        except (TypeError, ValueError):
            return None, False


__all__ = ["ControlPortBeamAvailabilityLookup"]
