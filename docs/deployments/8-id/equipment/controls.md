# Controls

*The control stack and the softGlue timing fabric. First cut; handles read from the beamline config, carried confirm.*

8-ID runs on the APS EPICS control stack, the same floor as the 2-BM pilot. CORA observes that floor and, where it replaces Bluesky-style orchestration, conducts over it; it does not replace EPICS itself.

## Device handles

The control handles are filled from the beamline's own Bluesky instrument repo ([BCDA-APS/8id-bits](https://github.com/BCDA-APS/8id-bits)), so the descriptor carries the real PV prefixes and per-axis maps (`8idaSoft:MN1:`, `8ideSoft:CR8-E1:`, `8iddSoft:TRANS:`, and so on). They remain confirm-pending: a value read from the operator's config is evidence to verify with staff, not a CORA-owned fact (`CTRL-1`).

## Timing

XPCS exposures are gated by a softGlueZynq FPGA timing fabric (`8idMZ1:`). It is modelled here as a single `TimingController` device; the full softGlue signal graph (the counter, multiplexer, and pulse-train routing that drives the Rigaku and the other detectors) is not modelled (`XPCS-3`). This timing precision is central to XPCS, so the signal graph is the most likely first thing to firm up when CORA begins to conduct 8-ID acquisitions.

## Peripheral electronics

The function generators (Keysight), the LabJack, and the EPICS PV storage registers appear in the beamline config but are not modelled as Assets in this cut. They relate to the acquisition chain sideways; whether they become CORA Assets depends on whether they are beamline equipment CORA should track.

## Equipment protection

8-ID carries an equipment-protection interlock separate from the personnel PSS, as 2-BM does. CORA does not model the interlock logic; it would only observe outcomes, mapping utility faults to Supply status and device faults to an Asset condition. That mapping is not modelled in this cut.
