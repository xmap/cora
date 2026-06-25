# Controls

*The control stack and the bluesky-orchestration seam. First cut; handles read from the profile collection, carried confirm.*

ESM runs on the NSLS-II EPICS / ophyd control stack, the same floor as the other NSLS-II beamlines. CORA observes that floor and, where it replaces bluesky-style orchestration, conducts over it; it does not replace EPICS itself.

## Device handles

The control handles are filled from the beamline's own bluesky profile collection ([NSLS2/esm-arpes-profile-collection](https://github.com/NSLS2/esm-arpes-profile-collection)), so the descriptor carries the real PV roots and per-axis maps (`XF:21IDB-OP{Mono:1-Ax:8_Eng}Mtr`, `XF21ID1-ES-SES`, the EPU `SR:C21-ID:G1A{EPU:1`, and so on). They remain confirm-pending: a value read from the profile collection is evidence to verify with staff, not a CORA-owned fact (`CTRL-1`).

## The orchestration seam

The ARPES acquisition (the energy moves, the analyzer sweeps, the manipulator scans) runs through bluesky plans and the queue server (`40-ESM_plans.py`, `41-ESM_motion.py`). That orchestration is the seam CORA's edge replaces: CORA conducts the run over the `ControlPort`, driving through ophyd / EPICS rather than replacing it. The analyzer's spectrum file-writing is plumbing CORA observes, not data it owns; CORA keeps its own data-of-record.

## Equipment protection

ESM carries an equipment-protection interlock separate from the personnel PSS, as the other NSLS-II beamlines do, with the UHV system adding vacuum interlocks (gate valves, pressure trips) across the optics and the two endstation branches. CORA does not model the interlock logic; it would only observe outcomes, mapping utility and vacuum faults to Supply status and device faults to an Asset condition. That mapping is not modelled in this cut.
