# Controls

*The control stack and the bound device handles. First cut; handles read from the beamline config, carried confirm.*

4-ID POLAR runs on the APS EPICS control stack, the same floor as the 2-BM pilot. CORA observes that floor and, where it replaces Bluesky-style scan and alignment orchestration, conducts over it; it does not replace EPICS itself.

## Device handles

CORA models each device's control handle as an opaque string set at the edge. Unlike the 7-BM and 32-ID design-phase scaffolds, the handles here are filled: they were read from the beamline's own Bluesky instrument repo ([BCDA-APS/polar-bits](https://github.com/BCDA-APS/polar-bits)), so the descriptor carries the real PV prefixes and per-axis maps (`4idVDCM:`, `4idgSoft:`, `4idHHLM:`, and so on). They remain confirm-pending: a value read from the operator's config is evidence to verify with staff, not a CORA-owned fact (`CTRL-1`). This is the one way this deployment departs from the design-phase scaffolds, and it follows from POLAR being operational.

## Triggering

The diffraction and scattering acquisition timing (detector and stage synchronization during a scan) is not modelled here; the polar-bits config carries plans, not a single timing device. It joins, as a `TimingController` device, once the scan-trigger hardware and PVs are confirmed (`CTRL-1`).

## Peripheral electronics

The preamplifiers (`LocalPreAmp`), the lock-in amplifier (`srs810`), the LabJacks, and the high-pressure-cell controllers (Pace `PC1` / `PC2`) appear in the beamline config but are not modelled as Assets in this cut (`SAMPLE-2`). They relate to the sample signal chain sideways; whether they become CORA Assets depends on whether they are beamline equipment or user-brought.

## Equipment protection

4-ID carries an equipment-protection interlock separate from the personnel PSS, as 2-BM does. CORA does not model the interlock logic; it would only observe outcomes, mapping utility faults to Supply status and device faults to an Asset condition. That mapping is not yet modelled in this cut.
