# Controls

*The control stack and the bluesky-orchestration seam. First cut; handles read from the profile collection, carried confirm.*

IXS runs on the NSLS-II EPICS / ophyd control stack, the same floor as FXI, HXN, BMM, SRX, SIX, and CHX. CORA observes that floor and, where it replaces bluesky-style orchestration, conducts over it; it does not replace EPICS itself.

## Device handles

The control handles are filled from the beamline's own bluesky profile collection ([NSLS2/ixs-profile-collection](https://github.com/NSLS2/ixs-profile-collection)), so the descriptor carries the real PV roots and per-axis maps (`SR:C10-ID:G1{IVU22:1-Ax:Gap}-Mtr`, `XF:10IDA-OP{Mono:DCM-Ax:P}Mtr`, `XF:10IDB-OP{Mono:HRM2-Ax:UTO}Mtr`, `XF:10IDD-OP{Spec:1-Ax:2Th}Mtr`, and so on). They remain confirm-pending: a value read from the profile collection is evidence to verify with staff, not a CORA-owned fact (`CTRL-1`).

## The orchestration seam

The IXS acquisition (the incident-energy scan over the DCM and the high-resolution monochromator, the six-circle Q moves, the analyzer alignment, the point counting) runs through bluesky plans and the queue server (the startup plans, the alignment scans, and the SPEC-derived macros). That orchestration is the seam CORA's edge replaces: CORA conducts the run over the `ControlPort`, driving through ophyd / EPICS rather than replacing it. The file-writing to the NSLS-II filestore is plumbing CORA observes, not data it owns; CORA keeps its own data-of-record (see [Model](../model.md)).

## Equipment protection

The personnel PSS search-and-secure permit signals, the front-end and photon shutters, and any equipment-protection interlock tier are absent from the profile collection and are not invented here (`PSS-1`). If CORA later models them, it would not model the interlock logic itself; it would only observe outcomes, mapping utility and vacuum faults to Supply status and device faults to an Asset condition. That mapping is not modelled in this cut.
