# Controls

*The control stack and the bluesky-orchestration seam. First cut; handles read from the profile collection, carried confirm.*

IOS runs on the NSLS-II EPICS / ophyd control stack, the same floor as the other NSLS-II beamlines. CORA observes that floor and, where it replaces bluesky-style orchestration, conducts over it; it does not replace EPICS itself.

## Device handles

The control handles are filled from the beamline's own bluesky profile collection ([NSLS2/ios-profile-collection](https://github.com/NSLS2/ios-profile-collection)), so the descriptor carries the real PV roots and per-axis maps (`XF:23ID2-OP{Mono}Enrgy-SP`, `XF:23ID2-ES{APPES:1-Ax:X}Mtr`, `XF:23ID2-ES{SPECS}`, and so on). They remain confirm-pending: a value read from the profile collection is evidence to verify with staff, not a CORA-owned fact (`CTRL-1`).

## The orchestration seam

The AP-PES / NEXAFS acquisition (the PGM energy fly-scans with their coupled EPU edge-table switching, the SPECS spectrum acquisition, and the electron- and fluorescence-yield reads) runs through bluesky plans, published to Kafka and the NSLS-II document store. Whether a queue server is in use is not in the profile collection (`CTRL-1`). That orchestration is the seam CORA's edge replaces: CORA conducts the run over the `ControlPort`, driving through ophyd / EPICS rather than replacing it. The SPECS and Xspress3 HDF5 file-writing to the NSLS-II filestore is plumbing CORA observes, not data it owns; CORA keeps its own data-of-record.

## Equipment protection

IOS carries an equipment-protection interlock separate from the personnel PSS, as the other NSLS-II beamlines do, with the UHV system adding vacuum interlocks (gate valves, pressure trips); the gate valves (`XF:23ID2-VA`) are in the profile as vacuum plumbing, not modelled as Assets in this cut. The PSS search-and-secure permit signals are absent from the profile collection and are not invented here (`PSS-1`). CORA does not model the interlock logic; it would only observe outcomes, mapping utility and vacuum faults to Supply status and device faults to an Asset condition. That mapping is not modelled in this cut.
