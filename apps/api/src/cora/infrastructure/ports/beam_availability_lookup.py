"""BeamAvailabilityLookup port: run/procedure pre-flight beam-availability read.

Consumed by the Run and Operation BC start handlers to answer "is beam
available right now?" before a Run / Procedure begins (BEAM-1). Lives in
`cora.infrastructure.ports` alongside the other cross-BC lookup ports
(`EnclosureLookup`, `SupplyLookup`, `ClearanceLookup`, ...).

## A point-in-time live read, not a projection

Every OTHER cross-BC lookup here reads a denormalized PROJECTION
(`proj_*_summary`). This one is different by design: beam-open state
(the FES / SBS `BeamBlockingM` PVs) changes many times per scan and has
no standalone audit value (BEAM-1 says NOT to record the cycling), so it
is read LIVE from the control system at the pre-flight instant rather
than event-sourced into an aggregate + projection. The novelty is
contained behind this port: the production adapter
(`ControlPortBeamAvailabilityLookup`) reads the configured PVs through
the Operation BC's `ControlPort`; the consuming decider still sees only
a `BeamAvailabilityLookupResult` value object, so it stays pure and
projection-shaped. See [[project_non_determinism_principle]]: the
handler injects the reading, the decider is pure.

## Fail-closed

A read whose quality is not Good (PV disconnected / bad / timed out) sets
`quality_ok=False`; the consuming decider treats that as "beam
availability unknown" and refuses the start, so a dead gateway can never
read as "beam open".

## No BC imports

`BeamAvailabilityLookupResult` carries bare `bool`s so this port stays inside
`cora.infrastructure.ports`'s `depends_on = []` tach contract.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class BeamAvailabilityLookupResult:
    """Point-in-time beam-availability reading for the run / procedure gate.

    `fes_open` / `sbs_open` are the front-end and station (P6-50) shutter
    open states, derived from their `BeamBlockingM` PVs with INVERTED
    polarity (`BeamBlockingM == 0` means not blocking, i.e. open).

    `fes_permit` is the ACIS upstream composite (`SR-ACIS:2BM:FesPermitM`,
    `1` = FES-open permitted) folding storage-ring health, injection,
    APS-wide permits, and the BLEPS chain into one boolean. When the
    deployment does not configure an ACIS PV it defaults to `True`
    (nothing extra to gate on).

    `quality_ok` is `False` when ANY contributing PV read had non-Good
    quality (disconnected / bad / timed out); the decider fails closed.
    """

    fes_open: bool
    sbs_open: bool
    fes_permit: bool
    quality_ok: bool


class BeamAvailabilityLookup(Protocol):
    """Cross-BC port: read current beam availability for the start gate."""

    async def read_beam_availability(self) -> BeamAvailabilityLookupResult:
        """Return the current beam-availability reading.

        Never raises for substrate disconnects: a failed / bad-quality
        read surfaces as `quality_ok=False` so the decider can fail
        closed rather than the handler erroring out mid-pre-flight.
        """
        ...


class AllBeamOpenLookup:
    """Stub: beam is always fully available (every flag True).

    The default `BeamAvailabilityLookup` when no `BEAM_AVAILABILITY_PVS`
    are configured (generic / non-2BM deployments) and the default for
    tests that do not exercise the beam gate. Mirrors the abstract-
    adjective stub family (`AllSatisfiedSupplyLookup`,
    `AlwaysPermittedEnclosureLookup`): the name states the always-pass
    posture. With every flag True the start decider's beam gate passes
    trivially, preserving the pre-BEAM-1 "no beam gate" behavior.
    """

    async def read_beam_availability(self) -> BeamAvailabilityLookupResult:
        return BeamAvailabilityLookupResult(
            fes_open=True, sbs_open=True, fes_permit=True, quality_ok=True
        )


__all__ = [
    "AllBeamOpenLookup",
    "BeamAvailabilityLookup",
    "BeamAvailabilityLookupResult",
]
