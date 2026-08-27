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
from enum import StrEnum
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


class BeamState(StrEnum):
    """What the pre-flight observed, as a closed vocabulary.

    A closed enum rather than a summary string on purpose. The record
    exporter's disposition generator keeps an enum and DROPS free text
    (the safe default for anything that might carry operator prose), so
    a `str` here would have been stripped from the published record,
    silently removing the one field that lets an outside reader tell a
    beam-available start from a declared-exemption start. Typing it
    closed keeps it disclosable.

    Per-flag detail (which of fes_open / sbs_open / fes_permit was
    false) is deliberately NOT carried here. It is diagnostic rather
    than auditable: the refusal error names the failing flags when the
    gate refuses, and the substrate's own history holds the rest. What
    the record has to answer is the coarser question of whether beam was
    there.
    """

    OPEN = "Open"
    """All three flags true: beam was available."""

    BLOCKED = "Blocked"
    """The read was good and at least one flag was false."""

    UNKNOWN = "Unknown"
    """The read had non-Good quality, so CORA could not tell."""


def summarize_beam_state(result: "BeamAvailabilityLookupResult | None") -> "BeamState | None":
    """Render a reading as the stable summary string the Run and
    Procedure start events record.

    Exists so a start event says what beam looked like at the instant it
    began, INDEPENDENTLY of whether the gate refused on it. Once a
    `BeamRequirement.NOT_REQUIRED` execution can skip the gate, "started
    with beam" and "started without beam under a declared exemption"
    would otherwise be the same event, and no auditor could separate
    them after the fact.

    `None` means the deployment configures no beam PVs, so CORA has
    nothing to say. That is deliberately distinct from `UNKNOWN` (it
    tried to look and could not) and from `BLOCKED` (it looked and beam
    was absent).
    """
    if result is None:
        return None
    if not result.quality_ok:
        return BeamState.UNKNOWN
    if result.fes_open and result.sbs_open and result.fes_permit:
        return BeamState.OPEN
    return BeamState.BLOCKED


class BeamAvailabilityLookup(Protocol):
    """Cross-BC port: read current beam availability for the start gate."""

    async def read(self) -> BeamAvailabilityLookupResult:
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

    async def read(self) -> BeamAvailabilityLookupResult:
        return BeamAvailabilityLookupResult(
            fes_open=True, sbs_open=True, fes_permit=True, quality_ok=True
        )


__all__ = [
    "AllBeamOpenLookup",
    "BeamAvailabilityLookup",
    "BeamAvailabilityLookupResult",
    "BeamState",
    "summarize_beam_state",
]
