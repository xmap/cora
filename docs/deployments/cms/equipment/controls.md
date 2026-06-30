# Controls

*The control stack and the bluesky-orchestration seam. First cut; handles read from the profile collection, carried confirm.*

CMS runs on the NSLS-II EPICS / ophyd control stack, the same floor as FXI, HXN, SRX, BMM, SIX, CHX, ESM, and its 12-ID twin SMI. CORA observes that floor and, where it replaces bluesky-style orchestration, conducts over it; it does not replace EPICS itself.

## Device handles

The control handles are filled from the beamline's own bluesky profile collection ([NSLS2/cms-profile-collection](https://github.com/NSLS2/cms-profile-collection), the `startup/*.py` files), so the descriptor carries the real PV roots and per-axis maps. The optics enclosure (XF:11BMA, with the newer mirror on XF:11BM1) carries the double-multilayer monochromator (`XF:11BMA-OP{Mono:DMM-Ax:Bragg}`, `MONO-1`); the endstation enclosure (XF:11BMB) carries the sample chamber (`XF:11BMB-ES{Chm:Smpl}`, `SAMPLE-1`) and the area detectors (`XF:11BMB-ES{Det:PIL2M}`, `XF:11BMB-ES{Det:PIL800K}`, `DET-1`). They remain confirm-pending: a value read from the profile collection is evidence to verify with staff, not a CORA-owned fact (`CTRL-1`).

A note on the goniometer axes: the logical sample angles (`sth`, `schi`, `sphi`) are rebound across physical PVs by the `beamline_stage` configs at startup, and staff have at times swapped `sth` and `schi`. CORA models the logical Goniometer and treats the physical binding as a setting rather than a fixed handle (`SAMPLE-1`).

## The orchestration seam

The CMS acquisition runs through bluesky plans: the SAXS / WAXS / GISAXS exposures (held frames on the Pilatus heads), the GIBar sample exchange (the sample-bar arm in and out of the chamber), and the specular reflectivity (XR) scans. That orchestration is the seam CORA's edge replaces: CORA conducts the run over the `ControlPort`, driving through ophyd / EPICS rather than replacing it. The area-detector file-writing to the NSLS-II filestore is plumbing CORA observes, not data it owns; CORA keeps its own data-of-record (see [Model](../model.md)).

What CORA conducts over the floor, by leg:

| Floor activity (bluesky today) | CORA leg | Devices conducted |
| --- | --- | --- |
| SAXS / WAXS / GISAXS exposure | acquisition over `ControlPort` | Goniometer, Camera (the Pilatus heads), Slit, BeamStop, FluxMonitor |
| GIBar sample exchange | acquisition over `ControlPort` | the sample-exchange arm, modelled by its LinearStage axes (`ROBOT-1`) |
| Specular reflectivity (XR) scan | acquisition over `ControlPort` | Goniometer (`sth`), Camera (a tracked region of the fixed Pilatus), FluxMonitor (`XR-1`) |
| Frames to the NSLS-II filestore | observed plumbing | none owned; CORA moves frames into its own Dataset of record |

### The XR scan specifically

Specular reflectivity is the one loop worth spelling out, because CMS has no physical two-theta detector arm and no point detector. The area detector stays fixed; the "two-theta" is synthetic. CORA steps the sample theta (`sth` on the Goniometer) and, in lockstep, slides a software region-of-interest across the fixed Pilatus face to where the reflected beam lands, integrating the specular intensity off that tracked region against the incident flux. CORA conducts that coupled step (Goniometer angle and Camera region together) over the `ControlPort` rather than leaving EPICS to own the loop (`XR-1`). No new hardware is invoked: XR reuses the Goniometer, the SAXS Pilatus (read over the tracked region), and a FluxMonitor.

## Equipment protection

The personnel PSS search-and-secure permit signals, the front-end and photon shutters, and any equipment-protection interlock tier are absent from the profile collection and are not invented here (`PSS-1`). 11-BM is a bending-magnet source, so there is no undulator or insertion-device handle to gate either (`SRC-1`). If CORA later models the protection tier, it would not model the interlock logic itself; it would only observe outcomes, mapping the in-situ environments (the vacuum optics and flight path, the Linkam temperature stage) to Supply and Asset condition. That mapping is not modeled in this cut.
