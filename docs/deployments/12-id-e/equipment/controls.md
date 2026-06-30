# Controls

*The control stack and the bluesky / BITS-orchestration seam. First cut; handles read from the instrument config, carried confirm.*

12-ID-E runs on the APS EPICS / ophyd control stack, the same floor as 2-BM, 2-ID, 7-BM, 32-ID, 19-BM, 4-ID, 8-ID, and 9-ID. CORA observes that floor and, where it replaces bluesky-style orchestration, conducts over it; it does not replace EPICS itself.

## Device handles

The control handles are filled from the beamline's own bluesky / BITS instrument ([BCDA-APS/usaxs-bits](https://github.com/BCDA-APS/usaxs-bits)), so the descriptor carries the real PV roots and per-axis maps. The namespaces split by IOC and subsystem:

| Namespace | What it carries |
| --- | --- |
| `usxLAX:` | the LAX soft IOC: USAXS calculations, scalers (`usxLAX:vsc:c0` / `c1`), slits, and many motors |
| `usxAERO:` | the Aerotech motors, including the rocking rotations (`usxAERO:m6`, `usxAERO:m12`) |
| `12idPyFilter:` | the Al / Ti attenuator filter bank |
| `usxRIO:` | the Femto amplifier RIO (`usxRIO:fem02-05:seq01:`) |
| `usxLINKAM:` / `usxTEMP:` | sample temperature (Linkam T96, PTC10) |
| `usxPI:` | the PI C-867 sample rotator |

The autoranging amplifier path runs through `usxLAX:fem09:seq02:` (amplifier) and `usxLAX:pd01:seq02:` (autorange), with the photocurrent at `usxLAX:USAXS:upd`. These handles remain confirm-pending: a value read from the instrument config is evidence to verify with staff, not a CORA-owned fact (`CTRL-1`). The full source / optics walk and the per-device list live on the generated [beamline page](../beamline.md); this page covers the control seam, not the device roster.

## The orchestration seam

The USAXS acquisition runs through bluesky plans and the BITS instrument: the rocking-curve fly-scan that rocks the Bonse-Hart collimator and analyzer crystal stages through the Bragg condition, the multi-decade autoranging of the Femto transimpedance amplifier on the UPD photodiode, and the scaler counting of the amplifier channels. That orchestration is the seam CORA's edge replaces: CORA conducts the run over the `ControlPort`, driving through ophyd / EPICS rather than replacing it.

The same instrument also runs pinhole SAXS and WAXS on Pilatus area detectors, which reuse the existing scattering Capabilities. The area-detector file-writing to the APS filestore is plumbing CORA observes, not data it owns; CORA keeps its own data-of-record (see [Model](../model.md)).

## Equipment protection

The personnel PSS search-and-secure permit signals, the front-end and photon shutters, and any equipment-protection interlock tier are absent from the instrument config and are not invented here (`PSS-1`). If CORA later models them, it would not model the interlock logic itself; it would only observe outcomes, mapping utility and vacuum faults to Supply status and device faults to an Asset condition. That mapping is not modelled in this cut.
