# Controls

*The control stack and the bluesky-orchestration seam. First cut; handles read from the profile collection, carried confirm.*

CSX runs on the NSLS-II EPICS / ophyd control stack, the same floor as the other NSLS-II beamlines. CORA observes that floor and, where it replaces bluesky-style orchestration, conducts over it; it does not replace EPICS itself.

## Device handles

The control handles are filled from the beamline's own bluesky profile collection ([NSLS2/csx-profile-collection](https://github.com/NSLS2/csx-profile-collection)), so the descriptor carries the real PV roots and per-axis maps (`XF:23ID1-OP{Mono}Enrgy-SP`, `XF:23ID1-ES{Dif-Ax:Th}Mtr`, `XF:23ID1-ES{FCCD}`, and so on). They remain confirm-pending: a value read from the profile collection is evidence to verify with staff, not a CORA-owned fact (`CTRL-1`).

## The orchestration seam

The RSXS / coherent-scattering acquisition (the energy fly-scans, the TARDIS reciprocal-space moves, the coherent / holography plans) runs through bluesky plans and the queue server. That orchestration is the seam CORA's edge replaces: CORA conducts the run over the `ControlPort`, driving through ophyd / EPICS rather than replacing it. The FastCCD HDF5 file-writing to the NSLS-II filestore is plumbing CORA observes, not data it owns; CORA keeps its own data-of-record.

## Equipment protection

CSX carries an equipment-protection interlock separate from the personnel PSS, as the other NSLS-II beamlines do, with the in-vacuum system adding vacuum interlocks (gate valves, pressure trips). CORA does not model the interlock logic; it would only observe outcomes, mapping utility and vacuum faults to Supply status and device faults to an Asset condition. That mapping is not modelled in this cut.
