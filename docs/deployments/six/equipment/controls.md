# Controls

*The control stack and the bluesky-orchestration seam. First cut; handles read from the profile collection, carried confirm.*

SIX runs on the NSLS-II EPICS / ophyd control stack, the same floor as FXI, HXN, and BMM. CORA observes that floor and, where it replaces bluesky-style orchestration, conducts over it; it does not replace EPICS itself.

## Device handles

The control handles are filled from the beamline's own bluesky profile collection ([NSLS2/six-profile-collection](https://github.com/NSLS2/six-profile-collection)), so the descriptor carries the real PV roots and per-axis maps (`XF:02IDB-OP{Mono:1-Ax:9_Eng}`, `XF:02IDD-ES{BT:1-Ax:`, `XF:02ID1-ES{RIXSCam}`, and so on). They remain confirm-pending: a value read from the profile collection is evidence to verify with staff, not a CORA-owned fact (`CTRL-1`).

## The orchestration seam

The RIXS acquisition (the energy moves, the alignment scans, the spectrometer-geometry moves) runs through bluesky plans and the queue server (`41-custom-plans.py`, `43-alignment_scans.py`, `97-standard-plans.py`). That orchestration is the seam CORA's edge replaces: CORA conducts the run over the `ControlPort`, driving through ophyd / EPICS rather than replacing it. The RIXS-camera HDF5 file-writing to the NSLS-II filestore is plumbing CORA observes, not data it owns; CORA keeps its own data-of-record.

## Equipment protection

SIX carries an equipment-protection interlock separate from the personnel PSS, as the other NSLS-II beamlines do, with the UHV system adding vacuum interlocks (gate valves, pressure trips). CORA does not model the interlock logic; it would only observe outcomes, mapping utility and vacuum faults to Supply status and device faults to an Asset condition. That mapping is not modelled in this cut.
